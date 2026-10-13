// Shared cartoon SVG helpers + page chrome (header, progress, step reveal).
// Every helper returns an SVG string in local coordinates, wrapped in a <g transform>.
const INK = '#2B2D42';
const C = {
  ink: INK, orange: '#D97757', teal: '#2A9D8F', blue: '#3D7DCA', blueL: '#8DB6E8',
  yellow: '#F2BE36', red: '#E0574F', green: '#4FA35A', purple: '#8B67C9',
  wood: '#E3AE72', woodD: '#B97A3E', woodL: '#F2CFA3', steel: '#DCE3EC', pink: '#F28B82',
};

function g(x, y, s, rot, inner) {
  return `<g transform="translate(${x},${y}) rotate(${rot || 0}) scale(${s || 1})">${inner}</g>`;
}

// Two-pass "outlined" stroke: thick ink under a coloured stroke.
function oline(d, color, w, extra) {
  w = w || 10;
  return `<path d="${d}" fill="none" stroke="${INK}" stroke-width="${w + 7}" stroke-linecap="round" stroke-linejoin="round" ${extra || ''}/>` +
         `<path d="${d}" fill="none" stroke="${color}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" ${extra || ''}/>`;
}

// DNA as chunky yarn. d = SVG path string (absolute coordinates).
function yarn(d, color, w) {
  color = color || C.blue; w = w || 12;
  return oline(d, color, w) +
    `<path d="${d}" fill="none" stroke="#fff" stroke-opacity=".45" stroke-width="3" stroke-dasharray="3 13" stroke-linecap="round"/>`;
}

// Nucleosome as a wooden spool with yarn wrapped around it. Local size ~84 x 104.
function spool(x, y, s, rot, yarnColor) {
  yarnColor = yarnColor || C.blue;
  let wraps = '';
  for (let i = 0; i < 5; i++) {
    const yy = -30 + i * 14;
    wraps += `<path d="M-27 ${yy} L27 ${yy + 9}" stroke="${INK}" stroke-width="12" stroke-linecap="butt"/>` +
             `<path d="M-27 ${yy} L27 ${yy + 9}" stroke="${yarnColor}" stroke-width="7" stroke-linecap="butt"/>`;
  }
  const inner =
    `<rect x="-28" y="-38" width="56" height="76" rx="6" fill="${C.woodL}" stroke="${INK}" stroke-width="4"/>` +
    wraps +
    `<rect x="-28" y="-38" width="56" height="76" rx="6" fill="none" stroke="${INK}" stroke-width="4"/>` +
    `<rect x="-44" y="-52" width="88" height="18" rx="9" fill="${C.wood}" stroke="${INK}" stroke-width="4"/>` +
    `<rect x="-44" y="34" width="88" height="18" rx="9" fill="${C.wood}" stroke="${INK}" stroke-width="4"/>` +
    `<path d="M-34 -46 L30 -46" stroke="#fff" stroke-opacity=".5" stroke-width="4" stroke-linecap="round"/>`;
  return g(x, y, s, rot, inner);
}

// Tn5 as a cute pair of scissors, blades pointing right. open: blade angle in degrees.
function scissors(x, y, s, rot, open, withTags) {
  open = open == null ? 14 : open;
  const blade = (sign) =>
    `<g transform="rotate(${sign * open / 2})">` +
    `<path d="M-6 ${-9 * sign} L96 ${-4 * sign} Q106 0 96 ${3 * sign} L-6 ${9 * sign} Z" fill="${C.steel}" stroke="${INK}" stroke-width="4" stroke-linejoin="round"/>` +
    `<path d="M8 ${-4 * sign} L84 ${-1 * sign}" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-opacity=".9"/>` +
    `<path d="M-6 ${-2 * sign} Q-26 ${-16 * sign} -40 ${-26 * sign}" fill="none" stroke="${INK}" stroke-width="17" stroke-linecap="round"/>` +
    `<path d="M-6 ${-2 * sign} Q-26 ${-16 * sign} -40 ${-26 * sign}" fill="none" stroke="${C.red}" stroke-width="10" stroke-linecap="round"/>` +
    `<ellipse cx="-58" cy="${-34 * sign}" rx="24" ry="18" fill="none" stroke="${INK}" stroke-width="17"/>` +
    `<ellipse cx="-58" cy="${-34 * sign}" rx="24" ry="18" fill="none" stroke="${C.red}" stroke-width="10"/>` +
    `</g>`;
  const face =
    `<ellipse cx="30" cy="-2" rx="4.5" ry="6" fill="${INK}"/><ellipse cx="46" cy="-1" rx="4.5" ry="6" fill="${INK}"/>` +
    `<circle cx="29" cy="-4" r="1.6" fill="#fff"/><circle cx="45" cy="-3" r="1.6" fill="#fff"/>`;
  let tags = '';
  if (withTags) {
    tags = adapterTag(-40, -70, 1, -12, C.pink) + adapterTag(-44, 64, 1, 10, C.teal);
  }
  const inner = tags + blade(-1) + blade(1) +
    `<circle cx="0" cy="0" r="9" fill="#B8C0CC" stroke="${INK}" stroke-width="4"/>` + face;
  return g(x, y, s, rot, inner);
}

