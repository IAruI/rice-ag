/* rice.ag scanner worker: runs the engine off the main thread */
importScripts('engine.js?v=__VER__');
self.onmessage = function (e) {
  const { width, height, buffer, options } = e.data;
  try {
    const res = self.RiceScanner.analyze({ width, height, data: new Uint8ClampedArray(buffer) }, options);
    self.postMessage({ ok: true, res });
  } catch (err) {
    self.postMessage({ ok: false, error: String(err && err.message || err) });
  }
};
