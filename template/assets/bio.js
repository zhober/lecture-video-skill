// Scientific-schematic drawing helpers (flat, textbook style). All return SVG strings.
const B = {
  ink: '#2B2D42', grey: '#8A8FA3', dna1: '#2F63A8', dna2: '#8FB3E0', rung: '#C3D2E8',
  h2a: '#F6BD60', h2b: '#F28482', h3: '#84A59D', h4: '#A5A6D6',
  tn5: '#2A9D8F', tn5d: '#1F776C', adA: '#E63946', adB: '#3A7BD5',
  tf: '#8E6CC8', tfd: '#6B4FA3', peak: '#E07A5F', peakL: '#F6CDBF',
  gene: '#2B2D42', open: '#FDE9C7', closed: '#E4E1EC', green: '#4FA35A', red: '#E63946',
};

// Straight double-helix DNA from (x1,y) to (x2,y).
function helix(x1, x2, y, amp, period, opts) {
  amp = amp || 9; period = period || 36; opts = opts || {};
  const c1 = opts.c1 || B.dna1, c2 = opts.c2 || B.dna2, w = opts.w || 4;
  let p1 = '', p2 = '', rungs = '';
  const n = Math.max(2, Math.round((x2 - x1) / 3));
  for (let i = 0; i <= n; i++) {
    const x = x1 + (x2 - x1) * i / n, ph = 2 * Math.PI * (x - x1) / period;
    p1 += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + (y + amp * Math.sin(ph)).toFixed(1) + ' ';
    p2 += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + (y - amp * Math.sin(ph)).toFixed(1) + ' ';
  }
  for (let x = x1 + period / 8; x < x2; x += period / 4) {
    const ph = 2 * Math.PI * (x - x1) / period, dy = amp * Math.sin(ph);
    if (Math.abs(dy) > 2) rungs += `<line x1="${x}" y1="${y + dy}" x2="${x}" y2="${y - dy}" stroke="${B.rung}" stroke-width="2"/>`;
  }
  return `<path d="${p2}" fill="none" stroke="${c2}" stroke-width="${w}" stroke-linecap="round"/>` + rungs +
         `<path d="${p1}" fill="none" stroke="${c1}" stroke-width="${w}" stroke-linecap="round"/>`;
}

// Nucleosome: histone octamer (4 visible lobes) with ~1.7 turns of DNA wrapped around.
function nucleosome(x, y, r) {
  r = r || 32;
  const lobe = (dx, dy, c) => `<circle cx="${x + dx}" cy="${y + dy}" r="${r * 0.56}" fill="${c}" stroke="${B.ink}" stroke-width="1.6"/>`;
  const back = `<ellipse cx="${x}" cy="${y + 4}" rx="${r + 9}" ry="${r * 0.5}" transform="rotate(-16 ${x} ${y})" fill="none" stroke="${B.dna2}" stroke-width="7"/>`;
  const front = (dy) => {
    const rx = r + 9, ry = r * 0.5;
    return `<path d="M${x - rx} ${y + dy} A${rx} ${ry} 0 0 0 ${x + rx} ${y + dy}" transform="rotate(-16 ${x} ${y})" fill="none" stroke="${B.dna1}" stroke-width="7" stroke-linecap="round"/>`;
  };
  return back +
    lobe(-r * 0.4, -r * 0.34, B.h3) + lobe(r * 0.4, -r * 0.34, B.h4) +
    lobe(-r * 0.4, r * 0.34, B.h2a) + lobe(r * 0.4, r * 0.34, B.h2b) +
    `<circle cx="${x - r * 0.35}" cy="${y - r * 0.45}" r="${r * 0.16}" fill="#fff" opacity=".55"/>` +
    front(-7) + front(9);
}

// Chromatin fibre: helix linker DNA with nucleosomes at the given x positions.
function chromatin(x1, x2, y, nucXs, r) {
  r = r || 32;
  let s = helix(x1, x2, y, 8, 34);
  nucXs.forEach(nx => s += `<rect x="${nx - r - 12}" y="${y - 14}" width="${2 * r + 24}" height="28" fill="${B.bg || '#FAF8F3'}"/>`);
  nucXs.forEach(nx => s += nucleosome(nx, y, r));
  return s;
}

