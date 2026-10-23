import { useEffect, useRef, useState } from "react";
import { api, type Announcement } from "./api";
import { Modal } from "./components";
import { notificationVersion } from "./notificationEvents";

type Page = { items: Announcement[]; total: number; page: number; size: number };

export function AnnouncementFeed({ userId, revision, compact = false }: {
  userId?: string; revision: number; compact?: boolean;
}) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [selected, setSelected] = useState<Announcement | null>(null);
  const [error, setError] = useState("");
  const [readError, setReadError] = useState("");
  const [retry, setRetry] = useState(0);
  const [reading, setReading] = useState(false);
  const sequence = useRef(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    let alive = true;
    async function load() {
      const request = ++sequence.current, epoch = notificationVersion();
      try {
        const result = await api<Page>(`/announcements/feed?page=${page}&size=${compact ? 5 : 20}&unread_only=${!!userId && compact}`);
        if (!alive || request !== sequence.current || epoch !== notificationVersion()) return;
        if (page > 1 && !result.items.length) { setPage(page - 1); return; }
        setData(result); setError("");
      } catch (cause) {
        if (alive && request === sequence.current) setError((cause as Error).message);
      }
    }
    void load();
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void load(); }, 10000);
    return () => { alive = false; clearInterval(timer); };
  }, [userId, revision, compact, page, retry]);

  async function markRead(a: Announcement) {
    if (!userId || a.is_read) return;
    setReading(true); setReadError("");
    try {
      await api("/announcements/mark-read", "POST", { ids: [a.id] });
      if (mounted.current) {
        setSelected((value) => value?.id === a.id ? { ...value, is_read: true } : value);
        // Removal happens beneath the open detail; the reader never loses the text.
        setData((value) => value ? { ...value, items: compact ? value.items.filter((item) => item.id !== a.id)
          : value.items.map((item) => item.id === a.id ? { ...item, is_read: true } : item) } : value);
        if (compact) setPage(1);
      }
    } catch (cause) { if (mounted.current) setReadError((cause as Error).message); }
    finally { if (mounted.current) setReading(false); }
  }

  return <div className="announcement-feed">
    {error && <p role="alert" className="form-error">{error} <button type="button" onClick={() => setRetry((n) => n + 1)}>重试</button></p>}
    {!data && !error && <p className="hint">正在加载公告…</p>}
    {data?.items.map((a) => <article className={`announcement ${a.is_read === false ? "unread" : ""}`} key={a.id}>
      <span className={`announcement-kind ${a.kind === "更新" ? "update" : ""}`}>{a.kind}</span>
      <button type="button" className="announcement-open" onClick={() => { setSelected(a); setReadError(""); void markRead(a); }}>
        <strong>{a.title}</strong><span>{a.body.slice(0, 90)}{a.body.length > 90 ? "…" : ""}</span>
        <small>{a.is_read === true ? "已读 · " : ""}查看全文 →</small>
      </button>
    </article>)}
    {data && !data.items.length && <p className="hint">{compact && userId ? "暂无未读公告" : "暂无公告"}</p>}
    {data && data.total > data.size && <div className="announcement-pages">
      <button type="button" className="text-button" disabled={page === 1} onClick={() => setPage((n) => n - 1)}>上一页</button>
      <span>第 {page} / {Math.ceil(data.total / data.size)} 页</span>
      <button type="button" className="text-button" disabled={page * data.size >= data.total} onClick={() => setPage((n) => n + 1)}>下一页</button>
    </div>}
    {selected && <Modal title={selected.title} onClose={() => setSelected(null)}>
      <div className="announcement-body">{selected.body}</div>
      <p className="hint">{new Date(selected.created_at).toLocaleString("zh-CN")}{reading ? " · 正在标记已读…" : selected.is_read ? " · 已读" : ""}</p>
      {readError && <p className="form-error" role="alert">{readError} <button type="button" disabled={reading} onClick={() => void markRead(selected)}>重试标记已读</button></p>}
    </Modal>}
  </div>;
}
