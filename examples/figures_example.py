"""Generate realistic-looking (simulated) result figures in the style of the real tools.
Output: assets/figs/*.png  (these are illustrative, generated from simulated data)."""

from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.textpath import TextPath
from matplotlib.patches import PathPatch
from matplotlib.transforms import Affine2D
from matplotlib.font_manager import FontProperties
from scipy.ndimage import gaussian_filter1d
from scipy.cluster.hierarchy import linkage, dendrogram

OUT = Path(__file__).resolve().parent / "figs"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "Arial", "font.size": 11, "axes.linewidth": 0.8, "savefig.dpi": 200})
rng = np.random.default_rng(7)
SAMPLES = ["Control1", "Control2", "Control3", "Treatment1", "Treatment2", "Treatment3"]
CBLUE, CRED = "#2F6DB5", "#D0453E"


def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


# 1 ------------------------------------------------ FastQC adapter content
def fastqc_adapter():
    x = np.arange(1, 151)
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    for i in range(0, 150, 10):
        if (i // 10) % 2 == 0:
            ax.axvspan(i + 0.5, i + 10.5, color="#EDEDED", lw=0)
    series = {"Illumina Universal Adapter": ("#E41A1C", 0.02), "Illumina Small RNA 3' Adapter": ("#377EB8", 0.0),
              "Illumina Small RNA 5' Adapter": ("#4DAF4A", 0.0), "Nextera Transposase Sequence": ("#984EA3", 0.35),
              "PolyA": ("#FF7F00", 0.05), "PolyG": ("#A65628", 0.03)}
    for lab, (c, top) in series.items():
        y = top * (x / 150) ** 2.2 + np.abs(rng.normal(0, 0.005, x.size))
        ax.plot(x, y, color=c, lw=1.6, label=lab)
    ax.set_ylim(0, 100); ax.set_xlim(0.5, 150.5)
    ax.set_yticks(range(0, 101, 10)); ax.grid(axis="y", color="#CCCCCC", lw=0.6)
    ax.set_xlabel("Position in read (bp)"); ax.set_title("% Adapter", fontsize=12)
    ax.legend(loc="upper right", fontsize=8.5, frameon=True)
    save(fig, "fastqc_adapter.png")


# 2 ------------------------------------------------ FastQC per-base sequence content
def fastqc_content():
    x = np.arange(1, 151)
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    for i in range(0, 150, 10):
        if (i // 10) % 2 == 0:
            ax.axvspan(i + 0.5, i + 10.5, color="#EDEDED", lw=0)
    base = {"%T": ("#E41A1C", 27.5), "%C": ("#377EB8", 22.5), "%A": ("#4DAF4A", 27.5), "%G": ("#222222", 22.5)}
    bias = {"%T": [18, 36, 20, 31, 24, 33, 26, 29, 27], "%C": [31, 17, 28, 20, 26, 20, 24, 22, 23],
            "%A": [22, 30, 27, 33, 25, 28, 27, 27, 27], "%G": [29, 17, 25, 16, 25, 19, 23, 22, 23]}
    for k, (c, lvl) in base.items():
        y = lvl + rng.normal(0, 0.25, x.size)
        y[:9] = bias[k]
        ax.plot(x, y, color=c, lw=1.6, label=k)
    ax.set_ylim(0, 100); ax.set_xlim(0.5, 150.5); ax.set_yticks(range(0, 101, 10))
    ax.grid(axis="y", color="#CCCCCC", lw=0.6)
    ax.set_xlabel("Position in read (bp)"); ax.set_title("Sequence content across all bases", fontsize=12)
    ax.legend(loc="upper right", fontsize=9)
    save(fig, "fastqc_seqcontent.png")


# 3 ------------------------------------------------ ATACseqQC fragment size distribution (6 samples)
def frag_curve(bp, scale=1.0, jitter=0.0):
    nfr = np.exp(-((bp - 55) ** 2) / (2 * 30 ** 2)) * (1 + 0.18 * np.sin(2 * np.pi * bp / 10.4) * np.exp(-bp / 140))
    mono = 0.42 * np.exp(-((bp - 200) ** 2) / (2 * 32 ** 2))
    di = 0.13 * np.exp(-((bp - 395) ** 2) / (2 * 40 ** 2))
    tri = 0.045 * np.exp(-((bp - 590) ** 2) / (2 * 48 ** 2))
    tail = 0.10 * np.exp(-bp / 260)
    y = (nfr + mono + di + tri + tail) * scale
    y = y * (1 + jitter * rng.normal(0, 1, bp.size))
    y[bp < 18] = y[bp < 18] * (bp[bp < 18] / 18) ** 2
    return y


def fragsize():
    bp = np.arange(1, 1001)
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 5.6), sharex=True)
    for ax, s, sc in zip(axes.flat, SAMPLES, [7.4, 7.0, 7.2, 7.8, 7.5, 7.1]):
        y = frag_curve(bp, sc, 0.012)
        ax.plot(bp, y, color="black", lw=0.9)
        ax.set_facecolor("#FFFFFF"); ax.grid(color="#E6E6E6", lw=0.6)
        ax.set_title(s, fontsize=10.5, style="italic", fontweight="bold",
                     bbox=dict(facecolor="#D9D9D9", edgecolor="#888888", boxstyle="square,pad=0.35"), pad=8)
        ax.set_xlim(0, 1000); ax.set_xticks([0, 200, 400, 600, 800, 1000])
        for sp in ax.spines.values():
            sp.set_color("#888888")
    fig.supxlabel("Fragment length (bp)", fontsize=11)
    fig.supylabel("Normalized read density (×10$^{-3}$)", fontsize=11)
    fig.tight_layout()
    save(fig, "fragsize_6samples.png")
    # single-sample good vs bad (for teaching)
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.plot(bp, frag_curve(bp, 7.3, 0.01), color=CBLUE, lw=1.3)
    ax.set_xlim(0, 1000); ax.set_xlabel("Fragment length (bp)"); ax.set_ylabel("Density (×10$^{-3}$)")
    ax.set_title("Control1", fontsize=11); ax.grid(color="#EEEEEE")
    save(fig, "fragment_size_simulated.png")


