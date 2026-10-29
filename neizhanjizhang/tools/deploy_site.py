"""发布官网到阿里云服务器。

一条命令做三件事：重新打包下载区（tools/build_site.py）→ 整目录上传 → 校验线上清单。

用法（在 neizhanjizhang 目录）：
    python tools\\deploy_site.py

前提：本机 Windows 自带 ssh/tar（Win10 以后都有），私钥在 ~/.ssh/aliyun_license，
服务器上 nginx 已在 /etc/nginx/conf.d/neizhanjizhang.conf 里指向 /opt/neizhanjizhang/site。

只更新页面、不动安装包时可以加 --skip-build；它仍会整目录覆盖上传。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DEFAULT_HOST = "47.95.146.168"
DEFAULT_USER = "admin"
DEFAULT_KEY = Path.home() / ".ssh" / "aliyun_license"
REMOTE_DIR = "/opt/neizhanjizhang/site"


def run(command: str) -> None:
    print(f"$ {command}")
    subprocess.run(command, shell=True, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="发布押金记账官网")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--key", default=str(DEFAULT_KEY))
    parser.add_argument("--skip-build", action="store_true", help="不重新生成下载区，只传现有文件")
    args = parser.parse_args()

    if not (SITE / "index.html").exists():
        print(f"找不到 {SITE / 'index.html'}")
        return 1
    if not args.skip_build:
        run(f'"{sys.executable}" "{ROOT / "tools" / "build_site.py"}"')

    ssh = f'ssh -i "{args.key}" -o BatchMode=yes {args.user}@{args.host}'
    remote = (
        f"sudo mkdir -p {REMOTE_DIR} && sudo rm -rf {REMOTE_DIR}/* && "
        f"sudo tar -xzf - -C {REMOTE_DIR} && sudo chown -R {args.user}:{args.user} {REMOTE_DIR}"
    )
    run(f'tar -czf - -C "{SITE}" . | {ssh} "{remote}"')

    manifest = SITE / "downloads" / "manifest.json"
    if not manifest.exists():
        print("本地没有 manifest.json，跳过线上校验。")
        return 0
    local = json.loads(manifest.read_text(encoding="utf-8"))
    url = f"http://{args.host}/downloads/manifest.json"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            online = json.loads(response.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001 - 发布后的连通性检查
        print(f"线上清单读取失败：{error}")
        return 1

    if online.get("sha256") != local.get("sha256"):
        print("线上清单与本地不一致，检查上传是否完整。")
        print(f"  本地 {local.get('sha256')}")
        print(f"  线上 {online.get('sha256')}")
        return 1
    print(f"已发布：http://{args.host}/  版本 {online.get('version')}，sha256 一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
