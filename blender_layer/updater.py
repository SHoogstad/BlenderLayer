"""Checks GitHub releases for a newer version of the plugin and installs it into the pykrita folder.

A release must have a tag "v<major>.<minor>.<patch>" and a .zip asset built by scripts/package.py.
The asset is verified against the sha256 digest GitHub reports for it before anything is written.
"""

import hashlib, importlib, io, json, os, shutil, tempfile, zipfile

from .qt import QObject, QUrl, pyqtSignal, binding
from .version import __version__, parseVersion

API_URL = os.environ.get('BLENDER_LAYER_UPDATE_URL', 'https://api.github.com/repos/SHoogstad/BlenderLayer')
PACKAGE = 'blender_layer'

class Updater(QObject):
    checking = pyqtSignal()
    available = pyqtSignal(str)
    upToDate = pyqtSignal()
    installed = pyqtSignal(str)
    failed = pyqtSignal(str)  # checking for updates failed
    installFailed = pyqtSignal(str)

    def __init__(self, pluginDir=None, apiUrl=None):
        super().__init__()
        self.pluginDir = pluginDir or os.path.dirname(os.path.abspath(__file__))
        self.apiUrl = apiUrl or API_URL
        self.currentVersion = 'v' + __version__
        self.latest = None
        self.checked = False
        self.restartRequired = False
        self.busy = False
        self.qtnet = None
        self.net = None
        self.reply = None
        self.callback = None

    def check(self):
        if self.busy or self.restartRequired:
            return
        self.busy = True
        self.checked = True
        self.checking.emit()
        self._get(f'{self.apiUrl}/releases/latest', self._onReleaseInfo)

    def install(self):
        if self.busy or not self.latest:
            return
        self.busy = True
        self._get(self.latest['url'], self._onPackage)

    def _get(self, url, callback):
        try:
            self._startRequest(url, callback)
        except Exception as e:
            # E.g. a Krita build without QtNetwork, the plugin keeps working without updates
            self._fail(callback, e)

    def _startRequest(self, url, callback):
        if self.net is None:
            # Imported on first use so a missing QtNetwork can't keep the plugin from loading
            self.qtnet = importlib.import_module(f'{binding}.QtNetwork')
            self.net = self.qtnet.QNetworkAccessManager(self)
        QNetworkRequest = self.qtnet.QNetworkRequest
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b'User-Agent', b'BlenderLayer-Krita-Plugin')
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        if hasattr(request, 'setTransferTimeout'):  # Qt 5.15+
            request.setTransferTimeout(60000)
        # One request at a time (see busy). The slot is a bound method on purpose: a lambda holding the
        # reply is released while the reply is being deleted, which crashes PyQt5 on Python 3.10 (Krita 5.2)
        self.callback = callback
        self.reply = self.net.get(request)
        self.reply.finished.connect(self._onFinished)

    def _onFinished(self):
        reply, callback = self.reply, self.callback
        self.reply = self.callback = None
        try:
            if reply.error() != self.qtnet.QNetworkReply.NetworkError.NoError:
                status = reply.attribute(self.qtnet.QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                if status == 404 and callback == self._onReleaseInfo:
                    raise RuntimeError(i18n("No release published yet"))
                raise RuntimeError(reply.errorString())
            callback(reply.readAll().data())
        except Exception as e:
            self._fail(callback, e)
        finally:
            reply.deleteLater()

    def _fail(self, callback, error):
        self.busy = False
        (self.installFailed if callback == self._onPackage else self.failed).emit(str(error))

    def _onReleaseInfo(self, data):
        release = json.loads(data)
        tag = release.get('tag_name', '')
        latest = parseVersion(tag)
        if latest is None:
            raise RuntimeError(i18n("Invalid release tag: {0}").format(tag))
        self.busy = False
        if latest <= parseVersion(self.currentVersion):
            self.upToDate.emit()
            return
        asset = next((a for a in release.get('assets', []) if a.get('name', '').endswith('.zip')), None)
        digest = (asset.get('digest') or '') if asset else ''
        if not digest.startswith('sha256:'):
            raise RuntimeError(i18n("Release {0} has no verifiable package").format(tag))
        self.latest = {'tag': tag, 'url': asset['browser_download_url'], 'sha256': digest[len('sha256:'):]}
        self.available.emit(tag)

    def _onPackage(self, data):
        sha256 = hashlib.sha256(data).hexdigest()
        if sha256 != self.latest['sha256']:
            raise RuntimeError(i18n("Downloaded package is corrupted (checksum mismatch)"))
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            for name in names:
                parts = name.replace('\\', '/').split('/')
                if name.startswith(('/', '\\')) or '..' in parts or ':' in name or not (parts[0] == PACKAGE or name == PACKAGE + '.desktop'):
                    raise RuntimeError(i18n("Unexpected file in package: {0}").format(name))
            if PACKAGE + '/__init__.py' not in names:
                raise RuntimeError(i18n("Package does not contain the plugin"))
            self._replacePlugin(archive)
        self.busy = False
        self.restartRequired = True
        self.currentVersion = self.latest['tag']
        self.installed.emit(self.latest['tag'])

    def _replacePlugin(self, archive):
        """Swaps the plugin folder for the new one with renames, so a failure leaves either the old or
        the new version complete, and files dropped from the new release don't linger"""
        pluginDir = os.path.abspath(self.pluginDir)
        pykrita = os.path.dirname(pluginDir)
        # A symlink or junction (e.g. to a git checkout) would be replaced by a plain folder
        if os.path.normcase(os.path.realpath(pluginDir)) != os.path.normcase(os.path.join(os.path.realpath(pykrita), os.path.basename(pluginDir))):
            raise RuntimeError(i18n("The plugin folder is a link, update it manually"))
        # Staged next to the plugin so the renames stay on one drive
        temp = tempfile.mkdtemp(prefix='.' + PACKAGE + '_update_', dir=pykrita)
        try:
            archive.extractall(temp)
            old = os.path.join(temp, 'old')
            if os.path.exists(pluginDir):
                os.replace(pluginDir, old)
            try:
                os.replace(os.path.join(temp, PACKAGE), pluginDir)
            except Exception:
                if os.path.exists(old):
                    os.replace(old, pluginDir)
                raise
            desktop = os.path.join(temp, PACKAGE + '.desktop')
            if os.path.isfile(desktop):
                os.replace(desktop, os.path.join(pykrita, PACKAGE + '.desktop'))
        finally:
            shutil.rmtree(temp, ignore_errors=True)

_updater = None

def getUpdater():
    """One updater shared by the dockers of all Krita windows"""
    global _updater
    if _updater is None:
        _updater = Updater()
    return _updater
