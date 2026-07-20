import React, { useEffect, useMemo, useState } from "react";
import { api, flushQueue, AuthError, getToken, setToken } from "./api.js";
import Illo from "./Illo.jsx";
import Chat from "./Chat.jsx";
import {
  PALETTE as C, MEAL_TAGS, THEME_EMOJI, WORKOUTS, WORKOUT_ORDER, WORKOUT_EMOJI,
  todayKey, fmtDate, weekdayKeyOf,
} from "./content.js";

const GUIDE_TABS = [...WORKOUT_ORDER, "rest"];

// Exercise check-offs stay in localStorage: there's no server table for them
// (iPhone Health data is the workout source of truth); meals/weight/comments
// all go to the FastAPI backend.
const EX_KEY = "vtaper-exercises-v1";
const OLD_STORE_KEY = "vtaper-tracker-v1";
const MIGRATED_KEY = "vtaper-migrated-v1";

const readJSON = (key, fallback) => {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
};

const mealTag = (mealId, wdKey) => {
  if (mealId.startsWith("offplan:")) return "Off-plan";
  if (wdKey === "sun" && mealId === "b") return "Brunch";
  return MEAL_TAGS[mealId] || mealId;
};

// One-time import of the old localStorage-only tracker data into the API,
// so history survives the switch. Meal names/macros come from the active plan.
function migrateLegacyData(plan) {
  if (localStorage.getItem(MIGRATED_KEY)) return;
  const old = readJSON(OLD_STORE_KEY, null);
  if (old && old.days) {
    const dates = Object.keys(old.days).sort().slice(-30); // bound the replay
    const exStore = readJSON(EX_KEY, {});
    for (const date of dates) {
      const day = old.days[date];
      const items = plan.meals[weekdayKeyOf(date)]?.items || [];
      for (const item of items) {
        if (day.meals && day.meals[item.id]) {
          api.logMeal({ date, meal_id: item.id, name: item.name,
            kcal: item.kcal, protein_g: item.protein_g, checked: true });
        }
      }
      const w = parseFloat(day.weight);
      if (w >= 40 && w <= 150) api.logWeight({ date, weight_kg: w });
      if (day.exercises) exStore[date] = { ...day.exercises, ...exStore[date] };
    }
    localStorage.setItem(EX_KEY, JSON.stringify(exStore));
  }
  localStorage.setItem(MIGRATED_KEY, "1");
}

// Shown until a valid API token is stored. One token = one person; tokens are
// minted server-side with `python -m app.create_user "<name>"`.
function PairScreen() {
  const [tokenInput, setTokenInput] = useState("");
  const save = () => {
    if (!tokenInput.trim()) return;
    setToken(tokenInput.trim());
    window.location.reload();
  };
  return (
    <div className="vt-root" style={{ display: "grid", placeItems: "center", padding: 24 }}>
      <div style={{ maxWidth: 420, width: "100%" }}>
        <div className="vt-kicker">V-Taper Log</div>
        <h1 className="vt-h1">Pair this device</h1>
        <div className="vt-cue" style={{ marginTop: 10 }}>
          Paste your personal API token. Whoever runs the server creates it with{" "}
          <span className="vt-mono">python -m app.create_user "YourName"</span> — the
          same token also goes in your iPhone Shortcut.
        </div>
        <input className="vt-weightin" style={{ width: "100%", marginTop: 16 }}
          type="password" placeholder="API token" value={tokenInput}
          onChange={(e) => setTokenInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && save()}
          aria-label="API token" />
        <button className="vt-send" style={{ marginTop: 12 }}
          disabled={!tokenInput.trim()} onClick={save}>
          Pair
        </button>
      </div>
    </div>
  );
}

function Gauge({ label, val, target, unit, color }) {
  const pct = Math.min(100, Math.round((val / target) * 100));
  const over = val > target;
  return (
    <div className="vt-gauge">
      <div className="vt-gaugehead">
        <span>{label}</span>
        <span>
          <strong style={{ color: over ? C.red : C.text }}>{val}</strong> / {target} {unit}
        </span>
      </div>
      <div className="vt-bar">
        <div className="vt-fill" style={{ width: pct + "%", background: over ? C.red : color }} />
      </div>
    </div>
  );
}

