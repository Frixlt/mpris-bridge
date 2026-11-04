"""Runs the helper against a real session bus and talks to its players like a desktop would.

Needs a session bus (run under `dbus-run-session`) and the helper built with `cargo build --release`; PyGObject is only
the test client. Skipped without a bus.
"""
import json
import os
import struct
import subprocess
import time
import unittest

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
except (ImportError, ValueError):
    gi = None

# The helper under test: the release build, or whatever MPRIS_BRIDGE_HOST points at
HOST = os.environ.get("MPRIS_BRIDGE_HOST") or os.path.join(os.path.dirname(__file__), "..", "host", "target", "release", "mpris-bridge-host")
HOST_CMD = [HOST]
PREFIX = "org.mpris.MediaPlayer2.firefox_bridge."
PLAYER = "org.mpris.MediaPlayer2.Player"


def tab_state(**over):
    base = {"tab": 7, "title": "Video", "artist": "Channel", "album": "example.com", "artUrl": "https://example.com/a.jpg",
            "url": "https://example.com/v", "lengthUs": 120_000_000, "positionUs": 5_000_000, "playing": True,
            "buffering": False, "rate": 1.0, "volume": 0.8, "canNext": True, "canPrev": False, "canSeek": True}
    base.update(over)
    return base


@unittest.skipIf(gi is None or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"), "needs PyGObject and a session bus")
@unittest.skipUnless(os.path.exists(HOST), "build the helper first: make build")
class HostTest(unittest.TestCase):
    def setUp(self):
        self.proc = subprocess.Popen(HOST_CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def tearDown(self):
        self.proc.stdin.close()
        self.proc.wait(5)
        self.proc.stdout.close()

    def tx(self, msg):
        data = json.dumps(msg).encode()
        self.proc.stdin.write(struct.pack("=I", len(data)) + data)
        self.proc.stdin.flush()

    def rx(self):
        (size,) = struct.unpack("=I", self.proc.stdout.read(4))
        return json.loads(self.proc.stdout.read(size))

    def names(self):
        reply = self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames",
                                   None, None, Gio.DBusCallFlags.NONE, -1, None)
        return [n for n in reply.unpack()[0] if n.startswith(PREFIX) and ".p%dt" % self.proc.pid in n]

    def wait_name(self):
        for _ in range(50):
            names = self.names()
            if names:
                return names[0]
            time.sleep(0.1)
        self.fail("player never appeared")

    def get(self, name, prop):
        reply = self.bus.call_sync(name, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", "Get",
                                   GLib.Variant("(ss)", (PLAYER, prop)), None, Gio.DBusCallFlags.NONE, -1, None)
        return reply.unpack()[0]

    def metadata_types(self, name):
        """The D-Bus type of every Metadata entry: desktops reject a trackid sent as a string or a length as unsigned."""
        reply = self.bus.call_sync(name, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", "Get",
                                   GLib.Variant("(ss)", (PLAYER, "Metadata")), None, Gio.DBusCallFlags.NONE, -1, None)
        meta = reply.get_child_value(0).get_variant()
        return {meta.get_child_value(i).get_child_value(0).get_string():
                meta.get_child_value(i).get_child_value(1).get_variant().get_type_string() for i in range(meta.n_children())}

    def call(self, name, method, params=None):
        self.bus.call_sync(name, "/org/mpris/MediaPlayer2", PLAYER, method, params, None, Gio.DBusCallFlags.NONE, -1, None)

    def test_browser_artwork_cache_and_lifecycle(self):
        import base64
        from pathlib import Path
        from urllib.parse import urlparse, unquote
        image = (Path(__file__).parent / "e2e/site/art96.png").read_bytes()
        remote = "https://i.ytimg.com/vi/test/hqdefault.jpg"
        self.tx(tab_state(artUrl=remote, artData=base64.b64encode(image).decode()))
        name = self.wait_name()
        art = self.get(name, "Metadata")["mpris:artUrl"]
        self.assertTrue(art.startswith("file://"), art)
        path = Path(unquote(urlparse(art).path))
        self.assertEqual(path.read_bytes(), image)
        # Ordinary five-second reports must keep the downloaded file, not revert to HTTP.
        self.tx(tab_state(artUrl=remote))
        time.sleep(0.2)
        self.assertEqual(self.get(name, "Metadata")["mpris:artUrl"], art)
        self.tx(tab_state(tab=8, artUrl=remote, artData=base64.b64encode(image).decode()))
        time.sleep(0.2)
        second = next(n for n in self.names() if n.endswith("t8"))
        other = Path(unquote(urlparse(self.get(second, "Metadata")["mpris:artUrl"]).path))
        self.assertNotEqual(path, other)
        self.tx({"tab":7,"gone":True})
        time.sleep(0.2)
        self.assertFalse(path.exists())
        self.assertEqual(other.read_bytes(), image)

    def test_invalid_artwork_does_not_keep_previous_cover(self):
        import base64
        from pathlib import Path
        from urllib.parse import urlparse, unquote
        image = (Path(__file__).parent / "e2e/site/art96.png").read_bytes()
        self.tx(tab_state(artUrl="https://example.org/old.png", artData=base64.b64encode(image).decode()))
        name = self.wait_name()
        old = Path(unquote(urlparse(self.get(name,"Metadata")["mpris:artUrl"]).path))
        self.tx(tab_state(artUrl="https://example.org/new.png", artData=base64.b64encode(b"<html>not an image</html>").decode()))
        time.sleep(0.2)
        self.assertEqual(self.get(name,"Metadata")["mpris:artUrl"],"https://example.org/new.png")
        self.assertFalse(old.exists())

    def test_player_lifecycle(self):
        self.tx(tab_state())
        name = self.wait_name()
        meta = self.get(name, "Metadata")
        self.assertEqual(meta["xesam:title"], "Video")
        self.assertEqual(meta["xesam:artist"], ["Channel"])
        self.assertEqual(meta["mpris:length"], 120_000_000)
        self.assertEqual(meta["mpris:artUrl"], "https://example.com/a.jpg")
        types = self.metadata_types(name)
        self.assertEqual(types["mpris:trackid"], "o")
        self.assertEqual(types["mpris:length"], "x")
        self.assertEqual(types["xesam:artist"], "as")
        self.assertEqual(types["xesam:title"], "s")
        self.assertEqual(types["mpris:artUrl"], "s")
        self.assertEqual(self.get(name, "PlaybackStatus"), "Playing")
        self.assertTrue(self.get(name, "CanGoNext"))
        self.assertFalse(self.get(name, "CanGoPrevious"))
        self.assertGreaterEqual(self.get(name, "Position"), 5_000_000)

        self.tx(tab_state(buffering=True))
        time.sleep(0.3)
        self.assertEqual(self.get(name, "PlaybackStatus"), "Paused")  # a stalled stream must not keep a progress bar running

        self.tx(tab_state(artUrl="blob:https://example.com/x"))
        time.sleep(0.3)
        self.assertNotIn("mpris:artUrl", self.get(name, "Metadata"))  # nothing but http(s)/file URLs can be loaded by a desktop

        self.tx({"tab": 7, "gone": True})
        for _ in range(30):
            if not self.names():
                break
            time.sleep(0.1)
        self.assertEqual(self.names(), [])

    def test_commands_reach_the_extension(self):
        self.tx(tab_state())
        name = self.wait_name()
        self.call(name, "PlayPause")
        self.assertEqual(self.rx(), {"tab": 7, "cmd": "PlayPause", "value": None})
        self.call(name, "SetPosition", GLib.Variant("(ox)", ("/x", 30_000_000)))
        self.assertEqual(self.rx(), {"tab": 7, "cmd": "SetPosition", "value": 30_000_000})
        self.call(name, "Seek", GLib.Variant("(x)", (-5_000_000,)))
        self.assertEqual(self.rx(), {"tab": 7, "cmd": "Seek", "value": -5_000_000})

    def test_partial_updates_and_bad_input(self):
        self.tx(tab_state())
        name = self.wait_name()
        self.tx({"tab": 7, "playing": False})  # only what changed
        time.sleep(0.3)
        self.assertEqual(self.get(name, "PlaybackStatus"), "Paused")
        self.assertEqual(self.get(name, "Metadata")["xesam:title"], "Video")
        for junk in ({"tab": "x"}, {"nope": 1}, {"tab": 7, "lengthUs": "bad"}):
            self.tx(junk)
        self.tx(tab_state(title="Still alive"))
        time.sleep(0.3)
        self.assertEqual(self.get(name, "Metadata")["xesam:title"], "Still alive")

    def test_track_change_gets_new_id(self):
        self.tx(tab_state())
        name = self.wait_name()
        first = self.get(name, "Metadata")["mpris:trackid"]
        self.tx(tab_state(title="Other", url="https://example.com/other"))
        time.sleep(0.3)
        self.assertNotEqual(self.get(name, "Metadata")["mpris:trackid"], first)


if __name__ == "__main__":
    unittest.main()
