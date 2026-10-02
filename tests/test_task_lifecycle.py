"""Exercise shutdown in subprocesses: a Qt fatal must not abort pytest itself."""

import os
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize("case", ["ncbi_tab", "update_window", "nested_blast", "mafft", "muscle", "multiple", "close_deadline"])
def test_close_running_task_exits_cleanly(case):
    script = textwrap.dedent('''
        import os, sys, time, tempfile
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PyQt6.QtCore import QThread, QTimer, qInstallMessageHandler
        from PyQt6.QtWidgets import QApplication, QMessageBox
        import main_window
        qInstallMessageHandler(lambda kind, ctx, msg: print(msg, flush=True))
        app = QApplication([])
        window = main_window.MainWindow()
        window.show()
        case = sys.argv[1]
        def unexpected_dialog(*args, **kwargs):
            raise AssertionError('A closing task displayed a dialog')
        QMessageBox.information = unexpected_dialog
        QMessageBox.warning = unexpected_dialog
        QMessageBox.critical = unexpected_dialog
        if case == 'update_window':
            main_window.fetch_latest_version = lambda timeout=5: (time.sleep(.3) or '1.0.0')
            window.check_for_updates()
            QTimer.singleShot(50, window.close)
        else:
            app.setQuitOnLastWindowClosed(False)
            if case in ('ncbi_tab', 'multiple'):
                from Bio import Entrez
                from modules.download_from_ncbi_tab import DownloadFromNCBITab
                class Response:
                    def __enter__(self): return self
                    def __exit__(self, *args): pass
                    def read(self):
                        time.sleep(.3)
                        return '>AB123.1\\nATGC\\n'
                Entrez.efetch = lambda **kwargs: Response()
                tab = DownloadFromNCBITab()
                tab.email_edit.setText('test@example.com')
                tab.acc_edit.setPlainText('AB123.1')
                tempdir = tempfile.TemporaryDirectory()
                tab.output_edit.setText(os.path.join(tempdir.name, 'download.fasta'))
                window.tabs.addTab(tab, 'Download')
                tab.run_download()
                if case == 'multiple':
                    main_window.fetch_latest_version = lambda timeout=5: (time.sleep(.3) or '1.0.0')
                    window.check_for_updates()
            elif case in ('mafft', 'muscle'):
                import subprocess
                from modules.mafft_alignment_tab import MafftAlignmentTab, _MafftWorker
                from modules.multiple_sequence_alignment_tab import MultipleSequenceAlignmentTab, _MuscleWorker
                original_popen = subprocess.Popen
                processes = []
                tempdir = tempfile.TemporaryDirectory()
                marker = os.path.join(tempdir.name, 'tool.exe')
                open(marker, 'w').close()
                def launch(cmd, **kwargs):
                    if cmd[0] == marker:
                        proc = original_popen([sys.executable, '-c', 'import time; time.sleep(30)'], **kwargs)
                        processes.append(proc)
                        return proc
                    return original_popen(cmd, **kwargs)
                subprocess.Popen = launch
                if case == 'mafft':
                    tab = MafftAlignmentTab()
                    worker = _MafftWorker('>a\\nAAAA\\n>b\\nAAAT\\n', 'Auto', 1, marker, 'FASTA')
                    tab._worker = worker
                    tab.start_worker(worker)
                else:
                    tab = MultipleSequenceAlignmentTab()
                    worker = _MuscleWorker('>a\\nAAAA\\n>b\\nAAAT\\n', 'fast', 1, marker)
                    tab._worker = worker
                    worker.start()
                window.tabs.addTab(tab, case)
            elif case == 'close_deadline':
                from modules.blast_local_tab import BlastLocalTab
                class IgnoreStopThread(QThread):
                    def run(self): self.msleep(1200)
                    def cancel(self): pass  # simulates a task that ignores its stop request
                tab = BlastLocalTab()
                window.tabs.addTab(tab, 'BLAST')
                tab._run_tab._thread = IgnoreStopThread()
                tab._run_tab._thread.start()
                main_window._CLOSE_DEADLINE_MS = 100
            else:
                from modules.blast_local_tab import BlastLocalTab
                class SlowThread(QThread):
                    def run(self): self.msleep(300)
                    def cancel(self): self.requestInterruption()
                tab = BlastLocalTab()
                window.tabs.addTab(tab, 'BLAST')
                tab._run_tab._thread = SlowThread()
                tab._run_tab._thread.start()
            QTimer.singleShot(50, window.close if case in ('multiple', 'close_deadline') else lambda: window.close_tab(0))
            def finish():
                if case == 'close_deadline':
                    assert not window.isVisible(), 'Window did not close past the deadline'
                    assert not window._closing_tabs, 'Closing tab was not released'
                    thread = tab._run_tab._thread
                    def quit_when_done():
                        try:
                            running = thread.isRunning()
                        except RuntimeError:
                            running = False  # parked thread already deleted
                        if not running:
                            app.quit()
                    ping = QTimer(window)  # parented so it is not garbage-collected
                    ping.setInterval(50)
                    ping.timeout.connect(quit_when_done)
                    ping.start()
                    return
                assert not window._closing_tabs, 'Closed tab was not released'
                if case in ('mafft', 'muscle'):
                    assert processes and all(p.poll() is not None for p in processes), 'Tool process survived close'
                window.close()
                app.quit()
            QTimer.singleShot(800, finish)
        QTimer.singleShot(4000, lambda: os._exit(99))
        app.exec()
        print('shutdown-complete', flush=True)
    ''')
    result = subprocess.run(
        [sys.executable, "-c", script, case],
        capture_output=True, encoding="utf-8", errors="replace", timeout=8,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "shutdown-complete" in result.stdout
    assert "Destroyed while thread" not in result.stdout + result.stderr
