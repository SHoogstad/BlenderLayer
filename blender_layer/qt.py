"""Qt binding used by the plugin: PyQt6 on Krita 6, PyQt5 on Krita 5.2 and 5.3.

The binding must match the one Krita was built with, which Krita has already imported by the
time plugins load. Outside of Krita (tests) PyQt6 is preferred if installed.
Set BLENDER_LAYER_QT=5 or BLENDER_LAYER_QT=6 to force a binding.

Use fully scoped enums (Qt.AlignmentFlag.AlignCenter, not Qt.AlignCenter) and exec() instead of
exec_(), those work with both bindings.
"""

import importlib
import os
import sys


def _chooseBinding():
    forced = os.environ.get('BLENDER_LAYER_QT', '')
    if forced in ('5', '6'):
        return f'PyQt{forced}'
    for name in ('PyQt6', 'PyQt5'):
        if name in sys.modules:
            return name
    for name in ('PyQt6', 'PyQt5'):
        try:
            importlib.import_module(f'{name}.QtCore')
            return name
        except ImportError:
            pass
    raise ImportError("Blender Layer requires PyQt6 (Krita 6) or PyQt5 (Krita 5)")


binding = _chooseBinding()
QT6 = binding == 'PyQt6'

if QT6:
    from PyQt6.QtCore import *
    from PyQt6.QtGui import *
    from PyQt6.QtWidgets import *
else:
    from PyQt5.QtCore import *  # type: ignore
    from PyQt5.QtGui import *  # type: ignore
    from PyQt5.QtWidgets import *  # type: ignore


def imageBytes(image):
    """Pixels of a QImage as QByteArray. Not copied on PyQt5, PyQt6 has no fromRawData and copies once.
    The image must outlive the result."""
    bits = image.constBits()
    bits.setsize(image.sizeInBytes())
    return QByteArray(bits) if QT6 else QByteArray.fromRawData(bits)


def eventPos(event):
    """Position of a mouse event relative to the receiving widget, as QPointF"""
    return event.position() if QT6 else event.localPos()
