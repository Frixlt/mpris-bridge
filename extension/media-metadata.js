// Never combine a new YouTube URL with an old MediaSession title/art.
globalThis.bridgeYoutubeMetadata = function (href, details) {
  const url = new URL(href);
  if (!/(^|\.)youtube\.com$/.test(url.hostname)) return undefined;
  const requested = url.searchParams.get("v") || url.pathname.match(/^\/(?:shorts|embed|live)\/([^/?]+)/)?.[1];
  if (!details?.videoId || !details.title || (requested && requested !== details.videoId)) return null;
  const id = encodeURIComponent(details.videoId);
  return {
    title: String(details.title), artist: String(details.author || ""), album: "YouTube",
    artUrl: `https://i.ytimg.com/vi/${id}/hqdefault.jpg`,
    url: `https://www.youtube.com/watch?v=${id}`,
  };
};
