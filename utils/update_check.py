"""Check GitHub for a newer SeqSketch release.

Pure stdlib logic (no Qt) so the version comparison and the API call can be
tested without instantiating widgets; the UI layer in ``main_window.py`` runs
``fetch_latest_version`` on a worker thread and turns the result into dialogs.
"""

import json
import re
import urllib.error
import urllib.request

from utils.app_version import APP_VERSION

RELEASES_API_URL = "https://api.github.com/repos/yananzh/SeqSketch/releases/latest"
RELEASES_PAGE_URL = "https://github.com/yananzh/SeqSketch/releases/latest"


def parse_version(version):
    """Extract a numeric tuple from a version string: 'v1.2.3' -> (1, 2, 3)."""
    match = re.search(r"\d+(?:\.\d+)*", version or "")
    if not match:
        return ()
    return tuple(int(part) for part in match.group(0).split("."))


def is_newer_version(current, latest):
    """True when ``latest`` is strictly newer than ``current`` (zero-padded)."""
    cur = parse_version(current)
    new = parse_version(latest)
    width = max(len(cur), len(new))
    cur += (0,) * (width - len(cur))
    new += (0,) * (width - len(new))
    return new > cur


def fetch_latest_version(timeout=5.0):
    """Return the latest release version string from the GitHub Releases API.

    Raises urllib.error.URLError / OSError / ValueError on failure; callers
    decide how to report errors. GitHub requires a User-Agent header.
    """
    request = urllib.request.Request(
        RELEASES_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"SeqSketch/{APP_VERSION}",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    for key in ("tag_name", "name"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value.lstrip("vV")
    raise ValueError("Release payload has no tag_name")