// Transcription factor bound to DNA at (x, y): protein blob straddling the helix.
function tfProtein(x, y, color, label, s) {
  color = color || B.tf; s = s || 1;
  const body = `<path d="M${x - 26 * s} ${y + 4} C${x - 34 * s} ${y - 30 * s} ${x - 12 * s} ${y - 46 * s} ${x + 4 * s} ${y - 42 * s} C${x + 30 * s} ${y - 40 * s} ${x + 34 * s} ${y - 12 * s} ${x + 24 * s} ${y + 4} Z" fill="${color}" stroke="${B.ink}" stroke-width="2"/>`;
  const grip = `<path d="M${x - 22 * s} ${y + 2} Q${x} ${y + 22 * s} ${x + 22 * s} ${y + 2}" fill="none" stroke="${B.ink}" stroke-width="2"/>` +
               `<path d="M${x - 20 * s} ${y + 2} Q${x} ${y + 19 * s} ${x + 20 * s} ${y + 2}" fill="${color}" opacity=".85"/>`;
  const hl = `<path d="M${x - 16 * s} ${y - 26 * s} Q${x - 10 * s} ${y - 36 * s} ${x} ${y - 36 * s}" fill="none" stroke="#fff" stroke-opacity=".5" stroke-width="3" stroke-linecap="round"/>`;
  const lab = label ? `<text x="${x}" y="${y - 50 * s}" text-anchor="middle" font-size="${20 * s}" font-weight="700" fill="${B.ink}" font-family="PingFang SC">${label}</text>` : '';
  return body + grip + hl + lab;
}

// Tn5 transposome: dimer of Tn5 loaded with two adapters (red / blue). Centred at (x,y), scale s.
function tn5Dimer(x, y, s, withLabels) {
  s = s || 1;
  const adapter = (ax, ay, dir, col) => {
    // short duplex sticking out of the enzyme
    const x2 = ax + dir * 46 * s;
    return `<line x1="${ax}" y1="${ay - 4 * s}" x2="${x2}" y2="${ay - 4 * s}" stroke="${col}" stroke-width="${5 * s}" stroke-linecap="round"/>` +
           `<line x1="${ax}" y1="${ay + 4 * s}" x2="${x2}" y2="${ay + 4 * s}" stroke="${col}" stroke-width="${5 * s}" stroke-linecap="round" opacity=".55"/>`;
  };
  const lobeA = `<ellipse cx="${x - 20 * s}" cy="${y}" rx="${28 * s}" ry="${34 * s}" fill="${B.tn5}" stroke="${B.ink}" stroke-width="2"/>`;
  const lobeB = `<ellipse cx="${x + 20 * s}" cy="${y}" rx="${28 * s}" ry="${34 * s}" fill="${B.tn5}" stroke="${B.ink}" stroke-width="2"/>`;
  const seam = `<path d="M${x} ${y - 30 * s} Q${x - 6 * s} ${y} ${x} ${y + 30 * s}" fill="none" stroke="${B.tn5d}" stroke-width="2"/>`;
  const hl = `<path d="M${x - 36 * s} ${y - 14 * s} Q${x - 30 * s} ${y - 28 * s} ${x - 18 * s} ${y - 30 * s}" fill="none" stroke="#fff" stroke-opacity=".45" stroke-width="${4 * s}" stroke-linecap="round"/>`;
  let lab = '';
  if (withLabels) {
    lab = `<text x="${x - 72 * s}" y="${y + 34 * s}" text-anchor="middle" font-size="${18 * s}" font-weight="700" fill="${B.adA}" font-family="PingFang SC">接头 1</text>` +
          `<text x="${x + 72 * s}" y="${y + 34 * s}" text-anchor="middle" font-size="${18 * s}" font-weight="700" fill="${B.adB}" font-family="PingFang SC">接头 2</text>`;
  }
  return adapter(x - 44 * s, y + 6 * s, -1, B.adA) + adapter(x + 44 * s, y + 6 * s, 1, B.adB) + lobeA + lobeB + seam + hl + lab;
}

// A sequencing fragment: short duplex with red / blue adapter ends.
function seqFragment(x, y, len) {
  return `<line x1="${x}" y1="${y}" x2="${x + 22}" y2="${y}" stroke="${B.adA}" stroke-width="7" stroke-linecap="round"/>` +
         `<line x1="${x + 22}" y1="${y}" x2="${x + len - 22}" y2="${y}" stroke="${B.dna1}" stroke-width="7" stroke-linecap="round"/>` +
         `<line x1="${x + len - 22}" y1="${y}" x2="${x + len}" y2="${y}" stroke="${B.adB}" stroke-width="7" stroke-linecap="round"/>`;
}

