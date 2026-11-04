import os, json, time, http.server, threading, subprocess, zipfile, tempfile, pathlib, shutil
import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

ROOT = pathlib.Path(__file__).resolve().parents[2]
HOST = pathlib.Path(
    os.environ.get("MPRIS_BRIDGE_HOST", ROOT / "host/target/release/mpris-bridge-host")
).resolve()
assert HOST.is_file(), "Build the helper first or set MPRIS_BRIDGE_HOST"
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


def players():
    names = bus.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "ListNames",
        None,
        None,
        0,
        3000,
        None,
    ).unpack()[0]
    result = {}
    for name in names:
        if not name.startswith("org.mpris.MediaPlayer2.firefox_bridge."):
            continue
        try:
            result[name] = bus.call_sync(
                name,
                "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties",
                "GetAll",
                GLib.Variant("(s)", ("org.mpris.MediaPlayer2.Player",)),
                None,
                0,
                3000,
                None,
            ).unpack()[0]
        except GLib.Error as error:
            if Gio.DBusError.get_remote_error(error) not in (
                "org.freedesktop.DBus.Error.ServiceUnknown",
                "org.freedesktop.DBus.Error.NameHasNoOwner",
                "org.freedesktop.DBus.Error.NoReply",
            ):
                raise
    return result


def wait(desc, fn, timeout=25):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = fn()
        if v:
            print("PASS:", desc, flush=True)
            return v
        time.sleep(0.25)
    raise AssertionError((desc, players()))


class Site(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / "tests/e2e/site"), **kw)

    def do_GET(self):
        if self.path.startswith("/watch"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""<!doctype html><title>Old document title</title><div id="movie_player"></div><audio id="m" src="/tone.ogg" loop></audio><script>
const id=new URL(location.href).searchParams.get('v');
window.details={videoId:id,title:'Track '+id,author:'Author '+id,thumbnail:{thumbnails:[{url:'https://i.ytimg.com/vi/'+id+'/mqdefault.jpg',width:320,height:180}]}};
const yt=document.querySelector('#movie_player');
yt.getPlayerResponse=()=>({videoDetails:window.details});
yt.getVolume=()=>m.volume*100;yt.isMuted=()=>m.muted;
yt.setVolume=v=>{window.lastApiVolume=v;m.volume=v/100;};yt.unMute=()=>m.muted=false;yt.mute=()=>m.muted=true;
if(navigator.mediaSession) navigator.mediaSession.metadata=new MediaMetadata({title:'STALE SESSION TITLE',artwork:[{src:'/art96.png'}]});
m.play();
window.navigateTrack=(id)=>{history.pushState({},'', '/watch?v='+id);dispatchEvent(new Event('yt-navigate-finish'));};
window.finishTrack=(id)=>{window.details={videoId:id,title:'Track '+id,author:'Author '+id,thumbnail:{thumbnails:[{url:'https://i.ytimg.com/vi/'+id+'/mqdefault.jpg',width:320,height:180}]}};dispatchEvent(new Event('yt-player-updated'));};
</script>""")
            return
        if self.path.startswith("/firstchannel"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""<!doctype html><title>Stale channel</title><meta property="og:image" content="https://static-cdn.jtvnw.net/jtv_user_pictures/stale.png"><a id="channel" href="/firstchannel"><img id="avatar" alt="firstchannel" src="https://static-cdn.jtvnw.net/jtv_user_pictures/test-first-profile_image-300x300.png"></a><input id="level" type="range" min="0" max="1" step="0.01" value="0.6" data-a-target="player-volume-slider"><button id="mute">Mute</button><audio id="m" src="/tone.ogg" loop></audio><script>
            window.savedVolume=0.6;window.siteMuted=false;window.levelControl=level;
            function renderVolume(){m.volume=siteMuted?0:savedVolume;m.muted=siteMuted;levelControl.value=siteMuted?0:savedVolume;}
            window.levelControl=level;level.addEventListener('input',()=>{savedVolume=Number(levelControl.value);siteMuted=savedVolume===0;renderVolume();});
            mute.onclick=()=>{siteMuted=!siteMuted;renderVolume();};
            renderVolume();m.play();
            window.switchChannel=()=>history.pushState({},'', '/secondchannel');
            window.finishChannel=()=>{channel.href='/secondchannel';avatar.alt='secondchannel';avatar.src='https://static-cdn.jtvnw.net/jtv_user_pictures/test-second-profile_image-300x300.png';};
            </script>""")
            return
        super().do_GET()

    def log_message(self, *a):
        pass


