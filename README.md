# MPRIS Bridge

Firefox on Linux does publish an MPRIS player, but it's a thin one. You get a tab title and play/pause, no artist, no cover art, no skip buttons, and the player hops between tabs as you use them. MPRIS Bridge fills that in. A small extension reads what each tab is playing, and a helper program publishes every tab as its own MPRIS player, with whatever metadata the page provides.

Media keys, panels, lock screens, `playerctl` and shell widgets pick it up on their own. There is nothing to configure on that side.

I wrote it because plasma-browser-integration does this job but drags a good part of KDE along with it. This is one extension and one 1.5 MB binary.

```
page -> extension -> helper -> D-Bus (org.mpris.MediaPlayer2.firefox_bridge.*)
page <- extension <- helper <- play, pause, seek, next ...
```

## Install

You need two pieces: the helper, and the extension.

**Helper**

On Arch:

```
yay -S mpris-bridge
```

Anywhere else, with Rust installed:

```
git clone https://github.com/totti786/mpris-bridge
cd mpris-bridge
scripts/install-host.sh
```

That builds the helper, copies it to `~/.local/lib/mpris-bridge` and registers it with Firefox. It also registers it for LibreWolf, Zen, Floorp and Waterfox if their profile folders exist. `scripts/install-host.sh --remove` undoes it.

**Extension**

The add-on isn't on addons.mozilla.org yet. Until it is, open `about:debugging#/runtime/this-firefox`, choose "Load Temporary Add-on" and pick `extension/manifest.json`. Firefox forgets temporary add-ons when it restarts, so you'll need to repeat that each time.

Start something playing in a tab and run `playerctl -l`. A `firefox_bridge.p…t…` entry should show up.

## What you get

- Title, artist, album and cover art from the page's own media session. If a page doesn't set one, it falls back to the page title (with a leading "(3)" and a trailing " - YouTube" removed), the page's `og:image` and, on YouTube, the video thumbnail and channel name.
- Play, pause, stop, seeking, volume and playback speed.
- Next and previous, when the page supports them. YouTube's own buttons are used if the page doesn't register handlers.
- One player per tab. They appear when a tab starts playing and go away when it closes or navigates.
- A tab that is stalled waiting for data reports itself as paused, so a progress bar stops along with the picture.
- A new track gets a new track id, even on sites that keep reusing one.

## Things to know

- Firefox keeps publishing its own player too, so anything that lists every player will show two. Filter out the bus names starting with `org.mpris.MediaPlayer2.firefox.instance` when a `firefox_bridge` player exists.
- Private windows are ignored on purpose.
- Chromium-based browsers aren't supported. They would need a different manifest and a way to hook the page's media session without Firefox's `exportFunction`.
- It is Linux only, since it speaks D-Bus.

## Privacy

Page titles, URLs, artwork links and playback state go from the extension to the helper on your machine, and from there onto your session D-Bus, where any program you run can read them. Nothing is sent anywhere else, and the extension declares that it collects no data.

## Resource use

The helper uses about 4 MB of RAM no matter how many tabs are open. The extension adds roughly 1.7 MB per tab, because each page gets its own copy of the content script. [docs/MEMORY.md](docs/MEMORY.md) has the measurements and how to repeat them.

## Building and testing

```
make build     # helper, release mode
make test      # helper tests against a private session bus
make e2e       # loads the extension in a headless Firefox and drives the players
make memory    # memory and CPU against an empty control extension
make lint      # web-ext lint
make xpi       # dist/mpris-bridge-<version>.xpi
```

The tests need `python3` with PyGObject. `make e2e` also needs Firefox, Node (for `web-ext`) and ffmpeg. Releasing is described in [docs/PUBLISHING.md](docs/PUBLISHING.md).

## License

MIT
