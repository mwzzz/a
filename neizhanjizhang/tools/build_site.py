"""把打好的安装包放进官网，并生成下载清单 manifest.json。

官网本身是纯静态文件（site/index.html 等），这个脚本只做两件事：
1. 把 release\\押金记账.zip 复制成 ASCII 文件名的 site\\downloads\\yajinjizhang-YYYYMMDD.zip；
2. 算出大小、文件数、sha256，写进 site\\downloads\\manifest.json，页面再从清单里读。

用法：在 neizhanjizhang 目录执行 python tools\\build_site.py
每次重新打包后都要跑一次，否则官网上挂着的是旧包。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ZIP = ROOT / "release" / "押金记账.zip"
SITE = ROOT / "site"
DOWNLOADS = SITE / "downloads"
ICON = ROOT / "app" / "assets" / "icon.svg"


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if not SOURCE_ZIP.exists():
        print(f"找不到安装包：{SOURCE_ZIP}")
        print("先按 交接文档.md 里的命令打包，再跑这个脚本。")
        return 1
    if not (SITE / "index.html").exists():
        print(f"官网目录不完整：{SITE}")
        return 1

    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    built = datetime.fromtimestamp(SOURCE_ZIP.stat().st_mtime)
    stamp = built.strftime("%Y%m%d")

    # 清掉上一次的压缩包，避免官网上留着好几个版本
    for old in DOWNLOADS.glob("*.zip"):
        old.unlink()

    target = DOWNLOADS / f"yajinjizhang-{stamp}.zip"
    shutil.copyfile(SOURCE_ZIP, target)

    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
    leaked = [n for n in names if "/data/" in n]
    if leaked:
        print(f"警告：安装包里带了 data 目录（{len(leaked)} 项），交接文档要求跳过 data。")

    if ICON.exists():
        shutil.copyfile(ICON, SITE / "assets" / "icon.svg")

    manifest = {
        "version": f"{stamp[:4]}.{stamp[4:6]}.{stamp[6:]}",
        "file": target.name,
        "size_bytes": target.stat().st_size,
        "file_count": len(names),
        "sha256": sha256_of(target),
        "built_at": built.strftime("%Y-%m-%d"),
    }
    (DOWNLOADS / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    size_mb = manifest["size_bytes"] / 1024 / 1024
    print(f"安装包已就位：{target.relative_to(ROOT)}（{size_mb:.1f} MB，{len(names)} 个文件）")
    print(f"版本 {manifest['version']}，sha256 {manifest['sha256'][:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
