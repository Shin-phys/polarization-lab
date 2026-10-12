#!/usr/bin/env python3
"""偏光ラボ 検証キットの記録（CSV）を解析する。

使い方
  python analyze.py 記録.csv                 # G で解析
  python analyze.py 記録.csv --ch all        # R・G・B それぞれで解析
  python analyze.py 記録.csv --base hole1    # 位相の基準にする枠を指定
  python analyze.py 記録.csv --plot          # グラフを PNG で保存（matplotlib が要る）
  python analyze.py --demo                   # 模擬データを作って解析する（答えが分かっている）

出すもの（docs/07-verification-kit.md）
  - コマの間隔と回転むら（POL-Q-03 の目安）
  - 各枠の変動の深さ m と、基準に残る偏光 p/m（POL-Q-01）
  - 旋光角の推定法の比較（POL-Q-21）
      A：時間波形への正弦波の当てはめ
      B：リサージュ図形の符号付き面積
      C：角度軸の成分（印の検出が要るので、この版では未実装）
    それぞれ、補正なしの値と、ガンマ 2.2 で逆補正した値で求める。
  - 基準との比を取った場合と取らない場合の比較（POL-Q-22）

必要なもの：Python 3.8 以上、numpy（グラフを出すときは matplotlib）
"""
import argparse
import json
import math
import sys

import numpy as np

CH_INDEX = {"R": 0, "G": 1, "B": 2}


# ---------------------------------------------------------------- 読み込み
def load_csv(path):
    meta, header, rows = {}, None, []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("#"):
                body = line[1:].strip()
                if ":" in body:
                    k, v = body.split(":", 1)
                    meta[k.strip()] = v.strip()
                continue
            if header is None:
                header = line.split(",")
                continue
            rows.append([float(x) if x not in ("", "NaN") else np.nan for x in line.split(",")])
    if header is None or not rows:
        raise SystemExit("データ行がありません: " + path)
    data = np.array(rows, dtype=float)
    cols = {name: data[:, i] for i, name in enumerate(header)}
    labels = [h[:-2] for h in header if h.endswith("_R")]
    return meta, cols, labels


def role_of(label):
    for p in ("ref", "hole", "blank"):
        if label.startswith(p):
            return p
    return "sample"


# ---------------------------------------------------------------- 当てはめ
def design(t, f, tc):
    w = 2 * math.pi * f
    return np.column_stack([
        np.ones_like(t), t - tc,
        np.cos(w * t), np.sin(w * t),            # 1回転に2回（cos² の成分）
        np.cos(w * t / 2), np.sin(w * t / 2),    # 1回転に1回（画面のむら）
    ])


def fit(t, y, f):
    """y = c0 + c1 (t - tc) + A cos(2πft - φ) + (1回転に1回の項) を当てはめる。"""
    tc = t.mean()
    X = design(t, f, tc)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    a, b = coef[2], coef[3]
    amp = math.hypot(a, b)
    phase = math.atan2(b, a)
    resid = y - X @ coef
    return {"c0": coef[0], "amp": amp, "phase": phase, "rms": float(np.sqrt(np.mean(resid ** 2))),
            "model_slow": X[:, :2] @ coef[:2] + X[:, 4:] @ coef[4:]}


def amp_at(t, y, f):
    w = 2 * math.pi * f
    X = np.column_stack([np.ones_like(t), t - t.mean(), np.cos(w * t), np.sin(w * t)])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return math.hypot(coef[2], coef[3])


def estimate_freq(t, y):
    """cos² の振動数（1回転に2回）を、当てはめの振幅が最大になる振動数として求める。"""
    dur = t[-1] - t[0]
    dt = np.median(np.diff(t))
    fmin, fmax = 1.2 / dur, min(5.0, 0.25 / dt)
    if fmax <= fmin:
        raise SystemExit("記録が短すぎます。")
    grid = np.arange(fmin, fmax, 0.1 / dur)
    amps = np.array([amp_at(t, y, f) for f in grid])
    f = grid[int(np.argmax(amps))]
    for step in (0.02 / dur, 0.004 / dur):
        fine = np.arange(f - 5 * step, f + 5 * step, step)
        fine = fine[fine > 0]
        a = np.array([amp_at(t, y, ff) for ff in fine])
        f = fine[int(np.argmax(a))]
    return f


