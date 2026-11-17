"""把发布包里的 .env 片段合并进服务器 .env。

只覆盖片段里出现的键，保留服务器独有的键；下列基础设施配置永不覆盖。
用法：merge_env.py <片段文件> <目标 .env>
"""

import os
import sys
from pathlib import Path

PROTECTED = {"JWT_SECRET", "DB_PATH", "DEBUG", "CORS_ORIGINS"}


def parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in PROTECTED:
            values[key] = value.strip()
    return values


def main() -> None:
    merge_path, env_path = Path(sys.argv[1]), Path(sys.argv[2])
    updates = parse(merge_path.read_text(encoding="utf-8"))
    if not updates:
        print("   没有可同步的配置项")
        return

    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = None
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")

    tmp_path = env_path.with_name(env_path.name + ".tmp")
    tmp_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, env_path)
    print("   已更新配置项：" + "、".join(sorted(updates)))


if __name__ == "__main__":
    main()