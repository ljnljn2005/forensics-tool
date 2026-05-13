import os
import shutil
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app


class WebToolboxApiTests(unittest.TestCase):
    def setUp(self):
        self.root = os.path.join(os.getcwd(), "_toolbox_api_test")
        shutil.rmtree(self.root, ignore_errors=True)
        os.makedirs(self.root, exist_ok=True)
        self.images_dir = os.path.join(self.root, "images")
        os.makedirs(self.images_dir, exist_ok=True)
        Image.new("RGB", (120, 80), "red").save(os.path.join(self.images_dir, "a.jpg"))
        Image.new("RGB", (120, 80), "blue").save(os.path.join(self.images_dir, "b.jpg"))
        self.single_image = os.path.join(self.root, "single.png")
        Image.new("RGB", (400, 300), "green").save(self.single_image)
        self.client = TestClient(app)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_jigsaw_catalog_exists(self):
        response = self.client.get("/api/toolbox/jigsaw")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["key"], "jigsaw-puzzle")
        self.assertEqual(len(payload["features"]), 3)

    def test_montage_analysis_returns_layout(self):
        response = self.client.post(
            "/api/toolbox/jigsaw/montage/analyze",
            json={
                "folder_path": self.images_dir,
                "sort_mode": "name_asc",
                "cols": 2,
                "cell_width": 64,
                "cell_height": 64,
                "gap": 4,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["layout"]["cols"], 2)

    def test_square_preview_returns_dimensions(self):
        response = self.client.post(
            "/api/toolbox/jigsaw/square/preview",
            json={
                "image_path": self.single_image,
                "cols": 4,
                "rows": 3,
                "mode": "area",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["original_width"], 400)
        self.assertEqual(payload["cols"], 4)

    def test_puzzle_inspect_returns_piece_suggestions(self):
        response = self.client.post(
            "/api/toolbox/jigsaw/puzzle/inspect",
            json={"image_path": self.single_image},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["width"], 400)
        self.assertIn("valid_piece_sizes", payload)
        self.assertIn("suggestions", payload)
        self.assertTrue(payload["suggestions"])

    def test_puzzle_adapt_crops_to_divisible_size(self):
        response = self.client.post(
            "/api/toolbox/jigsaw/puzzle/adapt",
            json={"image_path": self.single_image, "piece_size": 64},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "crop")
        self.assertEqual(payload["crop"]["adapted_width"], 384)
        self.assertEqual(payload["crop"]["adapted_height"], 256)


if __name__ == "__main__":
    unittest.main()
