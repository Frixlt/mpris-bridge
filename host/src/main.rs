//! Native-messaging host that publishes the browser's media tabs as MPRIS players.
//!
//! Firefox starts it for the extension and talks to it with length-prefixed JSON on stdin/stdout.
//! Every tab with media becomes its own player, `org.mpris.MediaPlayer2.firefox_bridge.p<pid>t<tab>`.
//! It exits when Firefox closes the pipe, and the players go with it.
//!
//! in : {"tab", "gone"?, "title", "artist", "album", "artUrl", "url", "lengthUs", "positionUs",
//!       "playing", "buffering", "rate", "volume", "canNext", "canPrev", "canSeek"}   (partial updates merge)
//! out: {"tab", "cmd": "Play"|"Pause"|"PlayPause"|"Stop"|"Next"|"Previous"|"Seek"|"SetPosition"|"SetVolume"|"SetRate"|"Raise", "value"}
//!
//! stdout carries the protocol and nothing else: diagnostics go to stderr.

mod artwork;

use std::collections::hash_map::Entry;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::Instant;

use serde_json::{json, Value as Json};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::sync::mpsc::{unbounded_channel, UnboundedSender};
use zbus::object_server::SignalEmitter;
use zbus::zvariant::{ObjectPath, OwnedValue, Value};
use zbus::{connection, interface, Connection};

const PATH: &str = "/org/mpris/MediaPlayer2";
/// Firefox allows 4 GiB inbound; nothing this helper is sent comes near it
const MAX_MESSAGE: usize = 8 * 1024 * 1024;

type Out = UnboundedSender<Vec<u8>>;

#[derive(Clone)]
struct State {
    title: String,
    artist: String,
    album: String,
    art_url: String,
    url: String,
    length_us: i64,
    position_us: i64,
    playing: bool,
    buffering: bool,
    rate: f64,
    volume: f64,
    can_next: bool,
    can_prev: bool,
    can_seek: bool,
    stamp: Instant,
    /// Bumped when the track changes, so a page that keeps its own id still looks like a new track
    serial: u32,
}

impl State {
    fn new() -> Self {
        State {
            title: String::new(),
            artist: String::new(),
            album: String::new(),
            art_url: String::new(),
            url: String::new(),
            length_us: 0,
            position_us: 0,
            playing: false,
            buffering: false,
            rate: 1.0,
            volume: 1.0,
            can_next: false,
            can_prev: false,
            can_seek: false,
            stamp: Instant::now(),
            serial: 0,
        }
    }

    fn position(&self) -> i64 {
        if self.playing && !self.buffering {
            self.position_us + (self.stamp.elapsed().as_secs_f64() * 1e6 * self.rate) as i64
        } else {
            self.position_us
        }
    }

    fn status(&self) -> &'static str {
        // A stalled stream reads as Paused, so a progress bar stops with the picture
        if self.playing && !self.buffering { "Playing" } else { "Paused" }
    }
}

/// What a message changed, so only those properties are announced
#[derive(Default)]
struct Changes {
    status: bool,
    metadata: bool,
    rate: bool,
    volume: bool,
    can_next: bool,
    can_prev: bool,
    can_seek: bool,
    seeked: Option<i64>,
}

fn text(v: &Json, key: &str) -> Option<String> {
    v.get(key)?.as_str().map(str::to_owned)
}
fn num(v: &Json, key: &str) -> Option<f64> {
    v.get(key)?.as_f64()
}
fn flag(v: &Json, key: &str) -> Option<bool> {
    v.get(key)?.as_bool()
}

/// Merge a message into the state. Fields of the wrong type are ignored rather than fatal:
/// a panic would take every player with it.
fn apply(state: &mut State, msg: &Json) -> Changes {
    let before = state.clone();
    let before_pos = state.position();
    let mut c = Changes::default();

    if let Some(v) = text(msg, "title") { state.title = v; }
    if let Some(v) = text(msg, "artist") { state.artist = v; }
    if let Some(v) = text(msg, "album") { state.album = v; }
    if let Some(v) = text(msg, "artUrl") { state.art_url = v; }
    if let Some(v) = text(msg, "url") { state.url = v; }
    if let Some(v) = num(msg, "lengthUs") { state.length_us = v as i64; }
    if let Some(v) = num(msg, "positionUs") { state.position_us = v as i64; }
    if let Some(v) = flag(msg, "playing") { state.playing = v; }
    if let Some(v) = flag(msg, "buffering") { state.buffering = v; }
    if let Some(v) = num(msg, "rate") { state.rate = v; }
    if let Some(v) = num(msg, "volume") { state.volume = v; }
    if let Some(v) = flag(msg, "canNext") { state.can_next = v; }
    if let Some(v) = flag(msg, "canPrev") { state.can_prev = v; }
    if let Some(v) = flag(msg, "canSeek") { state.can_seek = v; }
    state.stamp = Instant::now();

    if state.url != before.url || state.title != before.title {
        state.serial += 1;
    }
    c.status = state.status() != before.status();
    c.metadata = state.title != before.title
        || state.artist != before.artist
        || state.album != before.album
        || state.art_url != before.art_url
        || state.url != before.url
        || state.length_us != before.length_us;
    c.rate = state.rate != before.rate;
    c.volume = state.volume != before.volume;
    c.can_next = state.can_next != before.can_next;
    c.can_prev = state.can_prev != before.can_prev;
    c.can_seek = state.can_seek != before.can_seek;
    // A position off the extrapolated line is a seek (a new track starting over is not one)
    if !c.metadata && (state.position_us - before_pos).abs() > 2_000_000 {
        c.seeked = Some(state.position_us);
    }
    c
}

