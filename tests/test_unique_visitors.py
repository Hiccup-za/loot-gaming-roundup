"""Unique visitors: Databuddy totals are not pageview sums, and the UI says so."""
import os
import unittest
from datetime import datetime
from unittest import mock

import build
import views_fetch

TZ = views_fetch.TZ


def _events(rows):
    return {"data": [{"parameter": "events_by_date", "data": rows}]}


class SummaryParsingTests(unittest.TestCase):
    def test_summary_data0_unique_visitors(self):
        payload = {"data": [{"unique_visitors": 19, "pageviews": 40}]}
        self.assertEqual(views_fetch.summary_unique_visitors(payload), 19)

    def test_summary_parameter_block(self):
        payload = {
            "data": [
                {
                    "parameter": "summary_metrics",
                    "data": [{"unique_visitors": 19, "pageviews": 80}],
                }
            ]
        }
        self.assertEqual(views_fetch.summary_unique_visitors(payload), 19)

    def test_summary_missing_field_is_none(self):
        self.assertIsNone(views_fetch.summary_unique_visitors({"data": [{"pageviews": 40}]}))

    def test_top_pages_matches_path(self):
        payload = {
            "data": [
                {"path": "/other", "visitors": 50, "pageviews": 90},
                {"path": "/2026-10-24.html", "visitors": 19, "pageviews": 40},
            ]
        }
        self.assertEqual(views_fetch.top_pages_visitors(payload, "/2026-10-24.html"), 19)

    def test_row_visitors_ignores_pageviews(self):
        self.assertEqual(views_fetch.row_visitors({"pageviews": 100, "visitors": 1}), 1)
        self.assertEqual(views_fetch.row_visitors({"pageviews": 100}), 0)

    def test_dated_paths_exclude_home(self):
        paths = views_fetch.edition_view_paths("2026-10-24")
        self.assertEqual(paths, ["/2026-10-24.html", "/2026-10-24"])
        self.assertNotIn("/", paths)

    def test_primary_total_takes_higher_and_html_on_tie(self):
        self.assertEqual(
            views_fetch.choose_primary_total({"/2026-10-24.html": 11, "/2026-10-24": 19}),
            ("/2026-10-24", 19),
        )
        self.assertEqual(
            views_fetch.choose_primary_total({"/2026-10-24.html": 19, "/2026-10-24": 19}),
            ("/2026-10-24.html", 19),
        )

    def test_sparse_hours_are_not_copied_forward(self):
        start = datetime(2026, 10, 24, 8, 0, tzinfo=TZ)
        end = datetime(2026, 10, 24, 12, 0, tzinfo=TZ)
        buckets = {
            datetime(2026, 10, 24, 8, 0, tzinfo=TZ): 10,
            datetime(2026, 10, 24, 10, 0, tzinfo=TZ): 9,
        }
        aligned = views_fetch.align_hourly_buckets(buckets, start, end)
        self.assertEqual(views_fetch.bucket_visitors(aligned, start, "hourly"), 10)
        nine = datetime(2026, 10, 24, 9, 0, tzinfo=TZ)
        self.assertEqual(views_fetch.bucket_visitors(aligned, nine, "hourly"), 0)

    def test_fully_shifted_hours_move_forward_once(self):
        start = datetime(2026, 10, 24, 8, 0, tzinfo=TZ)
        end = datetime(2026, 10, 24, 10, 0, tzinfo=TZ)
        buckets = {
            datetime(2026, 10, 24, 7, 0, tzinfo=TZ): 10,
            datetime(2026, 10, 24, 8, 0, tzinfo=TZ): 4,
        }
        # 08:00 is already on-grid, so this is not a full shift.
        self.assertEqual(
            views_fetch.align_hourly_buckets(buckets, start, end)[start],
            4,
        )
        early = {
            datetime(2026, 10, 24, 7, 0, tzinfo=TZ): 10,
            datetime(2026, 10, 24, 6, 0, tzinfo=TZ): 4,
        }
        aligned = views_fetch.align_hourly_buckets(early, start, end)
        self.assertEqual(aligned[start], 10)
        self.assertEqual(aligned[datetime(2026, 10, 24, 7, 0, tzinfo=TZ)], 4)

    def test_query_dates_do_not_include_an_exclusive_midnight(self):
        start = datetime(2026, 10, 24, 8, 0, tzinfo=TZ)
        end = datetime(2026, 10, 25, 0, 0, tzinfo=TZ)
        self.assertEqual(views_fetch.query_date_bounds(start, end), ("2026-10-24", "2026-10-24"))
        end_morning = datetime(2026, 10, 25, 8, 0, tzinfo=TZ)
        self.assertEqual(
            views_fetch.query_date_bounds(start, end_morning),
            ("2026-10-24", "2026-10-25"),
        )


