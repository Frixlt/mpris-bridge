// Use the site's own controls where it keeps a separate volume/mute store.
// Changing only HTMLMediaElement.volume leaves that store (and its UI) stale.
(() => {
  const clamp = value => Math.max(0, Math.min(1, value));
  function twitchSlider(media, href, doc) {
    if (!/^(www\.)?twitch\.tv$/.test(new URL(href).hostname)) return null;
    const root = media.closest?.('[data-a-target="video-player"], .video-player') || doc;
    return root.querySelector('[data-a-target="player-volume-slider"]');
  }
  function youtubePlayer(href, doc) {
    return /(^|\.)youtube\.com$/.test(new URL(href).hostname)
      ? doc.querySelector('#movie_player')?.wrappedJSObject : null;
  }
  globalThis.bridgeMediaVolume = function (media, href, doc) {
    try {
      const slider = twitchSlider(media, href, doc);
      if (slider) {
        const min = Number(slider.min || 0), max = Number(slider.max || 1);
        const level = (Number(slider.value) - min) / (max - min);
        if (Number.isFinite(level)) return media.muted ? 0 : clamp(level);
      }
      const player = youtubePlayer(href, doc);
      if (typeof player?.getVolume === 'function') {
        const value = Number(player.getVolume()) / 100;
        const muted = typeof player.isMuted === 'function' ? player.isMuted() : media.muted;
        if (Number.isFinite(value)) return muted ? 0 : clamp(value);
      }
    } catch (_) {}
    return media.muted ? 0 : clamp(media.volume);
  };
  globalThis.bridgeSetMediaVolume = function (media, input, href, doc) {
    if (!media || !Number.isFinite(input)) return false;
    const value = clamp(input);
    try {
      const slider = twitchSlider(media, href, doc);
      if (slider) {
        const min = Number(slider.min || 0), max = Number(slider.max || 1);
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        setter.call(slider, String(min + value * (max - min)));
        slider.dispatchEvent(new Event('input', { bubbles: true }));
        slider.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      }
      const player = youtubePlayer(href, doc);
      if (typeof player?.setVolume === 'function' && typeof player?.unMute === 'function') {
        player.setVolume(Math.round(value * 100));
        if (value > 0) player.unMute();
        else if (typeof player.mute === 'function') player.mute();
        return true;
      }
    } catch (_) {}
    media.volume = value;
    if (value > 0) media.muted = false;
    return true;
  };
})();