fn owned<'a>(v: impl Into<Value<'a>>) -> OwnedValue {
    OwnedValue::try_from(v.into()).unwrap_or_else(|_| OwnedValue::from(0u8))
}

struct Root {
    tab: i64,
    out: Out,
}

#[interface(name = "org.mpris.MediaPlayer2")]
impl Root {
    fn raise(&self) {
        send(&self.out, self.tab, "Raise", Json::Null);
    }
    fn quit(&self) {}

    #[zbus(property)]
    fn can_quit(&self) -> bool { false }
    #[zbus(property)]
    fn can_raise(&self) -> bool { true }
    #[zbus(property)]
    fn has_track_list(&self) -> bool { false }
    #[zbus(property)]
    fn identity(&self) -> String { "Firefox".into() }
    #[zbus(property)]
    fn desktop_entry(&self) -> String { "firefox".into() }
    #[zbus(property)]
    fn supported_uri_schemes(&self) -> Vec<String> { vec![] }
    #[zbus(property)]
    fn supported_mime_types(&self) -> Vec<String> { vec![] }
}

struct Player {
    tab: i64,
    out: Out,
    state: Arc<Mutex<State>>,
}

impl Player {
    fn with<T>(&self, f: impl FnOnce(&State) -> T) -> T {
        match self.state.lock() {
            Ok(s) => f(&s),
            Err(poisoned) => f(&poisoned.into_inner()),
        }
    }
    fn cmd(&self, cmd: &str, value: Json) {
        send(&self.out, self.tab, cmd, value);
    }
}

