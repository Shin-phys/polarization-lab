/* 偏光ラボ：枠を置くときのルーペ。
 * 枠を動かしている間と大きさを変えている間、その枠のまわりを拡大して、指で隠れない隅に表示する。
 * 拡大には処理用の縮小画像ではなく、元の映像（video）を使うので、細部まで見える。
 */
(function (root) {
  'use strict';

  function create({ wrap, video, view }) {
    const c = document.createElement('canvas');
    c.className = 'loupe';
    c.setAttribute('aria-hidden', 'true');
    Object.assign(c.style, {
      position: 'absolute', zIndex: 3, display: 'none', pointerEvents: 'none',
      borderRadius: '50%', border: '2px solid rgba(255,255,255,.9)', boxShadow: '0 4px 16px rgba(0,0,0,.6)',
      background: '#000',
    });
    wrap.appendChild(c);
    const g = c.getContext('2d');
    let target = null, others = [], hideTimer = 0;

    // target: { x, y, r, color, label }（x, y は 0〜1、r は処理画像の横幅に対する比）
    function show(t, rest = []) { target = t; others = rest; clearTimeout(hideTimer); c.style.display = 'block'; update(); }
    function hideSoon(ms = 500) { clearTimeout(hideTimer); hideTimer = setTimeout(hide, ms); }
    function hide() { target = null; c.style.display = 'none'; }
    const visible = () => !!target;

    function update() {
      if (!target) return;
      const vr = view.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
      if (!vr.width) return;
      // 大きさと置き場所：枠と反対側の上の隅（枠が上のほうにあるときは下の隅）
      const size = Math.round(Math.min(200, Math.max(120, vr.width * 0.42)));
      const dpr = window.devicePixelRatio || 1;
      if (c.width !== size * dpr) { c.width = size * dpr; c.height = size * dpr; c.style.width = size + 'px'; c.style.height = size + 'px'; }
      const left = target.x < 0.5 ? vr.right - wr.left - size - 8 : vr.left - wr.left + 8;
      const top = target.y < 0.45 ? vr.bottom - wr.top - size - 8 : vr.top - wr.top + 8;
      c.style.left = left + 'px'; c.style.top = top + 'px';

      // 元の映像の座標で、枠のまわりを切り出す
      const vw = video.videoWidth, vh = video.videoHeight;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.fillStyle = '#000'; g.fillRect(0, 0, size, size);
      const cx = target.x * vw, cy = target.y * vh;
      const half = Math.max(target.r * vw * 2.2, vw * 0.04);   // 枠の半径の約2倍の範囲を見せる
      const scale = size / (2 * half);
      if (vw && vh) {
        try { g.drawImage(video, cx - half, cy - half, 2 * half, 2 * half, 0, 0, size, size); } catch (e) { /* 映像がまだ無い */ }
      }
      const toL = (x, y) => [(x * vw - (cx - half)) * scale, (y * vh - (cy - half)) * scale];
      // ほかの枠（細線）
      for (const o of others) {
        const [ox, oy] = toL(o.x, o.y), orad = o.r * vw * scale;
        if (ox + orad < 0 || oy + orad < 0 || ox - orad > size || oy - orad > size) continue;
        g.strokeStyle = o.color; g.lineWidth = 1.5; g.globalAlpha = 0.7;
        g.beginPath(); g.arc(ox, oy, orad, 0, Math.PI * 2); g.stroke(); g.globalAlpha = 1;
      }
      // 動かしている枠（太線）と中心の十字
      const [tx, ty] = toL(target.x, target.y), trad = target.r * vw * scale;
      g.strokeStyle = 'rgba(0,0,0,.6)'; g.lineWidth = 4;
      g.beginPath(); g.arc(tx, ty, trad, 0, Math.PI * 2); g.stroke();
      g.strokeStyle = target.color || '#fff'; g.lineWidth = 2;
      g.beginPath(); g.arc(tx, ty, trad, 0, Math.PI * 2); g.stroke();
      g.lineWidth = 1; g.beginPath();
      g.moveTo(tx - 8, ty); g.lineTo(tx + 8, ty); g.moveTo(tx, ty - 8); g.lineTo(tx, ty + 8); g.stroke();
      if (target.label) {
        g.font = '12px system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'bottom';
        g.fillStyle = 'rgba(0,0,0,.6)'; const w = g.measureText(target.label).width + 8;
        g.fillRect(size / 2 - w / 2, size - 20, w, 16);
        g.fillStyle = '#fff'; g.fillText(target.label, size / 2, size - 6);
      }
    }

    return { show, update, hide, hideSoon, get visible() { return visible(); } };
  }

  root.PolLoupe = { create };
})(typeof self !== 'undefined' ? self : this);
