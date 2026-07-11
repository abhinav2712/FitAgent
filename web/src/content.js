// Static presentation content: the workout manual, meal-tag labels, day emoji.
// The *plan itself* (meals, targets, weekly workout schedule) comes from
// GET /plan/active — this file only holds what the plan document doesn't:
// exercise cues, illustrations, and cosmetic labels.

export const PALETTE = {
  ink: "#0C1B24",
  card: "#132836",
  cardUp: "#1A3344",
  line: "rgba(242,237,227,0.10)",
  text: "#F2EDE3",
  mute: "#8DA6B0",
  saff: "#F5A623",
  green: "#79C293",
  red: "#E07A5F",
};

// meal_id → user-facing tag. Sunday's "b" is brunch; offplan:* ids get their own label.
export const MEAL_TAGS = { b: "Breakfast", l: "Lunch", s: "Snack", d: "Dinner", x: "Dessert" };
export const THEME_EMOJI = {
  mon: "🫓", tue: "🍗", wed: "🥡", thu: "🧀", fri: "🫓", sat: "🍳", sun: "🍛",
};

export const WEEKDAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

export const todayKey = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
export const fmtDate = (key) => {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", {
    weekday: "short", day: "numeric", month: "short",
  });
};
export const weekdayKeyOf = (key) => {
  const [y, m, d] = key.split("-").map(Number);
  return WEEKDAY_KEYS[new Date(y, m - 1, d).getDay()];
};

export const WORKOUT_ORDER = ["push", "pull", "legs", "core"];

