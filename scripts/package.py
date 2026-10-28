"""Builds the release package dist/blender_layer-<version>.zip

The archive contains blender_layer/ and blender_layer.desktop, the layout Krita expects in its
pykrita folder and in "Tools > Scripts > Import Python Plugin from File...".

    python scripts/package.py                 build the package
    python scripts/package.py check-tag v1.0.0  fail if the tag does not match the plugin version
"""

import runpy
import sys
from pathlib import Path
from shutil import copy, copytree, ignore_patterns, make_archive, rmtree

root = Path(__file__).parent.parent
plugin = 'blender_layer'


def readVersion():
    version = runpy.run_path(str(root / plugin / 'version.py'))
    if version['parseVersion'](version['__version__']) is None:
        sys.exit(f"Version {version['__version__']} in {plugin}/version.py must be <major>.<minor>.<patch>, the auto-updater ignores anything else")
    return version['__version__']


def build():
    version = readVersion()
    staging = root / 'dist' / 'package'
    rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    copy(root / f'{plugin}.desktop', staging)
    copytree(root / plugin, staging / plugin, ignore=ignore_patterns('.*', '*.pyc', '__pycache__'))
    copy(root / 'LICENSE', staging / plugin)
    archive = make_archive(str(root / 'dist' / f'{plugin}-{version}'), 'zip', staging)
    rmtree(staging)
    print(archive)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if cmd == 'build':
        build()
    elif cmd == 'check-tag':
        tag, expected = sys.argv[2], 'v' + readVersion()
        if tag != expected:
            sys.exit(f'Tag {tag} does not match plugin version {expected} in {plugin}/version.py')
    else:
        sys.exit(f'Unknown command {cmd}')