// Read arrow (thin): dir 1 = forward (R1), -1 = reverse (R2)
function readArrow(x, y, len, dir, col) {
  const x2 = x + dir * len;
  return `<line x1="${x}" y1="${y}" x2="${x2}" y2="${y}" stroke="${col}" stroke-width="5" stroke-linecap="round"/>` +
         `<path d="M${x2} ${y} l${-dir * 10} -6 M${x2} ${y} l${-dir * 10} 6" stroke="${col}" stroke-width="4" stroke-linecap="round" fill="none"/>`;
}

// Coverage track (genome-browser style). peaks: [[center, height, width], ...] in px.
function coverage(x1, x2, y0, peaks, col, colL, noise) {
  col = col || B.peak; colL = colL || B.peakL; noise = noise == null ? 3 : noise;
  let d = `M${x1} ${y0} `;
  for (let x = x1; x <= x2; x += 3) {
    let h = noise * (1 + Math.sin(x * 0.31) * 0.6 + Math.sin(x * 0.07) * 0.4);
    peaks.forEach(([c, hh, w]) => h += hh * Math.exp(-((x - c) ** 2) / (2 * w * w)));
    d += `L${x} ${(y0 - h).toFixed(1)} `;
  }
  d += `L${x2} ${y0} Z`;
  return `<path d="${d}" fill="${colL}" stroke="${col}" stroke-width="2.5" stroke-linejoin="round"/>` +
         `<line x1="${x1}" y1="${y0}" x2="${x2}" y2="${y0}" stroke="${B.ink}" stroke-width="2"/>`;
}

// Gene model: intron line, exon boxes, TSS bent arrow at x1 (dir +1).
function geneModel(x1, x2, y, exons, name) {
  let s = `<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="${B.gene}" stroke-width="3"/>`;
  exons.forEach(([a, b]) => s += `<rect x="${a}" y="${y - 11}" width="${b - a}" height="22" rx="3" fill="${B.gene}"/>`);
  s += `<path d="M${x1} ${y - 11} L${x1} ${y - 36} L${x1 + 30} ${y - 36}" fill="none" stroke="${B.gene}" stroke-width="3"/>` +
       `<path d="M${x1 + 30} ${y - 36} l-9 -6 v12 z" fill="${B.gene}"/>`;
  if (name) s += `<text x="${x1 + 40}" y="${y - 30}" font-size="22" font-style="italic" font-weight="700" fill="${B.gene}" font-family="PingFang SC">${name}</text>`;
  return s;
}

// Region band label (rounded pill)
function band(x, y, w, h, fill, text, color, stroke) {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${h / 2}" fill="${fill}" ${stroke ? `stroke="${stroke}" stroke-width="2"` : ''}/>` +
         `<text x="${x + w / 2}" y="${y + h / 2 + 9}" text-anchor="middle" font-size="26" font-weight="800" fill="${color || B.ink}" font-family="PingFang SC">${text}</text>`;
}

// Bracket under/over a span with label
function bracket(x1, x2, y, up, label, col, sub) {
  col = col || B.ink;
  const d = up ? -14 : 14;
  let s = `<path d="M${x1} ${y} L${x1} ${y + d} L${x2} ${y + d} L${x2} ${y}" fill="none" stroke="${col}" stroke-width="3" stroke-linejoin="round"/>`;
  const ty = up ? y + d - 12 : y + d + 32;
  s += `<text x="${(x1 + x2) / 2}" y="${ty}" text-anchor="middle" font-size="26" font-weight="800" fill="${col}" font-family="PingFang SC">${label}</text>`;
  if (sub) s += `<text x="${(x1 + x2) / 2}" y="${ty + 28}" text-anchor="middle" font-size="21" font-weight="600" fill="${B.grey}" font-family="PingFang SC">${sub}</text>`;
  return s;
}

function txt(x, y, t, size, color, weight, anchor) {
  return `<text x="${x}" y="${y}" text-anchor="${anchor || 'start'}" font-size="${size || 24}" font-weight="${weight || 700}" fill="${color || B.ink}" font-family="PingFang SC">${t}</text>`;
}

