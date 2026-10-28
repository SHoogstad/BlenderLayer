"""Smoke test which runs the plugin outside of Krita, against tests/mock/krita.py.

Builds the docker, drives the navigation widget and dialogs, streams frames from a fake Blender
client through the real server, and installs an update from a fake GitHub API.
Run with PyQt5 or PyQt6 (BLENDER_LAYER_QT=5/6 selects one), headless with QT_QPA_PLATFORM=offscreen.
"""

import hashlib, io, json, os, pickle, socket, struct, sys, tempfile, threading, time, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from multiprocessing import shared_memory
from pathlib import Path

root = Path(__file__).parent.parent
sys.path[:0] = [str(root), str(root / 'tests' / 'mock')]
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# Fake GitHub API, the docker checks for updates when it is created
packageFiles = {
    'blender_layer/__init__.py': b'# updated\n',
    'blender_layer/version.py': b"__version__ = '9.9.9'\n",
    'blender_layer.desktop': b'[Desktop Entry]\n',
}

def makeZip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()

class FakeGitHub(BaseHTTPRequestHandler):
    routes = {}

    def do_GET(self):
        body = self.routes.get(self.path)
        self.send_response(200 if body is not None else 404)
        self.end_headers()
        self.wfile.write(body or b'{}')

    def log_message(self, *args):
        pass

http = ThreadingHTTPServer(('127.0.0.1', 0), FakeGitHub)
threading.Thread(target=http.serve_forever, daemon=True).start()
apiBase = f'http://127.0.0.1:{http.server_address[1]}'

def publishRelease(repo, tag, files, digest=None):
    data = makeZip(files)
    FakeGitHub.routes[f'/{repo}/package.zip'] = data
    FakeGitHub.routes[f'/repos/{repo}/releases/latest'] = json.dumps({
        'tag_name': tag,
        'assets': [{
            'name': 'blender_layer.zip',
            'browser_download_url': f'{apiBase}/{repo}/package.zip',
            'digest': 'sha256:' + (digest or hashlib.sha256(data).hexdigest()),
        }],
    }).encode()
    return f'{apiBase}/repos/{repo}'

os.environ['BLENDER_LAYER_UPDATE_URL'] = publishRelease('docker', 'v9.9.9', packageFiles)

from blender_layer.qt import QT6, binding, QApplication, QDialog, QEvent, QImage, QMouseEvent, QPoint, QPointF, Qt, QTimer, QWheelEvent
app = QApplication(sys.argv)

import krita
import blender_layer
from blender_layer.blenderLayer import BlenderLayer
from blender_layer.updater import Updater, getUpdater

print(f'Testing with {binding}, Python {sys.version.split()[0]}')
instance = krita.Krita.instance()
failures = []

def check(name, condition, detail=''):
    print(('ok   ' if condition else 'FAIL ') + name + (f' ({detail})' if detail and not condition else ''))
    if not condition:
        failures.append(name)

def waitFor(condition, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return False

def acceptNextDialog():
    def accept():
        dialogs = [w for w in QApplication.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]
        if dialogs:
            dialogs[0].accept()
        else:
            QTimer.singleShot(50, accept)
    QTimer.singleShot(100, accept)

# Plugin registration and docker
check('dock factory registered', len(instance.dockFactories) == 1 and instance.dockFactories[0].cls is BlenderLayer)
dock = BlenderLayer()
dock.show()
app.processEvents()
check('docker built', dock.uiContainer is not None)
check('update notice shown', waitFor(lambda: dock.updateNotice.isVisibleTo(dock.uiContainer)), dock.updateNoticeLabel.text())
check('update notice text', 'v9.9.9' in dock.updateNoticeLabel.text(), dock.updateNoticeLabel.text())

for mode in (2, 1, 0):
    dock.viewModeChanged(mode)
    dock.updateModeChanged(mode)
check('view and update modes', True)

# Navigation widget: drag to rotate, wheel to zoom, painting
nav = dock.navigate
nav.resize(120, 120)
rotations, zooms = [], []
nav.rotateSignal.connect(rotations.append)
nav.zoomSignal.connect(zooms.append)

def mouse(type, pos, button, buttons, modifiers=Qt.KeyboardModifier.NoModifier):
    return QMouseEvent(type, QPointF(*pos), QPointF(*pos), button, buttons, modifiers)

left = Qt.MouseButton.LeftButton
nav.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, (60, 60), left, left))
nav.mouseMoveEvent(mouse(QEvent.Type.MouseMove, (70, 65), Qt.MouseButton.NoButton, left))
nav.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, (70, 65), left, Qt.MouseButton.NoButton))
check('drag rotates view', len(rotations) == 1)