# 4 ------------------------------------------------ deepTools computeMatrix / plotHeatmap
def tss_heatmap():
    nbin, ngene = 120, 900
    x = np.linspace(-3000, 3000, nbin)
    fig = plt.figure(figsize=(7.2, 8.4))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 3.3], width_ratios=[1, 1, 0.06], hspace=0.12, wspace=0.14)
    strengths = rng.gamma(2.0, 0.5, ngene)
    strengths = np.sort(strengths)[::-1]
    for j, (name, amp) in enumerate([("Control", 1.0), ("Treatment", 1.08)]):
        width = 180 + 60 * rng.random(ngene)
        m = amp * strengths[:, None] * np.exp(-(x[None, :] ** 2) / (2 * width[:, None] ** 2))
        m += 0.25 * amp * strengths[:, None] * np.exp(-((x[None, :] - 180) ** 2) / (2 * 700 ** 2))
        m += rng.gamma(1.2, 0.03, m.shape)
        m = gaussian_filter1d(m, 1.0, axis=1)
        axp = fig.add_subplot(gs[0, j]); axh = fig.add_subplot(gs[1, j])
        axp.plot(x, m.mean(0), color="#1F3A93", lw=1.8, label="genes")
        axp.set_xlim(x[0], x[-1]); axp.set_ylim(0, 1.25); axp.set_xticks([-3000, 0, 3000]); axp.set_xticklabels(["-3.0", "TSS", "3.0Kb"])
        axp.set_title(name, fontsize=12)
        if j == 0:
            axp.set_ylabel("")
        else:
            axp.legend(loc="upper right", frameon=False, fontsize=9); axp.set_yticklabels([])
        im = axh.imshow(m, aspect="auto", cmap="Blues", vmin=0, vmax=1.6, extent=[x[0], x[-1], ngene, 0], interpolation="nearest")
        axh.set_xticks([-3000, 0, 3000]); axh.set_xticklabels(["-3.0", "TSS", "3.0Kb"]); axh.set_yticks([])
        axh.set_xlabel("gene distance (bp)")
        if j == 0:
            axh.set_ylabel("genes")
    cax = fig.add_subplot(gs[1, 2]); fig.colorbar(im, cax=cax)
    save(fig, "tss_heatmap.png")


