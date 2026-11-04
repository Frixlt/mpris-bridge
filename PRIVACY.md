# Privacy policy — MPRIS Tab Bridge

MPRIS Tab Bridge has no telemetry, advertising, account system or remote backend. It does not upload browsing history or media metadata to the developer.

The content script runs in non-private web pages and their frames. It reads media element state, MediaSession metadata and selected page information needed for media controls. While a page contains media, the extension sends the media title, artist, album, artwork URL, media/page URL, playback position, playback status, volume and supported controls through Firefox native messaging to a helper on the same computer. The helper exposes that information on the user's session D-Bus as MPRIS players. Other applications running in that session can read it and issue media-control commands.

The extension does not itself fetch album covers. Desktop media widgets may fetch the artwork URLs, including YouTube thumbnail URLs, from their respective providers. Those requests are governed by the desktop widget and artwork provider.

No metadata is intentionally retained on disk by the extension. In-memory frame state is removed when its document disconnects, is closed or discarded. The native helper is a separately installed Linux program. Private/incognito tabs are excluded.

Permissions:

- All web pages: detect and control media on arbitrary sites, including embedded frames.
- Tabs: associate frames with a tab, handle tab lifecycle and raise the chosen tab when requested.
- Native messaging: communicate with the local MPRIS helper.

For questions or reports, use https://github.com/Frixlt/mpris-bridge/issues.