nav.wheelEvent(QWheelEvent(QPointF(60, 60), QPointF(60, 60), QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))
check('wheel zooms', zooms == [-120 / 360.0], zooms)

image = nav.grab().toImage()
check('navigation widget paints', not image.isNull() and image.width() == 120)

# Pose library previews from raw RGBA bytes
pixels = bytes(128 * 128 * 4)
dock.settings.posePreviews = {'Standing': pixels}
dock.updatePoseLibrary(['Standing', 'Jumping'], False)
dock.loadPosePreview('Jumping', pixels)
check('pose previews', dock.poseList.count() == 2)

# Region stored in the selection mask of the Blender layer, 127 means viewport is not fixed
document = instance.activeDocument()
dock.saveFilenameToLayer('scene.blend')
mask = document.nodeByName(dock.settings.layerName).childNodes()[0]
mask.setSelection(krita.Selection(4, 6, 20, 10, 127))
dock.resetRegion(True)
check('region read from layer', (dock.regionX.value(), dock.regionY.value(), dock.regionWidth.value()) == (4, 6, 20))
check('region viewport flag', not dock.regionViewport.isChecked())
dock.regionViewport.setChecked(True)
dock.resetRegion(False)

# Settings dialog
acceptNextDialog()
dock.showSettings()
check('settings dialog accepted', instance.readSetting('blender_layer', 'checkUpdates', None) == 'True')

# Assistants file
assistantsFile = os.path.join(tempfile.mkdtemp(), 'test.paintingassistant')
dock.writeAssistants(('assistants', assistantsFile, 10, 20, False, 100, 20, False, 50, 500, False, 50, 40))
check('assistants written', open(assistantsFile).read().endswith('</paintingassistant>'))

# Server: a fake Blender connects, streams frames over the socket, shared memory and from a file
def sendObj(conn, obj):
    msg = pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)
    conn.sendall(struct.pack('>I', len(msg)) + msg)

def recvAll(conn, n):
    data = bytearray()
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

def recvObj(conn):
    size = recvAll(conn, 4)
    return pickle.loads(recvAll(conn, struct.unpack('>I', size)[0])) if size else None

with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    dock.settings.port = s.getsockname()[1]

w, h = document.width(), document.height()
frameFile = os.path.join(tempfile.mkdtemp(), 'frame.png')
frame = QImage(w, h, QImage.Format.Format_RGBA8888)
frame.fill(Qt.GlobalColor.red)
frame.save(frameFile)
blender = {'init': None, 'replies': [], 'error': None}

def fakeBlender():
    try:
        conn = None
        for _ in range(100):
            try:
                conn = socket.create_connection(('127.0.0.1', dock.settings.port), timeout=10)
                break
            except OSError:
                time.sleep(0.05)
        magic = recvAll(conn, 16)
        conn.sendall(magic)
        blender['init'] = recvObj(conn)
        sendObj(conn, ('info', True, 'scene.blend'))
        sendObj(conn, [('update', 0, 0, w, h, bytes(w * h * 4))])
        blender['replies'].append(recvObj(conn))
        shm = shared_memory.SharedMemory(name=f'krita_blender_layer:{dock.settings.port}')
        shm.buf[:w * h * 4] = bytes([255]) * (w * h * 4)
        shm.close()
        sendObj(conn, [('update', 0, 0, w, h, None)])
        blender['replies'].append(recvObj(conn))
        sendObj(conn, [('updateFromFile', 0, 0, frameFile), ('status', 'hello from blender')])
        blender['replies'].append(recvObj(conn))
        try:
            # Keep exchanging messages like Blender does until Krita stops the server
            while blender['replies'][-1] is not None:
                sendObj(conn, [])
                blender['replies'].append(recvObj(conn))
        except ConnectionError:
            pass
        conn.close()
    except Exception as e:
        blender['error'] = repr(e)

