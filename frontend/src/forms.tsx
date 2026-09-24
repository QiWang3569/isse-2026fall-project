import { useState, type FormEvent } from "react";
import { ArrowRight, Check, ImagePlus, Sparkles, X } from "lucide-react";
import { api, type Meta, type Parsed, type Item, type Wanted } from "./api";

type Common = { meta: Meta; onDone: () => void };

export function IntentForm({
  meta,
  initial,
  onDone,
}: Common & { initial: string }) {
  const [query, setQuery] = useState(initial);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [keywords, setKeywords] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (!parsed) {
        const result = await api<{ parsed: Parsed }>("/intents/parse", "POST", {
          raw_query: query,
        });
        setParsed(result.parsed);
        setKeywords(result.parsed.keywords.join("，"));
      } else {
        await api("/intents/", "POST", {
          raw_query: query,
          parsed: {
            ...parsed,
            keywords: keywords.split(/[，,\s]+/).filter(Boolean),
          },
        });
        onDone();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="stack-form" onSubmit={submit}>
      <div className="form-callout">
        <Sparkles size={22} />
        <p>
          告诉燕渡你需要什么。确认条件后，新上架的合适商品会自动来到你的通知里。
        </p>
      </div>
      <label>
        我想找…
        <textarea
          required
          minLength={2}
          maxLength={500}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setParsed(null);
          }}
          placeholder="例如：蹲一个万柳附近、300 元以内的静音鼠标"
          rows={3}
        />
      </label>
      {parsed && (
        <div className="parsed-box">
          <h3>
            <Check size={17} />
            确认一下，我们理解对了吗？
          </h3>
          {parsed.clarification && (
            <p className="hint">{parsed.clarification}</p>
          )}
          <div className="form-grid">
            <label>
              物品分类
              <select
                value={parsed.category || ""}
                onChange={(e) =>
                  setParsed({ ...parsed, category: e.target.value || null })
                }
              >
                <option value="">不限分类</option>
                {meta.categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              最高预算（元）
              <input
                aria-label="最高预算（元）"
                type="number"
                min="0"
                max="999999"
                step="0.01"
                value={parsed.max_price ?? ""}
                onChange={(e) =>
                  setParsed({
                    ...parsed,
                    max_price:
                      e.target.value === "" ? null : Number(e.target.value),
                  })
                }
                placeholder="不限预算"
              />
            </label>
            <label>
              期望校区
              <select
                value={parsed.campus}
                onChange={(e) =>
                  setParsed({ ...parsed, campus: e.target.value })
                }
              >
                {meta.campuses.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              最低成色
              <select
                value={parsed.condition_grade || ""}
                onChange={(e) =>
                  setParsed({
                    ...parsed,
                    condition_grade: e.target.value || null,
                  })
                }
              >
                <option value="">不限成色</option>
                {meta.conditions.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            物品与偏好关键词
            <input
              required
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="用逗号分隔，例如：鼠标，静音"
            />
          </label>
        </div>
      )}
      <p className="hint">
        每人最多 5 个活跃任务，默认持续 14 天，可随时暂停或结束。
        {meta.ai_mode === "local" &&
          "当前演示使用关键词规则解析，请确认筛选条件。"}
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary full" disabled={busy}>
        {busy ? "正在处理…" : parsed ? "确认条件，开始代蹲" : "理解我的需求"}
        {!busy && <ArrowRight size={17} />}
      </button>
    </form>
  );
}

export function PublishForm({
  meta,
  onDone,
  prefill,
}: Common & { prefill?: Wanted | null }) {
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [images, setImages] = useState<string[]>([]);
  const [error, setError] = useState("");
  async function upload(files: FileList | null) {
    if (!files?.length) return;
    if (images.length + files.length > 3) {
      setError("最多上传 3 张照片");
      return;
    }
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
        const body = new FormData();
        body.append("file", file);
        const result = await api<{ url: string }>("/uploads", "POST", body);
        setImages((prev) => [...prev, result.url]);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!images.length) {
      setError("请至少上传一张商品照片");
      return;
    }
    setBusy(true);
    setError("");
    const data = new FormData(e.currentTarget);
    try {
      await api<Item>("/items/", "POST", {
        title: data.get("title"),
        description: data.get("description"),
        category: data.get("category"),
        price: Number(data.get("price")),
        campus: data.get("campus"),
        condition_grade: data.get("condition"),
        tags: String(data.get("tags"))
          .split(/[，,\s]+/)
          .filter(Boolean),
        images,
      });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="stack-form" onSubmit={submit}>
      {prefill && (
        <div className="form-callout">
          <p>
            你正在回应“{prefill.title}
            ”。请填写你实际持有的商品信息，发布后买家可在校园市场中查看。
          </p>
        </div>
      )}
      <div>
        <span className="field-title">
          商品照片 <small>1–3 张 · JPG / PNG / WebP · 每张不超过 6 MB</small>
        </span>
        <div className="upload-row">
          {images.map((url) => (
            <div className="upload-preview" key={url}>
              <img src={url} alt="已上传的商品照片" />
              <button
                type="button"
                aria-label="移除这张照片"
                onClick={() => setImages(images.filter((i) => i !== url))}
              >
                <X size={14} />
              </button>
            </div>
          ))}
          {images.length < 3 && (
            <label className="upload-button">
              <ImagePlus size={25} />
              <span>{uploading ? "上传中…" : "添加照片"}</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                disabled={uploading || busy}
                onChange={(e) => {
                  void upload(e.target.files);
                  e.target.value = "";
                }}
              />
            </label>
          )}
        </div>
      </div>
      <label>
        给好物起个名字
        <input
          name="title"
          required
          minLength={2}
          maxLength={120}
          placeholder="例如：罗技 MX Master 3S 静音鼠标"
        />
      </label>
      <label>
        描述一下它
        <textarea
          name="description"
          required
          minLength={5}
          maxLength={3000}
          rows={3}
          placeholder="使用情况、配件、瑕疵、方便的交接时间…真实描述会让交易更顺利。"
        />
      </label>
      <div className="form-grid">
        <label>
          物品分类
          <select
            name="category"
            defaultValue={prefill?.category || meta.categories[0]}
          >
            {meta.categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          转让价格（元）
          <input
            name="price"
            required
            type="number"
            min="0"
            max="999999"
            step="0.01"
            placeholder="0.00"
          />
        </label>
        <label>
          所在校区
          <select
            name="campus"
            defaultValue={prefill?.campus || meta.campuses[0]}
          >
            {meta.campuses.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          商品成色
          <select name="condition" defaultValue="95新">
            {meta.conditions.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      <label>
        标签 <small>选填，最多 8 个</small>
        <input name="tags" placeholder="例如：鼠标，静音，无线" />
      </label>
      <p className="hint">
        商品默认在售 14 天。成交后记得标记“已售出”，让彼此少一点等待。
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary full" disabled={busy || uploading}>
        {busy ? "正在发布…" : "发布好物"}
        <ArrowRight size={17} />
      </button>
    </form>
  );
}

export function WantedForm({
  meta,
  onDone,
  initial,
}: Common & { initial: string }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(e.currentTarget);
    try {
      await api("/wanted/", "POST", {
        title: data.get("title"),
        description: data.get("description"),
        category: data.get("category"),
        budget: Number(data.get("budget")),
        campus: data.get("campus"),
      });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="stack-form" onSubmit={submit}>
      <p className="muted">
        把需要的物品告诉同学们，也许它正好在某个人的抽屉里。
      </p>
      <label>
        你想求购什么？
        <input
          name="title"
          required
          minLength={2}
          maxLength={120}
          defaultValue={initial}
          placeholder="求一本离散数学教材"
        />
      </label>
      <label>
        具体要求
        <textarea
          name="description"
          required
          minLength={5}
          maxLength={1000}
          rows={3}
          placeholder="型号、版本、能接受的成色、交接时间…"
        />
      </label>
      <div className="form-grid">
        <label>
          物品分类
          <select name="category">
            {meta.categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          最高预算（元）
          <input
            name="budget"
            type="number"
            required
            min="0"
            max="999999"
            step="0.01"
          />
        </label>
        <label>
          交接校区
          <select name="campus">
            {meta.campuses.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="hint">求购将展示 7 天，找到后可以提前结束。</p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary full" disabled={busy}>
        {busy ? "发布中…" : "发布求购"}
        <ArrowRight size={17} />
      </button>
    </form>
  );
}
