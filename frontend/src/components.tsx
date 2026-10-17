import { useEffect, useId, useRef, type CSSProperties, type ReactNode } from "react";
import {
  ArrowRight,
  Heart,
  MapPin,
  Plus,
  X,
  PackageOpen,
  SlidersHorizontal,
} from "lucide-react";
import { type Item, ago, campusShort, money, statusText } from "./api";

export function Brand({ small = false }: { small?: boolean }) {
  return (
    <div className={`brand ${small ? "small" : ""}`}>
      <svg viewBox="0 0 40 40" aria-hidden="true">
        <path
          d="M5 8c7 1 12 5 16 13L35 8l-5 16 5 9-13-6-9 8 3-13z"
          fill="currentColor"
        />
        <path d="m22 23 7-8" fill="none" stroke="#f6f7ef" strokeWidth="1.5" />
      </svg>
      <span>
        燕渡<small>Y A N D U</small>
      </span>
    </div>
  );
}

export function ProductArt({
  item,
}: {
  item: Pick<Item, "art" | "images" | "title"> & Partial<Pick<Item, "is_demo">>;
}) {
  const id = useId().replace(/:/g, "");
  if (item.images.length)
    return (
      <img
        className="product-photo"
        src={item.images[0]}
        alt={item.title}
        loading="lazy"
      />
    );
  if (!item.is_demo) return <div className="product-art product-placeholder" role="img" aria-label={`${item.title}（暂无图片）`}>
    <PackageOpen size={38} strokeWidth={1.25} /><span>暂无图片</span>
  </div>;
  const art = item.art;
  const bg: Record<string, string> = {
    mouse: "#e5e6df",
    books: "#ebe1d1",
    bike: "#e1e8dd",
    lamp: "#e6e5db",
    monitor: "#dce4e1",
    bag: "#f1e4d8",
    headphones: "#e4e1e8",
    shelf: "#e8ddcf",
    racket: "#e2e8e0",
  };
  return (
    <svg
      className="product-art"
      viewBox="0 0 360 260"
      role="img"
      aria-label={`${item.title}（演示插画）`}
      style={{ background: bg[art] || "#ece9e1" }}
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#676f68" />
          <stop offset="1" stopColor="#252d2a" />
        </linearGradient>
        <filter id={`${id}s`}>
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>
      <ellipse
        cx="180"
        cy="222"
        rx="91"
        ry="9"
        fill="#425348"
        opacity=".14"
        filter={`url(#${id}s)`}
      />
      {art === "mouse" ? (
        <g transform="rotate(-25 180 130)">
          <path
            d="M139 59c18-26 64-17 83 13 17 26 28 76 14 111-13 31-77 39-99 7-23-33-20-99 2-131Z"
            fill={`url(#${id})`}
          />
          <path
            d="M177 48c-8 48-5 77 9 107m-54-27c32 5 62-2 95-17"
            stroke="#929992"
            strokeWidth="1.2"
            fill="none"
          />
          <rect x="170" y="69" width="13" height="33" rx="6" fill="#111a17" />
          <path d="m145 156 1 35" stroke="#889088" strokeWidth="3" />
          <text
            x="180"
            y="183"
            fontSize="11"
            fill="#aeb5ab"
            textAnchor="middle"
          >
            logi
          </text>
        </g>
      ) : art === "books" ? (
        <g transform="rotate(-12 180 140)">
          <path d="M88 92h166v127H88z" fill="#345852" />
          <path d="M96 209h158v9H96z" fill="#e9e6d8" />
          <path d="M112 52h133v148H112z" fill="#e8bb71" />
          <path d="M120 190h125v10H120z" fill="#fff8e9" />
          <path d="M121 52v138" stroke="#c5934d" />
          <text x="140" y="104" fontSize="20" fill="#534b37" fontFamily="serif">
            {item.title.includes("GRE") ? "GRE" : "高等数学"}
          </text>
          <text x="143" y="127" fontSize="8" fill="#70634b">
            MATHEMATICS
          </text>
          <path
            d="m147 163 17-24 11 15 22-9 19 17"
            fill="none"
            stroke="#866f49"
          />
          <text x="140" y="183" fontSize="7" fill="#866f49">
            知识，传递给下一个你
          </text>
        </g>
      ) : art === "bike" ? (
        <g fill="none" strokeLinecap="round">
          <circle cx="91" cy="177" r="49" stroke="#444e45" strokeWidth="7" />
          <circle cx="270" cy="177" r="49" stroke="#444e45" strokeWidth="7" />
          <circle cx="91" cy="177" r="43" stroke="#a7b1a0" />
          <circle cx="270" cy="177" r="43" stroke="#a7b1a0" />
          <path
            d="m91 177 47-71 40 71H91l125-80 54 80m-132-71h87m-48 71-26-91m59 8-8-18 21-8"
            stroke="#7b9a76"
            strokeWidth="7"
          />
          <path d="M135 85h32m37-11 26-7" stroke="#333e35" strokeWidth="7" />
          <circle cx="178" cy="177" r="12" stroke="#333e35" strokeWidth="3" />
          <path d="m179 177 15 14h10" stroke="#333e35" strokeWidth="3" />
        </g>
      ) : art === "lamp" ? (
        <g>
          <ellipse cx="174" cy="217" rx="62" ry="13" fill="#bbbdaf" />
          <ellipse cx="174" cy="211" rx="62" ry="13" fill="#fafbf0" />
          <path
            d="m171 209 17-114 54-28"
            fill="none"
            stroke="#f7f7ef"
            strokeWidth="10"
          />
          <circle cx="188" cy="95" r="8" fill="#acb39f" />
          <path d="m190 59 67 9-6 25-70-10z" fill="#f8f8f1" />
          <path d="m183 84 68 9-39 99-105-13z" fill="#fffedb" opacity=".3" />
          <path d="m183 84 68 9" stroke="#dddcca" strokeWidth="3" />
        </g>
      ) : art === "monitor" ? (
        <g>
          <path d="M165 170h31v47h-31z" fill="#899c97" />
          <path d="m138 219 85 1-12 6h-93z" fill="#697e77" />
          <rect x="54" y="43" width="253" height="148" rx="8" fill="#37483f" />
          <rect x="62" y="51" width="237" height="130" rx="3" fill="#779d8e" />
          <path d="M62 153 148 76l38 52 36-31 77 64v20H62z" fill="#b9cbbb" />
          <path d="M62 155 125 117l75 64H62z" fill="#d9deca" />
          <circle cx="248" cy="79" r="14" fill="#e9dec3" />
          <text x="175" y="189" fontSize="7" fill="#c7d0c9">
            DELL
          </text>
        </g>
      ) : art === "bag" ? (
        <g transform="rotate(8 180 130)">
          <path
            d="M144 92V67a36 36 0 0 1 72 0v25"
            stroke="#b2a184"
            strokeWidth="12"
            fill="none"
          />
          <path
            d="m112 80 132 4 14 137-159-1z"
            fill="#f8efd9"
            stroke="#d4c4a7"
            strokeWidth="2"
          />
          <path d="m113 81-8 134m136-132 10 134" stroke="#e1d3b5" />
          <circle cx="179" cy="147" r="31" fill="none" stroke="#486e5b" />
          <path
            d="m150 157 57-14m-34 24 4-49 14 47m-38-15 51 3"
            fill="none"
            stroke="#486e5b"
          />
          <text x="150" y="196" fontSize="9" fill="#486e5b" letterSpacing="4">
            燕园记忆
          </text>
        </g>
      ) : art === "headphones" ? (
        <g transform="rotate(-12 180 130)">
          <path
            d="M113 155V111a65 65 0 0 1 130 0v44"
            fill="none"
            stroke="#494a50"
            strokeWidth="22"
          />
          <path
            d="M115 114a63 63 0 0 1 126 0"
            fill="none"
            stroke="#77757d"
            strokeWidth="5"
          />
          <rect x="97" y="133" width="41" height="76" rx="19" fill="#4e4d56" />
          <rect x="222" y="133" width="41" height="76" rx="19" fill="#4e4d56" />
          <path d="M127 145v50m105-50v50" stroke="#27282e" strokeWidth="8" />
        </g>
      ) : art === "shelf" ? (
        <g>
          <path
            d="M89 70h180v13H89zm0 77h180v13H89zm0 65h180v13H89z"
            fill="#bb9468"
          />
          <path d="M98 62v164m158-164v164" stroke="#806b4d" strokeWidth="8" />
          <path d="M113 102h80v43h-80z" fill="#e6d5ab" />
          <path d="M207 111h32v34h-32z" fill="#82977d" />
          <path
            d="M144 81V53m-5 9-15-9m20 11 11-17"
            fill="none"
            stroke="#7b956e"
            strokeWidth="7"
          />
        </g>
      ) : art === "racket" ? (
        <g transform="rotate(25 180 135)">
          <ellipse
            cx="170"
            cy="100"
            rx="43"
            ry="60"
            fill="none"
            stroke="#315c50"
            strokeWidth="5"
          />
          {[145, 155, 165, 175, 185, 195].map((x) => (
            <path key={x} d={`M${x} 51v98`} stroke="#8faaa0" />
          ))}
          {[65, 80, 95, 110, 125, 140].map((y) => (
            <path key={y} d={`M133 ${y}h75`} stroke="#8faaa0" />
          ))}
          <path
            d="m158 157 12 23 12-23m-12 23v52"
            fill="none"
            stroke="#41695e"
            strokeWidth="5"
          />
          <path d="M170 205v33" stroke="#243f38" strokeWidth="12" />
        </g>
      ) : (
        <g>
          <path d="m100 105 80-43 80 43v96l-80 35-80-35z" fill="#b1bd9d" />
          <path
            d="m100 105 80 38 80-38m-80 38v93"
            stroke="#728866"
            fill="none"
            strokeWidth="3"
          />
        </g>
      )}
    </svg>
  );
}

