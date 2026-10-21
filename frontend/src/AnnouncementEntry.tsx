import { useEffect, useRef } from "react";
import { type Announcement } from "./api";

export function AnnouncementEntry({ announcement: a, compact = false, onSeen }: {
  announcement: Announcement; compact?: boolean; onSeen: (id: string) => void;
}) {
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      if (document.visibilityState === "visible" && entries.some((entry) => entry.isIntersecting)) {
        onSeen(a.id);
        observer.disconnect();
      }
    }, { threshold: 0.5 });
    const observe = () => { if (title.current) observer.observe(title.current); };
    const onVisible = () => { observer.disconnect(); observe(); };
    observe();
    document.addEventListener("visibilitychange", onVisible);
    return () => { observer.disconnect(); document.removeEventListener("visibilitychange", onVisible); };
  }, [a.id, onSeen]);
  return <article className={compact ? "notice" : "announcement"}>
    <div>
      <span className={`announcement-kind ${a.kind === "更新" ? "update" : ""}`}>{a.kind}</span>
      <h3 ref={title}>{a.title}</h3>
      <p>{a.body}</p>
      {!compact && <time>{new Date(a.created_at).toLocaleString("zh-CN")}</time>}
    </div>
  </article>;
}
