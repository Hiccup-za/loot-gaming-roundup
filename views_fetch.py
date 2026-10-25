"""Databuddy unique-visitor snapshots for edition publish windows (stdlib only).

Series come from ``events_by_date`` (``visitors`` per bucket). The edition total
is ``summary_metrics`` ``unique_visitors`` for each dated path, and the higher
of those two figures. Hourly or daily ``visitors`` are not added up: the same
person in two buckets is counted twice (a checked example summed to 29 against
a true unique of 19). ``/`` is not included. Unique visitors on the home page
overlap the dated URLs and there is no union query.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

WEBSITE_ID = "d2f227a9-4c59-4917-b672-37f4eb3d81f9"
TZ = ZoneInfo("Africa/Johannesburg")
TRACKING_START = datetime(2026, 10, 22, 15, 0, 0, tzinfo=TZ)
DEFAULT_PUBLISH_TIME = (8, 0)  # 08:00 Africa/Johannesburg when published_at omitted

TRACKING_NOTE_PARTIAL = (
    "Visitor tracking began on 22 October 2026 at about 15:00 SAST. "
    "Visitors before that time in this window are not measured."
)
TRACKING_NOTE_BEFORE = (
    "Visitor tracking began on 22 October 2026 at about 15:00 SAST. "
    "This edition's measurement window ended before tracking was live."
)

VISITORS_PATHS_TOOLTIP = (
    "Unique visitors for this edition's publish window "
    "(/YYYY-MM-DD.html and /YYYY-MM-DD). "
    "The line shows when they arrived. "
    "Reloading the page does not increase the total. "
    "Home-page (/) visits are not added, because unique visitors cannot be combined across paths."
)
# Older name kept so callers written against the page-view tooltip still resolve.
VIEWS_PATHS_TOOLTIP = VISITORS_PATHS_TOOLTIP


def now_jhb() -> datetime:
    return datetime.now(TZ)


def parse_iso_datetime(raw: str) -> datetime:
    s = raw.strip()
    if s.endswith("Z"):
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def infer_published_at(data: dict) -> datetime:
    if data.get("published_at"):
        return parse_iso_datetime(data["published_at"])
    y, m, d = (int(x) for x in data["date"].split("-"))
    hour, minute = DEFAULT_PUBLISH_TIME
    return datetime(y, m, d, hour, minute, 0, tzinfo=TZ)


def add_days(iso: str, days: int) -> str:
    d = date.fromisoformat(iso)
    return (d + timedelta(days=days)).isoformat()


def query_date_bounds(start: datetime, end: datetime) -> tuple[str, str]:
    """Inclusive calendar dates overlapping ``[start, end)``.

    Databuddy ``summary_metrics`` and ``events_by_date`` take calendar dates,
    not hours. The end date is the last instant inside the window, so an
    exclusive midnight boundary does not pull in the next day. A window that
    ends at 08:00 still includes that calendar day, and the unique total can
    therefore include later the same day on that dated URL. The series is
    clipped to the hour window afterwards. The total is never the sum of the
    series.
    """
    start_d = start.astimezone(TZ).date()
    last = end.astimezone(TZ) - timedelta(microseconds=1)
    end_d = last.date()
    if end_d < start_d:
        end_d = start_d
    return start_d.isoformat(), end_d.isoformat()


def _unwrap_parameter_blocks(items: list) -> list:
    """Flatten Databuddy batch items like {parameter, data: [...]}."""
    if not items:
        return []
    if not isinstance(items[0], dict):
        return items
    if "parameter" not in items[0] and "data" not in items[0]:
        return items
    rows: list = []
    for block in items:
        if not isinstance(block, dict):
            continue
        inner = block.get("data")
        if isinstance(inner, list):
            rows.extend(inner)
        elif isinstance(block.get("rows"), list):
            rows.extend(block["rows"])
    return rows if rows else items


def extract_rows(payload) -> list:
    if payload is None:
        return []
    if isinstance(payload, list):
        return _unwrap_parameter_blocks(payload)
    if not isinstance(payload, dict):
        return []
    for key in ("rows", "data"):
        val = payload.get(key)
        if isinstance(val, list):
            return _unwrap_parameter_blocks(val)
        if isinstance(val, dict):
            for sub in val.values():
                if isinstance(sub, list):
                    return _unwrap_parameter_blocks(sub)
    for val in payload.values():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return _unwrap_parameter_blocks(val)
    return []


def _coerce_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def row_visitors(row: dict) -> int:
    """Visitors in one ``events_by_date`` bucket. Never pageviews."""
    for key in ("visitors", "unique_visitors"):
        if key in row and row[key] is not None:
            return _coerce_int(row[key]) or 0
    return 0


def summary_unique_visitors(payload) -> int | None:
    """``summary_metrics`` → ``data[0].unique_visitors``, or None if absent."""
    rows = [r for r in extract_rows(payload) if isinstance(r, dict)]
    if rows and "unique_visitors" in rows[0]:
        return _coerce_int(rows[0].get("unique_visitors")) or 0
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        row = data[0]
        if "unique_visitors" in row:
            return _coerce_int(row.get("unique_visitors")) or 0
        inner = row.get("data")
        if (
            isinstance(inner, list)
            and inner
            and isinstance(inner[0], dict)
            and "unique_visitors" in inner[0]
        ):
            return _coerce_int(inner[0].get("unique_visitors")) or 0
    return None


def top_pages_visitors(payload, path: str) -> int | None:
    """``top_pages`` → ``visitors`` for ``path``, else the first row."""
    rows = [r for r in extract_rows(payload) if isinstance(r, dict)]
    first = None
    for row in rows:
        if "visitors" in row and row["visitors"] is not None:
            n = _coerce_int(row.get("visitors")) or 0
        elif "unique_visitors" in row and row["unique_visitors"] is not None:
            n = _coerce_int(row.get("unique_visitors")) or 0
        else:
            continue
        if first is None:
            first = n
        row_path = row.get("path") or row.get("name") or row.get("page")
        if row_path == path:
            return n
    return first


def parse_bucket_datetime(row: dict) -> datetime | None:
    for key in ("timestamp", "period", "bucket", "hour", "datetime", "date"):
        raw = row.get(key)
        if not raw:
            continue
        s = str(raw)
        try:
            if "T" in s or "+" in s or s.endswith("Z"):
                return parse_iso_datetime(s)
            if len(s) >= 13 and s[10] == " ":
                return parse_iso_datetime(s.replace(" ", "T") + "+02:00")
            if len(s) == 10:
                return datetime.fromisoformat(s).replace(tzinfo=TZ)
            return parse_iso_datetime(s)
        except ValueError:
            continue
    return None


def post_query(api_key: str, body: dict):
    qs = urllib.parse.urlencode({"website_id": WEBSITE_ID, "timezone": "Africa/Johannesburg"})
    url = f"https://api.databuddy.cc/v1/query?{qs}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "x-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Databuddy HTTP {e.code}: {detail}") from e


def query_path_visitors(
    api_key: str,
    path: str,
    start: datetime,
    end: datetime,
    granularity: str,
) -> dict[datetime, int]:
    start_s, end_s = query_date_bounds(start, end)
    payload = post_query(
        api_key,
        {
            "parameters": ["events_by_date"],
            "startDate": start_s,
            "endDate": end_s,
            "granularity": granularity,
            "limit": 10000,
            "filters": [{"field": "path", "op": "eq", "value": path}],
        },
    )
    rows = extract_rows(payload)
    by_bucket: dict[datetime, int] = {}
    for row in rows:
        ts = parse_bucket_datetime(row)
        if ts is None:
            continue
        ts = ts.astimezone(TZ)
        # Same bucket on one path: keep the higher visitors figure, do not add.
        n = row_visitors(row)
        prev = by_bucket.get(ts)
        by_bucket[ts] = n if prev is None else max(prev, n)
    if os.environ.get("VIEWS_FETCH_DEBUG"):
        total = sum(by_bucket.values())
        print(
            f"views_fetch: path={path!r} {granularity} rows={len(rows)} "
            f"buckets={len(by_bucket)} visitors={total}",
            file=sys.stderr,
        )
    return by_bucket


def query_path_unique_visitors(
    api_key: str,
    path: str,
    start: datetime,
    end: datetime,
) -> int:
    """True uniques for ``path`` over the calendar dates overlapping the window."""
    start_s, end_s = query_date_bounds(start, end)
    summary = post_query(
        api_key,
        {
            "parameters": ["summary_metrics"],
            "startDate": start_s,
            "endDate": end_s,
            "filters": [{"field": "path", "op": "eq", "value": path}],
        },
    )
    unique = summary_unique_visitors(summary)
    if unique is not None:
        return unique
    pages = post_query(
        api_key,
        {
            "parameters": ["top_pages"],
            "startDate": start_s,
            "endDate": end_s,
            "limit": 5,
            "filters": [{"field": "path", "op": "eq", "value": path}],
        },
    )
    n = top_pages_visitors(pages, path)
    return 0 if n is None else n


def merge_visitor_maps(*maps: dict[datetime, int]) -> dict[datetime, int]:
    """Per bucket, the higher visitors count. Do not add paths together."""
    out: dict[datetime, int] = {}
    for m in maps:
        for ts, n in m.items():
            prev = out.get(ts)
            out[ts] = n if prev is None else max(prev, n)
    return out


def filter_buckets(
    buckets: dict[datetime, int], start: datetime, end: datetime, granularity: str
) -> dict[datetime, int]:
    out: dict[datetime, int] = {}
    for ts, n in buckets.items():
        if granularity == "hourly":
            if start <= ts < end:
                out[ts] = n
        else:
            day_start = datetime.combine(ts.date(), datetime.min.time(), tzinfo=TZ)
            day_end = day_start + timedelta(days=1)
            if day_end <= start or day_start >= end:
                continue
            out[ts] = n
    return out


def choose_granularity(start: datetime, end: datetime) -> str:
    if end - start <= timedelta(days=30):
        return "hourly"
    return "daily"


def floor_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def iter_bucket_starts(start: datetime, end: datetime, granularity: str) -> list[datetime]:
    """Bucket starts covering [start, end) in Africa/Johannesburg."""
    if granularity == "hourly":
        out: list[datetime] = []
        cur = floor_hour(start)
        while cur < end:
            out.append(cur)
            cur += timedelta(hours=1)
        return out
    out = []
    cur = start.date()
    last = (end - timedelta(seconds=1)).date()
    while cur <= last:
        out.append(datetime.combine(cur, datetime.min.time(), tzinfo=TZ))
        cur += timedelta(days=1)
    return out


def align_hourly_buckets(
    buckets: dict[datetime, int], start: datetime, end: datetime
) -> dict[datetime, int]:
    """Use on-grid hours. If every hit is an hour early, shift the map once.

    A missing hour must stay zero. Looking back one hour per bucket copies the
    previous hour into the gap (a reload-free visitor in hour N would also
    appear in hour N+1).
    """
    starts = iter_bucket_starts(start, end, "hourly")
    exact = sum(1 for b in starts if b in buckets)
    shifted = sum(
        1 for b in starts if b not in buckets and (b - timedelta(hours=1)) in buckets
    )
    if exact >= shifted:
        return buckets
    return {ts + timedelta(hours=1): n for ts, n in buckets.items()}


def bucket_visitors(
    buckets: dict[datetime, int], bucket_start: datetime, granularity: str
) -> int:
    """Look up visitors for a bucket start. Hourly keys are already aligned."""
    if granularity == "hourly":
        return buckets.get(bucket_start, 0)
    day = bucket_start.date()
    best = 0
    found = False
    for ts, n in buckets.items():
        if ts.date() == day:
            found = True
            best = max(best, n)
    return best if found else 0


def fetch_window_visitors(
    api_key: str,
    paths: list[str],
    start: datetime,
    end: datetime,
) -> tuple[dict[datetime, int], str]:
    """Query dated paths. Prefer hourly inside 30-day windows; fall back to daily if empty."""
    granularity = choose_granularity(start, end)
    merged = filter_buckets(
        merge_visitor_maps(
            *(query_path_visitors(api_key, p, start, end, granularity) for p in paths)
        ),
        start,
        end,
        granularity,
    )
    if granularity == "hourly":
        merged = align_hourly_buckets(merged, start, end)
    if granularity == "hourly" and sum(merged.values()) == 0:
        granularity = "daily"
        merged = filter_buckets(
            merge_visitor_maps(
                *(query_path_visitors(api_key, p, start, end, granularity) for p in paths)
            ),
            start,
            end,
            granularity,
        )
    return merged, granularity


def build_tracked_series(
    bucket_visitors_map: dict[datetime, int],
    window_start: datetime,
    window_end: datetime,
    effective_start: datetime,
    granularity: str,
) -> list[dict]:
    """Non-cumulative visitor buckets for the tracked portion of the window."""
    series: list[dict] = []
    for bucket_start in iter_bucket_starts(effective_start, window_end, granularity):
        n = bucket_visitors(bucket_visitors_map, bucket_start, granularity)
        point: dict = {
            "visitors": n,
            "tracked": True,
        }
        if granularity == "hourly":
            point["timestamp"] = bucket_start.isoformat()
        else:
            point["date"] = bucket_start.date().isoformat()
        series.append(point)
    return series


def edition_view_paths(edition_date: str) -> list[str]:
    """Dated URLs only.

    ``/YYYY-MM-DD.html`` and ``/YYYY-MM-DD``. Home (``/``) is intentionally
    omitted: its unique visitors overlap these paths and cannot be added on.
    """
    return [f"/{edition_date}.html", f"/{edition_date}"]


def choose_primary_total(path_totals: dict[str, int]) -> tuple[str, int]:
    """Higher unique total. On a tie, prefer the ``.html`` path."""
    if not path_totals:
        return "", 0
    primary = max(path_totals, key=lambda p: (path_totals[p], p.endswith(".html")))
    return primary, path_totals[primary]


def build_views_snapshot(
    edition_date: str,
    window_start: datetime,
    window_end: datetime,
    api_key: str,
) -> dict:
    fetched_at = now_jhb()
    base = {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "fetched_at": fetched_at.isoformat(),
    }

    if window_end <= TRACKING_START:
        return {
            **base,
            "total_unique_visitors": 0,
            "series": [],
            "tracking_note": TRACKING_NOTE_BEFORE,
        }

    effective_start = max(window_start, TRACKING_START)
    tracking_note = TRACKING_NOTE_PARTIAL if window_start < TRACKING_START else None

    if effective_start >= window_end:
        snap = {**base, "total_unique_visitors": 0, "series": []}
        if tracking_note:
            snap["tracking_note"] = tracking_note
        return snap

    paths = edition_view_paths(edition_date)
    path_totals = {
        path: query_path_unique_visitors(api_key, path, effective_start, window_end)
        for path in paths
    }
    primary_path, total_unique = choose_primary_total(path_totals)
    bucket_map, granularity = fetch_window_visitors(
        api_key, paths, effective_start, window_end
    )
    series = build_tracked_series(
        bucket_map, window_start, window_end, effective_start, granularity
    )
    # Do not use this sum as the edition total. It double-counts people who
    # appear in more than one hour or day.
    series_sum = sum(int(p.get("visitors") or 0) for p in series)

    if os.environ.get("VIEWS_FETCH_DEBUG"):
        print(
            f"views_fetch: edition={edition_date} granularity={granularity} "
            f"buckets={len(series)} series_sum={series_sum} unique={total_unique} "
            f"primary={primary_path}",
            file=sys.stderr,
        )

    snap = {
        **base,
        "granularity": granularity,
        "total_unique_visitors": total_unique,
        "primary_path": primary_path,
        "series": series,
    }
    if tracking_note:
        snap["tracking_note"] = tracking_note
    return snap


def snapshot_is_locked(data: dict, window_end: datetime, now: datetime | None = None) -> bool:
    now = now or now_jhb()
    snap = data.get("views_snapshot")
    return bool(snap and window_end <= now)


def needs_views_fetch(
    data: dict,
    window_end: datetime,
    *,
    refresh: bool = False,
    backfill: bool = False,
) -> bool:
    if not os.environ.get("DATABUDDY_API_KEY"):
        return False
    if refresh or backfill:
        return True
    now = now_jhb()
    if snapshot_is_locked(data, window_end, now):
        return False
    return True
