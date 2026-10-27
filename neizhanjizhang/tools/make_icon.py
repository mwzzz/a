"""把 SVG 图标做成 Windows 的 ico，供打包使用。"""

from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "app" / "assets" / "icon.svg"
ICO = ROOT / "app" / "assets" / "icon.ico"


def main() -> int:
    QApplication(sys.argv)
    icon = QIcon(str(SVG))
    images: list[Image.Image] = []
    for size in (16, 24, 32, 48, 64, 256):
        image = icon.pixmap(QSize(size, size)).toImage()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        images.append(Image.open(BytesIO(bytes(buffer.data()))).convert("RGBA"))
    images[0].save(
        ICO,
        format="ICO",
        sizes=[(item.width, item.height) for item in images],
        append_images=images[1:],
    )
    print(ICO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
