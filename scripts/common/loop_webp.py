#!/usr/bin/env python3
"""Animated-WebP probe / seamless-loop remake.

Three subcommands, all verified on Windows + Pillow 13 (bundled libwebp):

  probe  SOURCE.webp          read real frame timing, canvas, ring geometry, colours,
                              and whether the source actually loops (or resets mid-way)
  make   SOURCE.webp -o OUT   redraw the same assets as a seamless loop
  check  OUT.webp [--src SRC] verify frame count / duration / loop flag / seam continuity

Why redraw instead of editing frames: when the artwork is pure geometry (ring, arc,
stroke), an analytic distance-field rasteriser gives vector-grade edges and lets us
place the motion exactly where the loop seam has to be, instead of patching pixels.

Motion model (both invariants are what makes the loop seamless):
  leading edge  theta(t) = start + 360 * turns * t          <- constant angular speed
  arc length    L(t)     = lmin + (lmax - lmin) * (0.5 - 0.5*cos(2*pi*cycles*t))
  trailing edge = theta(t) - L(t)
  seamless  <=> turns and cycles are integers
  no crawl  <=> 360*turns - (lmax - lmin)*pi*cycles >= 0
"""

from __future__ import annotations

import argparse
import math
import struct
import sys

import numpy as np
from PIL import Image

SS = 4  # supersampling factor
FG_ALPHA_ON = 200
TRACK_ALPHA_MAX = 60


# --------------------------------------------------------------------------- riff
def read_anim(path):
    """Return (n_frames, durations_ms, loop_count) by parsing ANMF chunks directly."""
    raw = open(path, "rb").read()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
        raise SystemExit(f"not a WebP: {path}")
    pos, durs, loop = 12, [], None
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        if cid == b"ANIM":
            loop = struct.unpack("<H", raw[pos + 12:pos + 14])[0]
        elif cid == b"ANMF":
            durs.append(struct.unpack("<I", raw[pos + 20:pos + 23] + b"\x00")[0])
        pos += 8 + size + (size & 1)
    return len(durs), durs, loop


def frames_of(path):
    im = Image.open(path)
    out = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        out.append(np.array(im.convert("RGBA")))
    return out


# ------------------------------------------------------------------------ measure
def centreline_profile(a, cx, cy, radius, samples=2880):
    """Alpha sampled on the ring centreline -> (on_mask, angles_deg)."""
    ang = np.arange(samples) * 360.0 / samples
    rad = np.radians(ang)
    xs, ys = cx + radius * np.cos(rad), cy + radius * np.sin(rad)
    x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
    fx, fy = xs - x0, ys - y0
    al = a[:, :, 3].astype(np.float64) / 255.0
    v = (al[y0, x0] * (1 - fx) * (1 - fy) + al[y0, x0 + 1] * fx * (1 - fy)
         + al[y0 + 1, x0] * (1 - fx) * fy + al[y0 + 1, x0 + 1] * fx * fy)
    return v > 0.5, ang, v


def _kasa(pts):
    """Algebraic (Kasa) circle fit: returns (cx, cy, R)."""
    x, y = pts[:, 0], pts[:, 1]
    a = np.c_[2 * x, 2 * y, np.ones(len(x))]
    b = x ** 2 + y ** 2
    sol, *_ = np.linalg.lstsq(a, b, rcond=None)
    cx, cy = float(sol[0]), float(sol[1])
    return cx, cy, math.sqrt(max(sol[2] + cx ** 2 + cy ** 2, 0.0))


