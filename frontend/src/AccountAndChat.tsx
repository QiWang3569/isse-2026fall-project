import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, Flag, Mail, MessageCircle, Send, ShieldOff } from "lucide-react";
import { api, statusText, type ChatMessage, type Conversation, type Item, type Meta, type User } from "./api";
import { Empty, ProductArt } from "./components";

export function EmailSignIn({ meta, onSignedIn }: { meta: Meta; onSignedIn: (user: User) => void }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [nickname, setNickname] = useState("");
  const [campus, setCampus] = useState("燕园校本部");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (!sent) {
        await api("/auth/email/request-code", "POST", { email });
        setSent(true);
      } else {
        const result = await api<{ user: User }>("/auth/email/verify", "POST", {
          email, code, nickname, campus,
        });
        onSignedIn(result.user);
      }
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="stack-form email-sign-in" onSubmit={(event) => void submit(event)}>
      <p className="muted">使用北大邮箱收取一次性验证码。首次验证会创建普通用户账号。</p>
      <label>
        北大邮箱
        <input type="email" autoComplete="email" required value={email}
          disabled={sent || busy} placeholder="name@pku.edu.cn 或 name@stu.pku.edu.cn"
          onChange={(event) => setEmail(event.target.value)} />
      </label>
      {sent && <>
        <p className="hint" role="status">验证码已发送至 {email}，10 分钟内有效。</p>
        <label>
          8 位验证码
          <input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{8}"
            required value={code} onChange={(event) => setCode(event.target.value)} />
        </label>
        <div className="form-grid">
          <label>
            昵称（首次注册必填）
            <input value={nickname} maxLength={50} onChange={(event) => setNickname(event.target.value)} />
          </label>
          <label>
            校区（首次注册使用）
            <select value={campus} onChange={(event) => setCampus(event.target.value)}>
              {meta.campuses.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
        </div>
        <button type="button" className="text-button" onClick={() => { setSent(false); setCode(""); }}>
          更换邮箱或重新获取验证码
        </button>
      </>}
      {error && <p className="form-error" role="alert">{error}</p>}
      {!meta.email_auth_ready && <p className="form-error">邮件服务尚未配置，正式邮箱登录暂不可用。</p>}
      <button type="submit" className="button primary full" disabled={busy || !meta.email_auth_ready}>
        <Mail size={16} />{sent ? "验证并登录" : "发送验证码"}
      </button>
    </form>
  );
}

