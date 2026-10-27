"""启动卡密服务：python -m license_server"""

from __future__ import annotations

import argparse
from pathlib import Path

from license_server.http import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="卡密登录服务")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default="data/cards.db", help="卡密数据库路径")
    args = parser.parse_args()
    serve(args.host, args.port, Path(args.db))


if __name__ == "__main__":
    main()
