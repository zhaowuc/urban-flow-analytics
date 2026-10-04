from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

from backend.app.core.config import settings


class SparkManager:
    def __init__(self) -> None:
        self._session: Any | None = None
        self._lock = threading.Lock()
        self._error: str | None = None
        self._initializing = False

    def _configure_environment(self) -> None:
        java_home = os.environ.get("JAVA_HOME")
        if not java_home:
            candidate = settings.runtime_java
            if (candidate / "bin" / "java.exe").exists():
                java_home = str(candidate)
                os.environ["JAVA_HOME"] = java_home
        if not java_home or not (Path(java_home) / "bin" / "java.exe").exists():
            raise RuntimeError("未找到项目内 JRE 17，Spark 暂时无法初始化。")
        os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
        os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
        os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
        # PySpark's Windows batch bootstrap tries to execute PYSPARK_DRIVER_PYTHON
        # through cmd.exe when SPARK_HOME is absent, which splits Chinese paths
        # containing spaces. Point directly at the bundled pyspark package so the
        # batch bootstrap never needs that fragile path-detection subprocess.
        bundled_spark = Path(sys.executable).resolve().parent / "Lib" / "site-packages" / "pyspark"
        if (bundled_spark / "bin" / "spark-submit.cmd").exists():
            os.environ.setdefault("SPARK_HOME", str(bundled_spark))
        winutils_home = settings.app_home / "runtime" / "spark-winutils"
        if (winutils_home / "bin" / "winutils.exe").exists():
            os.environ.setdefault("HADOOP_HOME", str(winutils_home))
            os.environ.setdefault("hadoop.home.dir", str(winutils_home))
            winutils_bin = str(winutils_home / "bin")
            path_entries = os.environ.get("PATH", "").split(os.pathsep)
            if winutils_bin not in path_entries:
                os.environ["PATH"] = winutils_bin + os.pathsep + os.environ.get("PATH", "")
        spark_temp = settings.app_home / "work" / "spark-local"
        spark_temp.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("SPARK_LOCAL_DIRS", str(spark_temp))

    def get(self):
        if self._session is not None:
            return self._session
        with self._lock:
            if self._session is not None:
                return self._session
            self._initializing = True
            try:
                self._configure_environment()
                if os.name == "nt" and any(
                    not character.isascii() or character.isspace()
                    for character in str(settings.app_home)
                ):
                    import pyspark.context as pyspark_context
                    import pyspark.java_gateway as pyspark_java_gateway

                    from backend.app.spark.windows_gateway import launch_gateway_direct

                    pyspark_java_gateway.launch_gateway = launch_gateway_direct
                    pyspark_context.launch_gateway = launch_gateway_direct
                from pyspark.sql import SparkSession

                warehouse = settings.app_home / "work" / "spark-warehouse"
                winutils_home = settings.app_home / "runtime" / "spark-winutils"
                bundled_local_fs_jar = Path(sys.executable).resolve().parent / "Lib" / "site-packages" / "pyspark" / "jars" / "hadoop-bare-naked-local-fs-0.1.0.jar"
                local_fs_jar = bundled_local_fs_jar if bundled_local_fs_jar.exists() else settings.app_home / "runtime" / "spark-jars" / "hadoop-bare-naked-local-fs-0.1.0.jar"
                warehouse.mkdir(parents=True, exist_ok=True)
                builder = (
                    SparkSession.builder
                    .appName("UrbanPassengerFlowAnalysis")
                    .master(settings.spark_master)
                    .config("spark.driver.memory", settings.spark_driver_memory)
                    .config("spark.sql.shuffle.partitions", "8")
                    .config("spark.default.parallelism", "8")
                    .config("spark.ui.enabled", "false")
                    .config("spark.driver.host", "127.0.0.1")
                    .config("spark.driver.bindAddress", "127.0.0.1")
                    .config("spark.sql.warehouse.dir", warehouse.as_uri())
                    .config("spark.sql.session.timeZone", "Asia/Shanghai")
                    .config(
                        "spark.sql.streaming.checkpointFileManagerClass",
                        "org.apache.spark.sql.execution.streaming.FileSystemBasedCheckpointFileManager",
                    )
                )
                if local_fs_jar.exists():
                    builder = builder.config("spark.hadoop.fs.file.impl", "com.globalmentor.apache.hadoop.fs.BareLocalFileSystem")
                    if local_fs_jar != bundled_local_fs_jar:
                        builder = (
                            builder.config("spark.jars", str(local_fs_jar))
                            .config("spark.driver.extraClassPath", str(local_fs_jar))
                            .config("spark.executor.extraClassPath", str(local_fs_jar))
                        )
                self._session = builder.getOrCreate()
                self._session.sparkContext.setLogLevel("WARN")
                self._session.range(1).count()
                self._error = None
                return self._session
            except Exception as exc:
                self._error = str(exc)
                self._session = None
                raise RuntimeError(f"Spark 初始化失败：{self._error}") from exc
            finally:
                self._initializing = False

    def warm_async(self) -> None:
        if self._session is not None or self._initializing:
            return

        def _warm() -> None:
            try:
                self.get()
            except RuntimeError:
                pass

        threading.Thread(target=_warm, name="spark-warmup", daemon=True).start()

    def status(self) -> dict[str, Any]:
        if self._session is not None:
            try:
                self._session.range(1).count()
                return {"ok": True, "status": "正常", "master": self._session.sparkContext.master}
            except Exception as exc:
                self._error = str(exc)
                return {"ok": False, "status": "异常", "detail": self._error}
        if self._initializing:
            return {"ok": False, "status": "初始化中", "detail": "Spark 正在后台启动"}
        return {"ok": False, "status": "未就绪", "detail": self._error or "Spark 尚未初始化"}

    def stop(self) -> None:
        with self._lock:
            if self._session is not None:
                self._session.stop()
                self._session = None


spark_manager = SparkManager()


def get_spark():
    return spark_manager.get()