export function Card({
  item,
  onOpen,
  onFavorite,
  onCompare,
  selected,
}: {
  item: Item;
  onOpen: (i: Item) => void;
  onFavorite: (i: Item) => void;
  onCompare: (i: Item) => void;
  selected: boolean;
}) {
  return (
    <article className="item-card">
      <div className="card-visual">
        <button
          className="image-button"
          onClick={() => onOpen(item)}
          aria-label={`查看 ${item.title}`}
        >
          <ProductArt item={item} />
        </button>
        <span className="condition-chip">{item.condition_grade}</span>
        <button
          className={`favorite-button ${item.is_favorite ? "saved" : ""}`}
          onClick={() => onFavorite(item)}
          aria-label={
            item.is_favorite ? `取消收藏 ${item.title}` : `收藏 ${item.title}`
          }
        >
          <Heart size={17} fill={item.is_favorite ? "currentColor" : "none"} />
        </button>
        {item.status !== "ACTIVE" && (
          <span className="status-overlay">{statusText[item.status]}</span>
        )}
      </div>
      <div className="card-body">
        <button className="card-title" onClick={() => onOpen(item)}>
          {item.title}
        </button>
        <div className="card-tags">
          {item.tags.map((t) => (
            <span key={t}>{t}</span>
          ))}
          {item.is_demo && <span>演示商品</span>}
        </div>
        <div className="price-row">
          <span className="price">
            <small>¥</small>
            {money(item.price)}
          </span>
          <button
            className={`compare-add ${selected ? "selected" : ""}`}
            onClick={() => onCompare(item)}
            aria-label={`对比 ${item.title}`}
          >
            <Plus size={14} />
            {selected ? "已加入" : "对比"}
          </button>
        </div>
        <div className="card-foot">
          <span>
            <MapPin size={12} />
            {campusShort(item.campus)}
          </span>
          <span>{ago(item.created_at)}</span>
        </div>
      </div>
    </article>
  );
}

