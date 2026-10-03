import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  Heart,
  MapPin,
  MessageCircle,
  Package,
  Pencil,
  Sparkles,
  UserRound,
} from "lucide-react";
import { api, type Meta, type User } from "./api";
import { Modal } from "./components";

export type PersonalView =
  "profile" | "intents" | "messages" | "favorites" | "mine";

const sections = [
  {
    view: "intents",
    title: "我的代蹲",
    description: "查看需求和匹配进展",
    unit: "个任务",
    icon: Sparkles,
  },
  {
    view: "messages",
    title: "站内消息",
    description: "继续和同学沟通",
    unit: "个会话",
    icon: MessageCircle,
  },
  {
    view: "favorites",
    title: "我的收藏",
    description: "找回心动的好物",
    unit: "件好物",
    icon: Heart,
  },
  {
    view: "mine",
    title: "我发布的",
    description: "管理发布和交易状态",
    unit: "件发布",
    icon: Package,
  },
] as const;

export function ProfileNav({
  view,
  onNavigate,
  unread,
}: {
  view: PersonalView;
  onNavigate: (view: PersonalView) => void;
  unread: number;
}) {
  return (
    <nav className="profile-nav" aria-label="我的主页导航">
      <button
        className={view === "profile" ? "active" : ""}
        onClick={() => onNavigate("profile")}
      >
        主页
      </button>
      {sections.map(({ view: key, title }) => (
        <button
          key={key}
          className={view === key ? "active" : ""}
          onClick={() => onNavigate(key)}
        >
          {title}
          {key === "messages" && unread > 0 && (
            <span className="profile-badge">{unread}</span>
          )}
        </button>
      ))}
    </nav>
  );
}

type Overview = { intents: number; listings: number; favorites: number };

export function ProfileHome({
  user,
  meta,
  overview,
  unread,
  conversations,
  onNavigate,
  onAccount,
  onUpdated,
  onError,
}: {
  user: User;
  meta: Meta;
  overview: Overview | null;
  unread: number;
  conversations: number;
  onNavigate: (view: PersonalView) => void;
  onAccount: () => void;
  onUpdated: (user: User) => void;
  onError: (message: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [nickname, setNickname] = useState(user.nickname);
  const [campus, setCampus] = useState(user.campus);
  const [bio, setBio] = useState(user.bio ?? "");
  const [color, setColor] = useState(user.avatar_color ?? "sage");
  useEffect(() => {
    setNickname(user.nickname);
    setCampus(user.campus);
    setBio(user.bio ?? "");
    setColor(user.avatar_color ?? "sage");
  }, [user]);

  function openEditor() {
    setNickname(user.nickname);
    setCampus(user.campus);
    setBio(user.bio ?? "");
    setColor(user.avatar_color ?? "sage");
    setEditing(true);
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      const result = await api<{ user: User }>("/users/me", "PATCH", {
        nickname,
        campus,
        bio,
        avatar_color: color,
      });
      onUpdated(result.user);
      setEditing(false);
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const counts = {
    intents: overview?.intents,
    messages: conversations,
    favorites: overview?.favorites,
    mine: overview?.listings,
  };
  return (
    <>
      <section className="profile-hero">
        <div
          className={`profile-avatar avatar-color-${user.avatar_color ?? "sage"}`}
          aria-hidden="true"
        >
          {user.nickname[0]}
        </div>
        <div className="profile-identity">
          <span className="profile-eyebrow">
            <UserRound size={14} /> 我的校园主页
          </span>
          <h1>{user.nickname}</h1>
          <p className="profile-location">
            <MapPin size={15} />
            {user.campus} · {user.email ? "北大邮箱已验证" : "本地演示账号"}
          </p>
          <p className="profile-bio">
            {user.bio || "还没有个人介绍，写一句话让同学认识你吧。"}
          </p>
        </div>
        <div className="profile-actions">
          <button className="button primary" onClick={openEditor}>
            <Pencil size={15} />
            编辑资料
          </button>
          <button className="button secondary" onClick={onAccount}>
            账号设置
          </button>
        </div>
      </section>
      <div className="profile-section-heading">
        <div>
          <span>MY CORNER</span>
          <h2>我的校园日常</h2>
          <p>代蹲、聊天、收藏和发布，都从这里出发。</p>
        </div>
      </div>
      <div className="profile-grid">
        {sections.map(({ view, title, description, unit, icon: Icon }) => (
          <button
            className="profile-card"
            key={view}
            onClick={() => onNavigate(view)}
          >
            <span className={`profile-card-icon profile-icon-${view}`}>
              <Icon size={23} strokeWidth={1.8} />
            </span>
            <span className="profile-card-copy">
              <strong>{title}</strong>
              <small>{description}</small>
            </span>
            <span className="profile-card-count">
              <span>{counts[view] ?? "…"}</span>
              <small>{unit}</small>
              {view === "messages" && unread > 0 && <em>{unread} 未读</em>}
            </span>
            <ArrowRight className="profile-card-arrow" size={18} />
          </button>
        ))}
      </div>
      <div className="profile-footnote">
        <Sparkles size={17} />
        让闲置遇见需要它的人，也给自己留一处校园小角落。
      </div>
      {editing && (
        <Modal title="编辑个人资料" onClose={() => setEditing(false)}>
          <form className="stack-form" onSubmit={(event) => void save(event)}>
            <label>
              昵称
              <input
                value={nickname}
                onChange={(event) => setNickname(event.target.value)}
                minLength={2}
                maxLength={50}
                required
              />
            </label>
            <label>
              常用校区
              <select
                value={campus}
                onChange={(event) => setCampus(event.target.value)}
              >
                {meta.campuses.map((place) => (
                  <option key={place}>{place}</option>
                ))}
              </select>
            </label>
            <label>
              个人介绍
              <textarea
                value={bio}
                onChange={(event) => setBio(event.target.value)}
                maxLength={160}
                rows={3}
                placeholder="比如：喜欢淘旧书，也常在燕园出没。"
              />
            </label>
            <div className="profile-color-field">
              <span>头像配色</span>
              <div
                className="profile-color-options"
                role="group"
                aria-label="头像配色"
              >
                {(["sage", "blue", "peach", "lavender"] as const).map(
                  (choice) => (
                    <button
                      key={choice}
                      type="button"
                      className={`avatar-color-${choice} ${color === choice ? "selected" : ""}`}
                      aria-label={
                        {
                          sage: "鼠尾草绿",
                          blue: "湖蓝",
                          peach: "暖桃",
                          lavender: "浅紫",
                        }[choice]
                      }
                      aria-pressed={color === choice}
                      onClick={() => setColor(choice)}
                    >
                      {nickname[0] || "我"}
                    </button>
                  ),
                )}
              </div>
            </div>
            <p className="muted">邮箱用于登录验证，不在主页公开显示。</p>
            <button
              className="button primary full"
              type="submit"
              disabled={saving}
            >
              {saving ? "保存中…" : "保存资料"}
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