thread = threading.Thread(target=fakeBlender, daemon=True)
thread.start()
dock.startStopServer()
check('server connected', waitFor(lambda: dock.viewGroup.isEnabled()), dock.statusBar.text())
check('init message', blender['init'] is not None and blender['init'][0] == 'Init' and blender['init'][1:3] == (w, h))
layer = document.nodeByName(dock.settings.layerName)
check('frames written to layer', waitFor(lambda: len(layer.writes) >= 3), layer.writes)
check('frame sizes', [write[0] for write in layer.writes[:3]] == [w * h * 4] * 3, layer.writes)
check('blender status message', waitFor(lambda: 'hello from blender' in dock.statusBar.text()), dock.statusBar.text())
check('projection refreshed', waitFor(lambda: document.refreshed > 0))

# Alt + middle mouse anywhere in Krita is routed through the application event filter
middle = Qt.MouseButton.MiddleButton
alt = Qt.KeyboardModifier.AltModifier
target = instance.activeWindow().qwindow()
before = len(rotations)
QApplication.sendEvent(target, mouse(QEvent.Type.MouseButtonPress, (10, 10), middle, middle, alt))
QApplication.sendEvent(target, mouse(QEvent.Type.MouseMove, (30, 20), Qt.MouseButton.NoButton, middle, alt))
nav.releaseMouse()
check('alt + middle mouse navigates', len(rotations) == before + 1)

acceptNextDialog()
dock.updateAnimation()
check('animation dialog accepted', dock.progress.isVisibleTo(dock.uiContainer))
check('queued messages reached blender', waitFor(lambda: any(m[0] == 'requestAnimation' for r in list(blender['replies']) if r for m in r)))

dock.startStopServer()
check('server stopped', waitFor(lambda: dock.startstop.text() == 'Start Server'), dock.startstop.text())
thread.join(10)
check('fake blender finished', not thread.is_alive() and blender['error'] is None, blender['error'])

# Updater: install from the docker notice into a scratch plugin folder
pykrita = Path(tempfile.mkdtemp())
updater = getUpdater()
updater.pluginDir = str(pykrita / 'blender_layer')
dock.installUpdate()
check('update installed', waitFor(lambda: updater.restartRequired), dock.updateNoticeLabel.text())
check('update files', (pykrita / 'blender_layer' / 'version.py').read_bytes() == packageFiles['blender_layer/version.py'] and (pykrita / 'blender_layer.desktop').exists())
check('restart notice', 'Restart Krita' in dock.updateNoticeLabel.text(), dock.updateNoticeLabel.text())

def runUpdate(apiUrl, install=True):
    result = {}
    u = Updater(pluginDir=str(Path(tempfile.mkdtemp()) / 'blender_layer'), apiUrl=apiUrl)
    u.available.connect(lambda tag: result.setdefault('available', tag))
    u.upToDate.connect(lambda: result.setdefault('upToDate', True))
    u.installed.connect(lambda tag: result.setdefault('installed', tag))
    u.failed.connect(lambda error: result.setdefault('failed', error))
    u.check()
    waitFor(lambda: not u.busy)
    if install and 'available' in result:
        u.install()
        waitFor(lambda: not u.busy)
    return result

r = runUpdate(publishRelease('same', 'v' + blender_layer.version.__version__, packageFiles))
check('same version is up to date', r.get('upToDate') and 'available' not in r, r)
r = runUpdate(publishRelease('corrupt', 'v9.9.9', packageFiles, digest='0' * 64))
check('checksum mismatch rejected', 'checksum' in r.get('failed', '') and 'installed' not in r, r)
r = runUpdate(publishRelease('escape', 'v9.9.9', {**packageFiles, '../evil.py': b''}))
check('path traversal rejected', 'Unexpected file' in r.get('failed', '') and 'installed' not in r, r)
r = runUpdate(f'{apiBase}/repos/missing')
check('no release is reported', 'No release' in r.get('failed', ''), r)

http.shutdown()
print(f'{len(failures)} failure(s)' if failures else 'All checks passed')
sys.exit(1 if failures else 0)
