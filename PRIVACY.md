# Privacy policy — MPRIS Tab Bridge

MPRIS Tab Bridge has no telemetry, advertising, account system or remote backend. It does not upload browsing history or media metadata to the developer.

The content script runs in non-private web pages and their frames. It reads media element state, MediaSession metadata and selected page information needed for media controls. While a page contains media, the extension sends the media title, artist, album, artwork URL, media/page URL, playback position, playback status, volume and supported controls through Firefox native messaging to a helper on the same computer. The helper exposes that information on the user's session D-Bus as MPRIS players. Other applications running in that session can read it and issue media-control commands.

The extension downloads YouTube thumbnails from i.ytimg.com and Twitch channel avatars from static-cdn.jtvnw.net to pass them to the local helper. Image requests omit cookies and page referrers. The image providers receive the requested image URL and ordinary network connection information. The helper temporarily caches validated image bytes as local files and publishes those file URLs through MPRIS, so desktop widgets can display them without downloading them again. Other artwork providers may still be downloaded by the desktop widget.

The extension does not retain metadata on disk. The local helper temporarily stores downloaded images for active tabs and removes their files when the tab is removed or the helper exits normally. In-memory frame state is removed when its document disconnects, is closed or discarded. The native helper is a separately installed Linux program. Private/incognito tabs are excluded.

Permissions:

- All web pages: detect and control media on arbitrary sites, including embedded frames.
- Tabs: associate frames with a tab, handle tab lifecycle and raise the chosen tab when requested.
- Native messaging: communicate with the local MPRIS helper.
- i.ytimg.com and static-cdn.jtvnw.net: download the current YouTube thumbnail and Twitch avatar for local display.

For questions or reports, use https://github.com/Frixlt/mpris-bridge/issues.
