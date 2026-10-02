"""Keep task owners alive during cancellation, without blocking the Qt UI."""

import logging
import threading
from functools import wraps

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)
_TASK_ATTRIBUTES = (
    "worker", "worker_thread", "_worker", "_thread", "_batch_worker",
    "_render_thread", "_export_thread", "_update_worker", "_update_thread",
)
_PARKED_THREADS = {}


def task_objects(owner):
    """Include nested widgets (e.g. the BLAST query and database forms)."""
    objects = {}
    for widget in [owner, *owner.findChildren(QWidget)]:
        for name in _TASK_ATTRIBUTES:
            obj = getattr(widget, name, None)
            if obj is not None:
                objects[id(obj)] = obj
        for thread in widget.findChildren(QThread):
            objects[id(thread)] = thread
    return list(objects.values())


def tasks_running(objects):
    for obj in objects:
        try:
            if isinstance(obj, QThread) and obj.isRunning():
                return True
        except RuntimeError:
            continue  # a finished thread's C++ object has already been deleted
    return False


def mark_closing(owner):
    for widget in [owner, *owner.findChildren(QWidget)]:
        widget.setProperty("taskClosing", True)


def skip_when_closing(method):
    """Leave worker quit/cleanup connections intact but suppress result UI."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        if self.property("taskClosing"):
            return None
        return method(self, *args, **kwargs)
    return wrapped


def request_task_stop(obj):
    if obj is None:
        return
    try:
        if isinstance(obj, QThread):
            obj.requestInterruption()
            obj.quit()
        # WorkflowWorker polls its abort flag in addition to interruption.
        if hasattr(obj, "_abort"):
            obj._abort = True
        stop = getattr(obj, "cancel", None) or getattr(obj, "stop", None)
        if callable(stop):
            # External-tool stops may wait for taskkill/process exit. Keep that
            # wait off the GUI thread; the closing owner retains the task.
            def cancel():
                try:
                    stop()
                except RuntimeError:
                    pass
                except Exception:
                    logger.exception("Task cancellation failed")
            threading.Thread(target=cancel, daemon=True).start()
    except RuntimeError:
        pass


def park_thread(thread):
    """Retain and detach a QThread until its native finished signal fires."""
    if not isinstance(thread, QThread):
        return
    try:
        if not thread.isRunning():
            thread.deleteLater()
            return
        key = id(thread)
        if key in _PARKED_THREADS:
            return
        thread.setParent(None)
        _PARKED_THREADS[key] = thread
        # Several legacy subclasses shadow finished with a result signal.
        # Only QThread's actual completion permits destruction.
        QThread.finished.__get__(thread, QThread).connect(thread.deleteLater)
        thread.destroyed.connect(lambda: _PARKED_THREADS.pop(key, None))
    except RuntimeError:
        pass
