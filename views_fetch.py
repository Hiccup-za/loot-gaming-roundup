"""Databuddy pageview snapshots for edition publish windows (stdlib only)."""
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
    "View tracking began on 22 October 2026 at about 15:00 SAST. "
    "Views before that time in this window are not measured."
)
TRACKING_NOTE_BEFORE = (
    "View tracking began on 22 October 2026 at about 15:00 SAST. "
    "This edition's measurement window ended before tracking was live."
)

VIEWS_PATHS_TOOLTIP = (
    "Page views for this edition's publish window "
    "(/YYYY-MM-DD.html, clean URL, and / while this edition was the home page)."
)


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


def dates_inclusive(start: date, end: date) -> list[date]:
    if start > end:
        return []
    out: list[date] = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


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


def row_pageviews(row: dict) -> int:
    for key in ("pageviews", "page_views", "views", "count", "value"):
        if key in row:
            try:
                return int(row[key]) or 0
            except (TypeError, ValueError):
                return 0
    return 0


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


def query_path_pageviews(
    api_key: str,
    path: str,
    start: datetime,
    end: datetime,
    granularity: str,
) -> dict[datetime, int]:
    qs = urllib.parse.urlencode({"website_id": WEBSITE_ID, "timezone": "Africa/Johannesburg"})
    url = f"https://api.databuddy.cc/v1/query?{qs}"
    body = json.dumps(
        {
            "parameters": ["events_by_date"],
            "startDate": start.date().isoformat(),
            "endDate": end.date().isoformat(),
            "granularity": granularity,
            "filters": [{"field": "path", "op": "eq", "value": path}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "x-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Databuddy HTTP {e.code}: {detail}") from e
    rows = extract_rows(payload)
    by_bucket: dict[datetime, int] = {}
    for row in rows:
        ts = parse_bucket_datetime(row)
        if ts is None:
            continue
        ts = ts.astimezone(TZ)
        by_bucket[ts] = by_bucket.get(ts, 0) + row_pageviews(row)
    if os.environ.get("VIEWS_FETCH_DEBUG"):
        total = sum(by_bucket.values())
        print(
            f"views_fetch: path={path!r} {granularity} rows={len(rows)} buckets={len(by_bucket)} pv={total}",
            file=sys.stderr,
        )
    return by_bucket


def merge_path_maps(*maps: dict[datetime, int]) -> dict[datetime, int]:
    out: dict[datetime, int] = {}
    for m in maps:
        for ts, n in m.items():
            out[ts] = out.get(ts, 0) + n
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


def aggregate_daily_from_hourly(hourly: dict[datetime, int]) -> dict[date, int]:
    daily: dict[date, int] = {}
    for ts, n in hourly.items():
        daily[ts.date()] = daily.get(ts.date(), 0) + n
    return daily


def fetch_window_pageviews(
    api_key: str,
    paths: list[str],
    start: datetime,
    end: datetime,
) -> tuple[dict[date, int], str]:
    """Query paths; prefer hourly inside 30d windows, fall back to daily if hourly is empty."""
    granularity = choose_granularity(start, end)
    merged = filter_buckets(
        merge_path_maps(
            *(query_path_pageviews(api_key, p, start, end, granularity) for p in paths)
        ),
        start,
        end,
        granularity,
    )
    if granularity == "hourly" and sum(merged.values()) == 0:
        granularity = "daily"
        merged = filter_buckets(
            merge_path_maps(
                *(query_path_pageviews(api_key, p, start, end, granularity) for p in paths)
            ),
            start,
            end,
            granularity,
        )
    if granularity == "hourly":
        daily_pv = aggregate_daily_from_hourly(merged)
    else:
        daily_pv = {ts.date(): n for ts, n in merged.items()}
    return daily_pv, granularity


def edition_view_paths(edition_date: str) -> list[str]:
    return [f"/{edition_date}.html", f"/{edition_date}", "/"]


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
            "total_views": 0,
            "series": [],
            "tracking_note": TRACKING_NOTE_BEFORE,
        }

    effective_start = max(window_start, TRACKING_START)
    tracking_note = TRACKING_NOTE_PARTIAL if window_start < TRACKING_START else None

    if effective_start >= window_end:
        return {**base, "total_views": 0, "series": [], "tracking_note": tracking_note}

    paths = edition_view_paths(edition_date)
    daily_pv, granularity = fetch_window_pageviews(
        api_key, paths, effective_start, window_end
    )
    total_views = sum(daily_pv.values())

    if os.environ.get("VIEWS_FETCH_DEBUG"):
        print(
            f"views_fetch: edition={edition_date} granularity={granularity} total={total_views}",
            file=sys.stderr,
        )

    series: list[dict] = []
    for day in dates_inclusive(window_start.date(), (window_end - timedelta(seconds=1)).date()):
        iso = day.isoformat()
        if day < TRACKING_START.date():
            series.append({"date": iso, "pageviews": None, "tracked": False})
        elif day == TRACKING_START.date() and window_start < TRACKING_START:
            pv = daily_pv.get(day, 0)
            series.append({"date": iso, "pageviews": pv, "tracked": True})
        else:
            pv = daily_pv.get(day, 0)
            series.append({"date": iso, "pageviews": pv, "tracked": True})

    snap = {**base, "total_views": total_views, "series": series}
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
