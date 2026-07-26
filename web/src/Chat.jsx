import React, { useEffect, useRef, useState } from "react";
import { api, getToken } from "./api.js";
import { todayKey } from "./content.js";

// Tiny markdown for the subset the agent actually emits — **bold** and
// *italic*. Newlines are already handled by the bubble's white-space:pre-wrap,
// so everything else (including line breaks and emoji) passes through verbatim.
// Deliberately no markdown library: this is the whole grammar we use.
function renderRich(text) {
  if (!text) return text;
  const out = [];
  const re = /\*\*(.+?)\*\*|\*(.+?)\*/g; // bold tried first, then italic
  let last = 0, m, k = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(m[1] !== undefined
      ? <strong key={k++}>{m[1]}</strong>
      : <em key={k++}>{m[2]}</em>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

// Floating FitAgent chat. Messages are ordinary comments (POST /log/comment —
// the agent's inbox); the worker (still the only thing that ever invokes the
// agent — same as before) picks them up on its own poll and streams live
// progress over GET /log/chat/stream (SSE: activity/delta/done events) while
// this panel is open. GET /log/chat (agent_runs) is the durable source and a
// reconciliation fallback if the stream was missed or never connected.
//
// Native EventSource can't send the X-Api-Token header, so this hand-rolls
// SSE parsing over fetch()'s ReadableStream — same reason Con-Mon's guide
// gives for using fetch streaming instead of EventSource when auth is on.
export default function Chat({ open, onClose, onAgentReply }) {
  const [thread, setThread] = useState([]);
  const [draft, setDraft] = useState("");
  const [queued, setQueued] = useState(false);
  // live[comment_id] = { activity: "Checking your day"|null, text: "accumulated delta text" }
  const [live, setLive] = useState({});
  const endRef = useRef(null);
  const seenReplies = useRef(null); // null until first load — don't fire onAgentReply for old replies
  const abortRef = useRef(null);

  const load = async () => {
    try {
      const { data } = await api.chat();
      setThread(data);
      const replied = data.filter((m) => m.reply).map((m) => m.id);
      if (seenReplies.current === null) {
        seenReplies.current = new Set(replied);
      } else if (replied.some((id) => !seenReplies.current.has(id))) {
        replied.forEach((id) => seenReplies.current.add(id));
        onAgentReply(); // agent may have logged food / patched the plan — refresh
      }
      // Reconciled from the durable source — drop any stale live buffer.
      setLive((cur) => {
        const next = { ...cur };
        for (const m of data) if (m.reply) delete next[m.id];
        return next;
      });
    } catch {
      /* offline — keep whatever is shown */
    }
  };

  // One SSE connection for as long as the panel is open, independent of any
  // single message — events carry their own comment_id so late-open still
  // catches whichever run is in flight.
  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    (async () => {
      try {
        const res = await fetch("/log/chat/stream", {
          headers: { "X-Api-Token": getToken() },
          signal: ctrl.signal,
        });
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const frames = buf.split("\n\n");
          buf = frames.pop(); // last chunk may be incomplete — keep for next read
          for (const frame of frames) {
            const line = frame.split("\n").find((l) => l.startsWith("data: "));
            if (!line) continue; // keep-alive/comment frames have no "data:" line
            let ev;
            try { ev = JSON.parse(line.slice(6)); } catch { continue; }
            const id = ev.comment_id;
            setLive((cur) => {
              const prior = cur[id] || { activity: null, text: "" };
              if (ev.type === "activity") return { ...cur, [id]: { ...prior, activity: ev.label || ev.tool } };
              if (ev.type === "delta") return { ...cur, [id]: { activity: null, text: prior.text + ev.text } };
              if (ev.type === "done") {
                load(); // pull the durable row (and trigger onAgentReply if new)
                return { ...cur, [id]: { activity: null, text: ev.text } };
              }
              return cur;
            });
          }
        }
      } catch {
        /* connection dropped/aborted — the 4s poll below still gets replies */
      }
    })();
    return () => ctrl.abort();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [open]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [thread, live, open]);

  const send = async () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    setThread((t) => [...t, { id: "local-" + Date.now(), text, reply: null, processed: false }]);
    setQueued(!(await api.postComment({ date: todayKey(), text })));
    load();
  };

  if (!open) return null;
  return (
    <>
      <div className="vt-chat-backdrop" onClick={onClose} />
      <div className="vt-chat" role="dialog" aria-label="FitAgent chat">
        <div className="vt-chat-head">
          <div>
            <div className="vt-cardtitle">🤖 FitAgent</div>
            <div className="vt-chat-sub">
              Tell it what happened — it rebalances your day or suggests how to hit
              the target. Streams live here, and replies on Telegram too.
            </div>
          </div>
          <button className="vt-chat-close" onClick={onClose} aria-label="Close chat">✕</button>
        </div>
        <div className="vt-msgs">
          {thread.length === 0 && (
            <div className="vt-cue">
              Try: "skipped lunch, ate 2 samosas at office" · "shoulder hurts, swap
              tomorrow's push day" · "what should I eat tonight to hit my protein?"
            </div>
          )}
          {thread.map((m) => {
            const l = live[m.id];
            return (
              <div key={m.id} className="vt-msg">
                <div className="vt-bubble user">{m.text}</div>
                {m.reply ? (
                  <div className="vt-bubble agent">{renderRich(m.reply)}</div>
                ) : l?.text ? (
                  <div className="vt-bubble agent">{renderRich(l.text)}</div>
                ) : l?.activity ? (
                  <div className="vt-bubble agent thinking">🔎 {l.activity}…</div>
                ) : m.processed ? (
                  <div className="vt-bubble agent thinking">✓ processed — check the Today tab for changes</div>
                ) : (
                  <div className="vt-bubble agent thinking">FitAgent is thinking…</div>
                )}
              </div>
            );
          })}
          <div ref={endRef} />
        </div>
        {queued && (
          <div className="vt-pill" style={{ color: "var(--saff)", marginBottom: 8 }}>
            ⏳ offline — message queued, will send when back online
          </div>
        )}
        <div className="vt-chat-inputrow">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="What did you do / eat / feel?"
            aria-label="Message to FitAgent"
            rows={1}
          />
          <button className="vt-send" style={{ marginTop: 0 }} disabled={!draft.trim()} onClick={send}>
            Send
          </button>
        </div>
      </div>
    </>
  );
}
