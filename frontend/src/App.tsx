import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ArrowDownUp,
  ArrowRight,
  Bell,
  Bike,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Compass,
  Flag,
  Heart,
  LayoutGrid,
  Leaf,
  LogOut,
  MapPin,
  Monitor,
  Package,
  Pause,
  Play,
  Plus,
  Search,
  ShieldCheck,
  Shirt,
  Sparkles,
  Sprout,
  Upload,
  X,
  Lamp,
  Copy,
  Share2,
  RefreshCw,
  CheckCheck,
} from "lucide-react";
import {
  api,
  type User,
  type Item,
  type Meta,
  type Intent,
  type Notice,
  type Wanted,
  type Report,
  type Log,
  money,
  campusShort,
  statusText,
} from "./api";
import {
  Brand,
  Busy,
  Card,
  Empty,
  Intro,
  Modal,
  ProductArt,
} from "./components";
import { IntentForm, PublishForm, WantedForm } from "./forms";

const nav = [
  { key: "market", label: "逛逛校园", icon: Compass },
  { key: "intents", label: "我的代蹲", icon: Sparkles },
  { key: "wanted", label: "求购看板", icon: Sprout },
  { key: "favorites", label: "我的收藏", icon: Heart },
  { key: "mine", label: "我发布的", icon: Package },
];
type View = "market" | "intents" | "wanted" | "favorites" | "mine" | "admin";
type ModalName =
  | "login"
  | "intent"
  | "publish"
  | "wanted"
  | "notifications"
  | "compare"
  | "detail"
  | null;
const validViews = [
  "market",
  "intents",
  "wanted",
  "favorites",
  "mine",
  "admin",
];
function currentView(): View {
  const v = location.hash.slice(1);
  return (validViews.includes(v) ? v : "market") as View;
}

