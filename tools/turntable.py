#!/usr/bin/env python3
"""回転台の回転速度と回転むらを、phyphox のジャイロの記録から求める（POL-Q-03）。

測り方
  1. 光源にするスマホで phyphox の「ジャイロスコープ」を開く。
  2. スマホを回転台の中央に載せ、記録を始める。少なくとも3回転（目安60秒）は回す。
  3. 「データのエクスポート」で CSV（zip）を書き出す。

使い方
  python turntable.py 2026-10-13_18-01-53.zip     # zip のまま、または中の "Raw Data.csv"
  python turntable.py 記録.zip --plot              # 図を PNG で保存（matplotlib が要る）
  python turntable.py 記録.zip --skip 2            # 最初の2秒（載せるときの揺れ）を除く

必要なもの：Python 3.8 以上、numpy
"""
import argparse
import csv
import io
import math
import sys
import zipfile

import numpy as np


def load(path):
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            name = next((n for n in z.namelist() if n.endswith("Raw Data.csv")), None)
            if name is None:
                raise SystemExit("zip の中に Raw Data.csv がありません。")
            text = z.read(name).decode("utf-8-sig")
            model = ""
            dev = next((n for n in z.namelist() if n.endswith("device.csv")), None)
            if dev:
                for row in csv.reader(io.StringIO(z.read(dev).decode("utf-8-sig"))):
                    if row and row[0] == "deviceModel":
                        model = row[1]
    else:
        text = open(path, encoding="utf-8-sig").read()
        model = ""
    rows = list(csv.reader(io.StringIO(text)))
    head = rows[0]
    data = np.array([[float(x) for x in r] for r in rows[1:] if r], dtype=float)
    if not any("Gyroscope" in h for h in head):
        raise SystemExit("ジャイロスコープの記録ではないようです（列名：" + ", ".join(head) + "）")
    return data[:, 0], data[:, 1], data[:, 2], data[:, 3], model


def smooth(x, n):
    n = max(1, int(n))
    return np.convolve(x, np.ones(n) / n, mode="same")


def main():
    ap = argparse.ArgumentParser(description="回転台の回転速度と回転むらを求める（phyphox のジャイロ）")
    ap.add_argument("path", help="phyphox で書き出した zip、または Raw Data.csv")
    ap.add_argument("--skip", type=float, default=1.0, help="最初に除く秒数（既定 1 秒）")
    ap.add_argument("--plot", action="store_true", help="図を PNG で保存する")
    a = ap.parse_args()

    t, wx, wy, wz, model = load(a.path)
    keep = t >= t[0] + a.skip
    t, wx, wy, wz = t[keep], wx[keep], wy[keep], wz[keep]
    dt = float(np.median(np.diff(t)))
    sign = 1.0 if np.mean(wz) >= 0 else -1.0
    w = sign * wz                                   # 回る向きによらず正にする

    th = np.concatenate([[0.0], np.cumsum((w[1:] + w[:-1]) / 2 * np.diff(t))])
    dur = t[-1] - t[0]
    turns = th[-1] / (2 * math.pi)
    period = 2 * math.pi * dur / th[-1]

    ws = smooth(w, 0.5 / dt)
    edge = int(0.25 / dt)
    core = slice(edge, len(t) - edge)

    print(f"■ 回転台  {a.path}" + (f"（{model}）" if model else ""))
    print(f"  記録 {dur:.1f} 秒（最初の {a.skip:g} 秒を除く）、{1 / dt:.0f} Hz、回った量 {turns:.2f} 回転、"
          f"向き {'反時計回り' if sign > 0 else '時計回り'}（画面を上にして見たとき）")
    print(f"  平均の周期 {period:.2f} 秒（{60 / period:.2f} rpm、角速度 {th[-1] / dur:.3f} rad/s）")
    print(f"  角速度（0.5 秒平均）{ws[core].min():.3f}〜{ws[core].max():.3f} rad/s（最大÷最小 {ws[core].max() / ws[core].min():.2f}）")

    # 90° ごとの所要時間
    marks = np.arange(0, th[-1], math.pi / 2)
    tm = np.interp(marks, th, t)
    q = np.diff(tm)
    if len(q):
        print("  90° ごとの所要時間（秒）: " + " ".join(f"{x:.2f}" for x in q))

    # 等速回転からのずれ
    c = np.polyfit(t[core], th[core], 1)
    dev = np.degrees(th - np.polyval(c, t))
    print(f"  等速回転からのずれ 最大 {np.max(np.abs(dev[core])):.1f}°")

    # 回転むらが角度で決まっているか（2回転以上あるとき）
    if turns >= 2.0:
        grid = np.linspace(0, 2 * math.pi, 73)[:-1]
        prof = []
        for k in range(int(turns)):
            prof.append(np.interp(grid + 2 * math.pi * k, th, ws))
        prof = np.array(prof)
        r = np.corrcoef(prof)[np.triu_indices(len(prof), 1)]
        slow = math.degrees(grid[int(np.argmin(prof.mean(axis=0)))])
        print(f"  1回転ごとの速さの形の相関 {np.mean(r):.2f}（1に近いほど、毎回同じ角度で遅くなる）。"
              f"いちばん遅いのは記録開始から {slow:.0f}° の向き")
    else:
        print("  ※ 2回転に満たないので、むらが毎回同じ角度で起こるかは判断できません（3回転以上を推奨）。")

    # 細かい振動
    res = (w - ws)[core]
    if len(res) > 64:
        spec = np.abs(np.fft.rfft(res * np.hanning(len(res))))
        fr = np.fft.rfftfreq(len(res), dt)
        band = fr > 0.5
        fpk = float(fr[band][np.argmax(spec[band])])
        amp = float(np.std(res) * math.sqrt(2))
        print(f"  細かい振動 約 {fpk:.1f} Hz、角速度の振れ ±{amp:.3f} rad/s → 角度の振れ ±{math.degrees(amp / (2 * math.pi * fpk)):.2f}°")

    # 傾き（回転軸に対してスマホが傾いていると、x・y の角速度が一定の向きに残る）
    wxy = np.hypot(np.mean(wx[core]), np.mean(wy[core]))
    print(f"  x・y の角速度の平均 {wxy:.3f} rad/s（回転軸に対する傾きの目安 {math.degrees(math.asin(min(1.0, wxy / max(1e-9, np.mean(w))))):.1f}°。"
          "ジャイロのずれも含む）")

    if a.plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib がないので、図は省略します。")
            return 0
        fig, ax = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
        ax[0].plot(t, w, lw=0.5, color="#bbbbbb", label="raw")
        ax[0].plot(t[core], ws[core], color="C0", label="0.5 s avg")
        ax[0].set_ylabel("omega [rad/s]")
        ax[0].legend()
        ax[1].plot(t[core], dev[core], color="C3")
        ax[1].set_ylabel("deviation from uniform [deg]")
        ax[1].set_xlabel("t [s]")
        fig.tight_layout()
        out = a.path.rsplit(".", 1)[0] + "_turntable.png"
        fig.savefig(out, dpi=110)
        print("図を保存しました: " + out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
