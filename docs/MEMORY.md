# Memory and CPU

Measured with `make memory`: the same headless Firefox (throwaway profile) with 12 tabs, one playing audio and eleven plain pages,
once with an empty control extension and once with this one, three runs each. Memory is PSS, which does not count pages that
Firefox's processes share twice. Numbers are from one machine (Firefox 159, Linux); treat them as orders of magnitude.

| | control | with MPRIS Bridge | difference |
|---|---|---|---|
| Content processes (9) | 228 MB | 248 MB | about +20 MB, roughly 1.7 MB per tab |
| Firefox main process | 471 MB | 473 MB | within noise |
| Native helper | none | 1.2-1.5 MB PSS (about 4 MB RSS) | |
| CPU over 30 s, whole session | 4.7 s | 5.6 s | within noise (control runs ranged 2.8-6.8 s) |

## Where it goes

- **The helper** is one Rust process, 2 threads, about 4 MB resident however many tabs there are (5 tabs: 4.3 MB). The Python
  helper it replaced used about 32 MB.
- **The content script** is the real cost: every page, and every frame in it, gets its own copy (a JavaScript compartment plus the
  wrappers Firefox keeps for the page-facing `MediaSession` hook), which is where the roughly 1.7 MB per tab comes from. Any
  extension that watches all pages for media pays it; the script itself is small and keeps no data.
- **The background page** holds one small state object per tab with media. It is not a measurable part of the difference.

## What the script does to stay cheap

- A page without media does no work: the once-a-second poll starts at the first media event and stops when the media is gone.
- Messages are sent only when something changed, plus a position sync every 5 seconds while playing; the helper extrapolates the
  position in between.
- Nothing is read from or written to storage, and no timers run in the background page.

## Not reduced, on purpose

- Injecting the script only into tabs that make sound would save the per-tab cost, but the page's `setActionHandler` calls happen
  at load, before a late-injected script could see them, so next/previous support would be lost.
- `all_frames` keeps embedded players (YouTube embeds, Twitch and the like) working at the price of one copy per frame.
