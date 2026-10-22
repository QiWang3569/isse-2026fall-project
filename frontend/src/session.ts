import { useEffect } from "react";
import { api, ApiError } from "./api";

// Only foreground entry and user input renew sessions; notification polling does not.
export function useSessionRenewal(userId: string | undefined, onExpired: (expired: boolean) => void, epoch: number) {
  useEffect(() => {
    if (!userId) return;
    let alive = true, pending = false, lastAttempt = 0;
    const expired = () => { if (alive) onExpired(true); };
    const renew = async () => {
      if (document.visibilityState !== "visible" || pending || Date.now() - lastAttempt < 5 * 60_000) return;
      pending = true;
      lastAttempt = Date.now();
      try {
        await api("/auth/refresh", "POST");
        if (alive) onExpired(false);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) expired();
      } finally { pending = false; }
    };
    const activity = () => { void renew(); };
    window.addEventListener("yandu-session-expired", expired);
    window.addEventListener("focus", activity);
    document.addEventListener("visibilitychange", activity);
    for (const name of ["pointerdown", "keydown", "wheel"]) document.addEventListener(name, activity, { passive: true });
    activity();
    return () => {
      alive = false;
      window.removeEventListener("yandu-session-expired", expired);
      window.removeEventListener("focus", activity);
      document.removeEventListener("visibilitychange", activity);
      for (const name of ["pointerdown", "keydown", "wheel"]) document.removeEventListener(name, activity);
    };
  }, [userId, onExpired, epoch]);
}
