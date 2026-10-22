import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, MessageCircle, Plus, X } from "lucide-react";
import { api, type User } from "./api";
import { Empty } from "./components";
import "./feedback.css";

type FeedbackStatus = "OPEN" | "IN_PROGRESS" | "RESOLVED" | "DECLINED";
const statuses: Record<FeedbackStatus, string> = {
  OPEN: "待处理", IN_PROGRESS: "处理中", RESOLVED: "已解决", DECLINED: "暂不采纳",
};
type Feedback = {
  id: string; category: string; body: string; page_path: string; status: FeedbackStatus;
  user: { id: string; nickname: string }; created_at: string; updated_at: string;
};
type FeedbackDetailData = Feedback & {
  images: string[]; notice_ids: string[];
  replies: { id: string; body: string; author: string; is_staff: boolean; status: FeedbackStatus | null; created_at: string }[];
};
export type FeedbackNotices = {
  count: number; items: { id: string; feedback_id: string; body: string; created_at: string }[];
};
const date = (value: string) => new Date(value).toLocaleString("zh-CN", { hour12: false });

export function FeedbackCenter({ user, initialId, onLogin, onChange }: {
  user: User | null; initialId: string | null; onLogin: () => void; onChange: () => void;
}) {
  if (!user) return <Empty title="登录后提交意见反馈" text="反馈和管理员回复会保存在站内，你可以随时回来查看。"
    action="登录或注册" onAction={onLogin} />;
  return <FeedbackWorkspace initialId={initialId} onChange={onChange} />;
}