def fit_ring(a):
    """Sub-pixel fit of (centre, centre radius, stroke width) from the fullest frame.

    Iterates: the alpha centroid is biased for a partial arc, so after each pass we
    re-centre with a Kasa circle fit through the per-angle stroke midpoints.
    """
    al = a[:, :, 3].astype(np.float64) / 255.0
    h, w = al.shape
    ys, xs = np.mgrid[0:h, 0:w]
    cx = (al * xs).sum() / al.sum() + 0.5
    cy = (al * ys).sum() / al.sum() + 0.5
    edges = np.linspace(-np.pi, np.pi, 181)
    stroke = 0.0
    for _ in range(4):
        rad = np.hypot(xs + 0.5 - cx, ys + 0.5 - cy)
        ang = np.arctan2(ys + 0.5 - cy, xs + 0.5 - cx)
        idx = np.digitize(ang, edges)
        mids, widths = [], []
        for b in range(1, 181):
            m = (idx == b) & (al > 0.02)
            if m.sum() < 3:
                continue
            r, v = rad[m], al[m]
            o = np.argsort(r)
            r, v = r[o], v[o]
            if v.max() < 0.9:
                continue
            on = np.where(v > 0.5)[0]
            lo, hi = on[0], on[-1]
            if hi + 1 >= len(r) or lo - 1 < 0:
                continue
            ro = r[hi] + (0.5 - v[hi]) / (v[hi + 1] - v[hi]) * (r[hi + 1] - r[hi])
            ri = r[lo] - (0.5 - v[lo]) / (v[lo - 1] - v[lo]) * (r[lo] - r[lo - 1])
            widths.append(ro - ri)
            theta = (edges[b - 1] + edges[b]) / 2
            rm = (ro + ri) / 2
            mids.append((cx + rm * math.cos(theta), cy + rm * math.sin(theta)))
        if len(mids) < 6:
            break
        cx, cy, radius = _kasa(np.array(mids))
        stroke = float(np.mean(widths))
    return cx, cy, radius, stroke


