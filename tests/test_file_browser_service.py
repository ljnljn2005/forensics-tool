import os
import shutil
import tempfile
import unittest

from backend.app.services.file_browser import inspect_mapped_path


class FileBrowserServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="file-browser-test-")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detects_sqlite_from_header_without_extension(self):
        path = os.path.join(self.temp_dir, "mystery")
        with open(path, "wb") as handle:
            handle.write(b"SQLite format 3\x00" + b"\x00" * 48)

        result = inspect_mapped_path(self.temp_dir, "mystery")

        self.assertEqual(result["detected_kind"], "database")
        self.assertEqual(result["preferred_extension"], ".db")

    def test_detects_png_from_header_without_extension(self):
        path = os.path.join(self.temp_dir, "image_blob")
        with open(path, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)

        result = inspect_mapped_path(self.temp_dir, "image_blob")

        self.assertEqual(result["detected_kind"], "image")
        self.assertEqual(result["preferred_extension"], ".png")

    def test_detects_mp4_and_mp3_children_in_directory_listing(self):
        video_path = os.path.join(self.temp_dir, "video_no_ext")
        audio_path = os.path.join(self.temp_dir, "audio_no_ext")
        with open(video_path, "wb") as handle:
            handle.write(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32)
        with open(audio_path, "wb") as handle:
            handle.write(b"ID3" + b"\x00" * 61)

        result = inspect_mapped_path(self.temp_dir, self.temp_dir)
        by_name = {item["name"]: item for item in result["children"]}

        self.assertEqual(by_name["video_no_ext"]["detected_kind"], "video")
        self.assertEqual(by_name["audio_no_ext"]["detected_kind"], "audio")


if __name__ == "__main__":
    unittest.main()