// Hepatocyte-like polygonal cell and neuron outline (for "same DNA, different cells")
function hepatocyte(x, y, s) {
  const pts = [[-90, -40], [-40, -88], [50, -84], [96, -30], [84, 50], [30, 88], [-56, 80], [-100, 24]]
    .map(([a, b]) => `${x + a * s},${y + b * s}`).join(' ');
  return `<polygon points="${pts}" fill="#F9D9CF" stroke="${B.ink}" stroke-width="2.5" stroke-linejoin="round"/>` +
         `<circle cx="${x}" cy="${y}" r="${34 * s}" fill="#fff" stroke="${B.ink}" stroke-width="2"/>`;
}
function neuron(x, y, s) {
  let den = '';
  [[-150, -40], [-120, 60], [-40, -110], [60, -100], [20, 110]].forEach(([a, b]) =>
    den += `<path d="M${x} ${y} Q${x + a * s * 0.5} ${y + b * s * 0.3} ${x + a * s} ${y + b * s}" fill="none" stroke="#9DBBE3" stroke-width="${9 * s}" stroke-linecap="round"/>`);
  const axon = `<path d="M${x} ${y} C${x + 90 * s} ${y + 20 * s} ${x + 140 * s} ${y - 10 * s} ${x + 190 * s} ${y + 30 * s}" fill="none" stroke="#9DBBE3" stroke-width="${8 * s}" stroke-linecap="round"/>`;
  return den + axon + `<circle cx="${x}" cy="${y}" r="${54 * s}" fill="#DCE8F7" stroke="${B.ink}" stroke-width="2.5"/>` +
         `<circle cx="${x}" cy="${y}" r="${28 * s}" fill="#fff" stroke="${B.ink}" stroke-width="2"/>`;
}

// ---------------------------------------------------------------- charts
// Axis frame with ticks. xs/ys: arrays of [value, label]; map functions supplied by caller.
function axes(x, y, w, h, xlabel, ylabel) {
  return `<line x1="${x}" y1="${y + h}" x2="${x + w}" y2="${y + h}" stroke="${B.ink}" stroke-width="2.5"/>` +
         `<line x1="${x}" y1="${y}" x2="${x}" y2="${y + h}" stroke="${B.ink}" stroke-width="2.5"/>` +
         (xlabel ? txt(x + w / 2, y + h + 48, xlabel, 22, B.ink, 700, 'middle') : '') +
         (ylabel ? `<text transform="translate(${x - 44},${y + h / 2}) rotate(-90)" text-anchor="middle" font-size="22" font-weight="700" fill="${B.ink}" font-family="PingFang SC">${ylabel}</text>` : '');
}
function xticks(x, y, w, h, maxv, ticks) {
  let s = '';
  ticks.forEach(v => {
    const px = x + w * v / maxv;
    s += `<line x1="${px}" y1="${y + h}" x2="${px}" y2="${y + h + 8}" stroke="${B.ink}" stroke-width="2"/>` + txt(px, y + h + 28, String(v), 18, B.grey, 700, 'middle');
  });
  return s;
}

// Fragment-length distribution. good=true -> periodic nucleosome ladder; false -> smooth decay.
function fragLenCurve(x, y, w, h, good, color, maxbp) {
  maxbp = maxbp || 1000; color = color || B.dna1;
  const f = bp => {
    if (!good) return 0.9 * Math.exp(-bp / 170) + 0.02;
    return 1.0 * Math.exp(-((bp - 60) ** 2) / (2 * 28 ** 2)) + 0.55 * Math.exp(-((bp - 195) ** 2) / (2 * 30 ** 2)) +
           0.22 * Math.exp(-((bp - 390) ** 2) / (2 * 36 ** 2)) + 0.09 * Math.exp(-((bp - 590) ** 2) / (2 * 42 ** 2)) +
           0.25 * Math.exp(-bp / 140) + 0.012;
  };
  let d = '', mx = 0;
  for (let bp = 20; bp <= maxbp; bp += 4) mx = Math.max(mx, f(bp));
  for (let bp = 20; bp <= maxbp; bp += 4) {
    const px = x + w * bp / maxbp, py = y + h - h * 0.92 * f(bp) / mx;
    d += (bp === 20 ? 'M' : 'L') + px.toFixed(1) + ' ' + py.toFixed(1) + ' ';
  }
  return `<path d="${d} L${x + w} ${y + h} L${x + w * 20 / maxbp} ${y + h} Z" fill="${color}" fill-opacity=".14"/>` +
         `<path d="${d}" fill="none" stroke="${color}" stroke-width="4" stroke-linejoin="round"/>`;
}