function useResource<T>(url: string, revision: number, enabled = true) {
  const [data, setData] = useState<T | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    setData(null);
    setError("");
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api<T>(url)
      .then((d) => {
        if (alive) setData(d);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [url, revision, enabled]);
  return { data, loading, error };
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null),
    [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<View>(currentView),
    [revision, setRevision] = useState(0);
  const [modal, setModal] = useState<ModalName>(null),
    [toast, setToast] = useState(""),
    [busy, setBusy] = useState(false);
  const [fatal, setFatal] = useState(""),
    [search, setSearch] = useState(""),
    [query, setQuery] = useState("");
  const [category, setCategory] = useState(""),
    [campus, setCampus] = useState(""),
    [price, setPrice] = useState(""),
    [sort, setSort] = useState("recommended"),
    [page, setPage] = useState(1);
  const [intentQuery, setIntentQuery] = useState(""),
    [selected, setSelected] = useState<Item | null>(null),
    [compare, setCompare] = useState<Item[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]),
    [prefill, setPrefill] = useState<Wanted | null>(null);
  const [draft, setDraft] = useState(""),
    [reporting, setReporting] = useState(false),
    [reportText, setReportText] = useState("");
  const refresh = useCallback(() => setRevision((v) => v + 1), []);
  useEffect(() => {
    const listener = () => {
      setView(currentView());
      setPage(1);
    };
    window.addEventListener("hashchange", listener);
    return () => window.removeEventListener("hashchange", listener);
  }, []);
  useEffect(() => {
    if (toast) {
      const t = window.setTimeout(() => setToast(""), 4500);
      return () => clearTimeout(t);
    }
  }, [toast]);
  useEffect(() => {
    Promise.all([api<Meta>("/meta"), api<{ user: User | null }>("/auth/me")])
      .then(([m, u]) => {
        setMeta(m);
        setUser(u.user);
      })
      .catch((e) => setFatal(e.message));
  }, []);
  useEffect(() => {
    if (revision)
      api<Meta>("/meta")
        .then(setMeta)
        .catch(() => {});
  }, [revision]);
  useEffect(() => {
    if (!user) {
      setNotices([]);
      return;
    }
    let alive = true;
    const read = () =>
      api<Notice[]>("/notifications/")
        .then((n) => {
          if (alive) setNotices(n);
        })
        .catch(() => {});
    void read();
    const id = window.setInterval(read, 10000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [user, revision]);
  useEffect(() => {
    const id = new URLSearchParams(location.search).get("item");
    if (id)
      api<Item>("/items/" + encodeURIComponent(id))
        .then((i) => {
          setSelected(i);
          setModal("detail");
        })
        .catch((e) => setToast(e.message));
  }, []);
  const navigate = (v: View) => {
    location.hash = v;
    setView(v);
    setPage(1);
  };
  const needUser = () => {
    if (!user) {
      setModal("login");
      return false;
    }
    return true;
  };
  async function operate(task: () => Promise<unknown>, message?: string) {
    setBusy(true);
    try {
      await task();
      refresh();
      if (message) setToast(message);
    } catch (e) {
      setToast((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function openForm(type: "intent" | "publish" | "wanted", text = "") {
    if (!needUser()) return;
    if (type === "intent") setIntentQuery(text);
    if (type === "publish") setPrefill(null);
    setModal(type);
  }
  async function openItem(item: Item) {
    setDraft("");
    setReporting(false);
    setReportText("");
    try {
      const fresh = await api<Item>("/items/" + item.id);
      setSelected(fresh);
      setModal("detail");
    } catch (e) {
      setToast((e as Error).message);
    }
  }
  function favorite(item: Item) {
    if (!needUser()) return;
    void operate(
      async () => {
        await api(
          "/items/" + item.id + "/favorite",
          item.is_favorite ? "DELETE" : "POST",
        );
        if (selected?.id === item.id)
          setSelected({ ...item, is_favorite: !item.is_favorite });
      },
      item.is_favorite ? "已取消收藏" : "已收藏，喜欢的好物不再错过",
    );
  }
  function addCompare(item: Item) {
    if (compare.some((i) => i.id === item.id))
      setCompare(compare.filter((i) => i.id !== item.id));
    else if (compare.length < 3) setCompare([...compare, item]);
    else setToast("每次最多对比 3 件商品");
  }
  async function copy(text: string, message: string) {
    try {
      await navigator.clipboard.writeText(text);
      setToast(message);
    } catch {
      setToast("复制失败，请手动选中文字复制");
    }
  }
  function searchSubmit(e: FormEvent) {
    e.preventDefault();
    setQuery(search);
    setPage(1);
    navigate("market");
  }
  const listParams = new URLSearchParams({
    q: query,
    category,
    campus,
    sort,
    page: String(page),
    size: "12",
  });
  if (price) listParams.set("max_price", price);
  if (view === "mine") listParams.set("mine", "true");
  if (view === "favorites") listParams.set("favorites", "true");
  const listingView = ["market", "favorites", "mine"].includes(view);
  const items = useResource<{ items: Item[]; total: number }>(
    "/items/?" + listParams.toString(),
    revision,
    listingView && (view === "market" || !!user),
  );
  const intents = useResource<Intent[]>(
    "/intents/my",
    revision,
    view === "intents" && !!user,
  );
  const wanted = useResource<Wanted[]>("/wanted/", revision, view === "wanted");
  const unread = notices.filter((n) => !n.is_read).length;

  if (!meta)
    return (
      <div className="boot">
        <Brand />
        {fatal ? (
          <>
            <p role="alert">暂时无法连接燕渡服务：{fatal}</p>
            <button
              className="button primary"
              onClick={() => location.reload()}
            >
              重新连接
            </button>
          </>
        ) : (
          <Busy>燕渡正在准备好物…</Busy>
        )}
      </div>
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="brand-button"
          onClick={() => navigate("market")}
          aria-label="燕渡首页"
        >
          <Brand />
        </button>
        <p className="brand-caption">旧物渡新主，学海渡轻舟</p>
        <div className="nav-label">校园生活的另一种循环</div>
        <nav aria-label="主导航">
          {nav.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              className={`nav-item ${view === key ? "active" : ""}`}
              onClick={() => {
                setCategory("");
                setQuery("");
                setSearch("");
                setPrice("");
                navigate(key as View);
              }}
            >
              <Icon size={20} strokeWidth={1.7} />
              <span>{label}</span>
              {key === "intents" && <span className="nav-new">NEW</span>}
            </button>
          ))}
          {user?.role === "admin" && (
            <button
              className={`nav-item ${view === "admin" ? "active" : ""}`}
              onClick={() => navigate("admin")}
            >
              <ShieldCheck size={20} />
              审核工作台
            </button>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="eco-note">
            <Leaf size={23} strokeWidth={1.4} />
            <h3>
              让每一件好物
              <br />
              都有下一段故事。
            </h3>
            <p>少一点闲置，多一点连接。</p>
            <span>
              在燕园，把美好传下去 <ArrowRight size={13} />
            </span>
          </div>
          <div className="sidebar-caption">
            <ShieldCheck size={15} />
            {meta.demo_mode ? "本地演示 · 校园认证待接入" : "燕渡校园社区"}
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="mobile-brand">
            <Brand small />
          </div>
          <form className="global-search" onSubmit={searchSubmit}>
            <Search size={19} />
            <input
              aria-label="搜索校园好物"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜搜你需要的校园好物…"
            />
            <kbd>Enter</kbd>
          </form>
          <div className="top-actions">
            <label className="campus-picker">
              <MapPin size={16} />
              <select
                aria-label="选择校区"
                value={campus}
                onChange={(e) => {
                  setCampus(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">全部校区</option>
                {meta.campuses
                  .filter((c) => c !== "不限校区")
                  .map((c) => (
                    <option key={c}>{c}</option>
                  ))}
              </select>
            </label>
            <button
              className="notification-button icon-button"
              aria-label={`通知${unread ? `，${unread} 条未读` : ""}`}
              onClick={() => {
                if (needUser()) setModal("notifications");
              }}
            >
              <Bell size={21} />
              {unread > 0 && <span>{unread}</span>}
            </button>
            <button
              className="avatar-button"
              onClick={() => setModal("login")}
              aria-label={user ? `当前账号 ${user.nickname}` : "登录"}
            >
              <span className="avatar">{user ? user.nickname[0] : "访"}</span>
              <span>{user?.nickname || "登录"}</span>
            </button>
          </div>
        </header>
        <main>
          {view === "market" && (
            <form className="mobile-search" onSubmit={searchSubmit}>
              <Search size={18} />
              <input
                aria-label="手机端搜索校园好物"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索物品、教材或型号…"
              />
              <button type="submit" className="text-button">
                搜索
              </button>
            </form>
          )}
          {view === "market" && (
            <>
              <section className="hero">
                <div className="hero-copy">
                  <span className="eyebrow">
                    <span className="live-dot" /> GOOD THINGS, NEXT CHAPTER
                  </span>
                  <h1>
                    旧物有新处，
                    <br />
                    好物等你来<span>。</span>
                  </h1>
                  <p>
                    从一本翻过的书，到陪你熬夜的台灯。
                    <br />
                    你的刚好闲置，也许是同学的正好需要。
                  </p>
                  <button
                    className="button primary"
                    onClick={() => openForm("publish")}
                  >
                    <Plus size={18} />
                    发布我的闲置
                    <ArrowRight size={16} />
                  </button>
                  <div className="hero-foot">
                    <Leaf size={15} />
                    <span>让闲置流转，让校园更有温度</span>
                  </div>
                </div>
                <div className="hero-art" aria-hidden="true">
                  <div className="hero-orbit orbit-one" />
                  <div className="hero-orbit orbit-two" />
                  <svg viewBox="0 0 420 320">
                    <ellipse
                      cx="233"
                      cy="261"
                      rx="111"
                      ry="11"
                      fill="#b5c4a2"
                      opacity=".23"
                    />
                    <path d="m130 167 191-54-79 121z" fill="#ecddbe" />
                    <path
                      d="m130 167 89 14 102-68-79 121-23-53"
                      fill="#faf6e8"
                    />
                    <path d="m219 181 7 36 16 17" fill="#d4c7a8" />
                    <path
                      d="m106 107 19-5-8 17"
                      fill="none"
                      stroke="#62826b"
                      strokeWidth="2"
                    />
                    <path
                      d="M292 84q27 2 34-21m-10 13 9-4"
                      stroke="#81966b"
                      fill="none"
                    />
                    <path
                      d="M302 231q6-57 27-89m-18 62q29-4 35-26-23 1-35 26m10-33q-21-9-19-30 23 8 19 30m-16 48q-25-1-31-22 29-1 31 22"
                      stroke="#78926a"
                      strokeWidth="2"
                      fill="#a7b790"
                    />
                    <circle cx="129" cy="217" r="4" fill="#e1b871" />
                    <circle cx="272" cy="58" r="3" fill="#81976e" />
                    <path
                      d="m93 161 8-9m-10 0 10 9"
                      stroke="#afbc97"
                      strokeWidth="2"
                    />
                  </svg>
                  <span className="floating-note note-one">
                    <BookOpen size={17} />
                    知识，也可以接力
                  </span>
                  <span className="floating-note note-two">
                    <Check size={15} />
                    在校园，遇见刚刚好
                  </span>
                  <span className="handwritten">
                    a little less waste,
                    <br />a little more connection.
                  </span>
                </div>
              </section>
              <section className="intent-banner">
                <div className="intent-symbol">
                  <Sparkles size={25} />
                </div>
                <div className="intent-banner-text">
                  <h2>你许个愿，燕渡帮你找。</h2>
                  <p>不用反复刷，有合适的好物就通知你。</p>
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    openForm("intent", intentQuery);
                  }}
                >
                  <input
                    aria-label="一句话描述需求"
                    value={intentQuery}
                    onChange={(e) => setIntentQuery(e.target.value)}
                    placeholder="试试：300 元以内的静音鼠标"
                  />
                  <button className="button dark" type="submit">
                    帮我代蹲
                    <ArrowRight size={16} />
                  </button>
                </form>
              </section>
            </>
          )}
          {listingView && (
            <section className="market-section">
              {view === "market" ? (
                <div className="section-heading">
                  <div>
                    <h2>
                      发现校园好物 <span className="small-dot" />
                    </h2>
                    <p>值得拥有的，不一定是全新的。</p>
                  </div>
                  <span className="listing-count">
                    {items.data?.total ?? "…"} 件好物 · 等待新主人
                  </span>
                </div>
              ) : (
                <Intro
                  kicker={
                    view === "favorites"
                      ? "YOUR LITTLE COLLECTION"
                      : "PASS IT FORWARD"
                  }
                  title={
                    view === "favorites"
                      ? "心动好物，留在这里。"
                      : "我发布的闲置"
                  }
                  text={
                    view === "favorites"
                      ? "遇到喜欢的先收藏，慢慢找到合适的那一件。"
                      : "管理商品状态，让闲置顺利开启下一段故事。"
                  }
                >
                  {view === "mine" && (
                    <button
                      className="button primary"
                      onClick={() => openForm("publish")}
                    >
                      <Plus size={17} />
                      发布闲置
                    </button>
                  )}
                </Intro>
              )}
              <div className="category-tabs" role="group" aria-label="物品分类">
                {["全部好物", ...meta.categories].map((c, index) => {
                  const Icon = [
                    LayoutGrid,
                    BookOpen,
                    Monitor,
                    Bike,
                    Lamp,
                    Shirt,
                  ][index];
                  return (
                    <button
                      key={c}
                      className={category === (index ? c : "") ? "active" : ""}
                      onClick={() => {
                        setCategory(index ? c : "");
                        setPage(1);
                      }}
                    >
                      <Icon size={17} />
                      {index
                        ? [
                            "课程书籍",
                            "数码影音",
                            "出行运动",
                            "宿舍生活",
                            "服饰周边",
                          ][index - 1]
                        : c}
                    </button>
                  );
                })}
              </div>
              <div className="filter-row">
                <div className="filter-left">
                  <span className="filter-label">筛选</span>
                  <label>
                    <span className="sr-only">最高价格</span>
                    <select
                      value={price}
                      onChange={(e) => {
                        setPrice(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="">不限价格</option>
                      <option value="50">50 元以内</option>
                      <option value="100">100 元以内</option>
                      <option value="300">300 元以内</option>
                      <option value="500">500 元以内</option>
                    </select>
                  </label>
                  {query && (
                    <button
                      className="query-tag"
                      onClick={() => {
                        setQuery("");
                        setSearch("");
                      }}
                    >
                      “{query}”<X size={13} />
                    </button>
                  )}
                  <span className="filter-hint">
                    {view === "market"
                      ? "只看正在出售的好物"
                      : "包含已售与过期商品"}
                  </span>
                </div>
                <label className="sort-picker">
                  <ArrowDownUp size={14} />
                  <select
                    aria-label="商品排序"
                    value={sort}
                    onChange={(e) => {
                      setSort(e.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="recommended">为你挑选</option>
                    <option value="newest">最新发布</option>
                    <option value="price_asc">价格从低到高</option>
                    <option value="price_desc">价格从高到低</option>
                  </select>
                </label>
              </div>
              {!user && view !== "market" ? (
                <Empty
                  title="登录后，继续你的校园之旅"
                  text="收藏和发布记录会跟随你的账号保存。"
                  action="进入演示账号"
                  onAction={() => setModal("login")}
                />
              ) : items.loading ? (
                <Busy />
              ) : items.error ? (
                <Empty
                  title="好物暂时没有加载出来"
                  text={items.error}
                  action="重试"
                  onAction={refresh}
                />
              ) : items.data?.items.length ? (
                <>
                  <div className="item-grid">
                    {items.data.items.map((item) => (
                      <Card
                        key={item.id}
                        item={item}
                        onOpen={openItem}
                        onFavorite={favorite}
                        onCompare={addCompare}
                        selected={compare.some((i) => i.id === item.id)}
                      />
                    ))}
                  </div>
                  {items.data.total > 12 && (
                    <div className="pagination">
                      <button
                        className="button secondary"
                        disabled={page <= 1}
                        onClick={() => setPage(page - 1)}
                      >
                        <ChevronLeft size={16} />
                        上一页
                      </button>
                      <span>
                        {page} / {Math.ceil(items.data.total / 12)}
                      </span>
                      <button
                        className="button secondary"
                        disabled={page * 12 >= items.data.total}
                        onClick={() => setPage(page + 1)}
                      >
                        下一页
                        <ChevronRight size={16} />
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <Empty
                  title={
                    view === "favorites"
                      ? "把喜欢的好物，先收藏起来"
                      : view === "mine"
                        ? "你的第一件闲置，还在等待出发"
                        : "暂时没有合适的好物"
                  }
                  text={
                    view === "market"
                      ? "换个筛选条件，或留下求购，让有闲置的同学找到你。"
                      : "每一件物品，都值得一段新的故事。"
                  }
                  action={
                    view === "market"
                      ? "发布求购"
                      : view === "mine"
                        ? "发布闲置"
                        : "去逛逛校园"
                  }
                  onAction={() =>
                    view === "market"
                      ? openForm("wanted")
                      : view === "mine"
                        ? openForm("publish")
                        : navigate("market")
                  }
                />
              )}
            </section>
          )}
          {view === "intents" && (
            <>
              <Intro
                kicker="LET YANDU KEEP AN EYE OUT"
                title="你忙你的，燕渡帮你找。"
                text="每一个小小心愿，都值得被认真留意。"
              >
                <button
                  className="button primary"
                  onClick={() => openForm("intent")}
                >
                  <Plus size={17} />
                  新建代蹲
                </button>
              </Intro>
              <div className="info-strip">
                <Sparkles size={17} />
                <span>
                  {meta.ai_mode === "local"
                    ? "当前为本地关键词匹配演示"
                    : "当前为语义向量匹配"}{" "}
                  · 每个任务持续 14 天 · 最多 5 个活跃任务
                </span>
              </div>
              {!user ? (
                <Empty
                  title="登录后，让燕渡替你留意"
                  text="你的需求和命中记录会保存在账号中。"
                  action="进入演示账号"
                  onAction={() => setModal("login")}
                />
              ) : intents.loading ? (
                <Busy />
              ) : intents.error ? (
                <Empty
                  title="任务暂时无法加载"
                  text={intents.error}
                  action="重试"
                  onAction={refresh}
                />
              ) : !intents.data?.length ? (
                <Empty
                  title="留一个心愿给燕渡"
                  text="例如：万柳附近 300 元以内的静音鼠标。现在没有也没关系，新商品上架后会再匹配。"
                  action="创建第一个代蹲任务"
                  onAction={() => openForm("intent")}
                />
              ) : (
                <div className="intent-list">
                  {intents.data.map((i) => (
                    <article className="intent-card" key={i.id}>
                      <div className="intent-card-top">
                        <span
                          className={`task-status ${i.status === "ACTIVE" ? "active" : ""}`}
                        >
                          <span className="live-dot" />
                          {i.status === "ACTIVE"
                            ? "正在替你留意"
                            : statusText[i.status]}
                        </span>
                        <span>
                          {new Date(i.expires_at).toLocaleDateString("zh-CN")}{" "}
                          到期
                        </span>
                      </div>
                      <h3>{i.raw_query}</h3>
                      <div className="pills">
                        <span>{i.category || "不限分类"}</span>
                        <span>
                          {i.max_price === null
                            ? "不限预算"
                            : `¥${money(i.max_price)} 以内`}
                        </span>
                        <span>{i.campus}</span>
                        {i.keywords.map((k) => (
                          <span key={k}>{k}</span>
                        ))}
                      </div>
                      <div className="intent-card-bottom">
                        <button
                          className="text-button"
                          onClick={() => setModal("notifications")}
                        >
                          <Bell size={16} />
                          累计发现 {i.match_count} 件好物
                          <ArrowRight size={14} />
                        </button>
                        {i.status !== "COMPLETED" && (
                          <div className="task-actions">
                            <button
                              disabled={busy}
                              onClick={() =>
                                void operate(() =>
                                  api(`/intents/${i.id}`, "PATCH", {
                                    action:
                                      i.status === "ACTIVE"
                                        ? "pause"
                                        : i.status === "EXPIRED"
                                          ? "renew"
                                          : "resume",
                                  }),
                                )
                              }
                            >
                              {i.status === "ACTIVE" ? (
                                <Pause size={14} />
                              ) : (
                                <Play size={14} />
                              )}{" "}
                              {i.status === "ACTIVE" ? "暂停" : "继续"}
                            </button>
                            <button
                              disabled={busy}
                              onClick={() =>
                                void operate(
                                  () =>
                                    api(`/intents/${i.id}`, "PATCH", {
                                      action: "renew",
                                    }),
                                  "已续期 14 天",
                                )
                              }
                            >
                              <RefreshCw size={13} />
                              续期
                            </button>
                            <button
                              disabled={busy}
                              onClick={() =>
                                void operate(
                                  () => api(`/intents/${i.id}`, "DELETE"),
                                  "代蹲已结束",
                                )
                              }
                            >
                              结束
                            </button>
                          </div>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
          {view === "wanted" && (
            <>
              <Intro
                kicker="SOMEONE MIGHT HAVE WHAT YOU NEED"
                title="你需要的，也许恰好有人闲置。"
                text="在这里写下需要，让好物与好物的下一位主人相遇。"
              >
                <button
                  className="button primary"
                  onClick={() => openForm("wanted")}
                >
                  <Plus size={17} />
                  发布求购
                </button>
              </Intro>
              {wanted.loading ? (
                <Busy />
              ) : wanted.error ? (
                <Empty
                  title="求购暂时无法加载"
                  text={wanted.error}
                  action="重试"
                  onAction={refresh}
                />
              ) : wanted.data?.length ? (
                <div className="wanted-grid">
                  {wanted.data.map((w) => (
                    <article className="wanted-card" key={w.id}>
                      <div className="wanted-card-top">
                        <span className="category-label">{w.category}</span>
                        <Sprout size={21} />
                      </div>
                      <h3>{w.title}</h3>
                      <p>{w.description}</p>
                      <div className="wanted-budget">
                        预算 <strong>¥{money(w.budget)}</strong>
                        <span>
                          <MapPin size={13} />
                          {campusShort(w.campus)}
                        </span>
                      </div>
                      <div className="wanted-bottom">
                        <span>
                          <span className="mini-avatar">
                            {w.buyer.nickname[0]}
                          </span>
                          {w.buyer.nickname}
                        </span>
                        {w.is_owner ? (
                          <button
                            className="text-button"
                            disabled={busy}
                            onClick={() =>
                              void operate(
                                () => api(`/wanted/${w.id}`, "DELETE"),
                                "求购已结束",
                              )
                            }
                          >
                            我已找到
                            <Check size={15} />
                          </button>
                        ) : (
                          <button
                            className="text-button"
                            onClick={() => {
                              if (needUser()) {
                                setPrefill(w);
                                setModal("publish");
                              }
                            }}
                          >
                            我有这件物品
                            <ArrowRight size={15} />
                          </button>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <Empty
                  title="第一个心愿，由你开始"
                  text="写下想找的物品，让同学们帮你留意。"
                  action="发布求购"
                  onAction={() => openForm("wanted")}
                />
              )}
            </>
          )}
          {view === "admin" && (
            <Admin
              user={user}
              revision={revision}
              refresh={refresh}
              notify={setToast}
            />
          )}
          <footer>
            <Brand small />
            <span>物尽其用，让美好在校园里循环。</span>
            <span className="footer-mode">
              {meta.demo_mode ? "演示环境 · 数据仅保存在本地" : "燕渡校园社区"}
            </span>
          </footer>
        </main>
      </div>
      {compare.length > 0 && (
        <div className="compare-tray">
          <span>
            <CheckCheck size={18} />
            已选 {compare.length} 件好物
          </span>
          <button
            className="button primary"
            disabled={compare.length < 2}
            onClick={() => setModal("compare")}
          >
            比较一下
            <ArrowRight size={15} />
          </button>
          <button
            className="icon-button"
            aria-label="清空对比"
            onClick={() => setCompare([])}
          >
            <X size={17} />
          </button>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          <CircleHelp size={17} />
          {toast}
          <button aria-label="关闭提示" onClick={() => setToast("")}>
            <X size={15} />
          </button>
        </div>
      )}
      {modal === "login" && (
        <Modal
          title={user ? "当前账号" : "欢迎来到燕渡"}
          onClose={() => setModal(null)}
        >
          <div className="stack-form">
            <p className="muted">
              {meta.demo_mode
                ? "这是本地演示环境。选择不同账号体验买家、卖家与管理员流程；这些账号不代表真实校园身份。"
                : "校园统一身份认证尚未接入，请联系项目管理员。"}
            </p>
            {meta.demo_mode && (
              <div className="login-options">
                {[
                  {
                    id: "buyer",
                    name: "林同学",
                    detail: "买家体验 · 许愿、收藏、接收匹配",
                  },
                  {
                    id: "seller",
                    name: "许同学",
                    detail: "卖家体验 · 发布、预订、标记售出",
                  },
                  {
                    id: "admin",
                    name: "管理员",
                    detail: "审核体验 · 检查举报、确认处理",
                  },
                ].map((p) => (
                  <button
                    disabled={busy}
                    key={p.id}
                    onClick={() =>
                      void operate(async () => {
                        const result = await api<{ user: User }>(
                          "/auth/demo",
                          "POST",
                          { profile: p.id },
                        );
                        setUser(result.user);
                        setModal(null);
                        setSelected(null);
                        setCompare([]);
                      }, `已进入${p.name}的演示账号`)
                    }
                  >
                    <span className="avatar">{p.name[0]}</span>
                    <span>
                      <strong>{p.name}</strong>
                      <small>{p.detail}</small>
                    </span>
                    <ArrowRight size={17} />
                  </button>
                ))}
              </div>
            )}
            {user && (
              <button
                className="button secondary full"
                disabled={busy}
                onClick={() =>
                  void operate(async () => {
                    await api("/auth/logout", "POST");
                    setUser(null);
                    setModal(null);
                    setCompare([]);
                    navigate("market");
                  }, "已退出账号")
                }
              >
                <LogOut size={16} />
                退出登录
              </button>
            )}
          </div>
        </Modal>
      )}
      {modal === "intent" && (
        <Modal title="把需要的，交给燕渡留意" onClose={() => setModal(null)}>
          <IntentForm
            meta={meta}
            initial={intentQuery}
            onDone={() => {
              setModal(null);
              setToast("代蹲已开始，已有商品也已完成首次匹配");
              refresh();
              navigate("intents");
            }}
          />
        </Modal>
      )}
      {modal === "publish" && (
        <Modal title="让闲置，开启下一段故事" onClose={() => setModal(null)}>
          <PublishForm
            meta={meta}
            prefill={prefill}
            onDone={() => {
              setModal(null);
              setToast("好物发布成功，已为有需要的同学进行匹配");
              refresh();
              navigate("mine");
            }}
          />
        </Modal>
      )}
      {modal === "wanted" && (
        <Modal title="告诉同学们，你在找什么" onClose={() => setModal(null)}>
          <WantedForm
            meta={meta}
            initial={query}
            onDone={() => {
              setModal(null);
              refresh();
              navigate("wanted");
              setToast("求购已发布，期待好物与你相遇");
            }}
          />
        </Modal>
      )}
      {modal === "notifications" && (
        <Modal title="燕渡为你捎来的消息" onClose={() => setModal(null)}>
          {notices.length ? (
            <div className="notice-list">
              {notices.map((n) => (
                <article
                  className={`notice ${n.is_read ? "" : "unread"}`}
                  key={n.id}
                >
                  <ProductArt item={n.item} />
                  <div>
                    <span className="task-status">
                      {n.available ? "有好物符合你的期待" : "这件商品已不在售"}
                    </span>
                    <h3>{n.item.title}</h3>
                    <p>{n.reason}</p>
                    <div>
                      <button
                        className="text-button"
                        onClick={() => {
                          void operate(() =>
                            api(`/notifications/${n.id}/read`, "PATCH"),
                          );
                          void openItem(n.item);
                        }}
                      >
                        查看商品
                        <ArrowRight size={14} />
                      </button>
                      {!n.is_read && (
                        <button
                          className="text-button"
                          disabled={busy}
                          onClick={() =>
                            void operate(() =>
                              api(`/notifications/${n.id}/read`, "PATCH"),
                            )
                          }
                        >
                          标为已读
                        </button>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <Empty
              title="好消息正在路上"
              text="创建代蹲任务后，符合条件的好物会出现在这里。"
              action="去许个愿"
              onAction={() => openForm("intent")}
            />
          )}
        </Modal>
      )}
      {modal === "compare" && (
        <Modal title="哪一件，更适合你？" onClose={() => setModal(null)} wide>
          <div
            className="comparison-grid"
            style={{
              gridTemplateColumns: `repeat(${compare.length}, minmax(0, 1fr))`,
            }}
          >
            {compare.map((i) => (
              <div key={i.id}>
                <ProductArt item={i} />
                <h3>{i.title}</h3>
                <p className="price">¥{money(i.price)}</p>
                <dl>
                  <dt>成色</dt>
                  <dd>{i.condition_grade}</dd>
                  <dt>校区</dt>
                  <dd>{i.campus}</dd>
                  <dt>卖家描述</dt>
                  <dd>{i.description}</dd>
                  <dt>卖家评价</dt>
                  <dd>暂无评价数据</dd>
                </dl>
                <button
                  className="button secondary full"
                  onClick={() => void openItem(i)}
                >
                  查看最新状态
                </button>
              </div>
            ))}
          </div>
          <p className="hint">
            以上为加入对比时的商品信息，交易前请重新查看商品状态。
          </p>
        </Modal>
      )}
      {modal === "detail" && selected && (
        <Modal title="好物详情" onClose={() => setModal(null)} wide>
          <div className="detail-grid">
            <div>
              <ProductArt item={selected} />
              {selected.images.length > 1 && (
                <div className="detail-photos">
                  {selected.images.slice(1).map((url) => (
                    <img
                      key={url}
                      src={url}
                      alt={`${selected.title}的补充照片`}
                    />
                  ))}
                </div>
              )}
              {selected.is_demo && (
                <p className="hint">演示商品插画，不代表真实在售商品。</p>
              )}
            </div>
            <div>
              <div className="detail-badges">
                <span className="category-label">{selected.category}</span>
                <span className="category-label">
                  {statusText[selected.status]}
                </span>
              </div>
              <h2 className="detail-title">{selected.title}</h2>
              <div className="detail-price">¥{money(selected.price)}</div>
              <div className="detail-meta">
                <span>
                  <MapPin size={15} />
                  {selected.campus}
                </span>
                <span>{selected.condition_grade}</span>
              </div>
              <p className="detail-description">{selected.description}</p>
              <div className="pills">
                {selected.tags.map((t) => (
                  <span key={t}>{t}</span>
                ))}
              </div>
              <div className="seller-info">
                <span className="avatar">{selected.seller.nickname[0]}</span>
                <div>
                  <strong>{selected.seller.nickname}</strong>
                  <small>
                    {selected.is_demo ? "校园演示账号" : "平台用户"}
                  </small>
                </div>
                <ShieldCheck size={20} />
              </div>
              {selected.is_owner ? (
                <div className="detail-actions">
                  {["ACTIVE", "RESERVED", "EXPIRED"].includes(
                    selected.status,
                  ) && (
                    <>
                      {selected.status !== "ACTIVE" && (
                        <button
                          className="button primary"
                          disabled={busy}
                          onClick={() =>
                            void operate(
                              async () =>
                                setSelected(
                                  await api<Item>(
                                    `/items/${selected.id}/status`,
                                    "PATCH",
                                    { status: "ACTIVE" },
                                  ),
                                ),
                              "商品已重新上架",
                            )
                          }
                        >
                          重新上架
                        </button>
                      )}
                      {selected.status === "ACTIVE" && (
                        <button
                          className="button secondary"
                          disabled={busy}
                          onClick={() =>
                            void operate(
                              async () =>
                                setSelected(
                                  await api<Item>(
                                    `/items/${selected.id}/status`,
                                    "PATCH",
                                    { status: "RESERVED" },
                                  ),
                                ),
                              "已标记为预订",
                            )
                          }
                        >
                          标记预订
                        </button>
                      )}
                      <button
                        className="button primary"
                        disabled={busy}
                        onClick={() =>
                          void operate(
                            async () =>
                              setSelected(
                                await api<Item>(
                                  `/items/${selected.id}/status`,
                                  "PATCH",
                                  { status: "SOLD" },
                                ),
                              ),
                            "已标记售出",
                          )
                        }
                      >
                        标记已售出
                      </button>
                    </>
                  )}
                </div>
              ) : (
                <div className="detail-actions">
                  <button
                    className="button primary"
                    disabled={busy || selected.status !== "ACTIVE"}
                    onClick={() => {
                      if (needUser())
                        void operate(async () => {
                          const d = await api<{ draft: string }>(
                            `/items/${selected.id}/message-draft`,
                            "POST",
                          );
                          setDraft(d.draft);
                        });
                    }}
                  >
                    生成咨询草稿
                    <ArrowRight size={16} />
                  </button>
                  <button
                    className="button secondary"
                    onClick={() => favorite(selected)}
                  >
                    <Heart
                      size={17}
                      fill={selected.is_favorite ? "currentColor" : "none"}
                    />
                    {selected.is_favorite ? "已收藏" : "收藏"}
                  </button>
                </div>
              )}
              <div className="detail-links">
                <button
                  onClick={() =>
                    void copy(
                      `${location.origin}/?item=${selected.id}`,
                      "商品链接已复制",
                    )
                  }
                >
                  <Share2 size={14} />
                  复制分享链接
                </button>
                <button
                  onClick={() => {
                    if (needUser()) setReporting(!reporting);
                  }}
                >
                  <Flag size={14} />
                  举报问题
                </button>
              </div>
            </div>
          </div>
          {draft && (
            <div className="draft-box">
              <h3>
                咨询草稿 <span>尚未发送</span>
              </h3>
              <textarea
                aria-label="咨询消息草稿"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={3}
              />
              <div>
                <p>由你确认并复制发送。演示版未接入站内聊天或微信。</p>
                <button
                  className="button secondary"
                  onClick={() => void copy(draft, "咨询草稿已复制，尚未发送")}
                >
                  <Copy size={15} />
                  复制草稿
                </button>
              </div>
            </div>
          )}
          {reporting && (
            <form
              className="stack-form report-form"
              onSubmit={(e) => {
                e.preventDefault();
                void operate(async () => {
                  await api(`/items/${selected.id}/reports`, "POST", {
                    reason: reportText,
                  });
                  setReporting(false);
                }, "举报已提交，等待管理员核实");
              }}
            >
              <label>
                请描述遇到的问题
                <textarea
                  value={reportText}
                  onChange={(e) => setReportText(e.target.value)}
                  required
                  minLength={5}
                  maxLength={1000}
                  placeholder="描述具体情况，方便管理员核实。"
                />
              </label>
              <button className="button secondary" disabled={busy}>
                提交举报
              </button>
            </form>
          )}
        </Modal>
      )}
    </div>
  );
}

function Admin({
  user,
  revision,
  refresh,
  notify,
}: {
  user: User | null;
  revision: number;
  refresh: () => void;
  notify: (v: string) => void;
}) {
  const reports = useResource<Report[]>(
    "/admin/reports",
    revision,
    user?.role === "admin",
  );
  const logs = useResource<Log[]>(
    "/admin/logs",
    revision,
    user?.role === "admin",
  );
  const [busy, setBusy] = useState(false);
  if (user?.role !== "admin")
    return (
      <Empty
        title="这里需要管理员权限"
        text="登录管理员演示账号后，可以查看举报和操作记录。"
      />
    );
  async function review(e: FormEvent<HTMLFormElement>, id: string) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    try {
      await api(`/admin/reports/${id}/review`, "POST", {
        action: data.get("action"),
        note: data.get("note"),
        confirmed: data.get("confirmed") === "on",
      });
      notify("处理结果已保存，并已记录审核日志");
      form.reset();
      refresh();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Intro
        kicker="A COMMUNITY WE CARE FOR"
        title="审核工作台"
        text="规则整理线索，管理员核实事实。每一次操作都有据可查。"
      />
      <div className="info-strip">
        <ShieldCheck size={18} />
        当前仅提供文字风险词与同名商品检查，不包含图片识别。举报本身不代表违规成立。
      </div>
      {reports.loading ? (
        <Busy />
      ) : reports.error ? (
        <Empty
          title="审核记录加载失败"
          text={reports.error}
          action="重试"
          onAction={refresh}
        />
      ) : reports.data?.length ? (
        <div className="review-list">
          {reports.data.map((r) => (
            <article className="review-card" key={r.id}>
              <div className="section-heading">
                <h3>{r.item.title}</h3>
                <span className="category-label">
                  {r.status} · 风险：{r.risk}
                </span>
              </div>
              <p>举报内容：{r.reason}</p>
              <ul>
                {r.evidence.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
              <form
                className="review-form"
                onSubmit={(e) => void review(e, r.id)}
              >
                <label>
                  处理方式
                  <select name="action">
                    <option value="dismiss">不采纳举报</option>
                    <option value="hide">隐藏商品</option>
                    <option value="restore">恢复被隐藏商品</option>
                  </select>
                </label>
                <label>
                  审核依据
                  <input
                    name="note"
                    required
                    minLength={5}
                    maxLength={500}
                    placeholder="请记录核实结果和依据"
                  />
                </label>
                <label className="check-label">
                  <input type="checkbox" name="confirmed" required />
                  我已核实，确认执行此操作
                </label>
                <button className="button primary" disabled={busy}>
                  确认处理
                </button>
              </form>
            </article>
          ))}
        </div>
      ) : (
        <Empty
          title="目前没有待核实的举报"
          text="收到新的举报后，相关证据会整理在这里。"
        />
      )}
      <h2 className="audit-title">最近操作记录</h2>
      {logs.error && <p className="form-error">{logs.error}</p>}
      <div className="audit-list">
        {logs.data?.map((l) => (
          <div key={l.id}>
            <span>{new Date(l.created_at).toLocaleString("zh-CN")}</span>
            <strong>{l.actor.nickname}</strong>
            <code>{l.action}</code>
            <span>{l.detail || l.target_id.slice(0, 12)}</span>
          </div>
        ))}
      </div>
    </>
  );
}
