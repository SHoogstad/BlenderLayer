# Release tag on GitHub is "v" + __version__, the auto-updater compares against it.
__version__ = '1.0.0'

import re

def parseVersion(tag):
    """(major, minor, patch) of a version or release tag, None if it isn't one the updater understands"""
    m = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', tag.strip())
    return tuple(int(x) for x in m.groups()) if m else None