function WeightChart({ points }) {
  const W = 560, H = 140, pad = 26;
  const ws = points.map((p) => p.w);
  const min = Math.min(...ws) - 0.4, max = Math.max(...ws) + 0.4;
  const x = (i) => pad + (i / Math.max(1, points.length - 1)) * (W - pad * 2);
  const y = (w) => H - pad - ((w - min) / (max - min)) * (H - pad * 2);
  const path = points
    .map((p, i) => (i === 0 ? "M" : "L") + x(i).toFixed(1) + "," + y(p.w).toFixed(1))
    .join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ marginTop: 10 }} role="img"
      aria-label="Weight trend chart">
      <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke={C.line} strokeWidth="1.5" />
      <path d={path} fill="none" stroke={C.saff} strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round" />
      {points.map((p, i) => (
        <g key={p.key}>
          <circle cx={x(i)} cy={y(p.w)} r="3.5" fill={C.ink} stroke={C.saff} strokeWidth="2" />
          {(i === 0 || i === points.length - 1) && (
            <text x={x(i)} y={y(p.w) - 9} textAnchor="middle" fontSize="11"
              fontFamily="'IBM Plex Mono', monospace" fill={C.text}>{p.w}</text>
          )}
        </g>
      ))}
    </svg>
  );
}

// Daily steps, last 14 calendar days. One series → one hue, no legend (the
// card title carries identity); missing days stay honest gaps; labels only on
// the max and latest bars; native <title> tooltips per bar.
function StepsChart({ byDate }) {
  const W = 560, H = 150, pad = 26;
  const days = [];
  const d = new Date();
  for (let i = 13; i >= 0; i--) {
    const dt = new Date(d); dt.setDate(d.getDate() - i);
    const key = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
    days.push({ key, steps: byDate[key] ?? null });
  }
  const max = Math.max(1, ...days.map((p) => p.steps || 0));
  const slot = (W - pad * 2) / 14;
  const bw = Math.floor(slot) - 2; // 2px gap between adjacent bars
  const y = (s) => (H - pad - 14) * (s / max);
  const maxIdx = days.findIndex((p) => p.steps === max);
  const lastIdx = days.map((p) => p.steps != null).lastIndexOf(true);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ marginTop: 10 }} role="img"
      aria-label="Daily steps, last 14 days">
      <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke={C.line} strokeWidth="1.5" />
      {days.map((p, i) => p.steps != null && (
        <g key={p.key}>
          <rect x={pad + i * slot + 1} y={H - pad - y(p.steps)} width={bw}
            height={Math.max(2, y(p.steps))} rx="3" fill={C.saff}>
            <title>{fmtDate(p.key)}: {p.steps.toLocaleString("en-IN")} steps</title>
          </rect>
          {(i === maxIdx || i === lastIdx) && (
            <text x={pad + i * slot + 1 + bw / 2} y={H - pad - y(p.steps) - 6}
              textAnchor="middle" fontSize="10.5"
              fontFamily="'IBM Plex Mono', monospace" fill={C.text}>
              {(p.steps / 1000).toFixed(1)}k
            </text>
          )}
        </g>
      ))}
      <text x={pad} y={H - 8} fontSize="10.5" fontFamily="'IBM Plex Mono', monospace"
        fill={C.mute}>{fmtDate(days[0].key)}</text>
      <text x={W - pad} y={H - 8} textAnchor="end" fontSize="10.5"
        fontFamily="'IBM Plex Mono', monospace" fill={C.mute}>{fmtDate(days[13].key)}</text>
    </svg>
  );
}

// Food items: {dish, restaurant, price, est_kcal, est_protein, reason}.
// Instamart items: {item, brand, pack_size, price, est_kcal, est_protein, reason}.
// Normalized to one shape so both recommendation kinds render through one card.
function normalizeRecItem(it) {
  return {
    name: it.dish || it.item || it.name,
    meta: it.restaurant || [it.brand, it.pack_size].filter(Boolean).join(" · "),
    price: it.price, est_kcal: it.est_kcal, est_protein: it.est_protein, reason: it.reason,
  };
}

function RecommendationCard({ icon, title, rec }) {
  if (!rec || !(rec.items || []).length) return null;
  return (
    <section className="vt-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 6 }}>
        <div className="vt-cardtitle">{icon} {title}</div>
        {rec.remaining_kcal != null && (
          <span className="vt-pill">{rec.remaining_kcal} kcal · {rec.remaining_protein}g P left when picked</span>
        )}
      </div>
      {rec.items.map((raw, i) => {
        const it = normalizeRecItem(raw);
        return (
          <div key={i} style={{ borderTop: i ? `1px solid ${C.line}` : "none", padding: "11px 0" }}>
            <div className="vt-name" style={{ fontWeight: 600 }}>
              {it.name}
              {it.price != null && <span style={{ color: C.mute, fontWeight: 400 }}> · ₹{it.price}</span>}
            </div>
            <div className="vt-macros">
              {it.meta}
              {it.est_kcal != null && <> · est. {it.est_kcal} kcal · {it.est_protein}g P</>}
            </div>
            {it.reason && <div className="vt-cue" style={{ marginTop: 3 }}>{it.reason}</div>}
          </div>
        );
      })}
      <div className="vt-macros" style={{ marginTop: 6 }}>
        Recommendations only — FitAgent can't place orders. Macros are estimates.
      </div>
    </section>
  );
}

