from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "release"
TARGET = RELEASE_ROOT / "城市出行客流数据分析系统"
WORK = ROOT / "work" / "launcher-build"


def find_node() -> Path | None:
    found = shutil.which("node")
    if found:
        return Path(found)
    candidate = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe"
    return candidate if candidate.exists() else None


def build_frontend() -> None:
    node = find_node()
    vite = ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    if node and vite.exists():
        subprocess.run([str(node), str(vite), "build"], cwd=ROOT / "frontend", check=True)
    elif not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise RuntimeError("未找到 Node.js 且不存在可复用的 frontend/dist，请先安装前端依赖。")
    else:
        print("[WARN] 未找到 Node.js，使用已验证的 frontend/dist 构建产物。")


def compile_launchers() -> tuple[Path, Path]:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates = [
        windir / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe",
        windir / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe",
    ]
    compiler = next((item for item in candidates if item.exists()), None)
    if compiler is None:
        raise RuntimeError("未找到 Windows .NET Framework C# 编译器。")
    WORK.mkdir(parents=True, exist_ok=True)
    outputs = []
    for source, name in (("StartSystem.cs", "启动系统.exe"), ("StopSystem.cs", "关闭系统.exe")):
        output = WORK / name
        subprocess.run([
            str(compiler), "/nologo", "/target:winexe", "/optimize+", "/platform:x64",
            "/reference:System.Windows.Forms.dll", "/reference:System.Drawing.dll",
            "/out:" + str(output), str(ROOT / "launcher" / source),
        ], check=True)
        outputs.append(output)
    return outputs[0], outputs[1]


def safe_recreate_target() -> None:
    release_resolved = RELEASE_ROOT.resolve()
    target_resolved = TARGET.resolve()
    if target_resolved.parent != release_resolved or target_resolved.name != "城市出行客流数据分析系统":
        raise RuntimeError("Release 目标目录校验失败。")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True)


def copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source, destination, dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache", ".DS_Store"),
    )


def choose_demo_records(db_path: Path) -> dict:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        analysis = connection.execute("SELECT * FROM analysis_tasks WHERE status='completed' ORDER BY id ASC LIMIT 1").fetchone()
        predictions = {}
        for model_type in ("arima", "random_forest"):
            predictions[model_type] = connection.execute(
                "SELECT * FROM prediction_tasks WHERE status='completed' AND model_type=? ORDER BY id ASC LIMIT 1", (model_type,),
            ).fetchone()
        predictions["gbt"] = connection.execute(
            "SELECT * FROM prediction_tasks WHERE status='completed' AND model_type='gbt' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        preprocessing = connection.execute(
            "SELECT * FROM preprocessing_tasks WHERE status='completed' AND dataset_id=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if analysis is None or preprocessing is None or any(item is None for item in predictions.values()):
            raise RuntimeError("Demo 分析、清洗或三类模型记录不完整。")
        return {"analysis": dict(analysis), "predictions": {key: dict(value) for key, value in predictions.items()}, "preprocessing": dict(preprocessing)}
    finally:
        connection.close()


def prune_release_database(db_path: Path, selected: dict) -> None:
    keep_analysis = selected["analysis"]["id"]
    keep_predictions = [item["id"] for item in selected["predictions"].values()]
    keep_preprocessing = selected["preprocessing"]["id"]
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        marks = ",".join("?" for _ in keep_predictions)
        connection.execute("DELETE FROM decision_records")
        connection.execute("DELETE FROM warnings")
        connection.execute("DELETE FROM operation_logs")
        connection.execute("DELETE FROM prediction_results WHERE task_id NOT IN (" + marks + ")", keep_predictions)
        connection.execute("DELETE FROM prediction_tasks WHERE id NOT IN (" + marks + ")", keep_predictions)
        connection.execute("DELETE FROM analysis_tasks WHERE id<>?", (keep_analysis,))
        connection.execute("DELETE FROM preprocessing_tasks WHERE id<>?", (keep_preprocessing,))
        connection.execute("DELETE FROM datasets WHERE id<>1")
        connection.execute("DELETE FROM user_roles WHERE user_id NOT IN (1,2,3)")
        connection.execute("DELETE FROM users WHERE id NOT IN (1,2,3)")
        connection.execute("UPDATE datasets SET processing_status='completed' WHERE id=1")
        clean_report = json.loads(selected["preprocessing"]["report"] or "{}")
        clean_report["output_path"] = "data/parquet/dataset_id=1"
        connection.execute("UPDATE preprocessing_tasks SET report=? WHERE id=?", (json.dumps(clean_report, ensure_ascii=False), keep_preprocessing))
        analysis_params = json.loads(selected["analysis"]["parameters"] or "{}")
        analysis_params.update({"dataset_id": 1, "parquet_path": "data/parquet/dataset_id=1"})
        connection.execute("UPDATE analysis_tasks SET parameters=? WHERE id=?", (json.dumps(analysis_params, ensure_ascii=False), keep_analysis))
        for item in selected["predictions"].values():
            params = json.loads(item["parameters"] or "{}")
            params.update({"dataset_id": 1, "parquet_path": "data/parquet/dataset_id=1"})
            connection.execute("UPDATE prediction_tasks SET parameters=? WHERE id=?", (json.dumps(params, ensure_ascii=False), item["id"]))
        connection.commit()
    finally:
        connection.close()


def copy_release_content(selected: dict, launchers: tuple[Path, Path]) -> None:
    for directory in ("backend", "spark_jobs"):
        copy_tree(ROOT / directory, TARGET / "app" / directory)
    copy_tree(ROOT / "frontend" / "dist", TARGET / "app" / "frontend" / "dist")
    copy_tree(ROOT / "runtime", TARGET / "runtime")
    copy_tree(ROOT / "assets", TARGET / "assets")
    copy_tree(ROOT / "config", TARGET / "config")
    copy_tree(ROOT / "data" / "demo", TARGET / "data" / "demo")
    copy_tree(ROOT / "data" / "parquet" / "dataset_id=1", TARGET / "data" / "parquet" / "dataset_id=1")
    (TARGET / "data" / "database").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "data" / "database" / "system.db", TARGET / "data" / "database" / "system.db")
    result_dir = TARGET / "data" / "result"; result_dir.mkdir(parents=True, exist_ok=True)
    result_paths = {selected["analysis"]["result_path"]}
    for item in selected["predictions"].values():
        metrics = json.loads(item["metrics"] or "{}")
        result_paths.add(metrics["result_path"])
        model_source = ROOT / item["model_path"]
        model_target = TARGET / item["model_path"]
        if model_source.is_dir(): copy_tree(model_source, model_target)
        else: model_target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(model_source, model_target)
    for relative in result_paths:
        source = ROOT / relative
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    (TARGET / "logs").mkdir(exist_ok=True); (TARGET / "work").mkdir(exist_ok=True); (TARGET / "models").mkdir(exist_ok=True)
    shutil.copy2(launchers[0], TARGET / "启动系统.exe"); shutil.copy2(launchers[1], TARGET / "关闭系统.exe")
    shutil.copy2(ROOT / "README.md", TARGET / "README.md")
    shutil.copy2(ROOT / "使用说明.txt", TARGET / "使用说明.txt")


