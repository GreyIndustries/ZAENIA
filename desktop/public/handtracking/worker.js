/* Local hand landmarks only. Frames are transferred in RAM, closed, never saved. */
importScripts("vision_bundle.js");
let tracker = null;
let lastAt = -Infinity;
self.onmessage = async event => {
  const message = event.data;
  if (message.type === "init") {
    try {
      const assets = await Vision.FilesetResolver.forVisionTasks(new URL("wasm", self.location.href).href);
      tracker = await Vision.HandLandmarker.createFromOptions(assets, {
        baseOptions: { modelAssetPath: new URL("hand_landmarker.task", self.location.href).href, delegate: "CPU" },
        runningMode: "VIDEO", numHands: 2, minHandDetectionConfidence: .65, minHandPresenceConfidence: .65, minTrackingConfidence: .65,
      });
      self.postMessage({ type: "ready" });
    } catch (error) { self.postMessage({ type: "error", detail: String(error) }); }
  } else if (message.type === "frame") {
    try {
      if (!Number.isFinite(message.at) || message.at <= lastAt) { self.postMessage({ type: "landmarks", hands: [], at: message.at }); return; }
      lastAt = message.at;
      const result = tracker ? tracker.detectForVideo(message.frame, message.at) : null;
      const handedness = result?.handedness ?? result?.handednesses ?? [];
      const hands = (result?.landmarks ?? []).slice(0, 2).map((points, index) => ({ points,
        handedness: handedness[index]?.[0]?.categoryName ?? "Unknown", score: handedness[index]?.[0]?.score ?? 0 }));
      self.postMessage({ type: "landmarks", hands, at: message.at });
    } catch (error) { self.postMessage({ type: "error", detail: String(error) }); }
    finally { message.frame?.close(); }
  } else if (message.type === "close") { tracker?.close(); tracker = null; self.close(); }
};
