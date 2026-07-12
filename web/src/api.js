// Same-origin API client. Postgres (via FastAPI) is the source of truth;
// localStorage is only a fallback so the tracker survives a flaky connection:
//  - reads cache their last good response and serve it when offline
//  - writes go through an ordered queue that replays when the network is back,
//    so a tap on the phone is never lost. All write endpoints are idempotent
//    (ON CONFLICT upserts), so replays are safe.
//
// AUTH: every request carries X-Api-Token (from the pairing screen; minted by
// `python -m app.create_user`). A 401 throws AuthError — never served from
// cache — so the app can show the pairing screen instead of stale data.

const QUEUE_KEY = "vtaper-write-queue-v1";
const CACHE_KEY = "vtaper-api-cache-v1";
const TOKEN_KEY = "vtaper-api-token-v1";

export class AuthError extends Error {}

export const getToken = () => localStorage.getItem(TOKEN_KEY) || "";

// Pairing as a different person on the same browser must not replay the
// previous user's queued writes or show their cached data — wipe both.
export function setToken(token) {
  if (token !== getToken()) {
    localStorage.removeItem(QUEUE_KEY);
    localStorage.removeItem(CACHE_KEY);
  }
  localStorage.setItem(TOKEN_KEY, token);
}

async function request(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", "X-Api-Token": getToken() },
    ...opts,
  });
  if (res.status === 401) throw new AuthError("invalid token");
  if (!res.ok) throw new Error(`${opts.method || "GET"} ${path} → ${res.status}`);
  return res.json();
}

function readStore(key) {
  try {
    return JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    return {};
  }
}

async function cachedGet(path, cacheField) {
  const cache = readStore(CACHE_KEY);
  try {
    const data = await request(path);
    cache[cacheField] = data;
    // per-day entries would grow forever — keep only the 7 most recent
    Object.keys(cache).filter((k) => k.startsWith("day:")).sort().slice(0, -7)
      .forEach((k) => delete cache[k]);
    localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
    return { data, fromCache: false };
  } catch (e) {
    if (e instanceof AuthError) throw e;
    if (cacheField in cache) return { data: cache[cacheField], fromCache: true };
    throw e;
  }
}

function loadQueue() {
  const q = readStore(QUEUE_KEY);
  return Array.isArray(q) ? q : [];
}

// Drains the queue in order; stops at the first failure to preserve write order.
// Returns how many writes are still pending (0 = fully synced).
async function drainOnce() {
  let q = loadQueue();
  while (q.length) {
    const { method, path, body } = q[0];
    try {
      await request(path, { method, body: JSON.stringify(body) });
    } catch {
      break; // network or auth — either way, keep the queue and retry later
    }
    q = q.slice(1);
    localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
  }
  return q.length;
}

// All drains are chained on one promise so two callers (a tap + the retry
// timer) can never interleave queue reads/writes.
let draining = Promise.resolve(0);
export function flushQueue() {
  draining = draining.catch(() => 0).then(drainOnce);
  return draining;
}

// Every write is appended to the queue first, then the queue is drained —
// strict ordering even when older writes are still pending.
async function write(method, path, body) {
  const q = loadQueue();
  q.push({ method, path, body });
  localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
  return (await flushQueue()) === 0;
}

export const api = {
  activePlan: () => cachedGet("/plan/active", "plan"),
  day: (date) => cachedGet(`/log/day/${date}`, `day:${date}`),
  history: (days = 21) => cachedGet(`/log/history?days=${days}`, "history"),
  chat: () => cachedGet("/log/chat?limit=30", "chat"),
  planHistory: () => cachedGet("/plan/history", "planHistory"),
  logMeal: (m) => write("POST", "/log/meals", m),
  logWeight: (w) => write("PUT", "/log/weight", w),
  postComment: (c) => write("POST", "/log/comment", c),
  pendingWrites: () => loadQueue().length,
};
