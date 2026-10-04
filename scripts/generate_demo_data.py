from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.demo_data import write_demo_files  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="生成固定虚拟城市客流演示数据")
    parser.add_argument("--rows", type=int, default=None, help="记录数，例如 100000/500000/1000000")
    parser.add_argument("--force", action="store_true", help="覆盖已有演示数据")
    args = parser.parse_args()
    targets = write_demo_files(args.rows, force=args.force)
    for kind, path in targets.items():
        print(f"{kind.upper()}: {path}")


if __name__ == "__main__":
    main()

