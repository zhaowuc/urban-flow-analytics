from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _discover_app_home() -> Path:
    configured = os.environ.get("URBAN_FLOW_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    app_home: Path
    app_name: str
    host: str
    port: int
    spark_master: str
    spark_driver_memory: str
    demo_seed: int
    demo_rows: int
    secret_key: str

    @property
    def database_path(self) -> Path:
        return self.app_home / "data" / "database" / "system.db"

    @property
    def frontend_dist(self) -> Path:
        release_dist = self.app_home / "app" / "frontend" / "dist"
        return release_dist if release_dist.exists() else self.app_home / "frontend" / "dist"

    @property
    def log_path(self) -> Path:
        return self.app_home / "logs" / "system.log"

    @property
    def runtime_java(self) -> Path:
        return self.app_home / "runtime" / "java"


def load_settings() -> Settings:
    home = _discover_app_home()
    config_path = home / "config" / "settings.json"
    raw: dict[str, object] = {}
    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    return Settings(
        app_home=home,
        app_name=str(raw.get("app_name", "城市出行客流数据分析系统")),
        host=str(raw.get("host", "127.0.0.1")),
        port=int(raw.get("port", 8765)),
        spark_master=str(raw.get("spark_master", "local[*]")),
        spark_driver_memory=str(raw.get("spark_driver_memory", "2g")),
        demo_seed=int(raw.get("demo_seed", 20260827)),
        demo_rows=int(raw.get("demo_rows", 60000)),
        secret_key=os.environ.get("URBAN_FLOW_SECRET", "urban-flow-local-release-secret-v1"),
    )


settings = load_settings()


def ensure_runtime_directories() -> None:
    for relative in (
        "data/database",
        "data/demo",
        "data/upload",
        "data/raw",
        "data/clean",
        "data/parquet",
        "data/stream/inbox",
        "data/result",
        "models",
        "logs",
    ):
        (settings.app_home / relative).mkdir(parents=True, exist_ok=True)
