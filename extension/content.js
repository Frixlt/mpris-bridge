// Reads the page's media (element state, MediaSession metadata) and runs the desktop's commands on it.
// MediaSession action handlers are write-only for pages, so setActionHandler is wrapped to keep a
// copy: that is how next/previous and "does this page support it" are known without a page script.
(() => {
  const handlers = {};
  try {
    const proto = window.wrappedJSObject.MediaSession.prototype;
    const original = proto.setActionHandler;
    proto.setActionHandler = exportFunction(function (action, handler) {
      handlers[action] = handler || null;
      return original.call(this, action, handler);
    }, window);
  } catch (e) {}

  let lastPlayed = null;
  const note = e => {
    if (e.target instanceof HTMLMediaElement) lastPlayed = e.target;
    schedule();
  };
  for (const type of ["play", "playing", "pause", "waiting", "seeked", "seeking", "ratechange", "volumechange",
                      "loadedmetadata", "durationchange", "ended", "emptied", "stalled", "canplay"])
    document.addEventListener(type, note, true);

  function isMedia(el) {
    const d = el.duration;
    if (el.muted && el.loop && el.getAttribute("aria-hidden") === "true") return false;                        // a looping background video
    if (!el.currentSrc && !el.src && el.readyState === 0) return false;
    if (isFinite(d) && d < 2) return false;                       // a sound effect or a preview
    return true;
  }

  function pickMedia() {
    const all = [...document.querySelectorAll("video,audio")].filter(isMedia);
    return all.find(e => !e.paused && !e.ended) || (all.includes(lastPlayed) ? lastPlayed : null) || all[0] || null;
  }

  const clean = s => (s || "").replace(/^\(\d+\)\s+/, "").replace(/\s+-\s+YouTube$/, "").trim();
  const abs = u => { try { return new URL(u, location.href).href; } catch (e) { return ""; } };

  function metadata() {
    if (/^(www\.)?twitch\.tv$/.test(location.hostname)) {
      const images = [...document.querySelectorAll('img')].map(image => ({
        src: image.currentSrc || image.src, alt: image.alt,
        href: image.closest('a[href]')?.href || '',
      }));
      const twitch = bridgeTwitchMetadata(location.href, images);
      if (twitch !== undefined) return twitch;
    }
    if (/(^|\.)youtube\.com$/.test(location.hostname)) {
      let details = null;
      try {
        const player = document.querySelector("#movie_player")?.wrappedJSObject;
        const raw = player?.getPlayerResponse?.()?.videoDetails || player?.getVideoData?.();
        if (raw) {
          // Copy primitives out of the page compartment before using array callbacks.
          // Firefox blocks passing content-script callbacks into page-owned arrays.
          details = { videoId: String(raw.videoId || raw.video_id || ''),
            title: String(raw.title || ''), author: String(raw.author || ''),
            thumbnail: { thumbnails: [] } };
          try {
            const thumbnails = raw.thumbnail?.thumbnails;
            for (let i = 0; thumbnails && i < thumbnails.length && i < 32; ++i) {
              const t = thumbnails[i];
              details.thumbnail.thumbnails.push({url:String(t.url || ''),width:Number(t.width),height:Number(t.height)});
            }
          } catch (_) {} // Thumbnail access must never hide an otherwise valid player.
        }
      } catch (_) {}
      return bridgeYoutubeMetadata(location.href, details);
    }
    let md = null;
    try { md = navigator.mediaSession.metadata; } catch (e) {}
    let art = "";
    try {
      const list = md && md.artwork ? Array.from(md.artwork) : [];
      list.sort((a, b) => parseInt((b.sizes || "0").split("x")[0]) - parseInt((a.sizes || "0").split("x")[0]));
      art = list.length ? abs(list[0].src) : "";
    } catch (e) {}
    if (!art) {
      const og = document.querySelector('meta[property="og:image"]');
      if (og && og.content) art = abs(og.content);
    }
    const artist = md ? md.artist : "";
    return {
      title: clean(md && md.title) || clean(document.title),
      artist: artist || "",
      album: (md && md.album) || location.hostname.replace(/^www\./, ""),
      artUrl: art,
    };
  }

  let last = "";
  let lastAt = 0;
  let gone = true;
  let timer = 0;

  function report() {
    timer = 0;
    const el = pickMedia();
    if (!el) {
      if (!gone) { gone = true; last = ""; send({ gone: true }); }
      clearInterval(ticker);
      ticker = 0;
      return;
    }
    const meta = metadata();
    if (!meta) {
      if (!gone) send({ gone: true });
      gone = true;
      last = "";
      return;
    }
    gone = false;
    const d = el.duration;
    const live = !isFinite(d);
    const state = Object.assign({ url: location.href }, meta, {
      pageUrl: location.href,
      lengthUs: live ? 0 : Math.round(d * 1e6),
      positionUs: Math.round((el.currentTime || 0) * 1e6),
      playing: !el.paused && !el.ended,
      // Playing on paper but waiting for data: the desktop reads it as paused, so a progress bar stops with the picture
      buffering: !el.paused && !el.ended && (el.readyState < 3 || el.seeking),
      rate: el.playbackRate || 1,
      volume: bridgeMediaVolume(el, location.href, document),
      canSeek: !live,
      canNext: !!handlers.nexttrack || !!document.querySelector(".ytp-next-button:not([style*='display: none'])"),
      canPrev: !!handlers.previoustrack || !!document.querySelector(".ytp-prev-button:not([style*='display: none'])"),
    });
    // Position is sent on its own clock (the helper extrapolates); everything else only when it changes
    const key = JSON.stringify(Object.assign({}, state, { positionUs: 0 }));
    const now = Date.now();
    if (key !== last || now - lastAt > 5000) {
      last = key;
      lastAt = now;
      send(state);
    }
  }

  // A page with no media does no work at all: the once-a-second poll (which catches metadata a page
  // changes without any media event, such as a single-page app moving to the next track) only runs
  // while the page has media, and the next media event starts it again.
  let ticker = 0;
  function schedule() {
    if (suspended) return;
    if (!timer) timer = setTimeout(report, 150);
    if (!ticker) ticker = setInterval(schedule, 1000);
  }

  function call(action, details) {
    const h = handlers[action];
    if (!h) return false;
    try { h(cloneInto(Object.assign({ action }, details || {}), window.wrappedJSObject)); } catch (e) { return false; }
    return true;
  }

  function onCommand(msg) {
    if (msg.cmd === "Refresh") { last = ""; schedule(); return; }
    const el = pickMedia();
    const play = () => { const r = el.play(); if (r && r.catch) r.catch(() => {}); };  // a page may refuse; that is not an error here
    switch (msg.cmd) {
      case "Play": if (!call("play") && el) play(); break;
      case "Pause": if (!call("pause") && el) el.pause(); break;
      case "PlayPause": if (el) { if (el.paused) { if (!call("play")) play(); } else if (!call("pause")) el.pause(); } break;
      case "Stop": if (!call("stop") && el) el.pause(); break;
      case "Next": if (!call("nexttrack")) { const b = document.querySelector(".ytp-next-button"); if (b) b.click(); } break;
      case "Previous": if (!call("previoustrack")) { const b = document.querySelector(".ytp-prev-button"); if (b) b.click(); } break;
      case "Seek": if (el && isFinite(el.duration)) el.currentTime = Math.max(0, Math.min(el.duration, el.currentTime + msg.value / 1e6)); break;
      case "SetPosition": if (el && isFinite(el.duration)) el.currentTime = Math.max(0, Math.min(el.duration, msg.value / 1e6)); break;
      case "SetVolume": bridgeSetMediaVolume(el, msg.value, location.href, document); break;
      case "SetRate": if (el) el.playbackRate = msg.value; break;
    }
    schedule();
  }

  let port = null;
  let suspended = false;
  function send(msg) {
    try { port?.postMessage(msg); } catch (_) {}
  }
  function connect() {
    if (suspended || port) return;
    port = browser.runtime.connect({ name: "mpris-bridge-media" });
    const connection = port;
    port.onMessage.addListener(onCommand);
    port.onDisconnect.addListener(() => {
      if (port !== connection) return;
      port = null;
      if (!suspended) setTimeout(connect, 1000);
    });
    last = "";
    schedule();
  }
  window.addEventListener("pagehide", () => {
    suspended = true;
    clearTimeout(timer); timer = 0;
    clearInterval(ticker); ticker = 0;
    send({ gone: true });
    port?.disconnect(); port = null;
  });
  window.addEventListener("pageshow", () => { suspended = false; connect(); schedule(); });
  for (const event of ["yt-navigate-finish", "yt-player-updated", "yt-page-data-updated", "popstate"])
    window.addEventListener(event, schedule);
  connect();
})();
