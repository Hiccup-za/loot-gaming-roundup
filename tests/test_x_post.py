"""Optional x_post metadata on edition JSON (LootRoundup X dashboard)."""
import os
import tempfile
import unittest

import build


class XPostValidationTests(unittest.TestCase):
    def test_effective_length_counts_urls_as_23(self):
        url = "https://loot-gaming-roundup.vercel.app/2026-10-28"
        text = f"Read today: {url}"
        raw = len(text)
        self.assertGreater(raw, 23 + 12)
        self.assertEqual(build.x_post_effective_length(text), 12 + 23)

    def test_effective_length_over_limit_warns(self):
        long_text = "x" * 281
        self.assertGreater(build.x_post_effective_length(long_text), 280)

    def test_valid_x_post_no_image_file_warns_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {
                "date": "2026-10-28",
                "x_post": {
                    "template": "games",
                    "data": {"story_titles": ["Example"]},
                    "text": "Short post.",
                    "image": "/x/2026-10-28.png",
                    "time": "08:00",
                },
            }
            warnings = []
            build.validate_x_post(data, tmp, warn=warnings.append)
            self.assertEqual(len(warnings), 1)
            self.assertIn("missing", warnings[0].lower())

    def test_invalid_template_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {
                "date": "2026-10-28",
                "x_post": {
                    "template": "not-a-template",
                    "data": {},
                    "text": "Hi",
                    "image": "/x/2026-10-28.png",
                    "time": "08:00",
                },
            }
            warnings = []
            build.validate_x_post(data, tmp, warn=warnings.append)
            self.assertTrue(any("template" in w for w in warnings))

    def test_edition_without_x_post_is_unchanged(self):
        html = build.render({"date": "2026-10-11", "date_label": "Sunday 11 October 2026"})
        self.assertNotIn("x_post", html)
        self.assertIn("Loot's Gaming Roundup", html)

    def test_fixture_sample_passes_field_checks(self):
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "fixtures", "x_post_sample.json")
        with open(path, encoding="utf-8") as f:
            import json

            data = json.load(f)
        warnings = []
        build.validate_x_post(data, os.path.dirname(here), warn=warnings.append)
        image_warns = [w for w in warnings if "missing" in w.lower()]
        self.assertEqual(image_warns, [])


if __name__ == "__main__":
    unittest.main()
