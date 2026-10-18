/* 偏光ラボ：旋光（M2）の解析。ブラウザでは window.PolAnalysis、Node では require で使う。
 * 仕様：docs/04-polarimeter-mode.md の10節、docs/03-requirements.md の POL-F-33・38・39。
 * tools/analyze.py と同じ手順で計算する（結果を突き合わせられるように）。
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PolAnalysis = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  const TAU = 2 * Math.PI;

  // ---------- 小さな線形代数 ----------
  function solve(A, b) {
    const n = b.length, M = A.map((row, i) => row.concat([b[i]]));
    for (let c = 0; c < n; c++) {
      let p = c;
      for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
      if (Math.abs(M[p][c]) < 1e-12) return null;
      [M[c], M[p]] = [M[p], M[c]];
      for (let r = c + 1; r < n; r++) {
        const k = M[r][c] / M[c][c];
        for (let j = c; j <= n; j++) M[r][j] -= k * M[c][j];
      }
    }
    const x = new Array(n).fill(0);
    for (let r = n - 1; r >= 0; r--) {
      let s = M[r][n];
      for (let j = r + 1; j < n; j++) s -= M[r][j] * x[j];
      x[r] = s / M[r][r];
    }
    return x;
  }

  // 列を返す関数 cols(i) => [x0, x1, ...] で最小二乗
  function lstsq(n, p, cols, y) {
    const A = Array.from({ length: p }, () => new Array(p).fill(0));
    const b = new Array(p).fill(0);
    const row = new Array(p);
    for (let i = 0; i < n; i++) {
      cols(i, row);
      for (let a = 0; a < p; a++) {
        b[a] += row[a] * y[i];
        for (let c = a; c < p; c++) A[a][c] += row[a] * row[c];
      }
    }
    for (let a = 0; a < p; a++) for (let c = 0; c < a; c++) A[a][c] = A[c][a];
    return solve(A, b);
  }

  function mean(a) { let s = 0; for (let i = 0; i < a.length; i++) s += a[i]; return s / a.length; }
  function median(a) { const s = Array.from(a).sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
  function quantile(a, q) {
    const s = Array.from(a).sort((x, y) => x - y);
    const pos = (s.length - 1) * q, lo = Math.floor(pos), hi = Math.ceil(pos);
    return s[lo] + (s[hi] - s[lo]) * (pos - lo);
  }
  function wrap(x) { return ((x + Math.PI) % TAU + TAU) % TAU - Math.PI; }
  const deg = r => r * 180 / Math.PI;

  // ---------- 当てはめ ----------
  // y = c0 + c1 (t - tc) + a cos(2πft) + b sin(2πft) [+ 1回転に1回の項]
  function fit(t, y, f, withSlow = true) {
    const n = t.length, tc = mean(t), w = TAU * f;
    const p = withSlow ? 6 : 4;
    const coef = lstsq(n, p, (i, r) => {
      const ti = t[i];
      r[0] = 1; r[1] = ti - tc; r[2] = Math.cos(w * ti); r[3] = Math.sin(w * ti);
      if (withSlow) { r[4] = Math.cos(w * ti / 2); r[5] = Math.sin(w * ti / 2); }
    }, y);
    if (!coef) return null;
    const amp = Math.hypot(coef[2], coef[3]);
    const phase = Math.atan2(coef[3], coef[2]);
    let ss = 0;
    for (let i = 0; i < n; i++) {
      const ti = t[i];
      let m = coef[0] + coef[1] * (ti - tc) + coef[2] * Math.cos(w * ti) + coef[3] * Math.sin(w * ti);
      if (withSlow) m += coef[4] * Math.cos(w * ti / 2) + coef[5] * Math.sin(w * ti / 2);
      ss += (y[i] - m) ** 2;
    }
    return { c0: coef[0], amp, phase, rms: Math.sqrt(ss / n) };
  }

  function ampAt(t, y, f) { const r = fit(t, y, f, false); return r ? r.amp : 0; }

  // cos² の振動数（1回転に2回）。fmax は既定 2 Hz（回転の周期 1 秒以上を想定）
  function estimateFreq(t, y, fmaxCap = 2.0) {
    const n = t.length;
    if (n < 16) return null;
    const dur = t[n - 1] - t[0];
    const dts = []; for (let i = 1; i < n; i++) dts.push(t[i] - t[i - 1]);
    const dt = median(dts);
    const fmin = 1.2 / dur, fmax = Math.min(fmaxCap, 0.25 / dt);
    if (!(fmax > fmin)) return null;
    const m0 = mean(y), yy = Array.from(y, v => v - m0);
    // 粗い探索は間引いたデータで行う（スマホでの計算時間を抑える）
    const stride = Math.max(1, Math.ceil(n / 400));
    const ts = [], ys = [];
    for (let i = 0; i < n; i += stride) { ts.push(t[i]); ys.push(yy[i]); }
    const fmaxC = Math.min(fmax, 0.25 / (dt * stride));
    let best = fmin, bestA = -1;
    for (let f = fmin; f < fmaxC; f += 0.1 / dur) {
      const a = ampAt(ts, ys, f); if (a > bestA) { bestA = a; best = f; }
    }
    bestA = ampAt(t, yy, best);
    for (const step of [0.02 / dur, 0.004 / dur]) {
      let b2 = best, a2 = bestA;
      for (let k = -5; k <= 5; k++) {
        const f = best + k * step; if (f <= 0) continue;
        const a = ampAt(t, yy, f); if (a > a2) { a2 = a; b2 = f; }
      }
      best = b2; bestA = a2;
    }
    const lo = quantile(yy, 0.02), hi = quantile(yy, 0.98);
    return { f: best, amp: bestA, halfRange: (hi - lo) / 2, dur };
  }

  function linearize(v, gamma) {
    if (gamma === 1) return Float64Array.from(v);
    return Float64Array.from(v, x => Math.pow(Math.max(x / 255, 1e-6), gamma));
  }

  function normQuantile(y) {
    const lo = quantile(y, 0.02), hi = quantile(y, 0.98), h = (hi - lo) / 2, c = (hi + lo) / 2;
    return Float64Array.from(y, v => h > 0 ? (v - c) / h : 0);
  }

  function signedArea(x, y) {
    let s = 0; for (let i = 0; i < x.length - 1; i++) s += x[i] * y[i + 1] - x[i + 1] * y[i];
    return 0.5 * s;
  }

  // ---------- 1回の記録の解析 ----------
  // rec = { t: [秒], rois: [{label, role, R:[], G:[], B:[], sat:[]}] }
  // opt = { gamma: 2.2, useRatio: true, channels: ['R','G','B'] }
  function analyze(rec, opt = {}) {
    const gamma = opt.gamma ?? 2.2;
    const channels = opt.channels || ['R', 'G', 'B'];
    const rois = rec.rois;
    const base = rois.find(r => r.role === 'blank') || rois.find(r => r.role === 'hole');
    const ref = rois.find(r => r.role === 'ref');
    const useRatio = !!(opt.useRatio ?? true) && !!ref;
    const samples = rois.filter(r => r.role === 'sample');
    const out = { ok: false, messages: [], channels: {}, samples: samples.map(s => s.label), base: base && base.label, ref: ref && ref.label, useRatio, gamma };
    if (!base) { out.messages.push('ブランクの枠がありません。'); return out; }
    const t0 = rec.t[0], tAll = Float64Array.from(rec.t, v => v - t0);
    if (tAll.length < 30) { out.messages.push('記録が短すぎます。'); return out; }

    // 振動数はブランクの G（補正後）から求め、全色で共通に使う
    const est = estimateFreq(tAll, linearize(base.G, gamma));
    if (!est) { out.messages.push('記録が短すぎます。'); return out; }
    const f = est.f;
    const nCyc = Math.floor(est.dur * f);
    let nUse = nCyc - (nCyc % 2);
    if (nUse < 2) { nUse = nCyc; out.messages.push('1回転に満たない記録です。結果は参考値です。'); }
    if (nUse < 1) { out.messages.push('ブランクの明るさの変化が1周期に満たないため、計算できません。'); return out; }
    const dtMed = median(Array.from({ length: tAll.length - 1 }, (_, i) => tAll[i + 1] - tAll[i]));
    const tEnd = nUse / f + 0.5 * dtMed;
    let n = 0; while (n < tAll.length && tAll[n] <= tEnd) n++;
    const t = tAll.subarray(0, n);
    out.f = f; out.period = 2 / f; out.rotations = nUse / 2; out.usedSec = t[n - 1] - t[0]; out.totalSec = est.dur; out.frames = n;

    for (const ch of channels) {
      const lin = r => linearize(r[ch].slice(0, n), gamma);
      const series = r => {
        const v = lin(r);
        if (!useRatio) return v;
        const rv = lin(ref);
        return Float64Array.from(v, (x, i) => x / Math.max(rv[i], 1e-9));
      };
      const yb = series(base);
      const fb = fit(t, yb, f);
      const fbLin = fit(t, lin(base), f);
      const res = { blankM: fbLin ? fbLin.amp / fbLin.c0 : NaN, samples: {} };
      if (ref) {
        const fr = fit(t, lin(ref), f);
        res.refPM = fr && fbLin ? (fr.amp / fr.c0) / (fbLin.amp / fbLin.c0) : NaN;
      }
      const xb = normQuantile(yb);
      for (const s of samples) {
        const ys = series(s);
        const fs = fit(t, ys, f);
        const fsLin = fit(t, lin(s), f);
        const aA = fs && fb ? deg(wrap(fs.phase - fb.phase)) / 2 : NaN;
        const area = signedArea(xb, normQuantile(ys)) / (Math.PI * nUse);
        const aB = deg(Math.asin(Math.max(-1, Math.min(1, area)))) / 2;
        const satFrac = s.sat ? mean(Array.from(s.sat.slice(0, n), v => (v > 0.01 ? 1 : 0))) : 0;
        res.samples[s.label] = { A: aA, B: aB, m: fsLin ? fsLin.amp / fsLin.c0 : NaN, sat: satFrac };
      }
      out.channels[ch] = res;
    }
    out.ok = true;
    return out;
  }

  // 記録中の自動停止の判定：ブランクが cos² の4周期（＝2回転）進んだか
  function cyclesSoFar(t, blankG, gamma = 2.2) {
    if (t.length < 30) return { cycles: 0, reliable: false };
    const t0 = t[0], tt = Float64Array.from(t, v => v - t0);
    const est = estimateFreq(tt, linearize(blankG, gamma));
    if (!est || est.halfRange <= 0) return { cycles: 0, reliable: false };
    const reliable = est.amp > 0.4 * est.halfRange && est.dur * est.f >= 1.5;
    return { cycles: est.dur * est.f, f: est.f, reliable };
  }

  return { analyze, cyclesSoFar, estimateFreq, fit, linearize, normQuantile, signedArea, quantile, wrap };
});
