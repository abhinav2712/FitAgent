import React from "react";
import { PALETTE as C } from "./content.js";

// Stick-figure exercise illustrations. Pure SVG, one figure per exercise id.
export default function Illo({ type, color = C.saff }) {
  const s = {
    fill: "none",
    stroke: color,
    strokeWidth: 2.5,
    strokeLinecap: "round",
    strokeLinejoin: "round",
  };
  const head = (cx, cy) => <circle cx={cx} cy={cy} r="5" style={s} />;
  const db = (x, y, rot = 0) => (
    <g transform={`rotate(${rot} ${x} ${y})`}>
      <line x1={x - 6} y1={y} x2={x + 6} y2={y} style={{ ...s, strokeWidth: 2 }} />
      <rect x={x - 8} y={y - 3} width="4" height="6" rx="1" style={{ ...s, strokeWidth: 1.8 }} />
      <rect x={x + 4} y={y - 3} width="4" height="6" rx="1" style={{ ...s, strokeWidth: 1.8 }} />
    </g>
  );
  const arrow = (d) => (
    <path d={d} style={{ ...s, stroke: C.mute, strokeWidth: 1.6, strokeDasharray: "3 3" }}
      markerEnd="url(#arr)" />
  );
  const ground = (
    <line x1="6" y1="74" x2="114" y2="74" style={{ ...s, stroke: C.line, strokeWidth: 2 }} />
  );
  const defs = (
    <defs>
      <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5"
        orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill={C.mute} />
      </marker>
    </defs>
  );

  const bodies = {
    pushup: (
      <g>
        {head(16, 50)}{ground}
        <path d="M22 53 L58 58 L92 62" style={s} />
        <path d="M30 54 L32 72 M34 54 L38 72" style={s} />
        <path d="M92 62 L106 72 M92 62 L102 73" style={s} />
        {arrow("M20 38 L20 28 M20 28 L20 38")}
      </g>
    ),
    diamond: (
      <g>
        {head(16, 50)}{ground}
        <path d="M22 53 L58 58 L92 62" style={s} />
        <path d="M30 54 L34 72 M36 54 L36 72" style={s} />
        <path d="M92 62 L106 72" style={s} />
        <path d="M30 70 L36 66 L42 70 L36 73 Z" style={{ ...s, strokeWidth: 1.6 }} />
      </g>
    ),
    press: (
      <g>
        {head(60, 26)}{ground}
        <path d="M60 31 L60 54 M60 54 L48 74 M60 54 L72 74" style={s} />
        <path d="M60 36 L46 30 L44 16 M60 36 L74 30 L76 16" style={s} />
        {db(44, 13)}{db(76, 13)}{arrow("M92 30 L92 14")}
      </g>
    ),
    floorpress: (
      <g>
        {head(20, 64)}{ground}
        <path d="M26 66 L64 66 L64 74 M64 66 L86 66 L96 74" style={s} />
        <path d="M40 66 L40 48 M52 66 L52 48" style={s} />
        {db(40, 45)}{db(52, 45)}{arrow("M72 56 L72 42")}
      </g>
    ),
    latraise: (
      <g>
        {head(60, 22)}{ground}
        <path d="M60 27 L60 52 M60 52 L50 74 M60 52 L70 74" style={s} />
        <path d="M60 33 L36 30 M60 33 L84 30" style={s} />
        {db(32, 30, 90)}{db(88, 30, 90)}{arrow("M28 48 Q22 38 30 32")}
      </g>
    ),
    row: (
      <g>
        {head(30, 30)}{ground}
        <path d="M34 34 L58 44 L60 60 M60 60 L48 74 M60 60 L74 74" style={s} />
        <path d="M44 39 L42 58" style={s} />
        {db(42, 61)}{arrow("M50 56 L52 42")}
      </g>
    ),
    renegade: (
      <g>
        {head(16, 46)}{ground}
        <path d="M22 49 L58 55 L92 60" style={s} />
        <path d="M32 51 L34 70 M92 60 L106 72" style={s} />
        <path d="M38 50 L40 34" style={s} />
        {db(34, 71)}{db(40, 31)}
      </g>
    ),
    revfly: (
      <g>
        {head(34, 28)}{ground}
        <path d="M38 32 L60 44 L62 60 M62 60 L50 74 M62 60 L76 74" style={s} />
        <path d="M48 37 L30 48 M50 38 L70 30" style={s} />
        {db(27, 50, 45)}{db(74, 28, -30)}{arrow("M40 56 Q30 50 30 42")}
      </g>
    ),
    curl: (
      <g>
        {head(60, 22)}{ground}
        <path d="M60 27 L60 52 M60 52 L50 74 M60 52 L70 74" style={s} />
        <path d="M60 33 L48 42 L46 30 M60 33 L72 42 L74 54" style={s} />
        {db(45, 27)}{db(75, 57)}{arrow("M84 52 Q92 42 84 32")}
      </g>
    ),
    superman: (
      <g>
        {head(22, 58)}{ground}
        <path d="M28 61 Q58 68 90 60" style={s} />
        <path d="M28 61 L12 50 M90 60 L108 52" style={s} />
        {arrow("M58 52 L58 44")}
      </g>
    ),
    goblet: (
      <g>
        {head(60, 24)}{ground}
        <path d="M60 29 L58 48 M58 48 L46 60 L48 74 M58 48 L70 60 L68 74" style={s} />
        <path d="M60 34 L52 40 M60 34 L66 40" style={s} />
        {db(59, 42)}{arrow("M86 40 L86 56 M86 56 L86 40")}
      </g>
    ),
    split: (
      <g>
        {head(48, 22)}{ground}
        <path d="M48 27 L48 50 M48 50 L36 62 L38 74 M48 50 L68 54 L84 50" style={s} />
        <rect x="82" y="50" width="24" height="12" rx="2" style={{ ...s, strokeWidth: 1.8 }} />
        <path d="M48 33 L40 44 M48 33 L56 44" style={s} />
        {db(39, 47)}{db(57, 47)}
      </g>
    ),
    rdl: (
      <g>
        {head(38, 26)}{ground}
        <path d="M42 30 L62 40 M62 40 L60 74 M62 40 L68 74" style={s} />
        <path d="M50 34 L48 54 M54 36 L52 54" style={s} />
        {db(48, 57)}{db(53, 57)}{arrow("M30 40 Q24 52 34 58")}
      </g>
    ),
    lunge: (
      <g>
        {head(56, 20)}{ground}
        <path d="M56 25 L56 46 M56 46 L38 56 L38 74 M56 46 L74 60 L88 68" style={s} />
        <path d="M56 30 L48 44 M56 30 L64 44" style={s} />
        {db(47, 47)}{db(65, 47)}
      </g>
    ),
    calf: (
      <g>
        {head(60, 20)}{ground}
        <path d="M60 25 L60 50 M60 50 L58 66 L58 72 M60 50 L70 58" style={s} />
        <path d="M60 30 L50 42" style={s} />
        {db(49, 45)}{arrow("M80 66 L80 54")}
        <path d="M52 74 L64 74" style={{ ...s, strokeWidth: 3 }} />
      </g>
    ),
    plank: (
      <g>
        {head(18, 48)}{ground}
        <path d="M24 51 L60 56 L94 62 M94 62 L108 73" style={s} />
        <path d="M30 52 L30 64 L40 64" style={s} />
        <path d="M30 64 L44 66" style={{ ...s, strokeWidth: 3 }} />
      </g>
    ),
    deadbug: (
      <g>
        {head(24, 62)}{ground}
        <path d="M30 64 L74 64" style={s} />
        <path d="M40 63 L36 42 M58 64 L64 46 L64 34 M74 64 L92 60 L104 68" style={s} />
        {arrow("M44 36 L52 30")}
      </g>
    ),
    legraise: (
      <g>
        {head(20, 62)}{ground}
        <path d="M26 64 L66 64" style={s} />
        <path d="M66 64 L92 40" style={s} />
        {arrow("M96 56 Q102 46 94 38")}
      </g>
    ),
    twist: (
      <g>
        {head(52, 32)}{ground}
        <path d="M54 37 L60 54 M60 54 L78 46 L92 52" style={s} />
        <path d="M56 42 L40 48" style={s} />
        {db(37, 50)}{arrow("M34 60 Q46 68 60 62")}
      </g>
    ),
    climber: (
      <g>
        {head(18, 44)}{ground}
        <path d="M24 47 L58 54 L80 58" style={s} />
        <path d="M32 49 L34 70" style={s} />
        <path d="M80 58 L98 70 M80 58 L74 44 L84 40" style={s} />
        {arrow("M92 38 L78 34")}
      </g>
    ),
    stretchsq: (
      <g>
        {head(60, 34)}{ground}
        <path d="M60 39 L58 54 M58 54 L44 58 L48 74 M58 54 L72 58 L68 74" style={s} />
        <path d="M60 43 L46 50 M60 43 L74 50" style={s} />
      </g>
    ),
    walkillo: (
      <g>
        {head(56, 22)}{ground}
        <path d="M56 27 L56 48 M56 48 L44 62 L40 74 M56 48 L68 60 L76 72" style={s} />
        <path d="M56 32 L46 42 M56 32 L66 42" style={s} />
        <path d="M14 70 Q30 62 44 70" style={{ ...s, stroke: C.mute, strokeWidth: 1.5 }} />
      </g>
    ),
  };

  return (
    <svg viewBox="0 0 120 80" width="100%" height="100%" role="img" aria-label={type}>
      {defs}
      {bodies[type] || bodies.pushup}
    </svg>
  );
}