export function ChatCenter({ user, conversations, initialItem, initialDraft, onStarted, refresh }: {
  user: User;
  conversations: Conversation[];
  initialItem: Item | null;
  initialDraft: string;
  onStarted: () => void;
  refresh: () => void;
}) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [recentConversation, setRecentConversation] = useState<Conversation | null>(null);
  const [newItem, setNewItem] = useState<Item | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loadedOlder, setLoadedOlder] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reportMessageId, setReportMessageId] = useState<string | null>(null);
  const [reportReason, setReportReason] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const loadingOlder = useRef(false);
  const handledItem = useRef<string | null>(null);
  useEffect(() => {
    if (!initialItem) { handledItem.current = null; return; }
    if (handledItem.current === initialItem.id) return;
    handledItem.current = initialItem.id;
    const existing = conversations.find((conversation) => conversation.item_id === initialItem.id);
    if (existing) {
      setActiveId(existing.id);
      setRecentConversation(existing);
      setNewItem(null);
      setMessages([]);
    } else {
      setActiveId(null);
      setNewItem(initialItem);
      setMessages([]);
    }
    setLoadedOlder(false);
    setDraft(initialDraft);
  }, [initialItem, initialDraft, conversations]);
  useEffect(() => {
    if (!activeId) return;
    let alive = true;
    async function load() {
      try {
        const result = await api<{ messages: ChatMessage[]; has_more: boolean }>(`/conversations/${activeId}/messages`);
        if (!alive) return;
        setMessages((current) => {
          if (current.length <= result.messages.length) return result.messages;
          const merged = new Map([...current, ...result.messages].map((message) => [message.id, message]));
          return [...merged.values()].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id));
        });
        if (!loadedOlder) setHasMore(result.has_more);
        setError("");
        if (result.messages.some((message) => message.sender_id !== user.id && !message.read_at)) {
          await api(`/conversations/${activeId}/read`, "POST");
          if (alive) refresh();
        }
      } catch (cause) {
        if (alive) setError((cause as Error).message);
      }
    }
    void load();
    const timer = window.setInterval(() => void load(), 8000);
    return () => { alive = false; clearInterval(timer); };
  }, [activeId, user.id, refresh, loadedOlder]);
  useEffect(() => {
    if (loadingOlder.current) { loadingOlder.current = false; return; }
    bottom.current?.scrollIntoView({ block: "end" });
  }, [activeId, messages.length]);
  const listedConversation = conversations.find((conversation) => conversation.id === activeId) ?? null;
  useEffect(() => {
    if (listedConversation && recentConversation?.id === listedConversation.id &&
      listedConversation.deal_status === recentConversation.deal_status &&
      listedConversation.blocked === recentConversation.blocked &&
      listedConversation.blocked_by_me === recentConversation.blocked_by_me) {
      setRecentConversation(null);
    }
  }, [listedConversation, recentConversation]);
  const active = recentConversation?.id === activeId ? recentConversation : listedConversation;
  async function changeDeal(action: "request" | "reserve" | "decline" | "cancel" | "sold" | "confirm") {
    if (!activeId) return;
    setBusy(true); setError("");
    try {
      const result = await api<Conversation>(`/conversations/${activeId}/deal`, "POST", { action: action.toLowerCase() });
      setRecentConversation(result); refresh();
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  async function toggleBlock() {
    if (!activeId || !active) return;
    setBusy(true); setError("");
    try {
      await api(`/conversations/${activeId}/block`, active.blocked_by_me ? "DELETE" : "POST");
      setRecentConversation({ ...active, blocked_by_me: !active.blocked_by_me,
        blocked: !active.blocked_by_me || (active.blocked && !active.blocked_by_me) });
      refresh();
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  async function submitReport(event: FormEvent) {
    event.preventDefault();
    if (!activeId || !reportMessageId) return;
    setBusy(true); setError("");
    try {
      await api(`/conversations/${activeId}/messages/${reportMessageId}/reports`, "POST", { reason: reportReason });
      setReportMessageId(null); setReportReason("");
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  async function send(event: FormEvent) {
    event.preventDefault();
    if (!draft.trim() || (!activeId && !newItem)) return;
    setBusy(true);
    setError("");
    try {
      if (activeId) {
        const message = await api<ChatMessage>(`/conversations/${activeId}/messages`, "POST", { body: draft });
        setMessages((current) => [...current, message]);
      } else if (newItem) {
        const result = await api<{ conversation: Conversation; message: ChatMessage }>(
          `/items/${newItem.id}/conversations`, "POST", { body: draft });
        setActiveId(result.conversation.id);
        setRecentConversation(result.conversation);
        setNewItem(null);
        setMessages([result.message]);
        onStarted();
      }
      setDraft("");
      refresh();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function loadOlder() {
    if (!activeId || !messages.length) return;
    try {
      const result = await api<{ messages: ChatMessage[]; has_more: boolean }>(
        `/conversations/${activeId}/messages?before_id=${encodeURIComponent(messages[0].id)}`);
      loadingOlder.current = result.messages.length > 0;
      setMessages((current) => [...result.messages, ...current]);
      setHasMore(result.has_more);
      setLoadedOlder(true);
    } catch (cause) { setError((cause as Error).message); }
  }
  return (
    <section className="chat-page">
      <div className="chat-heading"><MessageCircle size={22} /><div><h1>站内消息</h1><p>关于商品的沟通会保存在这里，只有买卖双方可见。</p></div></div>
      <div className={`chat-layout ${activeId || newItem ? "chat-active" : ""}`}>
        <div className="chat-list" aria-label="会话列表">
          {conversations.length ? conversations.map((conversation) => (
            <button key={conversation.id} className={`chat-list-item ${activeId === conversation.id ? "active" : ""}`}
              onClick={() => { setActiveId(conversation.id); setRecentConversation(conversation); setMessages([]); setLoadedOlder(false); setNewItem(null); setDraft(""); setReportMessageId(null); setError(""); onStarted(); }}>
              <span className="avatar">{conversation.counterpart.nickname[0]}</span>
              <span className="chat-list-text"><strong>{conversation.counterpart.nickname}</strong><small>{conversation.item_title}</small>
                <span>{conversation.last_message?.body ?? "开始沟通"}</span></span>
              {conversation.unread_count > 0 && <b className="chat-unread">{conversation.unread_count}</b>}
            </button>
          )) : <p className="muted chat-empty-list">还没有消息。打开一件商品，点击“联系卖家”开始。</p>}
        </div>
        <div className="chat-thread">
          {(active || newItem) ? <>
            <div className="chat-thread-head">
              <button type="button" className="chat-back" onClick={() => { setActiveId(null); setNewItem(null); onStarted(); }} aria-label="返回会话列表"><ArrowLeft size={18} /></button>
              <div><strong>{active?.counterpart.nickname ?? newItem?.seller.nickname}</strong>
                <small>{active?.item_title ?? newItem?.title} · {statusText[active?.item_status ?? newItem?.status ?? ""] ?? "状态未知"}</small></div>
              {active && <button type="button" className="text-button" disabled={busy} onClick={() => void toggleBlock()}>
                <ShieldOff size={15} />{active.blocked_by_me ? "解除拉黑" : "拉黑"}
              </button>}
            </div>
            {active && <div className="chat-deal-actions">
              {active.deal_status === "REQUESTED" && <span>买家已提出预订，等待卖家确认</span>}
              {active.deal_status === "RESERVED" && <span>卖家已确认预订，等待交接</span>}
              {active.deal_status === "SOLD" && <span>卖家已标记售出，等待买家确认</span>}
              {active.deal_status === "CONFIRMED" && <span>双方已确认成交</span>}
              {active.deal_status === "DECLINED" && <span>卖家已拒绝预订</span>}
              {active.deal_status === "CANCELED" && <span>预订已取消</span>}
              {user.id === active.buyer_id && ["NONE", "DECLINED", "CANCELED"].includes(active.deal_status) && active.item_status === "ACTIVE" &&
                <button className="text-button" disabled={busy || active.blocked} onClick={() => void changeDeal("request")}>申请预订</button>}
              {user.id === active.seller_id && active.deal_status === "REQUESTED" && <>
                <button className="text-button" disabled={busy} onClick={() => void changeDeal("reserve")}>确认预订</button>
                <button className="text-button" disabled={busy} onClick={() => void changeDeal("decline")}>拒绝预订</button></>}
              {user.id === active.buyer_id && ["REQUESTED", "RESERVED"].includes(active.deal_status) &&
                <button className="text-button" disabled={busy} onClick={() => void changeDeal("cancel")}>取消预订</button>}
              {user.id === active.seller_id && active.deal_status === "RESERVED" &&
                <button className="text-button" disabled={busy} onClick={() => void changeDeal("sold")}>确认售出</button>}
              {user.id === active.buyer_id && active.deal_status === "SOLD" &&
                <button className="text-button" disabled={busy} onClick={() => void changeDeal("confirm")}>确认已收到</button>}
            </div>}
            {active?.blocked && <p className="hint">双方已停止联系。聊天记录仍可查看，不能发送新消息。</p>}
            <div className="chat-history" aria-live="polite">
              {hasMore && <button className="text-button" onClick={() => void loadOlder()}>加载更早的消息</button>}
              {newItem && <div className="chat-start-item"><ProductArt item={newItem} /><span>{newItem.title}</span><ArrowRight size={16} /></div>}
              {messages.map((message) => <div key={message.id} className={`chat-bubble ${message.sender_id === user.id ? "own" : ""}`}>
                <p>{message.body}</p><time>{new Date(message.created_at).toLocaleString("zh-CN")}</time>
                {message.sender_id !== user.id && !message.hidden && <button className="text-button" type="button"
                  onClick={() => { setReportMessageId(message.id); setReportReason(""); }}><Flag size={13} />举报消息</button>}
              </div>)}
              <div ref={bottom} />
            </div>
            {reportMessageId && <form className="chat-report-form" onSubmit={(event) => void submitReport(event)}>
              <label>举报原因<input required minLength={5} maxLength={1000} value={reportReason}
                onChange={(event) => setReportReason(event.target.value)} placeholder="请说明这条消息的问题" /></label>
              <button className="button secondary" disabled={busy}>提交举报</button>
              <button type="button" className="text-button" onClick={() => setReportMessageId(null)}>取消</button>
            </form>}
            <form className="chat-compose" onSubmit={(event) => void send(event)}>
              <label className="sr-only" htmlFor="chat-message">消息内容</label>
              <textarea id="chat-message" value={draft} maxLength={2000} rows={3} disabled={active?.blocked}
                placeholder="输入想向对方确认的问题…" onChange={(event) => setDraft(event.target.value)} />
              <div><span>请勿提前转账；交接前当面核实商品。</span>
                <button className="button primary" disabled={busy || active?.blocked || !draft.trim()}><Send size={15} />确认发送</button></div>
              {error && <p className="form-error" role="alert">{error}</p>}
            </form>
          </> : <Empty title="选择一条会话" text="你与其他同学的商品沟通会显示在这里。" />}
        </div>
      </div>
    </section>
  );
}
