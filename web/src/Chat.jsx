import React, { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { todayKey } from "./content.js";

// Floating FitAgent chat. Messages are ordinary comments (POST /log/comment —
// the agent's inbox); replies come from the worker's agent run, surfaced via
// GET /log/chat. The panel polls while open, so a reply lands ~30s after send
// (the worker's comment-poll interval). Same message also arrives on Telegram.
export default function Chat({ open, onClose, onAgentReply }) {
  const [thread, setThread] = useState([]);
  const [draft, setDraft] = useState("");
  const [queued, setQueued] = useState(false);
  const endRef = useRef(null);
  const seenReplies = useRef(null); // null until first load — don't fire onAgentReply for old replies

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
    } catch {
      /* offline — keep whatever is shown */
    }
  };

  useEffect(() => {
    if (!open) return;
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [open]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [thread, open]);

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
              the target. Replies here and on Telegram in ~30s.
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
          {thread.map((m) => (
            <div key={m.id} className="vt-msg">
              <div className="vt-bubble user">{m.text}</div>
              {m.reply ? (
                <div className="vt-bubble agent">{m.reply}</div>
              ) : m.processed ? (
                <div className="vt-bubble agent thinking">✓ handled — details on Telegram</div>
              ) : (
                <div className="vt-bubble agent thinking">FitAgent is thinking…</div>
              )}
            </div>
          ))}
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
