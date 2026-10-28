"""Minimal stand-in for Krita's Python API, enough to build the docker and run the server outside Krita."""

import builtins
import enum
import importlib.util
from pathlib import Path

# Load the plugin's binding chooser without importing the plugin package, which imports this module
_spec = importlib.util.spec_from_file_location('blender_layer_qt', Path(__file__).parents[2] / 'blender_layer' / 'qt.py')
qt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qt)
QAction, QByteArray, QDockWidget, QIcon, QMainWindow, QObject, pyqtSignal = (
    qt.QAction, qt.QByteArray, qt.QDockWidget, qt.QIcon, qt.QMainWindow, qt.QObject, qt.pyqtSignal)

IS_MOCK = True


class Selection:
    def __init__(self, x=0, y=0, w=0, h=0, value=255):
        self.select(x, y, w, h, value)

    def select(self, x, y, w, h, value):
        self._rect = (x, y, w, h)
        self.value = value

    def x(self): return self._rect[0]
    def y(self): return self._rect[1]
    def width(self): return self._rect[2]
    def height(self): return self._rect[3]

    def pixelData(self, x, y, w, h):
        return QByteArray(bytes([self.value]) * (w * h))


class Node:
    def __init__(self, name, type):
        self._name = name
        self._type = type
        self.children = []
        self.locked = False
        self.writes = []
        self.selectionValue = None

    def name(self): return self._name
    def setName(self, name): self._name = name
    def type(self): return self._type
    def childNodes(self): return list(self.children)
    def addChildNode(self, node, above): self.children.append(node); return True
    def setLocked(self, locked): self.locked = locked
    def setColorSpace(self, model, depth, profile): return True
    def animated(self): return False
    def hasKeyframeAtTime(self, t): return False

    def setPixelData(self, data, x, y, w, h):
        assert isinstance(data, QByteArray), type(data)
        self.writes.append((len(data.data()), x, y, w, h))
        return True

    def selection(self): return self.selectionValue
    def setSelection(self, selection): self.selectionValue = selection


class Document:
    def __init__(self, width=64, height=48):
        self._width = width
        self._height = height
        self.root = Node('root', 'grouplayer')
        self.refreshed = 0
        self.modified = False
        self.locked = False

    def width(self): return self._width
    def height(self): return self._height
    def xRes(self): return 300.0
    def yRes(self): return 300.0
    def rootNode(self): return self.root
    def fileName(self): return ''
    def colorDepth(self): return 'U8'
    def colorModel(self): return 'RGBA'
    def colorProfile(self): return 'sRGB-elle-V2-srgbtrc.icc'
    def selection(self): return None
    def framesPerSecond(self): return 24
    def fullClipRangeStartTime(self): return 0
    def fullClipRangeEndTime(self): return 100

    def nodeByName(self, name):
        stack = [self.root]
        while stack:
            node = stack.pop()
            if node.name() == name:
                return node
            stack.extend(node.children)
        return None

    def createNode(self, name, type): return Node(name, type)
    def createSelectionMask(self, name): return Node(name, 'selectionmask')
    def setActiveNode(self, node): pass
    def setCurrentTime(self, t): pass
    def waitForDone(self): pass
    def setModified(self, modified): self.modified = modified
    def refreshProjection(self): self.refreshed += 1

    def tryBarrierLock(self):
        self.locked = True
        return True

    def unlock(self): self.locked = False


class Notifier(QObject):
    windowCreated = pyqtSignal()


class Window:
    def __init__(self):
        self.window = QMainWindow()
        self.actions = {}

    def qwindow(self): return self.window

    def createAction(self, name, text='', menu=''):
        self.actions[name] = QAction(name, self.window)
        return self.actions[name]


class Krita:
    _instance = None

    def __init__(self):
        self.settings = {}
        self.document = Document()
        self.window = None
        self._notifier = Notifier()
        self.dockFactories = []
        self.actions = {}

    @staticmethod
    def instance():
        if Krita._instance is None:
            Krita._instance = Krita()
        return Krita._instance

    @staticmethod
    def krita_i18n(text): return text

    def version(self): return '6.0.0'
    def icon(self, name): return QIcon()
    def notifier(self): return self._notifier
    def activeWindow(self):
        if self.window is None:
            self.window = Window()
        return self.window

    def activeDocument(self): return self.document
    def readSetting(self, group, key, default): return self.settings.get((group, key), default)
    def writeSetting(self, group, key, value): self.settings[(group, key)] = value
    def addDockWidgetFactory(self, factory): self.dockFactories.append(factory)

    def action(self, name):
        if name not in self.actions:
            self.actions[name] = QAction(name)
        return self.actions[name]


class DockWidget(QDockWidget):
    def canvasChanged(self, canvas):
        pass


class DockWidgetFactoryBase:
    class DockPosition(enum.Enum):
        DockRight = 1


class DockWidgetFactory:
    def __init__(self, id, position, cls):
        self.id = id
        self.position = position
        self.cls = cls


builtins.i18n = Krita.krita_i18n
builtins.Krita = Krita.instance()
builtins.Application = Krita.instance()

__all__ = ['Krita', 'DockWidget', 'DockWidgetFactory', 'DockWidgetFactoryBase', 'Selection']
