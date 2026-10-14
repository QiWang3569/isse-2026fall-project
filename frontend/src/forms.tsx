import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, Check, ImagePlus, Sparkles, Trash2, X } from "lucide-react";
import { api, type Meta, type Parsed, type ParsedItem, type Item, type ItemDraft, type Wanted, type Intent } from "./api";

type Common = { meta: Meta; onDone: () => void };

export function IntentForm({
  meta,
  initial,
  editingIntent,
  onDone,
}: Common & { initial: string; editingIntent?: Intent | null }) {
  const [query, setQuery] = useState(editingIntent?.raw_query || initial);
  const [parsed, setParsed] = useState<Parsed | null>(editingIntent ? {
    category: editingIntent.category, max_price: editingIntent.max_price, campus: editingIntent.campus,
    keywords: editingIntent.keywords, excluded_keywords: editingIntent.excluded_keywords,
    preferences: editingIntent.preferences, condition_grade: editingIntent.condition_grade, clarification: null,
  } : null);
  const [keywords, setKeywords] = useState(editingIntent?.keywords.join("，") || "");
  const [excluded, setExcluded] = useState(editingIntent?.excluded_keywords.join("，") || "");
  const [preferences, setPreferences] = useState(editingIntent?.preferences.join("，") || "");
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
        setExcluded(result.parsed.excluded_keywords.join("，"));
        setPreferences(result.parsed.preferences.join("，"));
      } else {
        await api(editingIntent ? `/intents/${editingIntent.id}/details` : "/intents/", editingIntent ? "PATCH" : "POST", {
          raw_query: query,
          parsed: {
            ...parsed,
            keywords: keywords.split(/[，,\s]+/).filter(Boolean),
            excluded_keywords: excluded.split(/[，,\s]+/).filter(Boolean),
            preferences: preferences.split(/[，,\s]+/).filter(Boolean),
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
          maxLength={2500}
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
            <p className="hint">
              助手想确认：{parsed.clarification}{" "}
              可修改上面的需求重新理解，或直接调整下方条件。
            </p>
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
            必须满足的物品与特征
            <input
              required
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="用逗号分隔，例如：鼠标，无线"
            />
          </label>
          <label>
            不接受的特征
            <input
              value={excluded}
              onChange={(e) => setExcluded(e.target.value)}
              placeholder="例如：游戏鼠标，缺少接收器"
            />
          </label>
          <label>
            最好具备的偏好（可选）
            <input
              value={preferences}
              onChange={(e) => setPreferences(e.target.value)}
              placeholder="例如：静音，黑色；不满足也可推荐"
            />
          </label>
        </div>
      )}
      <p className="hint">
        持续替你留意，直到你暂停或结束。{editingIntent?.wanted_id && "修改条件会同步更新求购看板。"}
        {meta.ai_mode === "local" &&
          "当前演示使用关键词规则解析，请确认筛选条件。"}
        {meta.ai_mode === "remote" &&
          "确认后，助手会在后台核对商品描述；信息不足的商品会标为待确认。"}
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary full" disabled={busy}>
        {busy ? "正在处理…" : parsed ? editingIntent ? "保存需求与条件" : "确认条件，开始代蹲" : "理解我的需求"}
        {!busy && <ArrowRight size={17} />}
      </button>
    </form>
  );
}

