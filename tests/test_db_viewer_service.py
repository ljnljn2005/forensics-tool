import os
import sqlite3
import tarfile
import tempfile
import unittest

from backend.app.services.db_viewer import inspect_sqlite_database


class DatabaseViewerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="db-viewer-test-")
        self.db_path = os.path.join(self.temp_dir, "sample.db")
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("CREATE TABLE clips (id INTEGER PRIMARY KEY, text TEXT)")
            connection.execute("INSERT INTO clips(text) VALUES (?)", ("first row",))
            connection.execute("INSERT INTO clips(text) VALUES (?)", ("second row",))
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for filename in files:
                os.remove(os.path.join(root, filename))
            for dirname in dirs:
                os.rmdir(os.path.join(root, dirname))
        os.rmdir(self.temp_dir)

    def test_inspect_sqlite_database_from_directory_mapping(self):
        result = inspect_sqlite_database(self.temp_dir, "sample.db")

        self.assertTrue(result["ok"])
        self.assertEqual(result["tables"][0]["name"], "clips")
        self.assertEqual(result["tables"][0]["row_count"], 2)
        self.assertEqual(result["tables"][0]["preview_rows"][0]["text"], "first row")

    def test_inspect_sqlite_database_from_tar_mapping(self):
        archive_path = os.path.join(self.temp_dir, "evidence.tar")
        with tarfile.open(archive_path, "w") as archive:
            archive.add(self.db_path, arcname="data/user/0/com.demo.app/databases/sample.db")

        result = inspect_sqlite_database(archive_path, "/data/user/0/com.demo.app/databases/sample.db")

        self.assertTrue(result["ok"])
        self.assertTrue(result["source_path"].endswith("data/user/0/com.demo.app/databases/sample.db"))
        self.assertEqual(result["tables"][0]["name"], "clips")

    def test_inspect_sqlite_database_without_extension(self):
        extensionless = os.path.join(self.temp_dir, "sample_blob")
        with open(self.db_path, "rb") as src, open(extensionless, "wb") as dst:
            dst.write(src.read())

        result = inspect_sqlite_database(self.temp_dir, "sample_blob")

        self.assertTrue(result["ok"])
        self.assertEqual(result["tables"][0]["name"], "clips")


if __name__ == "__main__":
    unittest.main()