export const WORKOUTS = {
  push: {
    label: "Push Day",
    tagline: "Chest · Shoulders · Triceps — the V-taper builders",
    color: PALETTE.saff,
    note: "3 rounds of the circuit. Rest 60–90s between rounds. Tempo is the weight: 3s down, 1s pause, explode up.",
    exercises: [
      { id: "pushup", name: "Push-ups (slow tempo)", scheme: "3 × near-failure",
        cue: "Chest to floor, elbows ~45°. Too hard? Hands on a table. Too easy? Feet on the bed.", illo: "pushup" },
      { id: "press", name: "Dumbbell shoulder press", scheme: "3 × 12–15",
        cue: "Seated on the mat. Press up and slightly back, squeeze 1s at the top.", illo: "press" },
      { id: "floorpress", name: "Dumbbell floor press", scheme: "3 × 15–20",
        cue: "Lying on the mat. Pause 1s when triceps touch the floor, then drive up.", illo: "floorpress" },
      { id: "latraise", name: "Lateral raises (3s up, 3s down)", scheme: "3 × 12–15",
        cue: "Slight forward lean, lead with the elbows. This is where shoulder WIDTH comes from.", illo: "latraise" },
      { id: "diamond", name: "Diamond push-ups", scheme: "3 × near-failure",
        cue: "Hands form a triangle under your chest. Knees-down version is fine — go to burn.", illo: "diamond" },
    ],
  },
  pull: {
    label: "Pull Day",
    tagline: "Back · Rear delts · Biceps — the width behind the taper",
    color: "#7EB8D4",
    note: "3 rounds. For rows, hold BOTH dumbbells in one hand = instant 10kg.",
    exercises: [
      { id: "row", name: "Bent-over row (both DBs, one hand)", scheme: "3 × 12–15 / side",
        cue: "Flat back, hinge at hips. Pull elbow to hip, squeeze the shoulder blade 1s.", illo: "row" },
      { id: "renegade", name: "Renegade rows", scheme: "3 × 8–10 / side",
        cue: "Push-up position on the DBs. Row one up without letting hips twist — core on fire.", illo: "renegade" },
      { id: "revfly", name: "Reverse flys (slow)", scheme: "3 × 15–20",
        cue: "Bent over, tiny bend in elbows. Rear delts give shoulders the 3-D look from behind.", illo: "revfly" },
      { id: "curl", name: "Dumbbell curls (3s lowering)", scheme: "3 × 12–15 / arm",
        cue: "The slow lowering is where the muscle is built. No swinging.", illo: "curl" },
      { id: "superman", name: "Superman hold", scheme: "3 × 30 sec",
        cue: "On the mat, lift arms + legs, squeeze glutes and lower back.", illo: "superman" },
    ],
  },
  legs: {
    label: "Legs Day",
    tagline: "Quads · Hamstrings · Glutes — biggest muscles, biggest burn",
    color: PALETTE.green,
    note: "3 rounds. Legs respond to depth and tempo — go slow and deep, not fast and shallow.",
    exercises: [
      { id: "goblet", name: "Goblet squat (both DBs at chest)", scheme: "3 × 15–20",
        cue: "10kg at your chest. 3s down, as deep as comfortable, drive through heels.", illo: "goblet" },
      { id: "split", name: "Bulgarian split squat", scheme: "3 × 10–12 / leg",
        cue: "Rear foot on bed/chair, 5kg in each hand. Brutal even light — the great equaliser.", illo: "split" },
      { id: "rdl", name: "Romanian deadlift", scheme: "3 × 15–20",
        cue: "Hinge at the hips, soft knees, DBs slide down the thighs. Feel the hamstring stretch.", illo: "rdl" },
      { id: "lunge", name: "Walking lunges", scheme: "3 × 12 / leg",
        cue: "Long steps, back knee kisses the floor, torso tall.", illo: "lunge" },
      { id: "calf", name: "Single-leg calf raises", scheme: "3 × 15–20 / leg",
        cue: "Hold one DB. Full stretch at the bottom, 1s pause at the top.", illo: "calf" },
    ],
  },
  core: {
    label: "Core + Mobility",
    tagline: "The tight-waist session — builds the abs the deficit will reveal",
    color: "#C9A0DC",
    note: "3 rounds. Remember: this builds the muscle underneath — the deficit removes the layer on top.",
    exercises: [
      { id: "plank", name: "Plank", scheme: "3 × 45–60 sec",
        cue: "Squeeze glutes, ribs down, don't let the hips sag.", illo: "plank" },
      { id: "deadbug", name: "Dead bugs", scheme: "3 × 12 / side",
        cue: "Lower back pressed into the mat the entire time. Slow opposite arm + leg.", illo: "deadbug" },
      { id: "legraise", name: "Lying leg raises", scheme: "3 × 12–15",
        cue: "Slow 3s lowering. If your back arches, bend the knees slightly.", illo: "legraise" },
      { id: "twist", name: "Russian twists (one 5kg DB)", scheme: "3 × 20 total",
        cue: "Feet down = easier, feet up = harder. Rotate from the ribs, not the arms.", illo: "twist" },
      { id: "climber", name: "Mountain climbers", scheme: "3 × 40 sec",
        cue: "Fast finisher. Hips low, knees drive to chest.", illo: "climber" },
      { id: "stretch", name: "Deep squat hold + hip stretch", scheme: "2–3 min",
        cue: "Undoes your 7 hours of sitting. Breathe into it.", illo: "stretchsq" },
    ],
  },
  rest: {
    label: "Rest Day",
    tagline: "Growth happens today — muscles are built in recovery, not in the workout",
    color: PALETTE.mute,
    note: "Easy walk only. No guilt: rest is programmed, not skipped.",
    exercises: [
      { id: "walk", name: "Easy lake walk (no jogging)", scheme: "3–5 km",
        cue: "Conversational pace. Enjoy it.", illo: "walkillo" },
      { id: "stretchday", name: "Full-body stretch on the mat", scheme: "10 min",
        cue: "Hamstrings, hips, chest doorway stretch, neck.", illo: "stretchsq" },
    ],
  },
};

// Used to render the week at a glance from plan.weekly_workouts (the schedule
// itself lives in the plan — the agent may change it, so never hard-code it here).
export const WORKOUT_EMOJI = { push: "💪", pull: "🔙", legs: "🦵", core: "🧱", rest: "😴" };