// TSS heatmap + mean profile. good=true -> sharp centre enrichment.
function tssHeatmap(x, y, w, h, strength, color, title) {
  strength = strength == null ? 1 : strength; color = color || '#1F4E9A';
  const rows = 40, cols = 60;
  let cells = '';
  const rgb = [parseInt(color.slice(1, 3), 16), parseInt(color.slice(3, 5), 16), parseInt(color.slice(5, 7), 16)];
  for (let r = 0; r < rows; r++) {
    const rs = strength * (1 - r / rows) ** 1.3;
    for (let c = 0; c < cols; c++) {
      const u = (c - cols / 2 + 0.5) / (cols / 2);
      let v = rs * Math.exp(-(u * u) / (2 * 0.07 * 0.07)) + 0.06 * Math.abs(Math.sin(r * 7.3 + c * 1.7));
      v = Math.min(1, v);
      const col = rgb.map(k => Math.round(255 - (255 - k) * v));
      cells += `<rect x="${(x + c * w / cols).toFixed(1)}" y="${(y + r * h / rows).toFixed(1)}" width="${(w / cols + 0.6).toFixed(1)}" height="${(h / rows + 0.6).toFixed(1)}" fill="rgb(${col})"/>`;
    }
  }
  return cells + `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="none" stroke="${B.ink}" stroke-width="2"/>` +
    (title ? txt(x + w / 2, y - 12, title, 22, B.ink, 800, 'middle') : '') +
    txt(x, y + h + 26, '-3kb', 18, B.grey, 700, 'start') + txt(x + w / 2, y + h + 26, 'TSS', 18, B.ink, 800, 'middle') + txt(x + w, y + h + 26, '+3kb', 18, B.grey, 700, 'end');
}
function tssProfile(x, y, w, h, strength, color) {
  color = color || B.dna1;
  let d = '';
  for (let i = 0; i <= 100; i++) {
    const u = (i - 50) / 50, v = 0.12 + strength * Math.exp(-(u * u) / (2 * 0.08 * 0.08)) * 0.85;
    d += (i ? 'L' : 'M') + (x + w * i / 100).toFixed(1) + ' ' + (y + h - h * v).toFixed(1) + ' ';
  }
  return `<path d="${d}" fill="none" stroke="${color}" stroke-width="4" stroke-linejoin="round"/>`;
}

// PCA scatter: groups = [{name, color, pts:[[px,py],...]}] in local px within (x,y,w,h)
function pcaPlot(x, y, w, h, groups, xl, yl) {
  let s = `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#fff" stroke="${B.ink}" stroke-width="2"/>`;
  s += `<line x1="${x}" y1="${y + h / 2}" x2="${x + w}" y2="${y + h / 2}" stroke="#E5E0D6" stroke-width="2"/>` +
       `<line x1="${x + w / 2}" y1="${y}" x2="${x + w / 2}" y2="${y + h}" stroke="#E5E0D6" stroke-width="2"/>`;
  groups.forEach(gp => gp.pts.forEach(([px, py], i) => {
    s += `<circle cx="${x + px}" cy="${y + py}" r="13" fill="${gp.color}" stroke="${B.ink}" stroke-width="2"/>`;
    if (gp.labels) s += txt(x + px + 18, y + py + 7, gp.labels[i], 18, B.ink, 700);
  }));
  s += txt(x + w / 2, y + h + 34, xl || 'PC1', 22, B.ink, 800, 'middle');
  s += `<text transform="translate(${x - 18},${y + h / 2}) rotate(-90)" text-anchor="middle" font-size="22" font-weight="800" fill="${B.ink}" font-family="PingFang SC">${yl || 'PC2'}</text>`;
  return s;
}