def wrap(x):
    return (x + math.pi) % (2 * math.pi) - math.pi


def norm_quantile(y):
    lo, hi = np.percentile(y, [2, 98])
    half = (hi - lo) / 2
    return (y - (hi + lo) / 2) / half if half > 0 else y * 0


def signed_area(x, y):
    return 0.5 * float(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]))


def zero_crossings(t, y):
    s = np.sign(y)
    idx = np.where((s[:-1] < 0) & (s[1:] >= 0))[0]
    # 線形補間で時刻を出す
    return np.array([t[i] - y[i] * (t[i + 1] - t[i]) / (y[i + 1] - y[i]) for i in idx])


# ---------------------------------------------------------------- 解析
def analyze(meta, cols, labels, ch="G", base=None, ref=None, out=print):
    t_all = cols["t_ms"] / 1000.0
    ok = np.isfinite(t_all)
    for lab in labels:
        ok &= np.isfinite(cols[lab + "_" + ch])
    t_all = t_all[ok]

    roles = {lab: role_of(lab) for lab in labels}
    if base is None:
        base = next((l for l in labels if roles[l] == "blank"), None) or \
               next((l for l in labels if roles[l] == "hole"), None) or \
               next((l for l in labels if roles[l] != "ref"), None)
    if ref is None:
        ref = next((l for l in labels if roles[l] == "ref"), None)
    if base is None:
        raise SystemExit("位相の基準にする枠（ブランクか穴）がありません。")

    raw = {lab: cols[lab + "_" + ch][ok] for lab in labels}
    sat = {lab: cols[lab + "_sat"][ok] for lab in labels if lab + "_sat" in cols}

    # コマの間隔
    dts = np.diff(t_all)
    med = float(np.median(dts))
    gaps = int(np.sum(dts > 1.5 * med))
    out(f"■ 記録  {meta.get('note', '') or '（メモなし）'}")
    out(f"  長さ {t_all[-1] - t_all[0]:.1f} 秒、{len(t_all)} コマ、平均 {1 / med:.1f} fps、"
        f"間隔が空いた所 {gaps} か所、取りこぼし {meta.get('dropped_frames', '?')} コマ")
    out(f"  色 {ch}、位相の基準 {base}、基準領域 {ref or 'なし'}")
    for lab, s in sat.items():
        if np.nanmax(s) > 0.01:
            out(f"  ※ {lab} が白飛びしているコマがあります（最大 {np.nanmax(s) * 100:.1f}%）。結果は信用できません。")

    # 振動数と、整数回転ぶんの切り出し
    f = estimate_freq(t_all, raw[base] - raw[base].mean())
    n_cyc = int((t_all[-1] - t_all[0]) * f)
    n_use = n_cyc - (n_cyc % 2)
    if n_use < 2:
        n_use = n_cyc
        out("  ※ 1回転に満たないため、整数回転での切り出しができません。")
    t0 = t_all[0]
    sel = t_all <= t0 + n_use / f + 0.5 * med
    t = t_all[sel]
    out(f"  回転の周期 {2 / f:.2f} 秒（cos² の周期 {1 / f:.2f} 秒）、使った範囲 {n_use / 2:.0f} 回転 = {t[-1] - t[0]:.1f} 秒")

    # 回転むら（ゼロ交差の間隔）
    fb = fit(t, raw[base][sel], f)
    zc = zero_crossings(t, raw[base][sel] - fb["model_slow"])
    if len(zc) >= 3:
        per = np.diff(zc)
        rot = per[:-1] + per[1:]
        out(f"  回転むら：cos² の1周期ごとの長さ 平均 {per.mean():.2f} 秒、ばらつき {per.std() / per.mean() * 100:.1f}%"
            f"（最短 {per.min():.2f}、最長 {per.max():.2f}）。1回転ごと {rot.mean():.2f} ± {rot.std():.2f} 秒")

    def series(lab, gamma, use_ratio):
        v = raw[lab][sel].astype(float)
        if gamma != 1.0:
            v = np.clip(v / 255.0, 1e-6, None) ** gamma
        if use_ratio:
            r = raw[ref][sel].astype(float)
            if gamma != 1.0:
                r = np.clip(r / 255.0, 1e-6, None) ** gamma
            v = v / r
        return v

    # 変動の深さと基準に残る偏光
    out("")
    out("■ 変動の深さ m（1回転に2回の成分の振幅 ÷ 平均、補正なし／ガンマ2.2）")
    fits1 = {lab: fit(t, series(lab, 1.0, False), f) for lab in labels}
    fits22 = {lab: fit(t, series(lab, 2.2, False), f) for lab in labels}
    for lab in labels:
        m1 = fits1[lab]["amp"] / fits1[lab]["c0"]
        m2 = fits22[lab]["amp"] / fits22[lab]["c0"]
        out(f"  {lab:<8} m = {m1:6.3f} / {m2:6.3f}")
    if ref is not None:
        p = fits22[ref]["amp"] / fits22[ref]["c0"]
        m = fits22[base]["amp"] / fits22[base]["c0"]
        dphi = math.degrees(wrap(fits22[ref]["phase"] - fits22[base]["phase"])) / 2
        out(f"  基準に残る偏光：p/m = {p / m * 100:.1f}%（ガンマ2.2、{ref} の変動の向きは {base} から {dphi:+.0f}°）"
            f"  → 目安は数%以下（POL-Q-01）")
        lock = meta.get("camera_lock", "")
        if "露出○" not in lock:
            out("  ※ 露出が固定されていない記録です。自動露出による明るさの変動が p に混ざるので、"
                "p/m は大きめに出ます。p/m は露出を固定した記録で判断してください。")

    # 旋光角
    targets = [l for l in labels if l not in (base, ref) and roles[l] != "ref"]
    if not targets:
        out("")
        out("（試料の枠がないので、旋光角の比較は省略）")
        return f

    out("")
    out(f"■ 旋光角 α（度、{base} を 0 とする。符号は回転の向きで決まる）")
    out("  A：時間波形への当てはめ　B：リサージュ図形の符号付き面積")
    groups = [("補正なし", 1.0, False), ("γ2.2", 2.2, False)]
    if ref is not None:
        groups.append(("比・γ2.2", 2.2, True))
    out("  " + " " * 8 + "".join(f"{name:^20}" for name, _, _ in groups))
    out("  " + " " * 8 + "".join(f"{'A':>10}{'B':>10}" for _ in groups))
    for lab in targets:
        vals = []
        for _, g, use_ratio in groups:
            yb, ys = series(base, g, use_ratio), series(lab, g, use_ratio)
            d_a = wrap(fit(t, ys, f)["phase"] - fit(t, yb, f)["phase"])
            x, y = norm_quantile(yb), norm_quantile(ys)
            d_b = math.asin(max(-1.0, min(1.0, signed_area(x, y) / (math.pi * n_use))))
            vals += [math.degrees(d_a) / 2, math.degrees(d_b) / 2]
        out("  " + f"{lab:<8}" + "".join(f"{v:10.2f}" for v in vals))
    out("  C（角度軸の成分）は、印の検出を入れてから比べる。")
    return f


