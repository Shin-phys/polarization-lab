/* 偏光ラボ：撮影済みの動画ファイルを、カメラの代わりに読み込む（POL-F-42）。
 * 動画は端末の中で再生するだけで、外部へは送らない（POL-N-01）。
 * 時刻は、再生中のフレームごとに動画内の時刻（mediaTime）を読む。
 * currentTime を指定してコマ送りする方法は、ずれや取りこぼしが起こりうるので使わない。
 */
(function (root) {
  'use strict';
  const hasRVFC = typeof HTMLVideoElement !== 'undefined' && 'requestVideoFrameCallback' in HTMLVideoElement.prototype;

  function create(video, { onFrame, onEnded } = {}) {
    let url = null, info = null, playing = false, lastMedia = -1, idleCb = null, idleOn = false, rafId = 0, lastPoll = -1;

    function waitEvent(name, ms = 8000) {
      return new Promise((resolve, reject) => {
        const ok = () => { clean(); resolve(); };
        const bad = () => { clean(); reject(video.error || new Error(name + ' timeout')); };
        const timer = setTimeout(bad, ms);
        function clean() { clearTimeout(timer); video.removeEventListener(name, ok); video.removeEventListener('error', bad); }
        video.addEventListener(name, ok, { once: true });
        video.addEventListener('error', bad, { once: true });
      });
    }

    async function load(file) {
      unload();
      url = URL.createObjectURL(file);
      video.srcObject = null;
      video.muted = true; video.playsInline = true; video.loop = false; video.autoplay = false;
      video.preload = 'auto';
      video.src = url;
      try {
        if (video.readyState < 1) await waitEvent('loadedmetadata');
        if (video.readyState < 2) await waitEvent('loadeddata');
      } catch (e) {
        unload();
        throw new Error('この動画は、このブラウザで再生できません。iPhone なら「設定 → カメラ → フォーマット」を「互換性優先」にして撮り直してください。');
      }
      await seekStart();
      info = { name: file.name, size: file.size, lastModified: file.lastModified, duration: video.duration,
        width: video.videoWidth, height: video.videoHeight, type: file.type || '' };
      return info;
    }

    async function seekStart() {
      video.pause();
      if (video.currentTime !== 0) {
        const p = waitEvent('seeked').catch(() => {});
        video.currentTime = 0;
        await p;
      }
    }

    function onVFC(now, meta) {
      if (!playing) return;
      if (meta.mediaTime > lastMedia) {
        lastMedia = meta.mediaTime;
        onFrame && onFrame({ captureTime: meta.mediaTime * 1000, mediaTime: meta.mediaTime, presentedFrames: meta.presentedFrames, fromFile: true });
      }
      video.requestVideoFrameCallback(onVFC);
    }
    function poll() {
      if (!playing) return;
      const t = video.currentTime;
      if (t !== lastPoll) { lastPoll = t; onFrame && onFrame({ captureTime: t * 1000, mediaTime: t, presentedFrames: null, fromFile: true }); }
      rafId = requestAnimationFrame(poll);
    }
    function handleEnded() { if (!playing) return; playing = false; onEnded && onEnded(); }

    async function play(rate = 1) {
      if (!url) return;
      await seekStart();
      lastMedia = -1; lastPoll = -1; playing = true;
      video.playbackRate = rate;
      video.addEventListener('ended', handleEnded, { once: true });
      if (hasRVFC) video.requestVideoFrameCallback(onVFC); else rafId = requestAnimationFrame(poll);
      try { await video.play(); } catch (e) { playing = false; throw e; }
    }

    function stop() {
      playing = false;
      cancelAnimationFrame(rafId);
      video.removeEventListener('ended', handleEnded);
      video.pause();
    }

    function unload() {
      stop(); idle(null);
      if (url) { video.removeAttribute('src'); video.load(); URL.revokeObjectURL(url); }
      url = null; info = null;
    }

    // 再生していないあいだ、止まった画面に枠を描き直すための軽いループ
    function idle(cb) {
      idleCb = cb;
      if (cb && !idleOn) {
        idleOn = true;
        let k = 0;
        const step = () => {
          if (!idleCb || !url) { idleOn = false; return; }
          if (!playing && (k++ % 4 === 0)) idleCb();
          requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }
    }

    return {
      load, play, stop, unload, idle, seekStart,
      get loaded() { return !!url; }, get playing() { return playing; }, get info() { return info; },
      get rvfc() { return hasRVFC; },
    };
  }

  root.PolVideoFile = { create, hasRVFC };
})(typeof self !== 'undefined' ? self : this);