export function FeedbackWorkspace({ admin = false, initialId = null, onChange }: {
  admin?: boolean; initialId?: string | null; onChange: () => void;
}) {
  const [tab, setTab] = useState<"new" | "list">(admin || initialId ? "list" : "new");
  const [selected, setSelected] = useState<string | null>(initialId);
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [list, setList] = useState<{ items: Feedback[]; total: number } | null>(null);
  const [error, setError] = useState("");
  const base = admin ? "/admin/feedback" : "/feedback";
  useEffect(() => {
    if (tab !== "list" || selected) return;
    let alive = true;
    setList(null); setError("");
    const load = () => api<{ items: Feedback[]; total: number }>(`${base}?page=${page}&${admin && status ? `status=${status}` : ""}`)
      .then((result) => { if (alive) { setList(result); setError(""); } })
      .catch((e: Error) => { if (alive) setError(e.message); });
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => { alive = false; clearInterval(timer); };
  }, [base, admin, page, status, tab, selected, revision]);
  const changed = () => { setRevision((n) => n + 1); onChange(); };
  return <section className="feedback-workspace" aria-label={admin ? "用户反馈" : "意见反馈"}>
    {admin ? <div className="feedback-heading"><MessageCircle size={24} /><div><h2>用户反馈</h2>
      <p className="hint">在这里回复用户，并记录处理进度。</p></div></div> :
      <nav className="feedback-tabs" aria-label="反馈导航">
        <button type="button" className={tab === "new" && !selected ? "active" : ""}
          onClick={() => { setTab("new"); setSelected(null); }}>提交反馈</button>
        <button type="button" className={tab === "list" || selected ? "active" : ""}
          onClick={() => { setTab("list"); setSelected(null); }}>我的反馈</button>
      </nav>}
    {selected ? <FeedbackDetail key={selected} id={selected} admin={admin}
      onBack={() => { setSelected(null); setTab("list"); }} onChange={changed} /> :
      tab === "new" && !admin ? <FeedbackForm onCreated={(item) => {
        setSelected(item.id); setTab("list"); changed();
      }} /> : <>
        {admin && <label className="feedback-filter">处理状态
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">全部状态</option>
            {Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></label>}
        {error && <p className="form-error" role="alert">{error}<button type="button" className="text-button"
          onClick={() => setRevision((n) => n + 1)}>重试</button></p>}
        {!list && !error && <p role="status">正在加载反馈…</p>}
        {list && <>
          <p className="hint">共 {list.total} 条反馈</p>
          {list.items.length === 0 && <Empty title="暂无反馈" text={admin ? "用户提交后会显示在这里。" : "遇到问题或有建议，都可以通过“提交反馈”告诉我们。"} />}
          <div className="feedback-list">{list.items.map((item) => <button type="button" className="feedback-card"
            key={item.id} onClick={() => setSelected(item.id)}>
            <span className="feedback-meta"><strong>{item.category}</strong><span className={`feedback-status ${item.status}`}>{statuses[item.status]}</span></span>
            <span className="feedback-preview">{item.body}</span>
            <span className="hint">{admin ? `${item.user.nickname} · ` : ""}更新于 {date(item.updated_at)}</span>
          </button>)}</div>
          {list.total > 20 && <div className="feedback-pagination">
            <button type="button" disabled={page === 1} onClick={() => setPage(page - 1)}>上一页</button>
            <span>第 {page} / {Math.ceil(list.total / 20)} 页</span>
            <button type="button" disabled={page * 20 >= list.total} onClick={() => setPage(page + 1)}>下一页</button>
          </div>}
        </>}
      </>}
  </section>;
}

function FeedbackForm({ onCreated }: { onCreated: (item: Feedback) => void }) {
  const [category, setCategory] = useState("功能异常");
  const [body, setBody] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [attachPage, setAttachPage] = useState(true);
  // Do not attach query parameters or arbitrary URL fragments that may contain secrets.
  const [pagePath] = useState(() => location.pathname + (/^#[a-z-]+(?:\/[A-Za-z0-9_-]+)?$/.test(location.hash) ? location.hash : ""));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function upload(files: FileList | null) {
    if (!files?.length) return;
    const selected = Array.from(files);
    if (selected.length + images.length > 3) { setError("最多添加 3 张截图"); return; }
    if (selected.some((f) => f.size > 6 * 1024 * 1024 || !["image/png", "image/jpeg", "image/webp"].includes(f.type))) {
      setError("请选择 JPG、PNG 或 WebP 图片，每张不超过 6 MB"); return;
    }
    setBusy(true); setError("");
    try {
      for (const file of selected) {
        const form = new FormData(); form.append("file", file);
        const result = await api<{ url: string }>("/feedback-uploads", "POST", form);
        setImages((current) => [...current, result.url]);
      }
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (body.trim().length < 5) { setError("请用至少 5 个字描述问题或建议"); return; }
    setBusy(true); setError("");
    try {
      const result = await api<Feedback>("/feedback", "POST", { category, body: body.trim(), images, page_path: attachPage ? pagePath : "" });
      onCreated(result);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <form className="stack-form feedback-form" onSubmit={(e) => void submit(e)}>
    <p className="hint">告诉我们哪里可以做得更好。回复会通过站内通知送达。</p>
    <fieldset disabled={busy}>
      <label>反馈类型<select value={category} onChange={(e) => setCategory(e.target.value)}>
        {["功能异常", "使用建议", "其他问题"].map((v) => <option key={v}>{v}</option>)}
      </select></label>
      <label>反馈内容<textarea required minLength={5} maxLength={3000} rows={5} value={body}
        onChange={(e) => setBody(e.target.value)} placeholder="例如：在手机上打开商品详情后，点击收藏没有反应。" /></label>
      <span className="feedback-counter">{body.length} / 3000</span>
      <label>截图（选填）<input type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={busy || images.length >= 3}
        onChange={(e) => { void upload(e.target.files); e.target.value = ""; }} /></label>
      <p className="hint">最多 3 张，每张不超过 6 MB。截图仅你和管理员可见。</p>
      <div className="feedback-images">{images.map((src, i) => <div className="feedback-image" key={src}>
        <a href={src} target="_blank" rel="noreferrer"><img src={src} alt={`反馈截图 ${i + 1}`} /></a>
        <button type="button" aria-label={`移除截图 ${i + 1}`} onClick={() => setImages(images.filter((v) => v !== src))}><X size={14} /></button>
      </div>)}</div>
      <label className="feedback-page"><input type="checkbox" checked={attachPage} onChange={(e) => setAttachPage(e.target.checked)} />
        附带当前页面 <code>{pagePath}</code></label>
    </fieldset>
    <p className="hint">商品或聊天违规问题，请在对应商品或消息中使用“举报”。</p>
    {error && <p className="form-error" role="alert">{error}</p>}
    <button className="primary-button" type="submit" disabled={busy}><Plus size={16} />{busy ? "正在处理…" : "提交反馈"}</button>
  </form>;
}

function FeedbackDetail({ id, admin, onBack, onChange }: {
  id: string; admin: boolean; onBack: () => void; onChange: () => void;
}) {
  const [data, setData] = useState<FeedbackDetailData | null>(null);
  const [body, setBody] = useState("");
  const [status, setStatus] = useState<FeedbackStatus>("OPEN");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [revision, setRevision] = useState(0);
  const changeRef = useRef(onChange);
  changeRef.current = onChange;
  const initialized = useRef(false);
  const base = `${admin ? "/admin/feedback" : "/feedback"}/${id}`;
  useEffect(() => {
    let alive = true;
    let pending = false;
    async function load() {
      if (pending) return;
      pending = true;
      try {
        const result = await api<FeedbackDetailData>(base);
        if (!alive) return;
        setData(result); setError("");
        if (!initialized.current) { setStatus(result.status); initialized.current = true; }
        if (!admin && result.notice_ids.length) {
          await api(`/feedback/${id}/read`, "POST", { notice_ids: result.notice_ids });
          if (alive) changeRef.current();
        }
      } catch (e) { if (alive) setError((e as Error).message); }
      finally { pending = false; }
    }
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => { alive = false; clearInterval(timer); };
  }, [base, id, admin, revision]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || !body.trim()) return;
    setBusy(true); setError(""); setSuccess("");
    try {
      const result = await api<FeedbackDetailData>(`${base}/${admin ? "reply" : "replies"}`, "POST",
        admin ? { body: body.trim(), status } : { body: body.trim() });
      setData(result); setBody(""); setStatus(result.status); setRevision((n) => n + 1);
      setSuccess(admin ? "回复已发送，用户将收到站内通知。" : "补充已提交，管理员会在这里回复你。");
      onChange();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="feedback-detail">
    <button type="button" className="text-button" onClick={onBack}><ArrowLeft size={16} />返回{admin ? "用户反馈" : "我的反馈"}</button>
    {!data && !error && <p role="status">正在加载反馈…</p>}
    {data && <>
      <div className="feedback-meta"><h3>{data.category}</h3><span className={`feedback-status ${data.status}`}>{statuses[data.status]}</span></div>
      <p className="hint">{data.user.nickname} · {date(data.created_at)}</p>
      <p className="feedback-body">{data.body}</p>
      {data.page_path && <p className="hint feedback-path">相关页面：<code>{data.page_path}</code></p>}
      <div className="feedback-images">{data.images.map((src, i) => <a key={src} href={src} target="_blank" rel="noreferrer">
        <img src={src} alt={`反馈截图 ${i + 1}`} /></a>)}</div>
      <h3 className="feedback-thread-title">处理记录</h3>
      {!data.replies.length && <p className="hint">反馈已提交，等待管理员处理。</p>}
      <div className="feedback-thread">{data.replies.map((r) => <article key={r.id} className={`feedback-reply ${r.is_staff ? "staff" : ""}`}>
        <div className="feedback-meta"><strong>{r.is_staff ? "管理员" : r.author}</strong><time>{date(r.created_at)}</time></div>
        <p className="feedback-body">{r.body}</p>
        {r.status && <span className="hint">状态更新为：{statuses[r.status]}</span>}
      </article>)}</div>
      <form className="stack-form feedback-form" onSubmit={(e) => void submit(e)}>
        <fieldset disabled={busy}>
          {admin && <label>处理状态<select value={status} onChange={(e) => setStatus(e.target.value as FeedbackStatus)}>
            {Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></label>}
          <label>{admin ? "回复内容与处理说明" : "补充说明"}<textarea required maxLength={3000} rows={3} value={body}
            onChange={(e) => setBody(e.target.value)} placeholder={admin ? "说明处理结果或需要用户补充的信息；暂不采纳时请说明原因。" : "补充遇到的情况，或回复管理员的问题…"} /></label>
        </fieldset>
        {!admin && ["RESOLVED", "DECLINED"].includes(data.status) && <p className="hint">继续补充会将反馈重新设为待处理。</p>}
        <button type="submit" className="primary-button" disabled={busy || !body.trim()}>{busy ? "发送中…" : admin ? "回复并更新状态" : "发送补充"}</button>
      </form>
    </>}
    {error && <p className="form-error" role="alert">{error}<button type="button" className="text-button" onClick={() => setRevision((n) => n + 1)}>刷新</button></p>}
    {success && <p className="hint" role="status">{success}</p>}
  </div>;
}
