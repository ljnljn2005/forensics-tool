import os
import shutil
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from src.log_analysis import LogAnalysisInterface, discover_logs, parse_evtx_text, read_log_detail


class _DummySignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in self._callbacks:
            callback(*args)


class _DummyScanThread:
    def __init__(self, mapping_path, module, parent=None):
        self.mapping_path = mapping_path
        self.module = module
        self.parent = parent
        self.finished_signal = _DummySignal()
        self.started = False

    def start(self):
        self.started = True


class _DummyDetailThread:
    def __init__(self, entry, parent=None):
        self.entry = entry
        self.parent = parent
        self.finished_signal = _DummySignal()
        self.started = False

    def start(self):
        self.started = True


class _ImmediateScanThread(_DummyScanThread):
    def start(self):
        self.started = True
        self.finished_signal.emit(discover_logs(self.mapping_path, self.module), "")


class _ImmediateDetailThread(_DummyDetailThread):
    def start(self):
        self.started = True
        events = parse_evtx_text(read_log_detail(self.entry)) if str(self.entry.get("path", "")).lower().endswith(".evtx") else []
        self.finished_signal.emit(read_log_detail(self.entry), events)


class _MainWindowStub(QWidget):
    def __init__(self, mapping_path=""):
        super().__init__()
        self.mapping_path = mapping_path


class LogAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_root = os.path.join(os.getcwd(), "_log_analysis_test")
        shutil.rmtree(self.temp_root, ignore_errors=True)
        os.makedirs(self.temp_root, exist_ok=True)
        self.host = _MainWindowStub()

    def tearDown(self):
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_discover_windows_logs_finds_evtx_and_text_logs(self):
        evtx_dir = os.path.join(self.temp_root, "Windows", "System32", "winevt", "Logs")
        text_dir = os.path.join(self.temp_root, "Windows", "Logs")
        os.makedirs(evtx_dir, exist_ok=True)
        os.makedirs(text_dir, exist_ok=True)
        with open(os.path.join(evtx_dir, "System.evtx"), "w", encoding="utf-8") as handle:
            handle.write("evtx placeholder")
        with open(os.path.join(text_dir, "CBS.log"), "w", encoding="utf-8") as handle:
            handle.write("cbs line 1\ncbs line 2")

        entries = discover_logs(self.temp_root, "windows")

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["name"], "System.evtx")
        self.assertEqual(entries[1]["name"], "CBS.log")

    def test_discover_linux_logs_finds_var_log_entries(self):
        log_dir = os.path.join(self.temp_root, "var", "log")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "auth.log"), "w", encoding="utf-8") as handle:
            handle.write("accepted password")

        entries = discover_logs(self.temp_root, "linux")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], "auth.log")
        self.assertIn("/var/log", entries[0]["display_path"])

    def test_log_workbench_layout_and_scan_output(self):
        log_dir = os.path.join(self.temp_root, "var", "log")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "syslog"), "w", encoding="utf-8") as handle:
            handle.write("kernel: boot ok")

        self.host.mapping_path = self.temp_root
        widget = LogAnalysisInterface(self.host, module="linux")

        self.assertEqual(widget.logSourceList.objectName(), "logSourceList")
        self.assertEqual(widget.resultTable.objectName(), "logResultTable")
        self.assertEqual(widget.previewPanel.objectName(), "logPreviewPanel")
        self.assertEqual(widget.eventTable.objectName(), "logEventTable")

        with patch("src.log_analysis.LogScanThread", side_effect=lambda mapping_path, module, parent=None: _ImmediateScanThread(mapping_path, module, parent)), patch(
            "src.log_analysis.LogDetailThread",
            side_effect=lambda entry, parent=None: _ImmediateDetailThread(entry, parent),
        ):
            widget.scan_logs()

        self.assertEqual(widget.resultTable.rowCount(), 1)
        self.assertIn("syslog", widget.previewOutput.textEdit.toPlainText())

    def test_invalid_mapping_path_reports_error(self):
        self.host.mapping_path = "Z:/missing"
        widget = LogAnalysisInterface(self.host, module="windows")

        widget.scan_logs()

        self.assertIn("无效路径", widget.previewOutput.textEdit.toPlainText())

    def test_scan_logs_starts_background_worker_and_disables_button(self):
        self.host.mapping_path = self.temp_root
        widget = LogAnalysisInterface(self.host, module="windows")
        created = []

        def build_thread(mapping_path, module, parent=None):
            thread = _DummyScanThread(mapping_path, module, parent)
            created.append(thread)
            return thread

        with patch("src.log_analysis.LogScanThread", side_effect=build_thread):
            widget.scan_logs()

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].mapping_path, self.temp_root)
        self.assertTrue(created[0].started)
        self.assertFalse(widget.scanBtn.isEnabled())

    def test_read_log_detail_parses_evtx_via_wevtutil(self):
        evtx_path = os.path.join(self.temp_root, "System.evtx")
        with open(evtx_path, "w", encoding="utf-8") as handle:
            handle.write("placeholder")

        entry = {
            "name": "System.evtx",
            "path": evtx_path,
            "display_path": "/Windows/System32/winevt/Logs/System.evtx",
            "category": "事件日志",
            "size": 10,
        }

        class _Result:
            returncode = 0
            stdout = "Event ID: 6005\nProvider Name: EventLog"
            stderr = ""

        with patch("src.log_analysis.subprocess.run", return_value=_Result()):
            detail = read_log_detail(entry)

        self.assertIn("Event ID: 6005", detail)
        self.assertIn("Provider Name: EventLog", detail)

    def test_parse_evtx_text_extracts_structured_event_rows(self):
        text = (
            "Event[0]:\n"
            "  Log Name: System\n"
            "  Source: EventLog\n"
            "  Date: 2024-05-01T10:20:30.000\n"
            "  Event ID: 6005\n"
            "  Level: Information\n"
            "\n"
            "Event[1]:\n"
            "  Log Name: Security\n"
            "  Provider Name: Microsoft-Windows-Security-Auditing\n"
            "  Date: 2024-05-01T10:21:30.000\n"
            "  Event ID: 4624\n"
            "  Level: Information\n"
        )

        events = parse_evtx_text(text)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_id"], "6005")
        self.assertEqual(events[0]["provider"], "EventLog")
        self.assertEqual(events[1]["event_id"], "4624")
        self.assertEqual(events[1]["provider"], "Microsoft-Windows-Security-Auditing")

    def test_parse_evtx_text_handles_adjacent_event_blocks(self):
        text = (
            "Event[0]:\n"
            "  Provider Name: EventLog\n"
            "  Date: 2024-05-01T10:20:30.000\n"
            "  Event ID: 6005\n"
            "  Level: Information\n"
            "Event[1]:\n"
            "  Provider Name: Service Control Manager\n"
            "  Date: 2024-05-01T10:21:30.000\n"
            "  Event ID: 7036\n"
            "  Level: Information\n"
            "Event[2]:\n"
            "  Provider Name: Microsoft-Windows-Winlogon\n"
            "  Date: 2024-05-01T10:22:30.000\n"
            "  Event ID: 7001\n"
            "  Level: Warning\n"
        )

        events = parse_evtx_text(text)

        self.assertEqual(len(events), 3)
        self.assertEqual(events[1]["event_id"], "7036")
        self.assertEqual(events[2]["provider"], "Microsoft-Windows-Winlogon")

    def test_evtx_detail_populates_event_table(self):
        evtx_path = os.path.join(self.temp_root, "System.evtx")
        with open(evtx_path, "w", encoding="utf-8") as handle:
            handle.write("placeholder")

        self.host.mapping_path = self.temp_root
        widget = LogAnalysisInterface(self.host, module="windows")
        entry = {
            "name": "System.evtx",
            "path": evtx_path,
            "display_path": "/Windows/System32/winevt/Logs/System.evtx",
            "category": "事件日志",
            "size": 10,
        }

        class _Result:
            returncode = 0
            stdout = "Event[0]:\n  Provider Name: EventLog\n  Date: 2024-05-01T10:20:30.000\n  Event ID: 6005\n  Level: Information"
            stderr = ""

        with patch("src.log_analysis.subprocess.run", return_value=_Result()), patch(
            "src.log_analysis.LogDetailThread",
            side_effect=lambda event_entry, parent=None: _ImmediateDetailThread(event_entry, parent),
        ):
            widget.show_entry_detail(entry)

        self.assertEqual(widget.eventTable.rowCount(), 1)
        self.assertEqual(widget.eventTable.item(0, 0).text(), "6005")
        self.assertEqual(widget.eventTable.item(0, 1).text(), "EventLog")

    def test_tables_enable_sorting_from_header(self):
        widget = LogAnalysisInterface(self.host, module="windows")

        self.assertTrue(widget.resultTable.isSortingEnabled())
        self.assertTrue(widget.eventTable.isSortingEnabled())

    def test_render_tables_keep_expected_rows_when_sorting_enabled(self):
        widget = LogAnalysisInterface(self.host, module="windows")

        widget._render_result_table(
            [
                {"name": "B.evtx", "category": "事件日志", "display_path": "/b", "size": 2},
                {"name": "A.evtx", "category": "事件日志", "display_path": "/a", "size": 1},
            ]
        )
        widget._render_event_table(
            [
                {"event_id": "6005", "provider": "EventLog", "time_created": "2024-05-01", "level": "Information"},
                {"event_id": "4624", "provider": "Security", "time_created": "2024-05-02", "level": "Information"},
            ]
        )

        self.assertEqual(widget.resultTable.rowCount(), 2)
        self.assertEqual(widget.eventTable.rowCount(), 2)
        self.assertEqual(widget.resultTable.item(0, 0).text(), "B.evtx")
        self.assertEqual(widget.resultTable.item(1, 0).text(), "A.evtx")
        self.assertEqual(widget.eventTable.item(0, 0).text(), "6005")
        self.assertEqual(widget.eventTable.item(1, 0).text(), "4624")


if __name__ == "__main__":
    unittest.main()