// Sequencing adapter: a small flag / sticker.
function adapterTag(x, y, s, rot, color) {
  const inner =
    `<rect x="-20" y="-13" width="40" height="26" rx="7" fill="${color}" stroke="${INK}" stroke-width="3.5"/>` +
    `<circle cx="-11" cy="0" r="3.5" fill="#fff" stroke="${INK}" stroke-width="2"/>`;
  return g(x, y, s, rot, inner);
}

// Transcription factor as a little clip creature that sits on the yarn at (x,y).
function clip(x, y, s, color, rot) {
  color = color || C.purple;
  const inner =
    `<path d="M-16 6 Q-20 26 -8 30" fill="none" stroke="${INK}" stroke-width="6" stroke-linecap="round"/>` +
    `<path d="M16 6 Q20 26 8 30" fill="none" stroke="${INK}" stroke-width="6" stroke-linecap="round"/>` +
    `<path d="M-26 8 Q-28 -34 0 -38 Q28 -34 26 8 Z" fill="${color}" stroke="${INK}" stroke-width="4" stroke-linejoin="round"/>` +
    `<ellipse cx="-8" cy="-14" rx="4" ry="5.5" fill="${INK}"/><ellipse cx="8" cy="-14" rx="4" ry="5.5" fill="${INK}"/>` +
    `<circle cx="-9" cy="-16" r="1.5" fill="#fff"/><circle cx="7" cy="-16" r="1.5" fill="#fff"/>` +
    `<path d="M-6 -3 Q0 2 6 -3" fill="none" stroke="${INK}" stroke-width="3" stroke-linecap="round"/>` +
    `<path d="M-18 -24 Q-14 -32 -6 -33" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="4" stroke-linecap="round"/>`;
  return g(x, y, s, rot, inner);
}

// A short sequencing read: rounded bar with an arrow head. dir = 1 (right) / -1 (left)
function read(x, y, len, color, dir) {
  dir = dir || 1;
  const x2 = x + len * dir;
  const head = `M${x2} ${y} L${x2 - 12 * dir} ${y - 9} M${x2} ${y} L${x2 - 12 * dir} ${y + 9}`;
  return oline(`M${x} ${y} L${x2} ${y}`, color, 8) +
    `<path d="${head}" fill="none" stroke="${INK}" stroke-width="5" stroke-linecap="round"/>`;
}

// A big red cross / green tick
function cross(x, y, s) {
  return g(x, y, s, 0,
    `<path d="M-18 -18 L18 18 M18 -18 L-18 18" stroke="${INK}" stroke-width="16" stroke-linecap="round"/>` +
    `<path d="M-18 -18 L18 18 M18 -18 L-18 18" stroke="${C.red}" stroke-width="9" stroke-linecap="round"/>`);
}
function tick(x, y, s) {
  return g(x, y, s, 0,
    `<path d="M-20 0 L-6 15 L22 -17" fill="none" stroke="${INK}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/>` +
    `<path d="M-20 0 L-6 15 L22 -17" fill="none" stroke="${C.green}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>`);
}

// Accent underline under page titles
function squiggle(w, color) {
  color = color || C.orange;
  return `<svg class="squiggle" width="${w}" height="16" viewBox="0 0 ${w} 16"><rect x="2" y="4" width="120" height="8" rx="4" fill="${color}"/></svg>`;
}

