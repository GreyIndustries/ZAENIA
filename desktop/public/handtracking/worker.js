/* Local hand landmarks only. Frames are transferred in RAM, closed, never saved. */
importScripts("vision_bundle.js");
let tracker = null;
self.onmessage = async event => {
  const message = event.data;
  if (message.type === "init") {
    try {
      const assets = await Vision.FilesetResolver.forVisionTasks(new URL("wasm", self.location.href).href);
      tracker = await Vision.HandLandmarker.createFromOptions(assets, {
        baseOptions: { modelAssetPath: new URL("hand_landmarker.task", self.location.href).href, delegate: "CPU" },
        runningMode: "VIDEO", numHands: 1, minHandDetectionConfidence: .65, minHandPresenceConfidence: .65, minTrackingConfidence: .65,
      });
      self.postMessage({ type: "ready" });
    } catch (error) { self.postMessage({ type: "error", detail: String(error) }); }
  } else if (message.type === "frame") {
    try {
      const result = tracker ? tracker.detectForVideo(message.frame, message.at) : null;
      self.postMessage({ type: "landmarks", points: result?.landmarks?.[0] ?? null, at: message.at });
    } catch (error) { self.postMessage({ type: "error", detail: String(error) }); }
    finally { message.frame?.close(); }
  } else if (message.type === "close") { tracker?.close(); tracker = null; self.close(); }
};