export function PublishWorkspace({ meta, onDone, onDraftPublished }: Common & { onDraftPublished?: () => void }) {
  const [tab, setTab] = useState<"single" | "batch" | "drafts">("single");
  const [source, setSource] = useState("");
  const [drafts, setDrafts] = useState<ItemDraft[]>([]);
  const [activeDraft, setActiveDraft] = useState<ItemDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const lines = source.split(/\r\n|\r|\n/).map((line) => line.trim()).filter(Boolean);

  useEffect(() => {
    let alive = true;
    api<ItemDraft[]>("/item-drafts/")
      .then((rows) => { if (alive) setDrafts(rows); })
      .catch((e) => { if (alive) setError((e as Error).message); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  async function importLines() {
    if (!lines.length || lines.length > 10) {
      setError("每次可导入 1–10 件商品，每行一件");
      return;
    }
    if (lines.some((line) => line.length < 5 || line.length > 3000)) {
      setError("每件商品的描述需要 5–3000 字");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const imported = await api<ItemDraft[]>("/item-drafts/import", "POST", { text: source });
      setDrafts((existing) => [...imported, ...existing]);
      setSource("");
      setNotice(`已导入 ${imported.length} 件待发布商品。请逐件核对并上传照片。`);
      setTab("drafts");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function removeDraft(draft: ItemDraft) {
    if (!window.confirm(`删除待发布商品「${draft.title || draft.raw.slice(0, 20)}」？`)) return;
    setBusy(true);
    setError("");
    try {
      await api(`/item-drafts/${draft.id}`, "DELETE");
      setDrafts((existing) => existing.filter((item) => item.id !== draft.id));
      setNotice("待发布商品已删除");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (activeDraft) return <PublishForm key={activeDraft.id} meta={meta} draft={activeDraft} onDone={() => {
    setDrafts((existing) => existing.filter((item) => item.id !== activeDraft.id));
    setActiveDraft(null);
    setNotice("商品已发布，可以继续处理其他待发布商品");
    onDraftPublished?.();
  }}
    onBack={() => setActiveDraft(null)} onDraftSaved={(saved) => {
      setDrafts((existing) => existing.map((item) => item.id === saved.id ? saved : item));
      setActiveDraft(null);
      setNotice("草稿已保存，随时可以继续完善并发布");
    }} />;

  return <div className="publish-workspace">
    <div className="publish-tabs" role="tablist" aria-label="发布方式">
      {([ ["single", "单件发布"], ["batch", "批量导入"], ["drafts", `待发布 ${drafts.length}`] ] as const).map(([key, label]) =>
        <button key={key} type="button" role="tab" aria-selected={tab === key}
          className={tab === key ? "active" : ""} onClick={() => { setTab(key); setError(""); }}>
          {label}
        </button>)}
    </div>
    <div hidden={tab !== "single"}><PublishForm meta={meta} onDone={onDone} /></div>
    {tab === "batch" && <div className="stack-form">
      <div className="form-callout"><Sparkles size={22} /><p>一行写一件商品，可一次导入 1–10 件。系统会分别识别标题、价格等信息并保存为私人草稿，不会立即公开。</p></div>
      <label>每行一件待发布商品
        <textarea rows={8} maxLength={10000} value={source} onChange={(e) => setSource(e.target.value)}
          placeholder={"九成新罗技静音鼠标，50 元，万柳面交\n高数教材一本，20 元，燕园面交"} />
      </label>
      <p className="hint">已填写 {lines.length} 件。导入后请逐件检查识别结果，可以添加照片，再选择发布。最多保存 50 件待发布商品。</p>
      <button type="button" className="button primary full" disabled={busy || !lines.length} onClick={() => void importLines()}>
        {busy ? "正在逐件识别…" : "导入待发布商品"}
      </button>
    </div>}
    {tab === "drafts" && <div className="draft-list">
      {loading ? <p className="muted">正在加载待发布商品…</p> : drafts.length === 0 ?
        <div className="draft-empty"><p>还没有待发布商品</p><button type="button" className="button secondary" onClick={() => setTab("batch")}>写一段话批量导入</button></div> :
        drafts.map((draft) => <article className="draft-card" key={draft.id}>
          <div className="draft-card-main">
            <span className="draft-status">待发布</span>
            <h3>{draft.title || "待补充标题"}</h3>
            <p>{draft.raw}</p>
            <small>{draft.price == null ? "待补充价格" : `¥${draft.price}`} · {draft.images.length ? `已上传 ${draft.images.length} 张照片` : "暂未添加照片（可选）"}</small>
            {draft.clarification && <small>请核对：{draft.clarification}</small>}
          </div>
          <div className="draft-card-actions">
            <button type="button" className="button secondary" onClick={() => setActiveDraft(draft)}>完善并发布</button>
            <button type="button" className="icon-button" aria-label={`删除 ${draft.title || "待发布商品"}`} disabled={busy} onClick={() => void removeDraft(draft)}><Trash2 size={17} /></button>
          </div>
        </article>)}
    </div>}
    {notice && <p className="draft-notice" role="status">{notice}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </div>;
}

export function PublishForm({
  meta,
  onDone,
  prefill,
  editingItem,
  draft,
  onDraftSaved,
  onBack,
}: Common & { prefill?: Wanted | null; editingItem?: Item | null; draft?: ItemDraft | null; onDraftSaved?: (draft: ItemDraft) => void; onBack?: () => void }) {
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [images, setImages] = useState<string[]>(editingItem?.images || draft?.images || []);
  const [error, setError] = useState("");
  const [raw, setRaw] = useState(draft?.raw || "");
  const [parsing, setParsing] = useState(false);
  const [title, setTitle] = useState(editingItem?.title || draft?.title || prefill?.title || "");
  const [description, setDescription] = useState(editingItem?.description || draft?.description || "");
  const [category, setCategory] = useState(editingItem?.category || (draft ? draft.category || "" : prefill?.category || meta.categories[0]));
  const [price, setPrice] = useState(editingItem ? String(editingItem.price) : draft?.price != null ? String(draft.price) : "");
  const [campus, setCampus] = useState(editingItem?.campus || draft?.campus || prefill?.campus || meta.campuses[0]);
  const [condition, setCondition] = useState(editingItem?.condition_grade || draft?.condition_grade || "95新");
  const [tags, setTags] = useState((editingItem?.tags || draft?.tags || []).join("，"));

  const payload = () => ({
    title: title.trim(), description: description.trim(), category,
    price: price === "" ? null : Number(price), campus,
    condition_grade: condition, tags: tags.split(/[，,\s]+/).filter(Boolean), images,
  });

  async function saveDraft() {
    if (!draft) return;
    setBusy(true);
    setError("");
    try {
      const values = payload();
      const saved = await api<ItemDraft>(`/item-drafts/${draft.id}`, "PATCH", {
        ...values, raw: raw.trim() || draft.raw,
        title: values.title || null, description: values.description || null,
        category: values.category || null,
      });
      onDraftSaved?.(saved);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function smartFill() {
    if (raw.trim().length < 5) {
      setError("请先输入一段商品描述");
      return;
    }
    setParsing(true);
    setError("");
    try {
      const result = await api<{ parsed: ParsedItem }>("/items/parse", "POST", {
        raw: raw.trim(),
      });
      const p = result.parsed;
      if (p.title) setTitle(p.title);
      if (p.description) setDescription(p.description);
      if (p.category) setCategory(p.category);
      if (p.price != null) setPrice(String(p.price));
      if (p.campus) setCampus(p.campus);
      if (p.condition_grade) setCondition(p.condition_grade);
      if (p.tags.length) setTags(p.tags.join("，"));
      if (p.clarification) setError(p.clarification);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setParsing(false);
    }
  }
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
    setBusy(true);
    setError("");
    try {
      const values = payload();
      if (editingItem) {
        await api<Item>(`/items/${editingItem.id}`, "PATCH", values);
      } else if (draft) {
        await api<Item>(`/item-drafts/${draft.id}/publish`, "POST", values);
      } else {
        await api<Item>("/items/", "POST", values);
      }
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="stack-form" onSubmit={submit}>
      {draft && onBack && <button type="button" className="text-button" onClick={onBack}>
        <ArrowLeft size={15} /> 返回待发布列表
      </button>}
      {prefill && (
        <div className="form-callout">
          <p>
            你正在回应“{prefill.title}
            ”。请填写你实际持有的商品信息，发布后买家可在校园市场中查看。
          </p>
        </div>
      )}
      <div className="form-callout">
        <Sparkles size={22} />
        <p>
          {draft ? "这件商品还未公开。请核对识别结果，再保存草稿或发布，照片可稍后补充。" : "懒人模式：把要卖的东西用一句话说出来，点“智能识别并填充”，信息会自动填好，确认信息后即可发布，照片选填。"}
        </p>
      </div>
      <label>
        一句话描述要卖的好物
        <textarea
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          maxLength={3000}
          rows={3}
          placeholder="例如：出一台九成新的罗技静音鼠标，50 元，燕园面交"
        />
      </label>
      <button
        type="button"
        className="button secondary"
        disabled={parsing || busy}
        onClick={() => void smartFill()}
      >
        <Sparkles size={16} />
        {parsing ? "识别中…" : "智能识别并填充"}
      </button>
      <div>
        <span className="field-title">
          商品照片 <small>选填，最多 3 张 · JPG / PNG / WebP · 每张不超过 6 MB</small>
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
          required
          minLength={2}
          maxLength={120}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="例如：罗技 MX Master 3S 静音鼠标"
        />
      </label>
      <label>
        描述一下它
        <textarea
          required
          minLength={5}
          maxLength={3000}
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="使用情况、配件、瑕疵、方便的交接时间…真实描述会让交易更顺利。"
        />
      </label>
      <div className="form-grid">
        <label>
          物品分类
          <select
            required
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {draft && <option value="" disabled>请选择商品分类</option>}
            {meta.categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          转让价格（元）
          <input
            required
            type="number"
            min="0"
            max="999999"
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder="0.00"
          />
        </label>
        <label>
          所在校区
          <select
            value={campus}
            onChange={(e) => setCampus(e.target.value)}
          >
            {meta.campuses.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          商品成色
          <select
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
          >
            {meta.conditions.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      <label>
        标签 <small>选填，最多 8 个</small>
        <input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="例如：鼠标，静音，无线"
        />
      </label>
      <p className="hint">
        商品持续展示，成交后记得标记“已售出”。照片可以稍后补充。
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="publish-actions">
        {draft && <button type="button" className="button secondary" disabled={busy || uploading} onClick={() => void saveDraft()}>
          保存草稿
        </button>}
        <button className="button primary" disabled={busy || uploading}>
          {busy ? "正在处理…" : editingItem ? "保存修改" : "发布好物"}
          {!busy && <ArrowRight size={17} />}
        </button>
      </div>
    </form>
  );
}

export function WantedForm({
  meta,
  onDone,
  initial,
  editingWanted,
  initialIntent,
}: Common & { initial: string; editingWanted?: Wanted | null; initialIntent?: Intent | null }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = new FormData(e.currentTarget);
      const payload = {
        title: data.get("title"),
        description: data.get("description"),
        category: data.get("category") || null,
        budget: data.get("budget") === "" ? null : Number(data.get("budget")),
        campus: data.get("campus"),
        ...(!editingWanted && initialIntent ? { intent_id: initialIntent.id } : {}),
      };
      if (editingWanted) {
        await api(`/wanted/${editingWanted.id}`, "PATCH", payload);
      } else {
        await api("/wanted/", "POST", payload);
      }
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
        发布到求购看板的同时，燕渡会自动替你代蹲。已有代蹲会沿用原来的匹配记录。
      </p>
      <label>
        你想求购什么？
        <input
          name="title"
          required
          minLength={2}
          maxLength={120}
          defaultValue={editingWanted?.title || initialIntent?.raw_query.split("\n")[0].slice(0, 120) || initial}
          placeholder="求一本离散数学教材"
        />
      </label>
      <label>
        具体要求
        <textarea
          name="description"
          maxLength={2500}
          rows={3}
          defaultValue={editingWanted?.description ?? initialIntent?.raw_query}
          placeholder="型号、版本、能接受的成色、交接时间…"
        />
      </label>
      <div className="form-grid">
        <label>
          物品分类
          <select name="category" defaultValue={editingWanted?.category || initialIntent?.category || ""}>
            <option value="">不限分类</option>
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
            min="0"
            max="999999"
            step="0.01"
            defaultValue={editingWanted?.budget ?? initialIntent?.max_price ?? ""}
            placeholder="不限预算"
          />
        </label>
        <label>
          交接校区
          <select name="campus" defaultValue={editingWanted?.campus || initialIntent?.campus || "不限校区"}>
            {meta.campuses.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="hint">求购持续展示；编辑条件、暂停或找到商品后，求购与代蹲会一起更新。</p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button primary full" disabled={busy}>
        {busy
          ? editingWanted
            ? "保存中…"
            : "发布中…"
          : editingWanted
            ? "保存修改"
            : "发布求购"}
        <ArrowRight size={17} />
      </button>
    </form>
  );
}
