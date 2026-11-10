"""Automated publish validation and submit helpers."""
import hashlib
import json
import os
import shutil
import tempfile
import unittest

from publish.validate import (
    EXPECTED_PNG_SIZE,
    PublishValidationError,
    png_dimensions,
    sha256_file,
    validate_edition_bundle,
)


class PublishValidationTests(unittest.TestCase):
    def _edition_png(self, dest: str) -> None:
        root = os.path.dirname(os.path.dirname(__file__))
        for name in ("2026-11-07.png", "2026-11-05.png"):
            src = os.path.join(root, "x", name)
            if os.path.isfile(src):
                shutil.copyfile(src, dest)
                return
        self.skipTest("no 1200×675 sample under x/")

    def test_png_dimensions_repo_sample(self):
        root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(root, "x", "2026-11-07.png")
        if not os.path.isfile(path):
            self.skipTest("x/2026-11-07.png not in checkout")
        self.assertEqual(png_dimensions(path), EXPECTED_PNG_SIZE)

    def test_validate_rejects_missing_x_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            edition = "2099-01-02"
            with open(os.path.join(tmp, f"{edition}.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {"date": edition, "date_label": "Test"},
                    f,
                )
            os.makedirs(os.path.join(tmp, "x"), exist_ok=True)
            self._edition_png(os.path.join(tmp, "x", f"{edition}.png"))
            with self.assertRaises(PublishValidationError):
                validate_edition_bundle(tmp, edition)

    def test_validate_accepts_sample_with_png(self):
        here = os.path.dirname(os.path.dirname(__file__))
        edition = "2099-01-01"
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copyfile(
                os.path.join(here, "tests", "fixtures", "x_post_sample.json"),
                os.path.join(tmp, f"{edition}.json"),
            )
            os.makedirs(os.path.join(tmp, "x"), exist_ok=True)
            self._edition_png(os.path.join(tmp, "x", f"{edition}.png"))
            hashes = validate_edition_bundle(tmp, edition)
            self.assertEqual(len(hashes["json_sha256"]), 64)
            self.assertEqual(hashes["png_sha256"], sha256_file(os.path.join(tmp, "x", f"{edition}.png")))

    def test_date_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            edition = "2099-01-03"
            with open(os.path.join(tmp, f"{edition}.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "date": "2099-01-04",
                        "date_label": "Wrong",
                        "x_post": {
                            "template": "haul",
                            "data": {},
                            "text": "x",
                            "image": "/x/2099-01-04.png",
                            "time": "08:00",
                        },
                    },
                    f,
                )
            os.makedirs(os.path.join(tmp, "x"), exist_ok=True)
            self._edition_png(os.path.join(tmp, "x", f"{edition}.png"))
            with self.assertRaises(PublishValidationError):
                validate_edition_bundle(tmp, edition)


if __name__ == "__main__":
    unittest.main()