tone = ROOT / "tests/e2e/site/tone.ogg"
if not tone.exists():
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=300",
            "-c:a",
            "libvorbis",
            "-q:a",
            "0",
            str(tone),
        ],
        check=True,
    )
server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site)

threading.Thread(target=server.serve_forever, daemon=True).start()
base = "http://www.youtube.com:" + str(server.server_port)
opts = Options()
opts.binary_location = (
    os.environ.get("FIREFOX") or shutil.which("firefox") or shutil.which("zen-browser")
)
opts.add_argument("-headless")
opts.add_argument("--allow-system-access")
opts.accept_insecure_certs = True
opts.page_load_strategy = "eager"
for k, v in {
    "network.dns.localDomains": "www.youtube.com,www.twitch.tv,player.test",
    "network.proxy.type": 0,
    "network.trr.mode": 5,
    "dom.security.https_only_mode": False,
    "dom.security.https_first": False,
    "media.autoplay.default": 0,
    "media.autoplay.blocking_policy": 0,
    "media.block-autoplay-until-in-foreground": False,
    "browser.startup.page": 0,
    "browser.tabs.warnOnClose": False,
}.items():
    opts.set_preference(k, v)
with tempfile.TemporaryDirectory(prefix="mpris-addon-test-") as temp:
    # Use the unmodified native helper directly, without the old 30-second supervisor.
    os.environ["HOME"] = temp
    os.environ["XDG_CONFIG_HOME"] = str(pathlib.Path(temp) / ".config")
    for folder in [
        ".mozilla/native-messaging-hosts",
        ".zen/native-messaging-hosts",
        ".config/zen/native-messaging-hosts",
    ]:
        target = pathlib.Path(temp) / folder
        target.mkdir(parents=True)
        (target / "mpris_tab_bridge.json").write_text(
            json.dumps(
                {
                    "name": "mpris_tab_bridge",
                    "description": "Test native host",
                    "path": str(HOST),
                    "type": "stdio",
                    "allowed_extensions": ["mpris-tab-bridge@frixlt.github.io"],
                }
            )
        )
    xpi = pathlib.Path(temp) / "bridge.xpi"
    with zipfile.ZipFile(xpi, "w") as z:
        for p in (ROOT / "extension").rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(ROOT / "extension"))
    driver = webdriver.Firefox(
        options=opts,
        service=Service(
            os.environ.get("GECKODRIVER") or shutil.which("geckodriver"),
            log_output=str(pathlib.Path(temp) / "geckodriver.log"),
        ),
    )
    try:
        driver.set_page_load_timeout(20)
        driver.install_addon(str(xpi), temporary=True)
        driver.switch_to.new_window("tab")
        driver.get(base + "/watch?v=ONE")
        first = driver.current_window_handle
        time.sleep(3)
        wait("first tab appears", lambda: bool(players()))
        driver.switch_to.new_window("tab")
        driver.get(base + "/watch?v=TWO")
        second = driver.current_window_handle
        states = wait(
            "two independent tab players",
            lambda: p if len(p := players()) == 2 else None,
        )
        one = next(
            k for k, v in states.items() if v["Metadata"]["xesam:title"] == "Track ONE"
        )
        two = next(
            k for k, v in states.items() if v["Metadata"]["xesam:title"] == "Track TWO"
        )
        assert states[one]["Metadata"]["mpris:artUrl"].endswith("/ONE/mqdefault.jpg")
        print(
            "PASS: page player data overrides stale MediaSession title/art", flush=True
        )
        subprocess.run(
            [
                "busctl",
                "--user",
                "set-property",
                one,
                "/org/mpris/MediaPlayer2",
                "org.mpris.MediaPlayer2.Player",
                "Volume",
                "d",
                "0.3",
            ],
            check=True,
        )
        wait(
            "volume routed to first tab only",
            lambda: (
                abs(players().get(one, {}).get("Volume", 0) - 0.3) < 0.01
                and abs(players().get(two, {}).get("Volume", 0) - 1) < 0.01
            ),
        )
        driver.switch_to.window(first)
        assert abs(driver.execute_script("return m.volume") - 0.3) < 0.01
        assert driver.execute_script("return lastApiVolume") == 30
        print("PASS: YouTube volume uses the site player API", flush=True)
        driver.execute_script("navigateTrack('THREE')")
        wait(
            "old player removed during mismatched video transition",
            lambda: one not in players(),
        )
        driver.execute_script("finishTrack('THREE')")
        wait(
            "SPA metadata changes on the same tab bus",
            lambda: (
                players().get(one, {}).get("Metadata", {}).get("xesam:title")
                == "Track THREE"
            ),
        )
        assert players()[one]["Metadata"]["mpris:artUrl"].endswith(
            "/THREE/mqdefault.jpg"
        )
        driver.switch_to.window(second)
        driver.close()
        driver.switch_to.window(first)
        wait("closed tab disappears immediately", lambda: two not in players())
        driver.get(base + "/plain.html")
        wait("navigation to a page without media removes player", lambda: not players())
        driver.get(base + "/watch?v=FOUR")
        wait("media returns after navigation", lambda: bool(players()))
        # Real browser discard via a small temporary controller extension.
        control = pathlib.Path(temp) / "control.xpi"
        manifest = {
            "manifest_version": 2,
            "name": "Test discard",
            "version": "1.0",
            "browser_specific_settings": {"gecko": {"id": "mpris-test-discard@local"}},
            "permissions": ["tabs"],
            "background": {"scripts": ["background.js"]},
        }
        with zipfile.ZipFile(control, "w") as z:
            z.writestr("manifest.json", json.dumps(manifest))
            z.writestr(
                "background.js",
                "browser.tabs.query({}).then(async tabs=>{const t=tabs.find(t=>t.url.includes('watch?v=FOUR'));await browser.tabs.create({url:'about:blank',active:true});await browser.tabs.discard(t.id);});",
            )
        driver.install_addon(str(control), temporary=True)
        wait("real browser tab discard removes player", lambda: not players())
        driver.switch_to.window(next(h for h in driver.window_handles if h != first))
        driver.switch_to.new_window("tab")
        driver.get("http://www.twitch.tv:" + str(server.server_port) + "/firstchannel")
        found = wait(
            "Twitch avatar belongs to the current channel",
            lambda: next(
                (
                    (n, p)
                    for n, p in players().items()
                    if p["Metadata"]
                    .get("mpris:artUrl", "")
                    .endswith("test-first-profile_image-300x300.png")
                ),
                None,
            ),
        )
        twitch = found[0]

        def set_volume(name, value):
            subprocess.run(
                [
                    "busctl",
                    "--user",
                    "set-property",
                    name,
                    "/org/mpris/MediaPlayer2",
                    "org.mpris.MediaPlayer2.Player",
                    "Volume",
                    "d",
                    str(value),
                ],
                check=True,
            )

        driver.execute_script("mute.click()")
        wait(
            "site mute publishes zero without removing the looping player",
            lambda: twitch in (p := players()) and p[twitch]["Volume"] == 0,
        )
        set_volume(twitch, 0.25)
        wait(
            "panel volume updates the Twitch UI store and unmutes",
            lambda: driver.execute_script(
                "return !siteMuted && !m.muted && Math.abs(savedVolume-.25)<.001 && Math.abs(m.volume-.25)<.001 && Math.abs(Number(level.value)-.25)<.001"
            ),
        )
        for expected in [0, 0.25]:
            driver.execute_script("mute.click()")
            wait(
                "Twitch mute toggle preserves the selected volume " + str(expected),
                lambda: (
                    abs(players().get(twitch, {}).get("Volume", -1) - expected) < 0.001
                ),
            )
        driver.execute_script(
            "level.value='.4';level.dispatchEvent(new Event('input',{bubbles:true}));"
        )
        wait(
            "Twitch slider changes reach MPRIS",
            lambda: abs(players().get(twitch, {}).get("Volume", -1) - 0.4) < 0.001,
        )
        driver.execute_script("mute.click()")
        set_volume(twitch, 0)
        assert driver.execute_script("return siteMuted && m.muted")
        set_volume(twitch, 0.35)
        wait(
            "a later panel adjustment restores sound at the requested volume",
            lambda: driver.execute_script(
                "return !siteMuted && Math.abs(savedVolume-.35)<.001 && Math.abs(m.volume-.35)<.001"
            ),
        )

        # The same implementation must work with Spotify's wrapper-labelled input,
        # with no Twitch selector and without mistaking the seek/resizer ranges for volume.
        driver.execute_script("""
        const input=level;input.removeAttribute('data-a-target');
        const wrapper=document.createElement('div');wrapper.dataset.testid='volume-bar';
        input.before(wrapper);wrapper.append(input);input.id='plain-range';input.step='0.1';
        window.volumeInput=input;
        const seek=document.createElement('input');seek.type='range';seek.min=0;seek.max=100;seek.value=33;seek.dataset.testid='playback-progressbar';document.body.append(seek);window.seek=seek;
        const resize=document.createElement('input');resize.type='range';resize.min=280;resize.max=420;resize.value=300;resize.className='LayoutResizer__input';document.body.append(resize);window.resize=resize;
        """)
        set_volume(twitch, 0.55)
        wait(
            "shared controller handles a Spotify-style volume wrapper at exact 5% steps",
            lambda: driver.execute_script(
                "return Math.abs(savedVolume-.55)<.001 && Math.abs(Number(volumeInput.value)-.55)<.001"
            ),
        )
        assert driver.execute_script('return seek.value==="33" && resize.value==="300"')
        driver.execute_script("mute.click();mute.click()")
        wait(
            "shared controller keeps the selected volume after mute/unmute",
            lambda: abs(players().get(twitch, {}).get("Volume", -1) - 0.55) < 0.001,
        )
        driver.execute_script("switchChannel()")
        wait(
            "Twitch SPA does not retain the previous channel avatar",
            lambda: (
                twitch in (p := players())
                and p[twitch]["Metadata"].get("xesam:title") == "secondchannel - Twitch"
                and not p[twitch]["Metadata"].get("mpris:artUrl")
            ),
        )
        driver.execute_script("finishChannel()")
        wait(
            "Twitch SPA picks the new channel avatar despite stale og:image",
            lambda: (
                players()
                .get(twitch, {})
                .get("Metadata", {})
                .get("mpris:artUrl", "")
                .endswith("test-second-profile_image-300x300.png")
            ),
        )
        driver.switch_to.new_window("tab")
        driver.get("http://player.test:" + str(server.server_port) + "/firstchannel")
        generic = wait(
            "unknown website exports a media player",
            lambda: next(
                (
                    n
                    for n, p in players().items()
                    if p["Metadata"]
                    .get("xesam:url", "")
                    .startswith("http://player.test:")
                ),
                None,
            ),
        )
        set_volume(generic, 0.45)
        wait(
            "the same volume controller works on an unknown domain",
            lambda: (
                driver.execute_script(
                    "return Math.abs(savedVolume-.45)<.001 && Math.abs(m.volume-.45)<.001"
                )
                and abs(players().get(generic, {}).get("Volume", -1) - 0.45) < 0.001
            ),
        )
        assert abs(players()[twitch]["Volume"] - 0.55) < 0.001
        for expected in [0, 0.45]:
            driver.execute_script("mute.click()")
            wait(
                "unknown-site mute retains its selected volume " + str(expected),
                lambda: (
                    abs(players().get(generic, {}).get("Volume", -1) - expected) < 0.001
                ),
            )
        print("ALL BROWSER REGRESSIONS PASSED", flush=True)
    finally:
        driver.quit()
        server.shutdown()
