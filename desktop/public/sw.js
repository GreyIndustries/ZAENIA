/* Visible Web Push only. No tokens, private API cache or background mic. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));

function appTarget(value) {
  const scope = new URL(self.registration.scope);
  try {
    const target = new URL(typeof value === "string" ? value : "", scope);
    if (target.origin === scope.origin && target.pathname.startsWith(scope.pathname)) return target.href;
  } catch { /* use this app's start page */ }
  return scope.href;
}

self.addEventListener("push", event => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch { /* generic visible notification */ }
  if (!data || typeof data !== "object") data = {};
  event.waitUntil(self.registration.showNotification(typeof data.title === "string" ? data.title.slice(0, 80) : "ZAE", {
    body: typeof data.body === "string" ? data.body.slice(0, 240) : "Open ZAE to view your notification.",
    icon: new URL("icons/zaenia-192.png", self.registration.scope).href,
    badge: new URL("icons/zaenia-192.png", self.registration.scope).href,
    tag: typeof data.tag === "string" ? data.tag.slice(0, 100) : undefined,
    data: { url: appTarget(data.url) },
  }));
});

self.addEventListener("notificationclick", event => {
  event.notification.close();
  const target = appTarget(event.notification.data?.url);
  const scope = new URL(self.registration.scope);
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(async list => {
    for (const client of list) {
      const url = new URL(client.url);
      if (url.origin === scope.origin && url.pathname.startsWith(scope.pathname) && "focus" in client) {
        if (client.url !== target && "navigate" in client) await client.navigate(target);
        return client.focus();
      }
    }
    return self.clients.openWindow(target);
  }));
});
