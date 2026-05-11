import os
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.windows_registry import (
    DefaultAppAssociation,
    FileHiveLoader,
    RegistrySearchItem,
    extract_registry_search_items,
    find_windows_hives,
    format_default_app_associations,
    get_default_app_associations,
    parse_reg_query_values,
    query_registry_path_report,
)
from src.windows_registry import _decode_reg_output


class WindowsRegistryTests(unittest.TestCase):
    def test_find_windows_hives_discovers_software_and_user_hives(self):
        root = r"C:\mount"
        software = os.path.join(root, "Windows", "System32", "config", "SOFTWARE")
        ntuser = os.path.join(root, "Users", "Alice", "NTUSER.DAT")

        def exists(path):
            return path in {software, ntuser}

        with (
            patch("src.windows_registry.os.path.abspath", return_value=root),
            patch("src.windows_registry.os.path.isdir", return_value=True),
            patch("src.windows_registry.os.path.exists", side_effect=exists),
            patch("src.windows_registry.os.listdir", return_value=["Alice", "Public"]),
        ):
            hives = find_windows_hives(str(root))

        self.assertEqual(hives.software_hive, software)
        self.assertEqual(len(hives.user_hives), 1)
        self.assertEqual(hives.user_hives[0].username, "Alice")
        self.assertEqual(hives.user_hives[0].path, ntuser)

    def test_parse_reg_query_values_reads_standard_reg_output(self):
        output = """
HKEY_USERS\\Temp\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\.pdf\\UserChoice
    Hash    REG_SZ    abc123
    ProgId    REG_SZ    AcroExch.Document.DC
"""

        values = parse_reg_query_values(output)

        self.assertEqual(values["Hash"], "abc123")
        self.assertEqual(values["ProgId"], "AcroExch.Document.DC")

    def test_decode_reg_output_handles_chinese_windows_errors(self):
        data = "错误: 客户端没有所需的特权。\r\n".encode("gbk")

        text = _decode_reg_output(data)

        self.assertIn("客户端没有所需的特权", text)

    def test_file_hive_loader_reads_synthetic_hive_without_reg_load(self):
        hive_bytes = build_synthetic_hive()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(hive_bytes)
            hive_path = tmp.name
        try:
            values = FileHiveLoader().query_values(hive_path, r"Software\Test")
        finally:
            os.unlink(hive_path)

        self.assertEqual(values["ProgId"], "Example.App")

    def test_file_hive_loader_returns_empty_for_missing_key(self):
        hive_bytes = build_synthetic_hive()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(hive_bytes)
            hive_path = tmp.name
        try:
            values = FileHiveLoader().query_values(hive_path, r"Software\Missing")
        finally:
            os.unlink(hive_path)

        self.assertEqual(values, {})

    def test_get_default_app_associations_queries_each_user_extension(self):
        loader = Mock()
        loader.query_values.side_effect = [
            {"ProgId": "AcroExch.Document.DC", "Hash": "abc"},
            {},
            {},
            {},
        ]
        hives = find_windows_hives_from_paths(
            user_hives=[("Alice", "C:/mount/Users/Alice/NTUSER.DAT")],
            software_hive="C:/mount/Windows/System32/config/SOFTWARE",
        )

        rows = get_default_app_associations(
            "C:/mount",
            extensions=[".pdf", ".html"],
            hive_loader=loader,
            hives=hives,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].username, "Alice")
        self.assertEqual(rows[0].extension, ".pdf")
        self.assertEqual(rows[0].prog_id, "AcroExch.Document.DC")
        queried_subkeys = [call.args[1] for call in loader.query_values.call_args_list]
        self.assertIn(
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice",
            queried_subkeys,
        )
        self.assertIn(
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.html\UserChoice",
            queried_subkeys,
        )

    def test_format_default_app_associations_has_clear_empty_state(self):
        text = format_default_app_associations([])

        self.assertIn("未找到默认应用关联", text)

    def test_lookup_default_apps_report_surfaces_hive_load_errors(self):
        loader = Mock()
        loader.query_values.side_effect = RuntimeError("A required privilege is not held by the client.")
        hives = find_windows_hives_from_paths(
            user_hives=[("Alice", "C:/mount/Users/Alice/NTUSER.DAT")],
            software_hive="C:/mount/Windows/System32/config/SOFTWARE",
        )

        from src.windows_registry import build_default_apps_report

        text = build_default_apps_report("C:/mount", hives=hives, hive_loader=loader)

        self.assertIn("注册表读取失败", text)
        self.assertIn("A required privilege is not held", text)
        self.assertNotIn("未找到默认应用关联", text)

    def test_format_default_app_associations_includes_rows(self):
        rows = [
            DefaultAppAssociation(
                username="Alice",
                extension=".pdf",
                prog_id="AcroExch.Document.DC",
                hash_value="abc",
                command="\"C:\\Program Files\\Adobe\\Acrobat.exe\" \"%1\"",
                hive_path="C:/mount/Users/Alice/NTUSER.DAT",
            )
        ]

        text = format_default_app_associations(rows)

        self.assertIn("Alice", text)
        self.assertIn(".pdf", text)
        self.assertIn("AcroExch.Document.DC", text)
        self.assertIn("Acrobat.exe", text)

    def test_extract_registry_search_items_imports_plugin_registry_blocks(self):
        plugins = {
            "Windows Plugin": {
                "blocks": [
                    {
                        "name": "Run Keys",
                        "cmd": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                        "type": "注册表查找",
                        "module": "windows",
                    },
                    {
                        "name": "Normal Command",
                        "cmd": "systeminfo",
                        "type": "SSH命令",
                        "module": "windows",
                    },
                ]
            }
        }

        items = extract_registry_search_items(plugins)

        self.assertEqual(
            items,
            [
                RegistrySearchItem(
                    plugin="Windows Plugin",
                    name="Run Keys",
                    registry_path=r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                    description="",
                )
            ],
        )

    def test_query_registry_path_report_queries_each_user_hive_for_hkcu(self):
        loader = Mock()
        loader.query_values.side_effect = [
            {"OneDrive": "C:\\OneDrive.exe"},
            {},
        ]
        hives = find_windows_hives_from_paths(
            user_hives=[
                ("Alice", "C:/mount/Users/Alice/NTUSER.DAT"),
                ("Bob", "C:/mount/Users/Bob/NTUSER.DAT"),
            ],
            software_hive="C:/mount/Windows/System32/config/SOFTWARE",
        )

        report = query_registry_path_report(
            "C:/mount",
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
            hive_loader=loader,
            hives=hives,
        )

        self.assertIn("Alice", report)
        self.assertIn("OneDrive", report)
        self.assertIn("C:\\OneDrive.exe", report)
        self.assertEqual(loader.query_values.call_count, 2)