class SnapshotFetchTests(unittest.TestCase):
    def test_total_is_summary_unique_not_series_sum(self):
        calls = []

        def fake_post(api_key, body):
            calls.append(body)
            kind = body["parameters"][0]
            path = body["filters"][0]["value"]
            self.assertNotEqual(path, "/")
            if kind == "summary_metrics":
                unique = 19 if path.endswith(".html") else 11
                return {"data": [{"unique_visitors": unique, "pageviews": 80}]}
            if kind == "events_by_date":
                if path.endswith(".html"):
                    rows = [
                        {"timestamp": "2026-10-24T08:00:00+02:00", "visitors": 10, "pageviews": 40},
                        {"timestamp": "2026-10-24T09:00:00+02:00", "visitors": 10, "pageviews": 30},
                        {"timestamp": "2026-10-24T10:00:00+02:00", "visitors": 9, "pageviews": 10},
                    ]
                else:
                    rows = [
                        {"timestamp": "2026-10-24T08:00:00+02:00", "visitors": 4, "pageviews": 20},
                        {"timestamp": "2026-10-24T09:00:00+02:00", "visitors": 8, "pageviews": 15},
                        {"timestamp": "2026-10-24T10:00:00+02:00", "visitors": 3, "pageviews": 5},
                    ]
                return _events(rows)
            raise AssertionError(kind)

        start = datetime(2026, 10, 24, 8, 0, tzinfo=TZ)
        end = datetime(2026, 10, 25, 8, 0, tzinfo=TZ)
        with mock.patch.object(views_fetch, "post_query", fake_post):
            snap = views_fetch.build_views_snapshot("2026-10-24", start, end, "test-key")

        self.assertEqual(snap["total_unique_visitors"], 19)
        self.assertEqual(snap["primary_path"], "/2026-10-24.html")
        self.assertNotIn("total_views", snap)
        series_sum = sum(p["visitors"] for p in snap["series"])
        self.assertEqual(series_sum, 29)
        self.assertNotEqual(snap["total_unique_visitors"], series_sum)
        by_hour = {p["timestamp"]: p["visitors"] for p in snap["series"]}
        self.assertEqual(by_hour["2026-10-24T08:00:00+02:00"], 10)
        self.assertEqual(by_hour["2026-10-24T09:00:00+02:00"], 10)
        self.assertEqual(by_hour["2026-10-24T10:00:00+02:00"], 9)
        paths = {body["filters"][0]["value"] for body in calls}
        self.assertEqual(paths, {"/2026-10-24.html", "/2026-10-24"})
        self.assertTrue(any(body["parameters"] == ["summary_metrics"] for body in calls))
        self.assertTrue(all("pageviews" not in p for p in snap["series"]))

    def test_top_pages_fallback_when_summary_has_no_unique_field(self):
        def fake_post(api_key, body):
            kind = body["parameters"][0]
            path = body["filters"][0]["value"]
            if kind == "summary_metrics":
                return {"data": [{"pageviews": 40}]}
            if kind == "top_pages":
                return {"data": [{"path": path, "visitors": 19, "pageviews": 40}]}
            raise AssertionError(kind)

        start = datetime(2026, 10, 24, 8, 0, tzinfo=TZ)
        end = datetime(2026, 10, 25, 8, 0, tzinfo=TZ)
        with mock.patch.object(views_fetch, "post_query", fake_post):
            n = views_fetch.query_path_unique_visitors("k", "/2026-10-24.html", start, end)
        self.assertEqual(n, 19)

    def test_before_tracking_does_not_call_the_api(self):
        start = datetime(2026, 10, 11, 8, 0, tzinfo=TZ)
        end = datetime(2026, 10, 12, 8, 0, tzinfo=TZ)
        with mock.patch.object(views_fetch, "post_query", side_effect=AssertionError("called")):
            snap = views_fetch.build_views_snapshot("2026-10-11", start, end, "k")
        self.assertEqual(snap["total_unique_visitors"], 0)
        self.assertEqual(snap["series"], [])
        self.assertIn("ended before tracking was live", snap["tracking_note"])
        self.assertIn("Visitor tracking", snap["tracking_note"])

    def test_refresh_and_backfill_bypass_the_lock(self):
        data = {"views_snapshot": {"total_views": 1}}
        end = datetime(2026, 10, 12, 8, 0, tzinfo=TZ)
        with mock.patch.dict(os.environ, {"DATABUDDY_API_KEY": "x"}, clear=False):
            self.assertFalse(views_fetch.needs_views_fetch(data, end))
            self.assertTrue(views_fetch.needs_views_fetch(data, end, refresh=True))
            self.assertTrue(views_fetch.needs_views_fetch(data, end, backfill=True))
        env = os.environ.copy()
        env.pop("DATABUDDY_API_KEY", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(views_fetch.needs_views_fetch(data, end, refresh=True))


class UiReadTests(unittest.TestCase):
    def test_sparkline_uses_unique_total_not_series_sum(self):
        data = {
            "date": "2026-10-24",
            "views_snapshot": {
                "total_unique_visitors": 19,
                "series": [
                    {"timestamp": "2026-10-24T08:00:00+02:00", "visitors": 10, "tracked": True},
                    {"timestamp": "2026-10-24T09:00:00+02:00", "visitors": 19, "tracked": True},
                ],
            },
        }
        html = build.views_sparkline(data)
        self.assertIn('<span class="views-num">19</span>', html)
        self.assertIn("unique visitors", html)
        self.assertNotIn('<span class="views-num">29</span>', html)
        self.assertNotIn("total views", html)
        self.assertNotIn("page views", html)
        self.assertIn("Reloading the page does not increase the total", html)

    def test_one_visitor_is_singular(self):
        data = {
            "date": "2026-10-24",
            "views_snapshot": {
                "total_unique_visitors": 1,
                "series": [
                    {"timestamp": "2026-10-24T08:00:00+02:00", "visitors": 1, "tracked": True},
                ],
            },
        }
        html = build.views_sparkline(data)
        self.assertIn('<span class="views-word">unique visitor</span>', html)
        self.assertIn('aria-label="1 unique visitor"', html)

    def test_legacy_pageview_snapshot_still_renders(self):
        data = {
            "date": "2026-10-23",
            "views_snapshot": {
                "total_views": 8,
                "series": [
                    {"timestamp": "2026-10-23T15:00:00+02:00", "pageviews": 4, "tracked": True},
                    {"timestamp": "2026-10-23T16:00:00+02:00", "pageviews": 4, "tracked": True},
                ],
            },
        }
        html = build.views_sparkline(data)
        self.assertIn('<span class="views-num">8</span>', html)
        self.assertIn("unique visitors", html)
        self.assertIn("page-view count", html)
        self.assertNotIn("total views", html)

    def test_old_tracking_note_is_rewritten(self):
        data = {
            "date": "2026-10-11",
            "views_snapshot": {
                "total_views": 0,
                "series": [],
                "tracking_note": (
                    "View tracking began on 22 October 2026 at about 15:00 SAST. "
                    "This edition's measurement window ended before tracking was live."
                ),
            },
        }
        html = build.views_sparkline(data)
        self.assertIn("Visitor tracking began", html)
        self.assertNotIn("View tracking began", html)
        self.assertNotIn("page-view count", html)

    def test_archive_copy(self):
        editions = [
            {
                "date": "2026-10-24",
                "date_label": "Saturday 24 October 2026",
                "views_snapshot": {
                    "total_unique_visitors": 19,
                    "series": [
                        {"timestamp": "2026-10-24T08:00:00+02:00", "visitors": 10, "tracked": True},
                        {"timestamp": "2026-10-24T09:00:00+02:00", "visitors": 19, "tracked": True},
                    ],
                },
            },
            {
                "date": "2026-10-11",
                "date_label": "Sunday 11 October 2026",
                "views_snapshot": {
                    "total_views": 0,
                    "series": [],
                    "tracking_note": (
                        "View tracking began on 22 October 2026 at about 15:00 SAST. "
                        "This edition's measurement window ended before tracking was live."
                    ),
                },
            },
        ]
        html = build.render_archive(editions)
        self.assertIn("Unique visitors", html)
        self.assertIn("Visitors per edition", html)
        self.assertIn("Visitors not tracked yet", html)
        self.assertIn(">19<", html)
        self.assertIn("unique visitors", html)
        self.assertNotIn("Total page views", html)
        self.assertNotIn("page views", html.lower())
        self.assertNotIn("Views per edition", html)
        self.assertNotIn("View tracking began", html)


if __name__ == "__main__":
    unittest.main()
