import assert from "node:assert/strict";
import test from "node:test";

class ListenerTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }

  emit(type) {
    for (const listener of this.listeners.get(type) || []) listener();
  }
}

test("auto refresh throttles focus/pageshow and refreshes visible tabs after the freshness window", async () => {
  const originalWindow = globalThis.window;
  const originalDocument = globalThis.document;
  const originalCustomEvent = globalThis.CustomEvent;
  const originalDateNow = Date.now;

  let now = 1_000_000;
  const events = [];
  const intervals = [];
  const windowTarget = new ListenerTarget();
  const documentTarget = new ListenerTarget();
  documentTarget.visibilityState = "visible";

  globalThis.window = Object.assign(windowTarget, {
    setInterval(callback, delay) {
      intervals.push({ callback, delay });
      return intervals.length;
    },
    dispatchEvent(event) {
      events.push(event);
      return true;
    },
  });
  globalThis.document = documentTarget;
  globalThis.CustomEvent = class {
    constructor(type, options = {}) {
      this.type = type;
      this.detail = options.detail;
    }
  };
  Date.now = () => now;

  try {
    await import(`../../docs/dashboard/auto-refresh.js?test=${now}`);

    assert.equal(intervals.length, 1);
    assert.equal(intervals[0].delay, 2 * 60 * 1000);

    windowTarget.emit("focus");
    assert.deepEqual(events.map((event) => event.detail.reason), ["focus"]);

    now += 5_000;
    windowTarget.emit("pageshow");
    assert.deepEqual(events.map((event) => event.detail.reason), ["focus"]);

    now += 10_000;
    windowTarget.emit("pageshow");
    assert.deepEqual(events.map((event) => event.detail.reason), ["focus", "pageshow"]);

    now += 59_000;
    documentTarget.emit("visibilitychange");
    assert.deepEqual(events.map((event) => event.detail.reason), ["focus", "pageshow"]);

    now += 1_000;
    documentTarget.emit("visibilitychange");
    assert.deepEqual(events.map((event) => event.detail.reason), ["focus", "pageshow", "visibilitychange"]);

    documentTarget.visibilityState = "hidden";
    now += 60_000;
    documentTarget.emit("visibilitychange");
    assert.deepEqual(events.map((event) => event.detail.reason), ["focus", "pageshow", "visibilitychange"]);

    intervals[0].callback();
    assert.deepEqual(events.map((event) => event.detail.reason), ["focus", "pageshow", "visibilitychange", "interval"]);
  } finally {
    Date.now = originalDateNow;
    globalThis.window = originalWindow;
    globalThis.document = originalDocument;
    globalThis.CustomEvent = originalCustomEvent;
  }
});
