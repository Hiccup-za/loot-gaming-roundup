/** Live today-page visitor API (archive editions use build-time views_snapshot in JSON).

Dated paths only (`/YYYY-MM-DD.html` and `/YYYY-MM-DD`). Series is `visitors`
per day from `events_by_date` (the higher of the two paths, not the sum).
The total is `summary_metrics` `unique_visitors` (or `top_pages` `visitors`),
the higher of the two paths. Home (`/`) is not added: uniques overlap and
cannot be combined. Do not sum the daily series into the total.
*/
const WEBSITE_ID = 'd2f227a9-4c59-4917-b672-37f4eb3d81f9';
const TIMEZONE = 'Africa/Johannesburg';
const TRACKING_START = '2026-10-22';
const CACHE_TTL_MS = 10 * 60 * 1000;

/** @type {Map<string, { expires: number, body: object }>} */
const cache = new Map();

function todayInTimezone(tz) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: tz }).format(new Date());
}

function addDays(isoDate, days) {
  const d = new Date(`${isoDate}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function datesBetween(start, end) {
  if (start > end) return [];
  const out = [];
  for (let cur = start; cur <= end; cur = addDays(cur, 1)) {
    out.push(cur);
  }
  return out;
}

function parseEditionDate(raw) {
  if (!raw || typeof raw !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    return null;
  }
  return raw;
}

function unwrapParameterBlocks(items) {
  if (!items.length) return items;
  const first = items[0];
  if (!first || typeof first !== 'object' || !('parameter' in first)) {
    return items;
  }
  const rows = [];
  for (const block of items) {
    if (!block || typeof block !== 'object') continue;
    if (Array.isArray(block.data)) rows.push(...block.data);
    else if (Array.isArray(block.rows)) rows.push(...block.rows);
  }
  return rows.length ? rows : items;
}

function extractRows(payload) {
  if (!payload || typeof payload !== 'object') return [];
  if (Array.isArray(payload)) return unwrapParameterBlocks(payload);
  if (Array.isArray(payload.rows)) return unwrapParameterBlocks(payload.rows);
  if (Array.isArray(payload.data)) return unwrapParameterBlocks(payload.data);
  if (payload.data && typeof payload.data === 'object') {
    for (const key of Object.keys(payload.data)) {
      const val = payload.data[key];
      if (Array.isArray(val)) return unwrapParameterBlocks(val);
    }
  }
  for (const key of Object.keys(payload)) {
    const val = payload[key];
    if (Array.isArray(val) && val.length && typeof val[0] === 'object') {
      return unwrapParameterBlocks(val);
    }
  }
  return [];
}

function rowDate(row) {
  return row.date || row.day || row.period || row.bucket;
}

function rowVisitors(row) {
  if (row.visitors != null) return Number(row.visitors) || 0;
  if (row.unique_visitors != null) return Number(row.unique_visitors) || 0;
  return 0;
}

async function postQuery(apiKey, body) {
  const qs = new URLSearchParams({
    website_id: WEBSITE_ID,
    timezone: TIMEZONE,
  });
  const res = await fetch(`https://api.databuddy.cc/v1/query?${qs}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Databuddy ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

function summaryUniqueVisitors(payload) {
  const rows = extractRows(payload);
  if (rows[0] && rows[0].unique_visitors != null) {
    return Number(rows[0].unique_visitors) || 0;
  }
  const data = payload && payload.data;
  if (Array.isArray(data) && data[0]) {
    if (data[0].unique_visitors != null) return Number(data[0].unique_visitors) || 0;
    const inner = data[0].data;
    if (Array.isArray(inner) && inner[0] && inner[0].unique_visitors != null) {
      return Number(inner[0].unique_visitors) || 0;
    }
  }
  return null;
}

function topPagesVisitors(payload, path) {
  const rows = extractRows(payload);
  let first = null;
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue;
    let n = null;
    if (row.visitors != null) n = Number(row.visitors) || 0;
    else if (row.unique_visitors != null) n = Number(row.unique_visitors) || 0;
    if (n == null) continue;
    if (first == null) first = n;
    const rowPath = row.path || row.name || row.page;
    if (rowPath === path) return n;
  }
  return first;
}

async function queryPathVisitors(apiKey, path, startDate, endDate) {
  const payload = await postQuery(apiKey, {
    parameters: ['events_by_date'],
    startDate,
    endDate,
    granularity: 'daily',
    limit: 10000,
    filters: [{ field: 'path', op: 'eq', value: path }],
  });
  /** @type {Map<string, number>} */
  const byDate = new Map();
  for (const row of extractRows(payload)) {
    const d = rowDate(row);
    if (!d) continue;
    const iso = String(d).slice(0, 10);
    const n = rowVisitors(row);
    const prev = byDate.get(iso);
    byDate.set(iso, prev == null ? n : Math.max(prev, n));
  }
  return byDate;
}

async function queryPathUniqueVisitors(apiKey, path, startDate, endDate) {
  const summary = await postQuery(apiKey, {
    parameters: ['summary_metrics'],
    startDate,
    endDate,
    filters: [{ field: 'path', op: 'eq', value: path }],
  });
  const unique = summaryUniqueVisitors(summary);
  if (unique != null) return unique;
  const pages = await postQuery(apiKey, {
    parameters: ['top_pages'],
    startDate,
    endDate,
    limit: 5,
    filters: [{ field: 'path', op: 'eq', value: path }],
  });
  const n = topPagesVisitors(pages, path);
  return n == null ? 0 : n;
}

async function buildViewsResponse(editionDate, apiKey) {
  const endDate = todayInTimezone(TIMEZONE);
  const queryStart =
    editionDate > TRACKING_START ? editionDate : TRACKING_START;

  const paths = [`/${editionDate}.html`, `/${editionDate}`];

  /** @type {Map<string, number>[]} */
  const pathMaps = paths.map(() => new Map());
  /** @type {number[]} */
  const pathTotals = paths.map(() => 0);
  if (queryStart <= endDate) {
    const seriesResults = await Promise.all(
      paths.map((path) => queryPathVisitors(apiKey, path, queryStart, endDate)),
    );
    seriesResults.forEach((map, i) => {
      pathMaps[i] = map;
    });
    const totals = await Promise.all(
      paths.map((path) => queryPathUniqueVisitors(apiKey, path, queryStart, endDate)),
    );
    totals.forEach((n, i) => {
      pathTotals[i] = n;
    });
  }

  const allDays = datesBetween(editionDate, endDate);
  const series = allDays.map((date) => {
    if (date < TRACKING_START) {
      return { date, visitors: null, tracked: false };
    }
    const visitors = pathMaps.reduce((best, map) => Math.max(best, map.get(date) || 0), 0);
    return { date, visitors, tracked: true };
  });

  const totalUniqueVisitors = pathTotals.reduce((best, n) => Math.max(best, n), 0);
  let launchDayVisitors = null;
  if (editionDate >= TRACKING_START) {
    const launch = series.find((p) => p.date === editionDate);
    launchDayVisitors = launch ? launch.visitors : 0;
  }

  return {
    editionDate,
    trackingStart: TRACKING_START,
    trackingNote:
      editionDate < TRACKING_START
        ? 'Visitor tracking began 22 October 2026. Earlier days on this chart are not measured.'
        : null,
    startDate: editionDate,
    endDate,
    series,
    launchDayVisitors,
    totalUniqueVisitors,
    unavailable: false,
  };
}

module.exports = async (req, res) => {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'method_not_allowed' });
  }

  const editionDate = parseEditionDate(
    req.query?.date ?? req.query?.Date,
  );
  if (!editionDate) {
    return res.status(400).json({ error: 'invalid_date' });
  }

  const apiKey = process.env.DATABUDDY_API_KEY;
  if (!apiKey) {
    res.setHeader('Cache-Control', 'no-store');
    return res.status(503).json({ unavailable: true, reason: 'not_configured' });
  }

  const cacheKey = `${editionDate}:${todayInTimezone(TIMEZONE)}`;
  const hit = cache.get(cacheKey);
  if (hit && hit.expires > Date.now()) {
    res.setHeader('Cache-Control', 'public, max-age=600, s-maxage=600, stale-while-revalidate=60');
    return res.status(200).json(hit.body);
  }

  try {
    const body = await buildViewsResponse(editionDate, apiKey);
    cache.set(cacheKey, { expires: Date.now() + CACHE_TTL_MS, body });
    res.setHeader('Cache-Control', 'public, max-age=600, s-maxage=600, stale-while-revalidate=60');
    return res.status(200).json(body);
  } catch {
    res.setHeader('Cache-Control', 'no-store');
    return res.status(503).json({ unavailable: true, reason: 'upstream_error' });
  }
};
