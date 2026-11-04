// Use the site's own controls where it keeps a separate volume/mute store.
// Changing only HTMLMediaElement.volume leaves that store (and its UI) stale.
(() => {
  const clamp = value => Math.max(0, Math.min(1, value));
  // Use semantic HTML controls, not a list of website hostnames/selectors.
  // Never confuse an unlabelled seek bar or layout resizer with volume.
  function volumeSlider(media, doc) {
    const volumeName = /volume|loudness|громк|lautstärke|volumen|głośno|音量|음량/iu;
    const candidates = [...doc.querySelectorAll('input[type="range"]')].filter(input => {
      if (input.disabled || input.getAttribute('aria-disabled') === 'true') return false;
      const min = Number(input.min || 0), max = Number(input.max || 100);
      if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return false;
      const labels = [...(input.labels || [])].map(label => label.textContent || '');
      for (const id of (input.getAttribute('aria-labelledby') || '').split(/\s+/))
        if (id) labels.push(doc.getElementById(id)?.textContent || '');
      if (volumeName.test(labels.join(' '))) return true;
      let node = input;
      for (let depth = 0; node && depth < 7; ++depth, node = node.parentElement) {
        if (node !== input && node.querySelectorAll('input[type="range"]').length !== 1) break;
        const names = [...node.attributes].filter(a =>
          ['id','class','name','title','aria-label','data-testid','data-a-target'].includes(a.name)
        ).map(a => a.value).join(' ');
        if (volumeName.test(names)) return true;
      }
      return false;
    });
    // Prefer controls belonging to the same media component on multi-player pages.
    for (let parent = media.parentElement; parent; parent = parent.parentElement) {
      if (parent.querySelectorAll('video,audio').length > 1) break;
      const local = candidates.filter(candidate => parent.contains(candidate));
      if (local.length === 1) return local[0];
    }
    return candidates.length === 1 ? candidates[0] : null;
  }
  function youtubePlayer(href, doc) {
    return /(^|\.)youtube\.com$/.test(new URL(href).hostname)
      ? doc.querySelector('#movie_player')?.wrappedJSObject : null;
  }
  globalThis.bridgeMediaVolume = function (media, href, doc) {
    try {
      const slider = volumeSlider(media, doc);
      if (slider) {
        const min = Number(slider.min || 0), max = Number(slider.max || 100);
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
      const slider = volumeSlider(media, doc);
      if (slider) {
        const min = Number(slider.min || 0), max = Number(slider.max || 100);
        // A coarse native keyboard step must not round a requested 5% change away.
        const step = Number(slider.step);
        if (Number.isFinite(step) && step > (max - min) / 100)
          slider.step = String((max - min) / 100);
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