#[interface(name = "org.mpris.MediaPlayer2.Player")]
impl Player {
    fn next(&self) { self.cmd("Next", Json::Null) }
    fn previous(&self) { self.cmd("Previous", Json::Null) }
    fn pause(&self) { self.cmd("Pause", Json::Null) }
    fn play_pause(&self) { self.cmd("PlayPause", Json::Null) }
    fn stop(&self) { self.cmd("Stop", Json::Null) }
    fn play(&self) { self.cmd("Play", Json::Null) }
    fn seek(&self, offset: i64) { self.cmd("Seek", json!(offset)) }
    fn set_position(&self, _track_id: ObjectPath<'_>, position: i64) { self.cmd("SetPosition", json!(position)) }
    fn open_uri(&self, _uri: String) {}

    #[zbus(signal)]
    async fn seeked(emitter: &SignalEmitter<'_>, position: i64) -> zbus::Result<()>;

    #[zbus(property)]
    fn playback_status(&self) -> String { self.with(|s| s.status().to_owned()) }
    #[zbus(property)]
    fn loop_status(&self) -> String { "None".into() }
    #[zbus(property)]
    fn set_loop_status(&mut self, _v: String) {}
    #[zbus(property)]
    fn rate(&self) -> f64 { self.with(|s| s.rate) }
    #[zbus(property)]
    fn set_rate(&mut self, v: f64) { self.cmd("SetRate", json!(v)) }
    #[zbus(property)]
    fn shuffle(&self) -> bool { false }
    #[zbus(property)]
    fn set_shuffle(&mut self, _v: bool) {}
    #[zbus(property)]
    fn metadata(&self) -> std::collections::HashMap<String, OwnedValue> {
        let tab = self.tab;
        self.with(|s| {
            let mut d = std::collections::HashMap::new();
            if let Ok(id) = ObjectPath::try_from(format!("/org/mpris_bridge/t{}/n{}", tab, s.serial)) {
                d.insert("mpris:trackid".to_owned(), owned(id));
            }
            d.insert("mpris:length".to_owned(), owned(s.length_us));
            d.insert("xesam:title".to_owned(), owned(s.title.as_str()));
            let artists: Vec<&str> = if s.artist.is_empty() { vec![] } else { vec![s.artist.as_str()] };
            d.insert("xesam:artist".to_owned(), owned(artists));
            d.insert("xesam:album".to_owned(), owned(s.album.as_str()));
            d.insert("xesam:url".to_owned(), owned(s.url.as_str()));
            // Only what a desktop can load: not blob: or data: URLs
            if ["http://", "https://", "file://"].iter().any(|p| s.art_url.starts_with(p)) {
                d.insert("mpris:artUrl".to_owned(), owned(s.art_url.as_str()));
            }
            d
        })
    }
    #[zbus(property)]
    fn volume(&self) -> f64 { self.with(|s| s.volume) }
    #[zbus(property)]
    fn set_volume(&mut self, v: f64) { self.cmd("SetVolume", json!(v)) }
    #[zbus(property(emits_changed_signal = "false"))]
    fn position(&self) -> i64 { self.with(|s| s.position()) }
    #[zbus(property)]
    fn minimum_rate(&self) -> f64 { 0.25 }
    #[zbus(property)]
    fn maximum_rate(&self) -> f64 { 4.0 }
    #[zbus(property)]
    fn can_go_next(&self) -> bool { self.with(|s| s.can_next) }
    #[zbus(property)]
    fn can_go_previous(&self) -> bool { self.with(|s| s.can_prev) }
    #[zbus(property)]
    fn can_play(&self) -> bool { true }
    #[zbus(property)]
    fn can_pause(&self) -> bool { true }
    #[zbus(property)]
    fn can_seek(&self) -> bool { self.with(|s| s.can_seek) }
    #[zbus(property)]
    fn can_control(&self) -> bool { true }
}

/// One message to the extension, written whole by the single writer task
fn send(out: &Out, tab: i64, cmd: &str, value: Json) {
    let payload = json!({ "tab": tab, "cmd": cmd, "value": value }).to_string().into_bytes();
    let mut frame = (payload.len() as u32).to_ne_bytes().to_vec();
    frame.extend_from_slice(&payload);
    let _ = out.send(frame);
}

struct Tab {
    state: Arc<Mutex<State>>,
    /// Its own connection: every player serves the same object path, and signals must carry this tab's
    /// bus name as their sender for desktops to tell the tabs apart. Dropping it releases the name.
    conn: Connection,
    artwork: artwork::Artwork,
}

async fn open_tab(tab: i64, out: &Out) -> zbus::Result<Tab> {
    let state = Arc::new(Mutex::new(State::new()));
    let conn = connection::Builder::session()?
        .name(format!("org.mpris.MediaPlayer2.firefox_bridge.p{}t{}", std::process::id(), tab))?
        .serve_at(PATH, Root { tab, out: out.clone() })?
        .serve_at(PATH, Player { tab, out: out.clone(), state: state.clone() })?
        .build()
        .await?;
    Ok(Tab { state, conn, artwork: artwork::Artwork::default() })
}

async fn announce(tab: &Tab, c: Changes) -> zbus::Result<()> {
    let iface = tab.conn.object_server().interface::<_, Player>(PATH).await?;
    let player = iface.get().await;
    let ctx = iface.signal_emitter();
    if c.status { player.playback_status_changed(ctx).await?; }
    if c.metadata { player.metadata_changed(ctx).await?; }
    if c.rate { player.rate_changed(ctx).await?; }
    if c.volume { player.volume_changed(ctx).await?; }
    if c.can_next { player.can_go_next_changed(ctx).await?; }
    if c.can_prev { player.can_go_previous_changed(ctx).await?; }
    if c.can_seek { player.can_seek_changed(ctx).await?; }
    if let Some(pos) = c.seeked {
        Player::seeked(ctx, pos).await?;
    }
    Ok(())
}

async fn handle(tabs: &mut HashMap<i64, Tab>, out: &Out, mut msg: Json) {
    let Some(id) = msg.get("tab").and_then(Json::as_i64) else { return };
    if flag(&msg, "gone") == Some(true) {
        tabs.remove(&id);
        return;
    }
    if let Entry::Vacant(slot) = tabs.entry(id) {
        match open_tab(id, out).await {
            Ok(t) => { slot.insert(t); }
            Err(e) => {
                eprintln!("mpris-bridge: cannot publish tab {id}: {e}");
                return;
            }
        }
    }
    let Some(tab) = tabs.get_mut(&id) else { return };
    tab.artwork.resolve(id, &mut msg);
    let changes = {
        let mut state = match tab.state.lock() {
            Ok(s) => s,
            Err(p) => p.into_inner(),
        };
        apply(&mut state, &msg)
    };
    if let Err(e) = announce(tab, changes).await {
        eprintln!("mpris-bridge: tab {id}: {e}");
    }
}

#[tokio::main(flavor = "current_thread")]
async fn main() {
    let (out_tx, mut out_rx) = unbounded_channel::<Vec<u8>>();

    // The only writer of stdout, so frames never interleave
    tokio::spawn(async move {
        let mut stdout = tokio::io::stdout();
        while let Some(frame) = out_rx.recv().await {
            if stdout.write_all(&frame).await.is_err() || stdout.flush().await.is_err() {
                std::process::exit(0);
            }
        }
    });

    let mut stdin = tokio::io::stdin();
    let mut tabs: HashMap<i64, Tab> = HashMap::new();
    loop {
        let mut len = [0u8; 4];
        if stdin.read_exact(&mut len).await.is_err() {
            break; // Firefox closed the pipe
        }
        let size = u32::from_ne_bytes(len) as usize;
        if size > MAX_MESSAGE {
            break;
        }
        let mut buf = vec![0u8; size];
        if stdin.read_exact(&mut buf).await.is_err() {
            break;
        }
        match serde_json::from_slice::<Json>(&buf) {
            Ok(msg) => handle(&mut tabs, &out_tx, msg).await,
            Err(e) => eprintln!("mpris-bridge: bad message: {e}"),
        }
    }
    drop(tabs);
    std::process::exit(0);
}
