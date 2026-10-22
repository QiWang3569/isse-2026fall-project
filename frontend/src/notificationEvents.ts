const eventName = "yandu-notifications-changed";
const storageKey = "yandu-notifications-version";
let version = 0;
export const notificationVersion = () => version;

export function notificationsChanged() {
  version++;
  window.dispatchEvent(new Event(eventName));
  try { localStorage.setItem(storageKey, `${Date.now()}:${Math.random()}`); } catch { /* Private browsing may disable storage. */ }
}

export function listenForNotificationChanges(listener: () => void) {
  const external = (event: StorageEvent) => {
    if (event.key === storageKey) { version++; listener(); }
  };
  const focus = () => { version++; listener(); };
  window.addEventListener(eventName, listener);
  window.addEventListener("storage", external);
  window.addEventListener("focus", focus);
  return () => {
    window.removeEventListener(eventName, listener);
    window.removeEventListener("storage", external);
    window.removeEventListener("focus", focus);
  };
}
