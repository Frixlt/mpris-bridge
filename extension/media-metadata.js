// Never combine a new YouTube URL with an old MediaSession title/art.
globalThis.bridgeYoutubeMetadata = function (href, details) {
  const url = new URL(href);
  if (!/(^|\.)youtube\.com$/.test(url.hostname)) return undefined;
  const requested = url.searchParams.get("v") || url.pathname.match(/^\/(?:shorts|embed|live)\/([^/?]+)/)?.[1];
  if (!details?.videoId || !details.title || (requested && requested !== details.videoId)) return null;
  const id = encodeURIComponent(details.videoId);
  return {
    title: String(details.title), artist: String(details.author || ""), album: "YouTube",
    artUrl: (details.thumbnail?.thumbnails || []).filter(t => {
      try { const u = new URL(t.url); return u.protocol === 'https:' && u.hostname === 'i.ytimg.com' && u.pathname.startsWith(`/vi/${id}/`) && t.width / t.height > 1.6; } catch (_) { return false; }
    }).sort((a,b) => b.width - a.width)[0]?.url || `https://i.ytimg.com/vi/${id}/mqdefault.jpg`,
    url: `https://www.youtube.com/watch?v=${id}`,
  };
};

// Twitch leaves MediaSession/og:image unchanged during client-side navigation.
// Bind the avatar to an image labelled/linked to the current channel instead.
globalThis.bridgeTwitchMetadata = function (href, images) {
  const url = new URL(href);
  if (!/^(www\.)?twitch\.tv$/.test(url.hostname)) return undefined;
  const channel = url.pathname.match(/^\/([a-zA-Z0-9_]+)\/?$/)?.[1]?.toLowerCase();
  if (!channel || ['directory','downloads','settings','videos','search','login','signup','subscriptions','inventory','wallet'].includes(channel)) return undefined;
  let avatar = '';
  for (const image of images) {
    let matches = (image.alt || '').toLowerCase() === channel;
    if (image.href) try {
      const link = new URL(image.href, href);
      matches ||= /^(www\.)?twitch\.tv$/.test(link.hostname) &&
        [ `/${channel}`, `/${channel}/`, `/${channel}/about` ].includes(link.pathname.toLowerCase());
    } catch (_) {}
    try {
      const src = new URL(image.src);
      if (matches && src.protocol === 'https:' && src.hostname === 'static-cdn.jtvnw.net' && src.pathname.startsWith('/jtv_user_pictures/')) {
        avatar = src.href.replace(/-profile_image-\d+x\d+\./, '-profile_image-300x300.'); break;
      }
    } catch (_) {}
  }
  return { title: `${channel} - Twitch`, artist: channel, album: 'Twitch',
    artUrl: avatar, url: `https://www.twitch.tv/${channel}` };
};