// Volcano plot (deterministic pseudo-random points)
function volcano(x, y, w, h, thrY) {
  let s = `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#fff" stroke="${B.ink}" stroke-width="2"/>`;
  thrY = thrY || 0.62;
  for (let i = 0; i < 420; i++) {
    const a = Math.sin(i * 12.9898) * 43758.5453, r1 = a - Math.floor(a);
    const b = Math.sin(i * 78.233) * 12345.678, r2 = b - Math.floor(b);
    const fc = (r1 - 0.5) * 2 * (0.3 + r2), sig = 0.92 * (1 - Math.exp(-2.6 * (Math.abs(fc) ** 1.5) * (0.4 + 1.2 * r2))) + 0.04 * r1;
    const px = x + w / 2 + fc * w * 0.42, py = y + h - 8 - sig * (h - 20);
    const up = fc > 0.25 && sig > 1 - thrY, dn = fc < -0.25 && sig > 1 - thrY;
    s += `<circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="4.5" fill="${up ? B.peak : dn ? B.adB : '#C9C4BA'}" opacity=".85"/>`;
  }
  const ty = y + h - 8 - (1 - thrY) * (h - 20);
  s += `<line x1="${x}" y1="${ty}" x2="${x + w}" y2="${ty}" stroke="${B.ink}" stroke-width="2" stroke-dasharray="6 6"/>`;
  s += txt(x + w / 2, y + h + 32, 'log2 Fold（Treatment / Control）', 20, B.ink, 700, 'middle');
  s += `<text transform="translate(${x - 16},${y + h / 2}) rotate(-90)" text-anchor="middle" font-size="20" font-weight="700" fill="${B.ink}" font-family="PingFang SC">-log10 FDR</text>`;
  return s;
}

// Pie chart. slices: [[label, fraction, color], ...]
function pie(cx, cy, r, slices, legendX, legendY) {
  let s = '', a0 = -Math.PI / 2, leg = '';
  slices.forEach(([lab, f, col], i) => {
    const a1 = a0 + f * 2 * Math.PI, large = f > 0.5 ? 1 : 0;
    const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0), x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    s += `<path d="M${cx} ${cy} L${x0} ${y0} A${r} ${r} 0 ${large} 1 ${x1} ${y1} Z" fill="${col}" stroke="#fff" stroke-width="3"/>`;
    if (legendX != null) leg += `<rect x="${legendX}" y="${legendY + i * 40 - 16}" width="22" height="22" rx="4" fill="${col}"/>` + txt(legendX + 32, legendY + i * 40 + 2, `${lab}  ${Math.round(f * 100)}%`, 22, B.ink, 700);
    a0 = a1;
  });
  return s + leg;
}

// Sequence logo: cols = [{A:.1,C:.1,G:.7,T:.1}, ...]
function seqLogo(x, y, colW, h, cols) {
  const colr = { A: '#2E9E4F', C: '#2F63A8', G: '#E8A317', T: '#D1453B' };
  let s = '';
  cols.forEach((c, i) => {
    const ic = 2 + Object.values(c).reduce((a, p) => a + (p > 0 ? p * Math.log2(p) : 0), 0);
    let yy = y + h;
    Object.entries(c).sort((a, b) => a[1] - b[1]).forEach(([base, p]) => {
      const hh = h * p * ic / 2;
      if (hh < 10) return;
      s += `<text x="0" y="0" font-family="Helvetica, Arial" font-weight="900" font-size="100" fill="${colr[base]}" text-anchor="middle" ` +
           `transform="translate(${x + i * colW + colW / 2},${yy}) scale(${colW / 70},${hh / 72})">${base}</text>`;
      yy -= hh;
    });
  });
  return s + `<line x1="${x}" y1="${y + h}" x2="${x + cols.length * colW}" y2="${y + h}" stroke="${B.ink}" stroke-width="2"/>`;
}

// Footprint profile: flanks raised, dip at the motif centre
function footprintCurve(x, y, w, h, depth, color) {
  depth = depth == null ? 1 : depth; color = color || B.tf;
  let d = '';
  for (let i = 0; i <= 120; i++) {
    const u = (i - 60) / 60;
    const v = 0.35 + 0.35 * Math.exp(-((Math.abs(u) - 0.28) ** 2) / (2 * 0.1 ** 2)) - depth * 0.28 * Math.exp(-(u * u) / (2 * 0.07 ** 2)) + 0.03 * Math.sin(i * 1.3);
    d += (i ? 'L' : 'M') + (x + w * i / 120).toFixed(1) + ' ' + (y + h - h * v).toFixed(1) + ' ';
  }
  return `<path d="${d}" fill="none" stroke="${color}" stroke-width="4" stroke-linejoin="round"/>`;
}

// Quiz countdown badge
function countdown(x, y, n) {
  return `<circle cx="${x}" cy="${y}" r="46" fill="#fff" stroke="${B.peak}" stroke-width="8"/>` + txt(x, y + 18, String(n), 52, B.peak, 900, 'middle');
}
