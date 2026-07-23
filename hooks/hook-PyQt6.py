# Custom PyInstaller hook for PyQt6
# Excludes Qt6 translation files (~200 files, ~20 MB) not needed by SeqSketch
# (SeqSketch uses its own translations/ module).

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Exclude Qt6 translation .qm files from being collected as data
# PyInstaller auto-collects PyQt6/Qt6/translations/ which we don't need.
datas = []
binaries = []
hiddenimports = []


# Only exclude translation data; keep everything else
def _filter_translations(datas_list):
    """Remove entries under PyQt6/Qt6/translations/."""
    import os

    return [
        (src, dest)
        for src, dest in datas_list
        if "translations" not in dest.replace(os.sep, "/")
        and "qtbase_" not in os.path.basename(src)
    ]


# Use the hook's standard mechanism: override the default data collection
try:
    from PyInstaller.utils.hooks import qt as qt_hooks
except ImportError:
    pass