// Arrow between two points (outlined, with head)
function arrow(x1, y1, x2, y2, color, w) {
  color = color || C.ink; w = w || 8;
  const a = Math.atan2(y2 - y1, x2 - x1), L = 22;
  const hx1 = x2 - L * Math.cos(a - 0.5), hy1 = y2 - L * Math.sin(a - 0.5);
  const hx2 = x2 - L * Math.cos(a + 0.5), hy2 = y2 - L * Math.sin(a + 0.5);
  return `<path d="M${x1} ${y1} L${x2} ${y2} M${hx1} ${hy1} L${x2} ${y2} L${hx2} ${hy2}" fill="none" stroke="${color}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;
}

// ---------- page chrome ----------
// Progress-bar labels come from script.json "progress_steps" (injected by render.py / export_pptx.py).
const STEPS = window.PROGRESS_STEPS || ['步骤一', '步骤二', '步骤三', '步骤四'];
function header(chapter, cur) {
  // cur: index 0..5 of current step, -1 = none highlighted, null = hide progress
  let prog = '';
  if (cur === -2) cur = null;
  if (cur !== null && cur !== undefined) {
    prog = '<div class="progress">' + STEPS.map((t, i) => {
      const cls = i === cur ? 'cur' : (cur >= 0 && i < cur ? 'done' : '');
      return `<div class="pstep ${cls}">${t}</div>` + (i < STEPS.length - 1 ? '<div class="parrow">›</div>' : '');
    }).join('') + '</div>';
  }
  return `<div class="header"><div class="chip">${chapter}</div>${prog}</div>`;
}

// Step reveal: ?step=N shows [data-s<=N]; data-until="M" hides from step M+1 on.
function applyStep() {
  const q = new URLSearchParams(location.search);
  const step = q.has('step') ? +q.get('step') : 999;
  document.querySelectorAll('[data-s]').forEach(e => {
    const s = +e.dataset.s, u = e.dataset.until ? +e.dataset.until : 999;
    e.classList.toggle('on', s <= step && step <= u);
  });
  document.querySelectorAll('[data-hl]').forEach(e => {
    const lst = e.dataset.hl.split(',').map(Number);
    e.classList.toggle('hl', lst.includes(step));
  });
  if (q.has('debug')) document.body.classList.add('debug');
  document.body.dataset.ready = '1';
}

// A pile of reads forming a "hill" (peak). Base centred at (x, y), width w, rows n.
function hill(x, y, w, n, color) {
  color = color || C.orange;
  let s = '';
  for (let r = 0; r < n; r++) {
    const rowW = w * (1 - r / n) * (0.92 + 0.08 * Math.cos(r * 1.7));
    const k = Math.max(1, Math.round(rowW / 46));
    const segW = rowW / k;
    for (let j = 0; j < k; j++) {
      const x0 = x - rowW / 2 + j * segW + 4 + ((r * 7 + j * 13) % 9);
      const len = Math.max(14, segW - 14);
      s += `<rect x="${x0}" y="${y - 18 - r * 17}" width="${len}" height="11" rx="5.5" fill="${color}" stroke="${INK}" stroke-width="2.5"/>`;
    }
  }
  return s;
}

// A DNA fragment (short yarn piece) with adapter tags on both ends.
function fragment(x, y, len, color) {
  return yarn(`M${x} ${y} L${x + len} ${y}`, color || C.blue, 10) +
    adapterTag(x - 18, y, 0.8, 0, C.pink) + adapterTag(x + len + 18, y, 0.8, 0, C.teal);
}

// Camera icon (for "snapshot")
function camera(x, y, s) {
  return g(x, y, s, 0,
    `<rect x="-46" y="-28" width="92" height="62" rx="12" fill="${C.teal}" stroke="${INK}" stroke-width="5"/>` +
    `<rect x="-20" y="-40" width="34" height="16" rx="5" fill="${C.teal}" stroke="${INK}" stroke-width="5"/>` +
    `<circle cx="0" cy="3" r="20" fill="#fff" stroke="${INK}" stroke-width="5"/>` +
    `<circle cx="0" cy="3" r="9" fill="${C.ink}"/><circle cx="30" cy="-16" r="4" fill="${C.yellow}"/>`);
}

// Simple cartoon cell with a nucleus; open marks = list of angles where a "light" is on.
function cell(x, y, s, color, label, lights) {
  let li = '';
  (lights || []).forEach((a, i) => {
    const r = 36, px = Math.cos(a) * r * 0.6, py = Math.sin(a) * r * 0.6;
    li += `<circle cx="${px}" cy="${py}" r="9" fill="${C.yellow}" stroke="${INK}" stroke-width="3"/>`;
  });
  return g(x, y, s, 0,
    `<ellipse cx="0" cy="0" rx="110" ry="92" fill="${color}" stroke="${INK}" stroke-width="5"/>` +
    `<ellipse cx="0" cy="0" rx="52" ry="46" fill="#fff" fill-opacity=".85" stroke="${INK}" stroke-width="4"/>` +
    `<path d="M-38 -8 q10 -14 20 0 t20 0 t20 0 t20 0" fill="none" stroke="${C.blue}" stroke-width="5" stroke-linecap="round"/>` +
    `<path d="M-38 12 q10 -14 20 0 t20 0 t20 0 t20 0" fill="none" stroke="${C.blue}" stroke-width="5" stroke-linecap="round"/>` +
    li +
    `<text x="0" y="128" text-anchor="middle" font-family="PingFang SC" font-weight="700" font-size="30" fill="${INK}">${label}</text>`);
}