def find_windows_hives_from_paths(user_hives, software_hive=None):
    from src.windows_registry import RegistryHives, UserHive

    return RegistryHives(
        software_hive=software_hive,
        user_hives=[UserHive(username=name, path=path) for name, path in user_hives],
    )


def build_synthetic_hive():
    data = bytearray(8192)
    data[0:4] = b"regf"
    struct.pack_into("<I", data, 0x24, 0x20)
    data[4096:4100] = b"hbin"

    def put_cell(rel_offset, payload):
        size = 4 + len(payload)
        if size % 8:
            size += 8 - (size % 8)
        abs_offset = 4096 + rel_offset
        struct.pack_into("<i", data, abs_offset, -size)
        data[abs_offset + 4:abs_offset + 4 + len(payload)] = payload

    def nk(name, subkey_count=0, subkey_list=0xFFFFFFFF, value_count=0, value_list=0xFFFFFFFF):
        name_bytes = name.encode("ascii")
        payload = bytearray(76 + len(name_bytes))
        payload[0:2] = b"nk"
        struct.pack_into("<H", payload, 2, 0x20)
        struct.pack_into("<I", payload, 20, subkey_count)
        struct.pack_into("<I", payload, 28, subkey_list)
        struct.pack_into("<I", payload, 36, value_count)
        struct.pack_into("<I", payload, 40, value_list)
        struct.pack_into("<H", payload, 72, len(name_bytes))
        payload[76:76 + len(name_bytes)] = name_bytes
        return payload

    def lf(entries):
        payload = bytearray(4 + len(entries) * 8)
        payload[0:2] = b"lf"
        struct.pack_into("<H", payload, 2, len(entries))
        for index, (offset, name) in enumerate(entries):
            struct.pack_into("<I", payload, 4 + index * 8, offset)
            payload[8 + index * 8:12 + index * 8] = name.encode("ascii")[:4].ljust(4, b"\0")
        return payload

    def value_list(offsets):
        payload = bytearray(len(offsets) * 4)
        for index, offset in enumerate(offsets):
            struct.pack_into("<I", payload, index * 4, offset)
        return payload

    def vk(name, value, data_offset):
        name_bytes = name.encode("ascii")
        value_bytes = value.encode("utf-16le") + b"\0\0"
        payload = bytearray(20 + len(name_bytes))
        payload[0:2] = b"vk"
        struct.pack_into("<H", payload, 2, len(name_bytes))
        struct.pack_into("<I", payload, 4, len(value_bytes))
        struct.pack_into("<I", payload, 8, data_offset)
        struct.pack_into("<I", payload, 12, 1)
        struct.pack_into("<H", payload, 16, 1)
        payload[20:20 + len(name_bytes)] = name_bytes
        return payload

    value_bytes = "Example.App".encode("utf-16le") + b"\0\0"
    put_cell(0x20, nk("ROOT", subkey_count=1, subkey_list=0x320))
    put_cell(0x120, nk("Software", subkey_count=1, subkey_list=0x360))
    put_cell(0x220, nk("Test", value_count=1, value_list=0x3A0))
    put_cell(0x320, lf([(0x120, "Software")]))
    put_cell(0x360, lf([(0x220, "Test")]))
    put_cell(0x3A0, value_list([0x3D0]))
    put_cell(0x3D0, vk("ProgId", "Example.App", 0x420))
    put_cell(0x420, value_bytes)
    return bytes(data)


if __name__ == "__main__":
    unittest.main()