export function Modal({
  title,
  children,
  onClose,
  wide = false,
  style,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const old = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    function key(e: KeyboardEvent) {
      if (e.key === "Escape") close.current();
      if (e.key === "Tab") {
        const nodes = ref.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]",
        );
        if (!nodes?.length) return;
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (
          e.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === ref.current)
        ) {
          e.preventDefault();
          last.focus();
        } else if (
          !e.shiftKey &&
          (document.activeElement === last ||
            document.activeElement === ref.current)
        ) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", key);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", key);
      old?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={`modal ${wide ? "wide" : ""}`}
        style={style}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        ref={ref}
      >
        <div className="modal-head">
          <h2 id={titleId}>{title}</h2>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="关闭窗口"
          >
            <X />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Empty({
  title,
  text,
  action,
  onAction,
}: {
  title: string;
  text: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <PackageOpen size={34} strokeWidth={1.25} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action && (
        <button className="button primary" onClick={onAction}>
          {action}
          <ArrowRight size={16} />
        </button>
      )}
    </div>
  );
}

export function Intro({
  kicker,
  title,
  text,
  children,
}: {
  kicker: string;
  title: string;
  text: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-intro">
      <div>
        <span className="eyebrow">{kicker}</span>
        <h1>{title}</h1>
        <p>{text}</p>
      </div>
      {children}
    </div>
  );
}

export function Busy({ children }: { children?: ReactNode }) {
  return (
    <div className="loading" role="status">
      <SlidersHorizontal size={20} className="spin" />
      {children || "正在寻找校园好物…"}
    </div>
  );
}