# 5 ------------------------------------------------ DiffBind correlation heatmap
def corr_heatmap():
    base = rng.normal(0, 1, (6, 400))
    grp = np.array([0, 0, 0, 1, 1, 1])
    sig = rng.normal(0, 1, 400)
    X = base * 0.28 + np.outer(np.where(grp == 1, 1, -1), sig) * 0.55 + rng.normal(0, 1, 400) * 1.0
    C = np.corrcoef(X)
    Z = linkage(X, "average", metric="correlation")
    fig = plt.figure(figsize=(6.6, 6.2))
    axd = fig.add_axes([0.1, 0.8, 0.62, 0.14]); d = dendrogram(Z, ax=axd, no_labels=True, color_threshold=0, above_threshold_color="#444444"); axd.axis("off")
    axl = fig.add_axes([0.0, 0.1, 0.09, 0.62]); dendrogram(Z, ax=axl, orientation="left", no_labels=True, color_threshold=0, above_threshold_color="#444444"); axl.axis("off"); axl.invert_yaxis()
    order = d["leaves"]
    axc = fig.add_axes([0.1, 0.735, 0.62, 0.045])
    axc.imshow([[0 if grp[i] == 0 else 1 for i in order]], cmap=matplotlib.colors.ListedColormap([CBLUE, CRED]), aspect="auto"); axc.axis("off")
    ax = fig.add_axes([0.1, 0.1, 0.62, 0.62])
    im = ax.imshow(C[np.ix_(order, order)], cmap="Greens", vmin=C.min() - 0.02, vmax=1)
    ax.set_xticks(range(6)); ax.set_xticklabels([SAMPLES[i] for i in order], rotation=90)
    ax.set_yticks(range(6)); ax.set_yticklabels([SAMPLES[i] for i in order]); ax.yaxis.tick_right()
    cax = fig.add_axes([0.86, 0.1, 0.03, 0.3]); fig.colorbar(im, cax=cax); cax.set_title("r", fontsize=10)
    save(fig, "corr_heatmap.png")


# 6 ------------------------------------------------ DiffBind PCA
def pca():
    pts = {"Control1": (-38, 9), "Control2": (-43, -6), "Control3": (-35, -2), "Treatment1": (37, 7), "Treatment2": (42, -9), "Treatment3": (34, 1)}
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    for s, (a, b) in pts.items():
        c = CBLUE if s.startswith("Control") else CRED
        ax.scatter(a, b, s=260, color=c, edgecolor="black", lw=0.6, zorder=3)
        ax.annotate(s, (a, b), xytext=(0, -20), textcoords="offset points", ha="center", fontsize=10)
    ax.set_xlim(-65, 65); ax.set_ylim(-28, 26)
    ax.set_xlabel("Principal Component #1 [71%]"); ax.set_ylabel("Principal Component #2 [9%]")
    ax.set_title("PCA: Condition", fontweight="bold")
    ax.scatter([], [], s=120, color=CBLUE, edgecolor="black", label="Control"); ax.scatter([], [], s=120, color=CRED, edgecolor="black", label="Treatment")
    ax.legend(loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.0))
    ax.grid(color="#EEEEEE")
    save(fig, "pca.png")