export default function App() {
  const [tab, setTab] = useState("today");
  const [guideTab, setGuideTab] = useState("push");
  const [plan, setPlan] = useState(null);
  const [day, setDay] = useState({ meals: [], weight_kg: null });
  const [history, setHistory] = useState([]);
  const [exercises, setExercises] = useState(() => readJSON(EX_KEY, {}));
  const [planVersions, setPlanVersions] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [offline, setOffline] = useState(false);
  const [sync, setSync] = useState("idle"); // idle | saving | saved | queued
  const [weightInput, setWeightInput] = useState("");
  const [chatOpen, setChatOpen] = useState(false);
  const [approvals, setApprovals] = useState([]);
  const [recs, setRecs] = useState({ food: null, instamart: null });
  const [me, setMe] = useState(null); // {name, lat, lng, location_label}
  const [locationOpen, setLocationOpen] = useState(false);

  const tKey = todayKey();
  const wdKey = weekdayKeyOf(tKey);

  const loadDay = () =>
    api.day(tKey).then(({ data }) => setDay(data)).catch(() => {});
  const loadHistory = () =>
    api.history(21).then(({ data }) => setHistory(data)).catch(() => {});
  const loadApprovals = () =>
    api.approvals().then(({ data }) => setApprovals(data)).catch(() => {});
  const loadRecs = () =>
    api.recommendations(tKey).then(({ data }) => setRecs(data)).catch(() => {});
  const loadMe = () =>
    api.me().then(({ data }) => setMe(data)).catch(() => {});

  // Same endpoint the Telegram buttons hit — ownership enforced server-side.
  // The plan may change on approve, so reload everything plan-shaped after.
  const decideApproval = async (id, decision) => {
    try {
      await api.resolveApproval(id, decision);
    } catch { /* already resolved elsewhere (e.g. Telegram) — just refresh */ }
    loadApprovals();
    api.activePlan().then(({ data }) => setPlan(data.plan)).catch(() => {});
    api.planHistory().then(({ data }) => setPlanVersions(data)).catch(() => {});
  };

  // Browser geolocation, not a hard-coded city — Swiggy search happens near
  // wherever the user actually is. label is just for display; lat/lng drive search.
  const [locStatus, setLocStatus] = useState("idle"); // idle | locating | saving | error
  const [locLabelInput, setLocLabelInput] = useState("");
  const useMyLocation = () => {
    if (!navigator.geolocation) { setLocStatus("error"); return; }
    setLocStatus("locating");
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        setLocStatus("saving");
        try {
          await api.setLocation(coords.latitude, coords.longitude, locLabelInput.trim() || null);
          await loadMe();
          setLocationOpen(false);
          setLocStatus("idle");
        } catch {
          setLocStatus("error");
        }
      },
      () => setLocStatus("error"),
      { timeout: 10000 }
    );
  };

  useEffect(() => {
    if (!getToken()) {
      setStatus("pair");
      return;
    }
    (async () => {
      try {
        const { data: planDoc, fromCache } = await api.activePlan();
        setPlan(planDoc.plan);
        setOffline(fromCache);
        migrateLegacyData(planDoc.plan);
        await Promise.all([loadDay(), loadHistory(), loadApprovals(), loadRecs(), loadMe()]);
        setStatus("ready");
      } catch (e) {
        setStatus(e instanceof AuthError ? "pair" : "error");
      }
    })();
  }, []);

  // Agent writes (off-plan food from comments) should show up when you come
  // back to the tab; queued writes retry on reconnect and every 20s.
  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "visible") {
        loadDay();
        loadApprovals(); // the 22:00 nightly review may have proposed a change
        loadRecs();      // the 18:00 dinner window may have left picks
      }
    };
    const retry = async () => {
      if (api.pendingWrites() > 0 && (await flushQueue()) === 0) {
        setSync("saved");
        setTimeout(() => setSync("idle"), 1200);
        loadDay();
      }
    };
    document.addEventListener("visibilitychange", refresh);
    window.addEventListener("online", retry);
    const t = setInterval(retry, 20000);
    return () => {
      document.removeEventListener("visibilitychange", refresh);
      window.removeEventListener("online", retry);
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    setWeightInput(day.weight_kg == null ? "" : String(day.weight_kg));
  }, [day.weight_kg]);

  useEffect(() => {
    if (tab === "progress") {
      loadHistory();
      api.planHistory().then(({ data }) => setPlanVersions(data)).catch(() => {});
    }
  }, [tab]);

  const planDay = plan?.meals?.[wdKey];
  const workoutType = plan?.weekly_workouts?.[wdKey] || "rest";
  const workout = WORKOUTS[workoutType] || WORKOUTS.rest;
  const targets = plan?.targets || { kcal: 0, protein_g: 0 };

  // The Guide opens on today's session, not a fixed default.
  useEffect(() => {
    if (plan && WORKOUTS[workoutType]) setGuideTab(workoutType);
  }, [plan, workoutType]);

  // Movement data: today's if the Shortcut already synced, else the most
  // recent day we have (the phone pushes nightly at 9:30 PM).
  const move = useMemo(() => {
    if (day.health) return { ...day.health, label: "today" };
    const h = history.find((x) => x.steps != null);
    return h ? { steps: h.steps, active_kcal: h.active_kcal, workouts: null,
                 label: fmtDate(h.date) } : null;
  }, [day.health, history]);

  const checkedById = useMemo(
    () => Object.fromEntries(day.meals.map((m) => [m.meal_id, m.checked])),
    [day.meals]
  );
  const offplanRows = day.meals.filter((m) => m.meal_id.startsWith("offplan:"));
  const eaten = day.meals.filter((m) => m.checked);
  const kcal = eaten.reduce((a, m) => a + m.kcal, 0);
  const prot = eaten.reduce((a, m) => a + m.protein_g, 0);

  const todayEx = exercises[tKey] || {};
  const exDone = workout.exercises.filter((e) => todayEx[e.id]).length;

  const finishWrite = (ok) => {
    setSync(ok ? "saved" : "queued");
    if (ok) setTimeout(() => setSync((s) => (s === "saved" ? "idle" : s)), 1200);
  };

  const toggleMeal = async (row) => {
    const next = !checkedById[row.meal_id];
    setDay((d) => {
      const rest = d.meals.filter((m) => m.meal_id !== row.meal_id);
      return { ...d, meals: [...rest, { ...row, checked: next }] };
    });
    setSync("saving");
    finishWrite(await api.logMeal({
      date: tKey, meal_id: row.meal_id, name: row.name,
      kcal: row.kcal, protein_g: row.protein_g, checked: next,
    }));
  };

  const toggleEx = (id) => {
    const next = { ...exercises, [tKey]: { ...todayEx, [id]: !todayEx[id] } };
    setExercises(next);
    localStorage.setItem(EX_KEY, JSON.stringify(next));
  };

  const commitWeight = async () => {
    const w = parseFloat(weightInput);
    if (!(w >= 40 && w <= 150) || w === day.weight_kg) return;
    setDay((d) => ({ ...d, weight_kg: w }));
    setSync("saving");
    finishWrite(await api.logWeight({ date: tKey, weight_kg: w }));
  };

  const progressRows = useMemo(() => {
    if (!plan) return [];
    return history.map((h) => {
      const wd = weekdayKeyOf(h.date);
      const items = plan.meals[wd]?.items || [];
      const checkedPlanned = items.filter((i) => h.meal_ids.includes(i.id)).length;
      const wk = WORKOUTS[plan.weekly_workouts?.[wd]] || WORKOUTS.rest;
      const ex = exercises[h.date] || {};
      return {
        ...h,
        theme: plan.meals[wd]?.theme || "",
        mealPct: items.length ? Math.round((checkedPlanned / items.length) * 100) : 0,
        workoutDone: wk.exercises.every((e) => ex[e.id]),
      };
    });
  }, [history, plan, exercises]);

  const streak = useMemo(() => {
    if (!plan) return 0;
    const byDate = Object.fromEntries(history.map((h) => [h.date, h]));
    let n = 0;
    const d = new Date();
    for (let i = 0; i < 90; i++) {
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      const h = byDate[key];
      if (h) {
        const items = plan.meals[weekdayKeyOf(key)]?.items || [];
        const done = items.filter((it) => h.meal_ids.includes(it.id)).length;
        if (items.length && done >= Math.ceil(items.length * 0.6)) {
          n++;
          d.setDate(d.getDate() - 1);
          continue;
        }
      }
      if (i === 0) { d.setDate(d.getDate() - 1); continue; } // today may be mid-flight
      break;
    }
    return n;
  }, [history, plan]);

  const weights = useMemo(
    () => history.filter((h) => h.weight_kg != null)
      .map((h) => ({ key: h.date, w: h.weight_kg }))
      .sort((a, b) => (a.key < b.key ? -1 : 1)),
    [history]
  );

  const stepsByDate = useMemo(() => {
    const m = {};
    history.forEach((h) => { if (h.steps != null) m[h.date] = h.steps; });
    return m;
  }, [history]);

  if (status === "loading") {
    return (
      <div className="vt-root" style={{ display: "grid", placeItems: "center" }}>
        <div className="vt-mono" style={{ color: C.mute }}>Opening your logbook…</div>
      </div>
    );
  }
  if (status === "pair") {
    return <PairScreen />;
  }
  if (status === "error") {
    return (
      <div className="vt-root" style={{ display: "grid", placeItems: "center", padding: 24 }}>
        <div style={{ textAlign: "center", maxWidth: 420 }}>
          <div className="vt-cardtitle">Can't reach FitAgent</div>
          <div className="vt-cue" style={{ marginTop: 8 }}>
            The API isn't responding and there's no cached plan yet. Start the stack
            (<span className="vt-mono">docker compose up</span>), create your user
            (<span className="vt-mono">python -m app.create_user "YourName"</span>),
            then reload.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="vt-root">
      <div className="vt-wrap">
        <header className="vt-hero">
          <div className="vt-kicker">V-Taper Log · {fmtDate(tKey)}</div>
          <h1 className="vt-h1">
            {tab === "today" && <span>{THEME_EMOJI[wdKey]} {planDay?.theme}</span>}
            {tab === "guide" && <span>The Workout Manual</span>}
            {tab === "progress" && <span>Your Numbers</span>}
          </h1>
          <div className="vt-sub">
            {tab === "today" && <span>{workout.label} · {targets.kcal} kcal · {targets.protein_g}g protein target</span>}
            {tab === "guide" && <span>Every move, every cue — 2×5kg dumbbells + one mat</span>}
            {tab === "progress" && <span>Trends beat single days. Judge the week, not the Tuesday.</span>}
          </div>
          {(sync !== "idle" || offline) && (
            <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
              {sync !== "idle" && (
                <span className="vt-pill" style={{ color: sync === "queued" ? C.saff : C.green }}>
                  {sync === "saving" ? "Saving…" : sync === "saved" ? "✓ Saved" : "⏳ Offline — queued, will sync"}
                </span>
              )}
              {offline && <span className="vt-pill" style={{ color: C.saff }}>showing last synced data</span>}
            </div>
          )}
          {tab === "today" && (
            <div style={{ marginTop: 8 }}>
              <button className="vt-locbtn" onClick={() => {
                if (!locationOpen) setLocLabelInput(me?.location_label || "");
                setLocationOpen((o) => !o);
              }}>
                📍 {me?.location_label || (me?.lat != null ? "Location set" : "Set your location")}
                <span style={{ color: C.mute }}> · change</span>
              </button>
              {locationOpen && (
                <div className="vt-loceditor">
                  <div className="vt-cue">
                    Used to find nearby Swiggy restaurants and Instamart stores — never guessed or hard-coded.
                  </div>
                  <input className="vt-weightin" style={{ width: "100%", marginTop: 8 }}
                    type="text" placeholder="Label, e.g. HSR Layout, Bengaluru"
                    value={locLabelInput} onChange={(e) => setLocLabelInput(e.target.value)} />
                  <div style={{ display: "flex", gap: 10, marginTop: 10, alignItems: "center", flexWrap: "wrap" }}>
                    <button className="vt-send" style={{ marginTop: 0 }}
                      disabled={locStatus === "locating" || locStatus === "saving"} onClick={useMyLocation}>
                      {locStatus === "locating" ? "Locating…" : locStatus === "saving" ? "Saving…" : "📍 Use my current location"}
                    </button>
                    {locStatus === "error" && (
                      <span className="vt-pill" style={{ color: C.red }}>
                        Couldn't get location — check browser permission and retry
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </header>

        {tab === "today" && (
          <>
            {approvals.map((a) => (
              <section key={a.id} className="vt-card" style={{ borderColor: C.saff }}>
                <div className="vt-cardtitle" style={{ color: C.saff }}>
                  🤖 Plan change awaiting your approval
                </div>
                <div style={{ fontSize: 14, marginTop: 6 }}>{a.summary}</div>
                {(a.patch || []).length > 0 && (
                  <details style={{ marginTop: 6 }}>
                    <summary className="vt-mono" style={{ color: C.mute, fontSize: 12, cursor: "pointer" }}>
                      {a.patch.length} change{a.patch.length === 1 ? "" : "s"}
                    </summary>
                    {a.patch.map((op, i) => (
                      <div key={i} className="vt-mono" style={{ fontSize: 11.5, color: C.mute,
                        padding: "3px 0 0 12px", overflowWrap: "anywhere" }}>
                        {op.op} {op.path}
                        {op.value !== undefined ? " → " + JSON.stringify(op.value) : ""}
                      </div>
                    ))}
                  </details>
                )}
                <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                  <button className="vt-send" style={{ background: C.green, marginTop: 0 }}
                    onClick={() => decideApproval(a.id, "approve")}>
                    ✅ Approve
                  </button>
                  <button className="vt-danger" style={{ marginTop: 0 }}
                    onClick={() => decideApproval(a.id, "reject")}>
                    ❌ Reject
                  </button>
                </div>
              </section>
            ))}

            <section className="vt-card">
              <div className="vt-cardtitle">Fuel gauge</div>
              <Gauge label="CALORIES" val={kcal} target={targets.kcal} unit="kcal" color={C.saff} />
              <Gauge label="PROTEIN" val={prot} target={targets.protein_g} unit="g" color={C.green} />
            </section>

            <section className="vt-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 6 }}>
                <div className="vt-cardtitle">Movement</div>
                <span className="vt-pill">
                  {move ? `${move.label} · from iPhone` : "from iPhone"}
                </span>
              </div>
              {move ? (
                <>
                  <div className="vt-stats">
                    <div className="vt-stat">
                      <div className="vt-kicker">🚶 Steps</div>
                      <div className="vt-statnum">{(move.steps ?? 0).toLocaleString("en-IN")}</div>
                    </div>
                    <div className="vt-stat">
                      <div className="vt-kicker">🔥 Burned walking</div>
                      <div className="vt-statnum">
                        {move.active_kcal ?? 0} <span style={{ fontSize: 14, color: C.mute, fontWeight: 500 }}>kcal</span>
                      </div>
                    </div>
                  </div>
                  {(move.workouts || []).map((w, i) => (
                    <div key={i} className="vt-macros" style={{ marginTop: 8 }}>
                      {w.type}{w.distance_km ? ` · ${w.distance_km} km` : ""}
                      {w.duration_min ? ` · ${Math.round(w.duration_min)} min` : ""}
                      {w.avg_pace_min_per_km ? ` · ${w.avg_pace_min_per_km} min/km` : ""}
                    </div>
                  ))}
                </>
              ) : (
                <div className="vt-cue" style={{ marginTop: 8 }}>
                  No Health data yet — the iPhone Shortcut syncs steps and walking
                  calories nightly at 9:30 PM.
                </div>
              )}
            </section>

            <section className="vt-card">
              <div className="vt-cardtitle" style={{ marginBottom: 6 }}>Today's plate</div>
              {(planDay?.items || []).map((m) => {
                const row = { meal_id: m.id, name: m.name, kcal: m.kcal, protein_g: m.protein_g };
                const done = !!checkedById[m.id];
                return (
                  <button key={m.id} className={"vt-item " + (done ? "done" : "")}
                    onClick={() => toggleMeal(row)}>
                    <span className="vt-check">{done ? "✓" : ""}</span>
                    <span>
                      <span className="vt-tag">{mealTag(m.id, wdKey)}</span>
                      <div className="vt-name">{m.name}</div>
                      <div className="vt-macros">{m.kcal} kcal · {m.protein_g}g protein</div>
                    </span>
                  </button>
                );
              })}
              {offplanRows.map((m) => (
                <button key={m.meal_id} className={"vt-item " + (m.checked ? "done" : "")}
                  onClick={() => toggleMeal(m)}>
                  <span className="vt-check">{m.checked ? "✓" : ""}</span>
                  <span>
                    <span className="vt-tag" style={{ color: C.red }}>Off-plan · logged by agent</span>
                    <div className="vt-name">{m.name}</div>
                    <div className="vt-macros">est. {m.kcal} kcal · {m.protein_g}g protein</div>
                  </span>
                </button>
              ))}
            </section>

            <RecommendationCard icon="🍽" title="Swiggy picks" rec={recs.food} />
            <RecommendationCard icon="🛒" title="Instamart — snacks to stock up on" rec={recs.instamart} />

            {(day.notes || []).length > 0 && (
              <section className="vt-card">
                <div className="vt-cardtitle">🤖 Today's notes</div>
                {day.notes.map((n, i) => (
                  <div key={i} style={{ fontSize: 14, lineHeight: 1.45, marginTop: 8,
                    paddingLeft: 10, borderLeft: `3px solid ${C.saff}` }}>
                    {n}
                  </div>
                ))}
              </section>
            )}

            <section className="vt-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 6 }}>
                <div className="vt-cardtitle" style={{ color: workout.color }}>{workout.label}</div>
                <span className="vt-pill">{exDone}/{workout.exercises.length} done</span>
              </div>
              <div className="vt-sub" style={{ marginTop: 4 }}>{workout.note}</div>
              <div style={{ marginTop: 6 }}>
                {workout.exercises.map((e) => (
                  <button key={e.id} className={"vt-item " + (todayEx[e.id] ? "done" : "")}
                    onClick={() => toggleEx(e.id)}>
                    <span className="vt-check">{todayEx[e.id] ? "✓" : ""}</span>
                    <span>
                      <div className="vt-name">{e.name}</div>
                      <div className="vt-macros">{e.scheme}</div>
                    </span>
                  </button>
                ))}
              </div>
            </section>

            <section className="vt-card">
              <div className="vt-cardtitle">
                Morning weight <span style={{ color: C.mute, fontWeight: 400, fontSize: 13 }}>
                  (optional — after toilet, before food)</span>
              </div>
              <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12 }}>
                <input className="vt-weightin" type="number" inputMode="decimal" step="0.1"
                  min="40" max="150" placeholder="kg" value={weightInput}
                  onChange={(e) => setWeightInput(e.target.value)}
                  onBlur={commitWeight}
                  onKeyDown={(e) => e.key === "Enter" && e.target.blur()}
                  aria-label="Morning weight in kilograms" />
                <span style={{ color: C.mute, fontSize: 13 }}>
                  Daily fluctuation is normal — the weekly average is the truth.
                </span>
              </div>
            </section>

          </>
        )}

        {tab === "guide" && (
          <>
            <div className="vt-guidebtns">
              {GUIDE_TABS.map((k) => (
                <button key={k} className={"vt-gbtn " + (guideTab === k ? "on" : "")}
                  style={guideTab === k ? { background: WORKOUTS[k].color, color: C.ink } : {}}
                  onClick={() => setGuideTab(k)}>
                  {WORKOUTS[k].label}{k === workoutType ? " · today" : ""}
                </button>
              ))}
            </div>
            <section className="vt-card">
              <div className="vt-cardtitle" style={{ color: WORKOUTS[guideTab].color }}>
                {WORKOUTS[guideTab].label}
              </div>
              <div className="vt-sub" style={{ marginTop: 3 }}>{WORKOUTS[guideTab].tagline}</div>
              <div style={{ marginTop: 8, fontSize: 13.5, background: C.cardUp,
                border: "1px solid " + C.line, borderRadius: 10, padding: "10px 12px" }}>
                {WORKOUTS[guideTab].note}
              </div>
              <div style={{ marginTop: 8 }}>
                {WORKOUTS[guideTab].exercises.map((e) => (
                  <div key={e.id} className="vt-ex">
                    <div className="vt-illobox">
                      <Illo type={e.illo} color={WORKOUTS[guideTab].color} />
                    </div>
                    <div>
                      <div className="vt-name" style={{ fontWeight: 600 }}>{e.name}</div>
                      <div className="vt-scheme">{e.scheme}</div>
                      <div className="vt-cue">{e.cue}</div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
            <section className="vt-card">
              <div className="vt-cardtitle">The week at a glance</div>
              <div style={{ marginTop: 8 }}>
                {["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map((k) => {
                  const t = plan?.weekly_workouts?.[k] || "rest";
                  return (
                    <div key={k} style={{ borderTop: "1px solid " + C.line, padding: "9px 0",
                      fontFamily: "'IBM Plex Mono', monospace", fontSize: 13 }}>
                      {k[0].toUpperCase() + k.slice(1)} {WORKOUTS[t]?.label.split(" ")[0]} {WORKOUT_EMOJI[t]}
                    </div>
                  );
                })}
              </div>
              <div className="vt-cue" style={{ marginTop: 10 }}>
                Push runs twice — chest and shoulders are the priority. Every session comes
                AFTER the 5km walk, 20–30 minutes, whey shake after.
              </div>
            </section>
          </>
        )}

        {tab === "progress" && (
          <>
            <section className="vt-card" style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 130 }}>
                <div className="vt-kicker">Streak</div>
                <div style={{ fontFamily: "'Bricolage Grotesque', sans-serif", fontWeight: 800,
                  fontSize: 34, marginTop: 4 }}>
                  {streak} <span style={{ fontSize: 15, color: C.mute, fontWeight: 500 }}>
                    day{streak === 1 ? "" : "s"} 🔥</span>
                </div>
              </div>
              <div style={{ flex: 1, minWidth: 130 }}>
                <div className="vt-kicker">Days logged</div>
                <div style={{ fontFamily: "'Bricolage Grotesque', sans-serif", fontWeight: 800,
                  fontSize: 34, marginTop: 4 }}>
                  {history.length}
                </div>
              </div>
            </section>

            {weights.length >= 2 && (
              <section className="vt-card">
                <div className="vt-cardtitle">Weight trend</div>
                <WeightChart points={weights} />
                <div className="vt-cue">
                  First & last logged: {weights[0].w}kg → {weights[weights.length - 1].w}kg.
                  Aim: ~0.4–0.5kg/week down.
                </div>
              </section>
            )}

            {Object.keys(stepsByDate).length > 0 && (
              <section className="vt-card">
                <div className="vt-cardtitle">Steps — last 14 days</div>
                <StepsChart byDate={stepsByDate} />
                <div className="vt-cue">
                  Synced nightly from your iPhone. Gaps are days with no sync.
                </div>
              </section>
            )}

            <section className="vt-card">
              <div className="vt-cardtitle" style={{ marginBottom: 4 }}>Day log</div>
              {progressRows.length === 0 && (
                <div className="vt-cue" style={{ padding: "14px 0" }}>
                  Nothing logged yet. Go to Today and check off your first meal — the log
                  starts building itself.
                </div>
              )}
              {progressRows.map((h) => (
                <div key={h.date} className="vt-row">
                  <span className="vt-mono" style={{ color: C.mute }}>
                    {fmtDate(h.date).replace(",", "")}
                  </span>
                  <span>
                    <div style={{ fontWeight: 500 }}>{h.theme}</div>
                    <div className="vt-macros">
                      {h.kcal} kcal · {h.protein_g}g P{h.weight_kg != null ? " · " + h.weight_kg + "kg" : ""}
                    </div>
                  </span>
                  <span className="vt-mono" style={{ color: h.mealPct === 100 ? C.green : C.mute }}>
                    {h.mealPct}%
                  </span>
                  <span className="vt-mono" style={{ color: h.workoutDone ? C.green : C.mute }}>
                    {h.workoutDone ? "✓ lift" : "· lift"}
                  </span>
                </div>
              ))}
              <div className="vt-cue" style={{ marginTop: 12 }}>
                Your log lives in Postgres now — every number here is what the agent sees.
              </div>
            </section>

            <section className="vt-card">
              <div className="vt-cardtitle" style={{ marginBottom: 4 }}>Plan history</div>
              <div className="vt-cue">
                Every version of your plan — who changed it, why, and what exactly changed.
                Plans are append-only: nothing is ever edited in place.
              </div>
              {planVersions.map((v) => (
                <div key={v.id} style={{ borderTop: "1px solid " + C.line, padding: "11px 0" }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                    <span className="vt-mono" style={{ color: C.mute, fontSize: 12 }}>
                      v{v.id} · {fmtDate(v.created_at.slice(0, 10))}
                    </span>
                    <span className="vt-pill" style={{
                      color: v.source === "agent" ? C.saff : C.green }}>
                      {v.source === "seed" ? "🌱 seed" : v.source === "agent" ? "🤖 agent" : "👤 you"}
                    </span>
                    <span className="vt-pill" style={{ color: v.approved ? C.green : C.red }}>
                      {v.approved ? "✓ applied" : "awaiting approval"}
                    </span>
                    {v.targets && (
                      <span className="vt-mono" style={{ color: C.mute, fontSize: 12 }}>
                        {v.targets.kcal} kcal · {v.targets.protein_g}g P
                      </span>
                    )}
                  </div>
                  {v.rationale && (
                    <div style={{ fontSize: 14, marginTop: 5 }}>{v.rationale}</div>
                  )}
                  {(v.patch || []).length > 0 && (
                    <details style={{ marginTop: 5 }}>
                      <summary className="vt-mono" style={{ color: C.mute, fontSize: 12, cursor: "pointer" }}>
                        {v.patch.length} change{v.patch.length === 1 ? "" : "s"}
                      </summary>
                      {v.patch.map((op, i) => (
                        <div key={i} className="vt-mono" style={{ fontSize: 11.5, color: C.mute,
                          padding: "3px 0 0 12px", overflowWrap: "anywhere" }}>
                          {op.op} {op.path}
                          {op.value !== undefined ? " → " + JSON.stringify(op.value) : ""}
                        </div>
                      ))}
                    </details>
                  )}
                </div>
              ))}
            </section>
          </>
        )}
      </div>

      {!chatOpen && (
        <button className="vt-fab" onClick={() => setChatOpen(true)} aria-label="Chat with FitAgent">
          🤖
        </button>
      )}
      <Chat open={chatOpen} onClose={() => setChatOpen(false)}
        onAgentReply={() => { loadDay(); loadHistory(); loadApprovals(); loadRecs(); }} />

      <nav className="vt-tabs" aria-label="Sections">
        {[["today", "Today"], ["guide", "Guide"], ["progress", "Progress"]].map(([k, label]) => (
          <button key={k} className={"vt-tab " + (tab === k ? "on" : "")} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}
