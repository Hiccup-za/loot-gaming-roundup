/** Live today-page views API (archive editions use build-time views_snapshot in JSON). */
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

function rowPageviews(row) {
  const n = row.pageviews ?? row.page_views ?? row.views ?? row.count ?? 0;
  return Number(n) || 0;
}

async function queryPathPageviews(apiKey, path, startDate, endDate) {
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
    body: JSON.stringify({
      parameters: ['events_by_date'],
      startDate,
      endDate,
      granularity: 'daily',
      filters: [{ field: 'path', op: 'eq', value: path }],
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Databuddy ${res.status}: ${text.slice(0, 200)}`);
  }
  const payload = await res.json();
  const rows = extractRows(payload);
  /** @type {Map<string, number>} */
  const byDate = new Map();
  for (const row of rows) {
    const d = rowDate(row);
    if (!d) continue;
    const iso = String(d).slice(0, 10);
    byDate.set(iso, (byDate.get(iso) || 0) + rowPageviews(row));
  }
  return byDate;
}

async function buildViewsResponse(editionDate, apiKey) {
  const endDate = todayInTimezone(TIMEZONE);
  const queryStart =
    editionDate > TRACKING_START ? editionDate : TRACKING_START;

  const paths = [`/${editionDate}.html`, `/${editionDate}`, '/'];

  /** @type {Map<string, number>[]} */
  const pathMaps = paths.map(() => new Map());
  if (queryStart <= endDate) {
    const results = await Promise.all(
      paths.map((path) => queryPathPageviews(apiKey, path, queryStart, endDate)),
    );
    results.forEach((m, i) => {
      pathMaps[i] = m;
    });
  }

  const allDays = datesBetween(editionDate, endDate);
  const series = allDays.map((date) => {
    if (date < TRACKING_START) {
      return { date, pageviews: null, tracked: false };
    }
    const pv = pathMaps.reduce((sum, m) => sum + (m.get(date) || 0), 0);
    return { date, pageviews: pv, tracked: true };
  });

  const tracked = series.filter((p) => p.tracked);
  const totalViews = tracked.reduce((s, p) => s + (p.pageviews || 0), 0);
  let launchDayViews = null;
  if (editionDate >= TRACKING_START) {
    const launch = series.find((p) => p.date === editionDate);
    launchDayViews = launch ? launch.pageviews : 0;
  }

  return {
    editionDate,
    trackingStart: TRACKING_START,
    trackingNote:
      editionDate < TRACKING_START
        ? 'View tracking began 22 October 2026. Earlier days on this chart are not measured.'
        : null,
    startDate: editionDate,
    endDate,
    series,
    launchDayViews,
    totalViews,
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