def probe(path):
    n, durs, loop = read_anim(path)
    frames = frames_of(path)
    h, w = frames[0].shape[:2]
    areas = [f[:, :, 3].astype(np.float64).sum() / 255 for f in frames]
    fullest = frames[int(np.argmax(areas))]
    cx, cy, radius, stroke = fit_ring(fullest)

    # colours: sample on the centreline of the sparsest frame -> pure track where "off"
    sparsest = frames[int(np.argmin(areas))]
    on, ang, _ = centreline_profile(sparsest, cx, cy, radius)
    rad = np.radians(ang)
    xs = np.clip((cx + radius * np.cos(rad)).astype(int), 0, w - 1)
    ys = np.clip((cy + radius * np.sin(rad)).astype(int), 0, h - 1)
    px = sparsest[ys, xs]

    def modal(mask):
        sel = px[mask]
        if len(sel) == 0:
            return None
        cols, cnt = np.unique(sel, axis=0, return_counts=True)
        return cols[int(np.argmax(cnt))]

    def median_colour(mask):
        """Median over samples whose alpha equals the modal alpha.

        Lossy exports leave the semi-transparent track with 1-3 levels of RGB noise
        around the design token; the alpha is stable, the RGB needs smoothing.
        """
        sel = px[mask]
        if len(sel) == 0:
            return None, 0
        alphas, counts = np.unique(sel[:, 3], return_counts=True)
        a_mode = int(alphas[int(np.argmax(counts))])
        keep = sel[np.abs(sel[:, 3].astype(int) - a_mode) <= 0]
        rgb = np.median(keep[:, :3].astype(float), axis=0)
        return np.rint(rgb).astype(int), a_mode

    track_rgb, track_alpha = median_colour((~on) & (px[:, 3] > 0) & (px[:, 3] <= TRACK_ALPHA_MAX))
    fg = modal(on & (px[:, 3] >= FG_ALPHA_ON))
    if fg is None:
        m = fullest[:, :, 3] >= FG_ALPHA_ON
        cols, cnt = np.unique(fullest[m], axis=0, return_counts=True)
        fg = cols[int(np.argmax(cnt))]

    steps = [abs(areas[i + 1] - areas[i]) for i in range(len(areas) - 1)]
    mean_step = float(np.mean(steps)) if steps else 0.0
    worst = int(np.argmax(steps)) if steps else 0

    # smallest repeating block of the coverage curve -> catches "same clip x N" exports
    tol = max(1.0, 0.02 * max(areas))
    cycle = n
    for p in range(1, n // 2 + 1):
        if all(abs(areas[i + p] - areas[i]) <= tol for i in range(n - p)):
            cycle = p
            break
    cycle_ms = sum(durs[:cycle])

    return {
        "frames": n, "durations": durs, "total_ms": sum(durs), "loop": loop,
        "canvas": (w, h), "centre": (cx, cy), "radius": radius, "stroke": stroke,
        "fg": tuple(int(v) for v in fg[:3]) if fg is not None else None,
        "track": tuple(int(v) for v in track_rgb[:3]) if track_rgb is not None else None,
        "track_alpha": int(track_alpha),
        "area_min": min(areas), "area_max": max(areas),
        "step_mean": mean_step, "step_max": max(steps) if steps else 0.0,
        "reset_at": worst + 1,
        "cycle_frames": cycle, "cycle_ms": cycle_ms,
    }


# ------------------------------------------------------------------------- render
class Ring:
    def __init__(self, canvas, centre, radius, stroke, fg, track, track_alpha):
        self.w, self.h = canvas
        self.cx, self.cy = centre
        self.r, self.half = radius, stroke / 2.0
        self.fg, self.track = np.array(fg, np.float64), np.array(track, np.float64)
        self.track_a = track_alpha / 255.0
        n = self.w * SS
        xs = (np.arange(n) + 0.5) / SS
        ys = (np.arange(n) + 0.5) / SS
        px, py = xs[None, :] - self.cx, ys[:, None] - self.cy
        self.xs, self.ys = xs, ys
        self.rho = np.hypot(px, py)
        self.ang = np.degrees(np.arctan2(py, px))
        self.track_cov = self._cov(np.abs(self.rho - self.r))

    def _down(self, g):
        return g.reshape(self.h, SS, self.w, SS).mean(axis=(1, 3))

    def _cov(self, d):
        return self._down(np.clip(0.5 - (d - self.half) * SS, 0.0, 1.0))

    def arc_cov(self, a0, a1):
        span = (a1 - a0) % 360.0
        if span == 0.0:
            return np.zeros((self.h, self.w))
        d = np.abs(self.rho - self.r)
        if span < 359.999:
            inside = ((self.ang - a0) % 360.0) <= span
            c = [(self.cx + self.r * math.cos(math.radians(a)),
                  self.cy + self.r * math.sin(math.radians(a))) for a in (a0, a1)]
            dcap = np.minimum(np.hypot(self.xs[None, :] - c[0][0], self.ys[:, None] - c[0][1]),
                              np.hypot(self.xs[None, :] - c[1][0], self.ys[:, None] - c[1][1]))
            d = np.where(inside, d, dcap)
        return self._cov(d)

    def frame(self, t, turns, cycles, lmin, lmax):
        head = -90.0 + 360.0 * turns * t
        k = 0.5 - 0.5 * math.cos(2.0 * math.pi * cycles * t)
        a_arc = self.arc_cov(head - (lmin + (lmax - lmin) * k), head)
        a_trk = self.track_a * self.track_cov
        alpha = a_arc + a_trk * (1.0 - a_arc)
        safe = np.maximum(alpha, 1e-9)
        rgb = self.fg * (a_arc / safe)[..., None] + self.track * (a_trk * (1.0 - a_arc) / safe)[..., None]
        out = np.empty((self.h, self.w, 4), np.uint8)
        out[:, :, :3] = np.rint(np.clip(rgb, 0, 255)).astype(np.uint8)
        out[:, :, 3] = np.rint(np.clip(alpha, 0, 1) * 255).astype(np.uint8)
        out[out[:, :, 3] == 0] = 0
        return Image.fromarray(out, "RGBA")


def make(args):
    info = probe(args.src)
    turns = args.turns
    cycles = args.cycles
    if turns <= 0 or cycles <= 0:
        raise SystemExit("turns/cycles must be positive integers for a seamless loop")
    runway = 360.0 * turns - (args.lmax - args.lmin) * math.pi * cycles
    if runway < 0:
        print(f"WARN tail crawls backwards (360*turns - A*pi*cycles = {runway:.1f}); "
              f"raise --turns or lower --lmax", file=sys.stderr)

    ring = Ring(args.canvas or info["canvas"],
                args.centre or info["centre"],
                args.radius or info["radius"],
                args.stroke or info["stroke"],
                args.fg or info["fg"],
                args.track or (info["track"] or info["fg"]),
                args.track_alpha if args.track_alpha is not None else info["track_alpha"])
    total = args.ms or info["total_ms"] or 3000
    n = int(round(total / 1000.0 * args.fps))
    frames = [ring.frame(i / n, turns, cycles, args.lmin, args.lmax) for i in range(n)]
    edges = [round(total * i / n) for i in range(n + 1)]
    durs = [edges[i + 1] - edges[i] for i in range(n)]
    frames[0].save(args.out, "WEBP", save_all=True, append_images=frames[1:],
                   duration=durs, loop=0, lossless=True, exact=True,
                   quality=100, method=6, minimize_size=True)
    print(f"wrote {args.out}: {n} frames, {sum(durs)} ms, turns={turns}, cycles={cycles}, "
          f"arc {args.lmin:g}-{args.lmax:g} deg, tail runway {runway:.0f} deg/loop")
    return 0


def on_background(f, bg=128.0):
    """Composite RGBA over a flat background -> what a viewer actually sees.

    Raw RGBA diffing is misleading: libwebp restores RGB under alpha=0 on key frames,
    so invisible pixels can differ by 250 while the rendered frame is identical.
    """
    a = f[:, :, 3:4].astype(np.float64) / 255.0
    return f[:, :, :3].astype(np.float64) * a + bg * (1.0 - a)


def check(args):
    n, durs, loop = read_anim(args.out)
    frames = frames_of(args.out)
    h, w = frames[0].shape[:2]
    areas = [f[:, :, 3].astype(np.float64).sum() / 255 for f in frames]
    cx, cy, radius, _ = fit_ring(frames[int(np.argmax(areas))])

    heads, tails, lens = [], [], []
    for f in frames:
        on, ang, _ = centreline_profile(f, cx, cy, radius)
        off = np.where(~on)[0]
        if len(off) == 0:
            continue
        runs, start, prev = [], off[0], off[0]
        for j in off[1:]:
            if j != prev + 1:
                runs.append((start, prev))
                start = j
            prev = j
        runs.append((start, prev))
        if runs[0][0] == 0 and runs[-1][1] == len(ang) - 1 and len(runs) > 1:
            runs[0] = (runs[-1][0] - len(ang), runs[0][1])
            runs.pop()
        g0, g1 = max(runs, key=lambda r: (r[1] - r[0]) % len(ang))
        t0 = (g1 + 1) % len(ang)
        t1 = (g0 - 1) % len(ang)
        tails.append(t0 * 360.0 / len(ang))
        heads.append(t1 * 360.0 / len(ang))
        lens.append(((t1 - t0) % len(ang) + 1) * 360.0 / len(ang))

    def unwrap(seq):
        out = [seq[0]]
        for v in seq[1:]:
            out.append(out[-1] + ((v - out[-1] + 180) % 360 - 180))
        return np.array(out)

    hd, tl = unwrap(heads), unwrap(tails)
    vis = [on_background(f) for f in frames]
    steps = [np.abs(vis[i + 1] - vis[i]).mean() for i in range(len(vis) - 1)]
    seam = np.abs(vis[0] - vis[-1]).mean()

    print(f"file        {args.out}")
    print(f"canvas      {w}x{h}   frames {n}   total {sum(durs)} ms   loop {loop}")
    print(f"durations   {sorted(set(durs))}")
    print(f"arc length  {min(lens):.1f} - {max(lens):.1f} deg")
    if max(lens) >= 359.0:
        print(            "            source fills a whole circle -> expect a hard reset, not a loop")
    print(f"head step   {np.diff(hd).mean():.2f} deg/frame (constant => steady rotation)")
    print(f"tail step   {np.diff(tl).min():.2f} - {np.diff(tl).max():.2f} deg/frame (>=0 => no crawl)")
    worst = int(np.argmax(steps))
    print(f"frame step  mean {np.mean(steps):.2f}  max {np.max(steps):.2f} at frame {worst + 1}")
    print(f"SEAM        {seam:.2f}  ({seam / max(np.mean(steps), 1e-6):.2f}x mean step)")

    mean_step = float(np.mean(steps))
    if np.max(steps) > 3 * mean_step:
        print(f"VERDICT     NOT A LOOP: frame {worst + 1} jumps "
              f"{np.max(steps) / mean_step:.0f}x the mean step")
    elif seam > 1.5 * mean_step:
        print(f"VERDICT     SEAM HITCH: wrap jumps {seam / mean_step:.1f}x the mean step")
    else:
        print("VERDICT     LOOP OK: wrap is indistinguishable from a normal frame step")

    if args.src:
        src = probe(args.src)
        same = abs(src["radius"] - radius) < 0.5
        print(f"vs source   R {src['radius']:.2f} vs {radius:.2f} "
              f"({'geometry matches' if same else 'DIFFERENT footprint'})")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="read timing + geometry + colours")
    p.add_argument("src")

    m = sub.add_parser("make", help="redraw as a seamless loop")
    m.add_argument("src")
    m.add_argument("-o", "--out", required=True)
    m.add_argument("--turns", type=int, default=3, help="full turns per loop (integer)")
    m.add_argument("--cycles", type=int, default=1, help="grow/shrink cycles per loop (integer)")
    m.add_argument("--lmin", type=float, default=40.0, help="min arc length, deg")
    m.add_argument("--lmax", type=float, default=266.0, help="max arc length, deg")
    m.add_argument("--fps", type=int, default=60)
    m.add_argument("--ms", type=int, default=0, help="total duration; 0 = copy from source")
    m.add_argument("--canvas", type=int, nargs=2)
    m.add_argument("--centre", type=float, nargs=2)
    m.add_argument("--radius", type=float)
    m.add_argument("--stroke", type=float)
    m.add_argument("--fg", type=int, nargs=3)
    m.add_argument("--track", type=int, nargs=3)
    m.add_argument("--track-alpha", type=int, dest="track_alpha")

    c = sub.add_parser("check", help="verify loop quality")
    c.add_argument("out")
    c.add_argument("--src")

    args = ap.parse_args()
    if args.cmd == "probe":
        info = probe(args.src)
        for k in ("canvas", "frames", "total_ms", "loop", "cycle_frames", "cycle_ms",
                  "centre", "radius", "stroke", "fg", "track", "track_alpha",
                  "area_min", "area_max", "step_mean", "step_max", "reset_at"):
            value = info[k]
            if isinstance(value, tuple) and value and hasattr(value[0], "item"):
                value = tuple(round(float(v), 2) for v in value)
            print(f"{k:<12} {value}")
        if info["step_max"] > info["step_mean"] * 3:
            print(f"\nNOTE frame {info['reset_at']} is a hard reset "
                  f"(step {info['step_max']:.0f} vs mean {info['step_mean']:.0f}) -> not a loop")
        if info["cycle_frames"] < info["frames"]:
            print(f"NOTE coverage repeats every {info['cycle_frames']} frames "
                  f"({info['cycle_ms']} ms) -> pass --ms {info['cycle_ms']} if one cycle is the intent")
    elif args.cmd == "make":
        return make(args)
    else:
        return check(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