def finalize_demo(selected: dict) -> None:
    env = os.environ.copy()
    env.update({"URBAN_FLOW_HOME": str(TARGET), "JAVA_HOME": str(TARGET / "runtime" / "java"), "PYTHONIOENCODING": "utf-8"})
    code = (
        "from backend.app.database.init_db import initialize_database; "
        "from backend.app.services.warnings import generate_warnings; "
        "from backend.app.services.reports import generate_decision_report; "
        "initialize_database(); generate_warnings(" + str(selected["predictions"]["gbt"]["id"]) + "); generate_decision_report()"
    )
    subprocess.run([str(TARGET / "runtime" / "python" / "python.exe"), "-c", code], cwd=TARGET / "app", env=env, check=True)
    version = {"version": "1.0.0", "build_time": datetime.now().isoformat(timespec="seconds"), "mode": "Spark Local 离线绿色版", "city": "星海示例市（虚拟）"}
    (TARGET / "version.json").write_text(json.dumps(version, ensure_ascii=False, indent=2), encoding="utf-8")


def scan_offline_build() -> None:
    forbidden = ["cdn.jsdelivr.net", "unpkg.com", "fonts.googleapis.com", "api.map.baidu.com", "webapi.amap.com", "maps.googleapis.com"]
    matches = []
    for path in (TARGET / "app" / "frontend" / "dist").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in forbidden:
                if marker in text: matches.append(str(path.relative_to(TARGET)) + ": " + marker)
    if matches: raise RuntimeError("发现必须联网的前端依赖：" + "; ".join(matches))


def main() -> None:
    print("[1/7] 构建 Vue 前端")
    build_frontend()
    print("[2/7] 编译 Windows 启停器")
    launchers = compile_launchers()
    print("[3/7] 选择并校验 Demo 计算结果")
    selected = choose_demo_records(ROOT / "data" / "database" / "system.db")
    print("[4/7] 创建绿色 Release 目录")
    safe_recreate_target(); copy_release_content(selected, launchers)
    print("[5/7] 清理自动化测试状态")
    prune_release_database(TARGET / "data" / "database" / "system.db", selected)
    print("[6/7] 生成统一预警、报告与版本信息")
    finalize_demo(selected)
    print("[7/7] 扫描离线依赖")
    scan_offline_build()
    print("Release 构建完成：" + str(TARGET))


if __name__ == "__main__":
    main()
