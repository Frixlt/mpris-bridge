// Collects what each tab's frames report and hands one state per tab to the native helper, which
// publishes it as an MPRIS player. Commands from the desktop come back the same way.
const HOST = "mpris_bridge";
const tabs = new Map(); // tabId -> { frames: Map(frameId -> state), active: frameId }
let port = null;
let retry = 5000;

function connect() {
  try {
    port = browser.runtime.connectNative(HOST);
  } catch (e) {
    port = null;
    return;
  }
  port.onMessage.addListener(msg => {
    retry = 5000;
    onCommand(msg);
  });
  port.onDisconnect.addListener(() => {
    port = null;
    // Helper missing or crashed: try again, less and less often
    setTimeout(connect, retry);
    retry = Math.min(retry * 2, 300000);
  });
  // A restarted helper knows nothing: tell it about every tab again
  for (const id of tabs.keys()) publish(id);
}

function post(msg) {
  if (port) port.postMessage(msg);
}

function publish(tabId) {
  const t = tabs.get(tabId);
  if (!t) return;
  let best = null;
  for (const [frame, s] of t.frames) {
    if (!best || (s.playing && !best.s.playing) || (s.playing === best.s.playing && s.at > best.s.at))
      best = { frame, s };
  }
  if (!best) {
    tabs.delete(tabId);
    post({ tab: tabId, gone: true });
    return;
  }
  t.active = best.frame;
  post(Object.assign({}, best.s, { tab: tabId }));
}

browser.runtime.onMessage.addListener((msg, sender) => {
  const tab = sender.tab;
  if (!tab || tab.incognito || typeof msg !== "object") return;
  let t = tabs.get(tab.id);
  if (msg.gone) {
    if (t) {
      t.frames.delete(sender.frameId);
      publish(tab.id);
    }
    return;
  }
  if (!t) tabs.set(tab.id, (t = { frames: new Map(), active: 0, windowId: tab.windowId }));
  t.windowId = tab.windowId;
  msg.at = Date.now();
  if (!msg.title) msg.title = tab.title || "";
  t.frames.set(sender.frameId, msg);
  publish(tab.id);
});

browser.tabs.onRemoved.addListener(id => {
  if (tabs.delete(id)) post({ tab: id, gone: true });
});
// A navigation drops the old page's frames; the new page reports for itself
browser.tabs.onUpdated.addListener((id, change) => {
  if (change.status === "loading" && change.url && tabs.has(id)) {
    tabs.delete(id);
    post({ tab: id, gone: true });
  }
});

function onCommand(msg) {
  const t = tabs.get(msg.tab);
  if (!t) return;
  if (msg.cmd === "Raise") {
    browser.tabs.update(msg.tab, { active: true });
    browser.windows.update(t.windowId, { focused: true });
    return;
  }
  browser.tabs.sendMessage(msg.tab, { cmd: msg.cmd, value: msg.value }, { frameId: t.active }).catch(() => {});
}

connect();
