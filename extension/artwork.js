// Download only artwork from known image CDNs. Cookies and page referrers are omitted.
// Pass the image to the local helper so desktop widgets do not need separate network access.
globalThis.bridgeArtworkAllowed = function (value) {
  try {
    const u = new URL(value);
    return u.protocol === "https:" && !u.username && !u.password && !u.port &&
      ((u.hostname === "i.ytimg.com" && /^\/vi(?:_webp)?\/[\w-]+\//.test(u.pathname)) ||
       (u.hostname === "static-cdn.jtvnw.net" && u.pathname.startsWith("/jtv_user_pictures/")));
  } catch (_) { return false; }
};
globalThis.bridgeFetchArtwork = async function (url) {
  if (!bridgeArtworkAllowed(url)) return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(url, { credentials: "omit", referrerPolicy: "no-referrer",
      redirect: "error", signal: controller.signal });
    if (!response.ok || !response.headers.get("Content-Type")?.startsWith("image/")) return null;
    const reader = response.body.getReader();
    const chunks = [];
    let length = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > 2 * 1024 * 1024) { await reader.cancel(); return null; }
      chunks.push(value);
    }
    let binary = "";
    for (const chunk of chunks) for (let i = 0; i < chunk.length; i += 8192)
      binary += String.fromCharCode(...chunk.subarray(i, i + 8192));
    return binary ? btoa(binary) : null;
  } catch (_) { return null; }
  finally { clearTimeout(timer); }
};