# 7 ------------------------------------------------ DiffBind volcano
def volcano(name="volcano.png", up_bias=0.0):
    n = 60000
    lfc = rng.normal(0, 0.55, n) + up_bias * np.abs(rng.normal(0, 0.8, n))
    se = 0.18 + 0.12 * rng.random(n)
    z = lfc / se
    from scipy.stats import norm
    p = 2 * norm.sf(np.abs(z))
    order = np.argsort(p); fdr = np.empty(n); rk = np.arange(1, n + 1)
    fdr[order] = np.minimum(1, np.minimum.accumulate((p[order] * n / rk)[::-1])[::-1])
    y = -np.log10(np.maximum(fdr, 1e-60))
    sig = fdr < 0.05
    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    ax.scatter(lfc[~sig], y[~sig], s=3, color="#9E9E9E", alpha=0.5, lw=0, rasterized=True)
    ax.scatter(lfc[sig], y[sig], s=4, color="#D7301F", alpha=0.7, lw=0, rasterized=True)
    ax.axhline(-np.log10(0.05), color="#444444", lw=0.8, ls="--")
    ax.set_xlabel("log Fold Change: Treatment - Control"); ax.set_ylabel("-log10(FDR)")
    nu, nd = int((sig & (lfc > 0)).sum()), int((sig & (lfc < 0)).sum())
    ax.set_title(f"Volcano plot: Treatment vs. Control   (up {nu:,} / down {nd:,})", fontsize=11)
    ax.grid(color="#EEEEEE")
    save(fig, name)


# 8 ------------------------------------------------ ChIPseeker annotation bar + pie
ANNO = [("Promoter (<=1kb)", 23.8, "#A6CEE3"), ("Promoter (1-2kb)", 4.6, "#1F78B4"), ("Promoter (2-3kb)", 3.1, "#B2DF8A"),
        ("5' UTR", 0.4, "#33A02C"), ("3' UTR", 1.7, "#FB9A99"), ("1st Exon", 1.1, "#E31A1C"), ("Other Exon", 3.0, "#FDBF6F"),
        ("1st Intron", 11.9, "#FF7F00"), ("Other Intron", 21.6, "#CAB2D6"), ("Downstream (<=300)", 0.8, "#6A3D9A"),
        ("Distal Intergenic", 28.0, "#FFFF99")]


def anno_bar():
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    left = 0
    for lab, v, c in ANNO:
        ax.barh(0, v, left=left, color=c, edgecolor="white", lw=0.4, label=lab); left += v
    ax.set_xlim(0, 100); ax.set_yticks([]); ax.set_xlabel("Percentage(%)"); ax.set_title("Feature Distribution", loc="left", fontsize=13)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8.5, frameon=False, title="Feature")
    save(fig, "anno_bar.png")
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.pie([v for _, v, _ in ANNO], colors=[c for *_, c in ANNO], startangle=90, counterclock=False,
           wedgeprops=dict(edgecolor="white", lw=0.6))
    ax.legend([f"{l} ({v:.2f}%)" for l, v, _ in ANNO], loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=8.5, frameon=False)
    save(fig, "anno_pie.png")


# 9 ------------------------------------------------ HOMER knownResults-style table with logos
LOGO_COL = {"A": "#1A9641", "C": "#2B83BA", "G": "#F39C12", "T": "#D7191C"}
FP = FontProperties(family="Arial", weight="bold")


def draw_logo(ax, x0, y0, w, h, pwm):
    cw = w / len(pwm)
    for i, col in enumerate(pwm):
        ic = 2 + sum(p * np.log2(p) for p in col.values() if p > 0)
        y = y0
        for b, p in sorted(col.items(), key=lambda kv: kv[1]):
            hh = h * p * ic / 2
            if hh < 0.01 * h:
                continue
            tp = TextPath((0, 0), b, size=1, prop=FP)
            bb = tp.get_extents()
            tr = Affine2D().translate(-bb.x0, -bb.y0).scale(cw * 0.94 / bb.width, hh / bb.height).translate(x0 + i * cw + cw * 0.03, y)
            ax.add_patch(PathPatch(tr.transform_path(tp), color=LOGO_COL[b], lw=0))
            y += hh


IUPAC = {"S": "CG", "W": "AT", "R": "AG", "Y": "CT", "K": "GT", "M": "AC", "N": "ACGT"}


def pwm_from(seq, strength=0.86):
    cols = []
    for ch in seq:
        opts = IUPAC.get(ch, ch)
        d = {b: (1 - strength) / (4 - len(opts)) if len(opts) < 4 else 0.25 for b in "ACGT"}
        for o in opts:
            d[o] = strength / len(opts) if len(opts) < 4 else 0.25
        cols.append(d)
    return cols