# ---------------------------------------------------------------- 図
def plot(meta, cols, labels, ch, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib がないので、図は省略します（pip install matplotlib）。")
        return
    t = cols["t_ms"] / 1000.0
    roles = {l: role_of(l) for l in labels}
    base = next((l for l in labels if roles[l] in ("blank", "hole")), labels[0])
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for lab in labels:
        ax[0].plot(t, cols[lab + "_" + ch], lw=1, label=lab)
    ax[0].set_xlabel("t [s]"); ax[0].set_ylabel(f"{ch} (0-255)"); ax[0].legend(fontsize=8)
    for lab in labels:
        if lab == base or roles[lab] == "ref":
            continue
        ax[1].plot(norm_quantile(cols[base + "_" + ch]), norm_quantile(cols[lab + "_" + ch]), lw=0.8, label=lab)
    ax[1].set_aspect("equal"); ax[1].set_xlabel(base); ax[1].set_ylabel("sample"); ax[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=120)
    print("図を保存しました: " + path)


# ---------------------------------------------------------------- 模擬データ
def make_demo(seed=1):
    """答えの分かっている模擬データ。条件は下の値で変える。"""
    rng = np.random.default_rng(seed)
    fps, dur, T = 30.0, 62.0, 20.0               # 30 fps、62 秒、1回転 20 秒
    wobble = 0.15                                 # 回転むら（rad）。θ = 2πt/T + wobble·sin(2πt/T)
    leak_p = 0.04                                 # 基準の紙に残る偏光
    gamma = 2.2                                   # カメラのガンマ
    alphas = {"blank1": 0.0, "s1": 5.0, "s2": 10.0, "s3": 20.0}
    t = np.arange(0, dur, 1 / fps) + rng.normal(0, 0.002, int(dur * fps))
    t.sort()
    th = 2 * np.pi * t / T + wobble * np.sin(2 * np.pi * t / T)
    lights = {}
    for i, (lab, a) in enumerate(alphas.items()):
        uneven = 1 + 0.03 * np.cos(th + i)        # 画面のむら（1回転に1回）
        lights[lab] = 0.6 * uneven * (np.cos(th - math.radians(a)) ** 2 + 0.01)
    lights["ref1"] = 0.35 * (1 + leak_p * np.cos(2 * th))
    mean_light = np.mean([v for k, v in lights.items()], axis=0)
    gain = 1.0 / (0.55 + 0.6 * mean_light)        # 自動露出：全体が暗いと明るくする
    cols = {"t_ms": t * 1000}
    for lab, v in lights.items():
        lin = np.clip(gain * v, 0, 1)
        pix = 255 * lin ** (1 / gamma) + rng.normal(0, 0.8, len(t))
        for c in "RGB":
            cols[f"{lab}_{c}"] = np.clip(pix, 0, 255)
        cols[f"{lab}_sat"] = (pix >= 250).astype(float)
    labels = ["ref1"] + list(alphas)
    meta = {"note": f"模擬データ：1回転 {T} 秒、回転むら {wobble} rad、基準の偏光 p={leak_p}、ガンマ {gamma}、"
                    f"真の α = " + ", ".join(f"{k} {v}°" for k, v in alphas.items()),
            "dropped_frames": "0"}
    return meta, cols, labels


def main():
    ap = argparse.ArgumentParser(description="偏光ラボ 検証キットの記録を解析する")
    ap.add_argument("csv", nargs="?", help="記録ページで保存した CSV")
    ap.add_argument("--ch", default="G", help="R / G / B / all（既定 G）")
    ap.add_argument("--base", help="位相の基準にする枠（既定：blank1、なければ hole1）")
    ap.add_argument("--ref", help="基準領域の枠（既定：ref1）")
    ap.add_argument("--plot", action="store_true", help="図を PNG で保存する")
    ap.add_argument("--demo", action="store_true", help="模擬データを作って解析する")
    a = ap.parse_args()

    if a.demo:
        meta, cols, labels = make_demo()
    elif a.csv:
        meta, cols, labels = load_csv(a.csv)
    else:
        ap.print_help()
        return 1

    chans = ["R", "G", "B"] if a.ch.lower() == "all" else [a.ch.upper()]
    for c in chans:
        if c not in CH_INDEX:
            raise SystemExit("--ch は R / G / B / all のいずれか")
        analyze(meta, cols, labels, ch=c, base=a.base, ref=a.ref)
        print()
    if a.plot:
        path = (a.csv.rsplit(".", 1)[0] if a.csv else "demo") + f"_{chans[0]}.png"
        plot(meta, cols, labels, chans[0], path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
