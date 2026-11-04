// A live content-script port owns each frame. Cached state cannot outlive its document.
const HOST = "mpris_tab_bridge";
const tabs = new Map();
let native = null;
let retry = 5000;
function post(msg) { try { if (native) native.postMessage(msg); } catch (_) {} }
function publish(id) {
  const tab = tabs.get(id);
  if (!tab) return;
  const frames = [...tab.frames.values()].filter(f => f.state);
  frames.sort((a, b) => Number(b.state.playing) - Number(a.state.playing) || b.at - a.at);
  tab.active = frames[0] || null;
  if (tab.active) post({ ...tab.active.state, tab: id });
  else post({ tab: id, gone: true });
}
function forget(id) {
  const tab = tabs.get(id);
  tabs.delete(id);
  post({ tab: id, gone: true });
  if (tab) for (const f of tab.frames.values()) f.port.disconnect();
}
function connect() {
  try { native = browser.runtime.connectNative(HOST); }
  catch (_) { native = null; setTimeout(connect, retry); return; }
  const connection = native;
  connection.onMessage.addListener(msg => { retry = 5000; onCommand(msg); });
  connection.onDisconnect.addListener(() => {
    if (native !== connection) return;
    native = null;
    setTimeout(connect, retry);
    retry = Math.min(retry * 2, 300000);
  });
  // Ask live documents instead of replaying potentially stale snapshots.
  for (const t of tabs.values()) for (const f of t.frames.values()) {
    f.state = null;
    try { f.port.postMessage({ cmd: "Refresh" }); } catch (_) {}
  }
}
browser.runtime.onConnect.addListener(port => {
  const sender = port.sender;
  if (port.name !== "mpris-bridge-media" || !sender.tab || sender.tab.incognito) return;
  const id = sender.tab.id;
  let tab = tabs.get(id);
  if (!tab) tabs.set(id, (tab = { frames: new Map(), active: null, windowId: sender.tab.windowId }));
  const frame = { port, state: null, at: 0, serial: 0 };
  tab.frames.set(sender.frameId, frame);
  port.onMessage.addListener(async msg => {
    if (!msg || typeof msg !== "object") return;
    const serial = ++frame.serial;
    if (msg.gone) {
      frame.state = null;
      if (tabs.get(id)?.frames.get(sender.frameId) === frame) publish(id);
      return;
    }
    // A queued report must not resurrect a discarded or navigated-away page.
    let current;
    try { current = await browser.tabs.get(id); } catch (_) { return; }
    if (serial !== frame.serial || tabs.get(id)?.frames.get(sender.frameId) !== frame) return;
    if (current.discarded || current.incognito) return;
    if (sender.frameId === 0 && msg.pageUrl !== current.url) return;
    frame.state = { ...msg, at: Date.now() };
    frame.at = Date.now();
    tab.windowId = current.windowId;
    publish(id);
  });
  port.onDisconnect.addListener(() => {
    const t = tabs.get(id);
    if (t?.frames.get(sender.frameId) !== frame) return;
    t.frames.delete(sender.frameId);
    publish(id);
    if (!t.frames.size) tabs.delete(id);
  });
});
browser.tabs.onRemoved.addListener(forget);
browser.tabs.onUpdated.addListener((id, change) => {
  if (change.discarded) { forget(id); return; }
  if (change.url) {
    const t = tabs.get(id);
    if (!t) return;
    for (const f of t.frames.values()) {
      f.state = null;
      try { f.port.postMessage({ cmd: "Refresh" }); } catch (_) {}
    }
    publish(id);
  }
});
function onCommand(msg) {
  const t = tabs.get(msg.tab);
  if (!t?.active) return;
  if (msg.cmd === "Raise") {
    browser.tabs.update(msg.tab, { active: true });
    browser.windows.update(t.windowId, { focused: true });
  } else {
    try { t.active.port.postMessage({ cmd: msg.cmd, value: msg.value }); } catch (_) {}
  }
}
connect();