def homer_known():
    rows = [("1", "TGASTCA", "AP-1(bZIP)", "1e-312", "38.41%", "12.87%"), ("2", "ATGASTCATN", "Fra1(bZIP)", "1e-298", "31.02%", "9.54%"),
            ("3", "ACAGGAAGTG", "ERG(ETS)", "1e-147", "29.85%", "15.62%"), ("4", "TTCCCACG", "Rbpj1(?)", "1e-66", "24.10%", "16.33%"),
            ("5", "CCTTTGTN", "Sox17(HMG)", "1e-41", "13.67%", "8.92%"), ("6", "NCTGGAATGC", "TEAD(TEA)", "1e-35", "11.20%", "7.02%")]
    fig, ax = plt.subplots(figsize=(10.5, 4.6)); ax.set_xlim(0, 10.5); ax.set_ylim(0, 7.4); ax.axis("off")
    heads = [("Rank", 0.15), ("Motif", 0.85), ("Name", 3.6), ("P-value", 5.6), ("% of Targets", 7.0), ("% of Background", 8.7)]
    ax.add_patch(matplotlib.patches.Rectangle((0, 6.5), 10.5, 0.8, color="#E8E8E8"))
    for t, x in heads:
        ax.text(x, 6.9, t, fontsize=11, fontweight="bold", va="center")
    for i, (rk, seq, name, p, tg, bg) in enumerate(rows):
        y = 5.5 - i * 1.02
        if i % 2:
            ax.add_patch(matplotlib.patches.Rectangle((0, y - 0.1), 10.5, 1.0, color="#F7F7F7"))
        ax.text(0.3, y + 0.4, rk, fontsize=11, va="center")
        draw_logo(ax, 0.85, y, 2.4, 0.82, pwm_from(seq))
        ax.text(3.6, y + 0.4, name, fontsize=11, va="center")
        ax.text(5.6, y + 0.4, p, fontsize=11, va="center")
        ax.text(7.0, y + 0.4, tg, fontsize=11, va="center")
        ax.text(8.7, y + 0.4, bg, fontsize=11, va="center")
    ax.set_title("Known Motif Enrichment Results (up.bed vs consensus_peaks.bed)", fontsize=12, loc="left")
    save(fig, "homer_known.png")


# 10 ------------------------------------------------ HINT-ATAC style footprint profile
def footprint():
    x = np.arange(-100, 101)
    def prof(depth, flank):
        y = 1 + flank * np.exp(-((np.abs(x) - 18) ** 2) / (2 * 9 ** 2)) - depth * np.exp(-(x ** 2) / (2 * 6 ** 2))
        y += 0.25 * np.exp(-(x ** 2) / (2 * 60 ** 2))
        return gaussian_filter1d(y + rng.normal(0, 0.025, x.size), 1.2)
    fig = plt.figure(figsize=(6.6, 4.8))
    ax = fig.add_axes([0.12, 0.3, 0.84, 0.6])
    ax.plot(x, prof(0.55, 0.9), color=CBLUE, lw=1.8, label="Control")
    ax.plot(x, prof(0.85, 1.35), color=CRED, lw=1.8, label="Treatment")
    ax.set_xlim(-100, 100); ax.set_ylabel("Average Tn5 cut count (norm.)"); ax.set_xticklabels([])
    ax.set_title("AP-1 (TGASTCA) footprint", fontsize=12); ax.legend(frameon=False); ax.grid(color="#EEEEEE")
    axl = fig.add_axes([0.12, 0.12, 0.84, 0.16]); axl.set_xlim(-100, 100); axl.set_ylim(0, 1)
    draw_logo(axl, -3.5 * 4, 0.05, 7 * 4, 0.9, pwm_from("TGASTCA", 0.9))
    axl.set_yticks([]); axl.set_xlabel("Distance from motif center (bp)")
    for sp in ["top", "right", "left"]:
        axl.spines[sp].set_visible(False)
    save(fig, "footprint.png")


if __name__ == "__main__":
    fastqc_adapter(); fastqc_content(); fragsize(); tss_heatmap(); corr_heatmap(); pca()
    volcano(); volcano("volcano_lopsided.png", up_bias=0.9); anno_bar(); homer_known(); footprint()
