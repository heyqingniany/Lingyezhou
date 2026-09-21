"""Render the vector brand mark into PNG and multi-size Windows ICO assets."""
import os
import sys
import struct
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QByteArray, QBuffer, QIODevice

root = Path(__file__).resolve().parents[1]
app = QApplication(sys.argv)
icon = QIcon(str(root / "assets/lingyezhou.svg"))
png = root / "assets/lingyezhou.png"
if not icon.pixmap(256, 256).save(str(png)):
    raise RuntimeError("Icon rendering failed")
sizes = [16, 24, 32, 48, 64, 128, 256]
images = []
for size in sizes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    icon.pixmap(size, size).save(buffer, "PNG")
    images.append(bytes(data))
offset = 6 + 16 * len(sizes)
entries = []
for size, data in zip(sizes, images):
    entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
    offset += len(data)
(root / "assets/lingyezhou.ico").write_bytes(struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries) + b"".join(images))
print("Generated PNG and multi-resolution ICO")
