"""Behaviour tests for production verification (mocked HTTP)."""
import json
import unittest
from unittest.mock import patch

from publish.verify_production import VerifyStatus, verify_production

SITE = "https://example.test"
EDITION = "2099-06-01"
LABEL = "Sunday 1 June 2099"
PNG_HASH = "ab" * 32


def _html(label: str) -> bytes:
    return f'<motion><div class="date">{label}</div></motion>'.encode()


def _json_body() -> bytes:
    return json.dumps(
        {
            "date": EDITION,
            "date_label": LABEL,
            "x_post": {"image": f"/x/{EDITION}.png"},
        }
    ).encode()


class VerifyProductionBehaviorTests(unittest.TestCase):
    def _png_bytes(self) -> bytes:
        return b"\x89PNGmock"

    @patch("publish.verify_production.fetch")
    def test_ok_when_home_edition_json_and_png_match(self, mock_fetch):
        png = self._png_bytes()
        import hashlib

        good_hash = hashlib.sha256(png).hexdigest()

        def side_effect(url, timeout):
            if url.endswith(".json"):
                return 200, _json_body(), "application/json"
            if url.endswith(".png"):
                return 200, png, "image/png"
            if url.endswith("/"):
                return 200, _html(LABEL), "text/html"
            if EDITION in url:
                return 200, _html(LABEL), "text/html"
            raise AssertionError(url)

        mock_fetch.side_effect = side_effect
        result = verify_production(
            EDITION,
            LABEL,
            good_hash,
            site_url=SITE,
            retries=1,
            retry_delay=0,
        )
        self.assertEqual(result.status, VerifyStatus.OK)

    @patch("publish.verify_production.fetch")
    def test_stale_homepage_is_pending_deploy(self, mock_fetch):
        png = self._png_bytes()
        import hashlib

        good_hash = hashlib.sha256(png).hexdigest()

        def side_effect(url, timeout):
            if url.endswith(".json"):
                return 200, _json_body(), "application/json"
            if url.endswith(".png"):
                return 200, png, "image/png"
            if url.endswith("/"):
                return 200, _html("Old homepage"), "text/html"
            return 200, _html(LABEL), "text/html"

        mock_fetch.side_effect = side_effect
        result = verify_production(
            EDITION,
            LABEL,
            good_hash,
            site_url=SITE,
            retries=2,
            retry_delay=0,
        )
        self.assertEqual(result.status, VerifyStatus.PENDING_DEPLOY)

    @patch("publish.verify_production.fetch")
    def test_absent_edition_page_pending(self, mock_fetch):
        import urllib.error

        png = self._png_bytes()
        import hashlib

        good_hash = hashlib.sha256(png).hexdigest()

        def side_effect(url, timeout):
            if url.endswith(".json"):
                return 200, _json_body(), "application/json"
            if url.endswith(".png"):
                return 200, png, "image/png"
            if url.endswith("/"):
                return 200, _html(LABEL), "text/html"
            raise urllib.error.HTTPError(url, 404, "missing", None, None)

        mock_fetch.side_effect = side_effect
        result = verify_production(
            EDITION,
            LABEL,
            good_hash,
            site_url=SITE,
            retries=2,
            retry_delay=0,
        )
        self.assertEqual(result.status, VerifyStatus.PENDING_DEPLOY)

    @patch("publish.verify_production.fetch")
    def test_image_hash_mismatch_is_content_error(self, mock_fetch):
        png = self._png_bytes()

        def side_effect(url, timeout):
            if url.endswith(".json"):
                return 200, _json_body(), "application/json"
            if url.endswith(".png"):
                return 200, png, "image/png"
            return 200, _html(LABEL), "text/html"

        mock_fetch.side_effect = side_effect
        result = verify_production(
            EDITION,
            LABEL,
            "00" * 32,
            site_url=SITE,
            retries=1,
            retry_delay=0,
        )
        self.assertEqual(result.status, VerifyStatus.CONTENT_ERROR)

    @patch("publish.verify_production.fetch")
    def test_delayed_deploy_retries_then_pending(self, mock_fetch):
        import hashlib

        png = self._png_bytes()
        good_hash = hashlib.sha256(png).hexdigest()

        def side_effect(url, timeout):
            if url.endswith(".json"):
                return 200, _json_body(), "application/json"
            if url.endswith(".png"):
                return 200, png, "image/png"
            if url.endswith("/"):
                return 200, _html("Stale homepage"), "text/html"
            return 200, _html(LABEL), "text/html"

        mock_fetch.side_effect = side_effect
        result = verify_production(
            EDITION,
            LABEL,
            good_hash,
            site_url=SITE,
            retries=2,
            retry_delay=0,
        )
        self.assertEqual(result.status, VerifyStatus.PENDING_DEPLOY)


if __name__ == "__main__":
    unittest.main()
