import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, Check, ImagePlus, Sparkles, Trash2, X } from "lucide-react";
import { api, type Meta, type Parsed, type ParsedItem, type ParsedWanted, type Item, type ItemDraft, type Wanted, type Intent } from "./api";
import { VisionPublisher } from "./VisionPublisher";
import { VisionBatchImporter } from "./VisionBatchImporter";

type Common = { meta: Meta; onDone: () => void };
const MAX_ITEM_IMAGES = 9;

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
  const [imageBusy, setImageBusy] = useState(false);
  const [publishIds, setPublishIds] = useState<string[]>([]);
  const [confirmBatch, setConfirmBatch] = useState(false);
  const publishing = useRef(false);
  const batchReceipt = useRef<{ body: string; id: string } | null>(null);
  const lines = source.split(/\r\n|\r|\n/).map((line) => line.trim()).filter(Boolean);

  useEffect(() => {
    let alive = true;
    api<ItemDraft[]>("/item-drafts/")
      .then((rows) => { if (alive) setDrafts(existing => [...existing, ...rows.filter(row => !existing.some(draft => draft.id === row.id))]); })
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
      setNotice(`已导入 ${imported.length} 件待发布商品。请逐件核对，可按需补充照片。`);
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
      setPublishIds((existing) => existing.filter((id) => id !== draft.id));
      setConfirmBatch(false);
      setNotice("待发布商品已删除");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const ready = (draft: ItemDraft) => Boolean(draft.title && draft.title.length >= 2
    && draft.description && draft.description.length >= 5 && draft.category && meta.categories.includes(draft.category)
    && draft.price != null && meta.campuses.includes(draft.campus) && meta.conditions.includes(draft.condition_grade));
  const selectedDrafts = drafts.filter(draft => publishIds.includes(draft.id));

  async function publishSelected() {
    if (busy || publishing.current || !confirmBatch || !selectedDrafts.length) return;
    const versions = selectedDrafts.map(draft => ({ id: draft.id, updated_at: draft.updated_at }));
    const body = JSON.stringify(versions);
    if (batchReceipt.current?.body !== body) batchReceipt.current = { body, id: crypto.randomUUID() };
    publishing.current = true; setBusy(true); setError("");
    try {
      const published = await api<Item[]>("/item-drafts/publish-batch", "POST", { request_id: batchReceipt.current.id, drafts: versions });
      setDrafts(existing => existing.filter(draft => !versions.some(version => version.id === draft.id)));
      setPublishIds([]); setConfirmBatch(false);
      setNotice(`已发布 ${published.length} 件商品，可在“我的售卖”中查看。`);
      onDraftPublished?.();
    } catch (e) { setError((e as Error).message); }
    finally { publishing.current = false; setBusy(false); }
  }

  return <>{activeDraft && <PublishForm key={activeDraft.id} meta={meta} draft={activeDraft} onDone={() => {
    setDrafts((existing) => existing.filter((item) => item.id !== activeDraft.id));
    setActiveDraft(null);
    setNotice("商品已发布，可以继续处理其他待发布商品");
    onDraftPublished?.();
  }}
    onBack={() => setActiveDraft(null)} onDraftSaved={(saved) => {
      setDrafts((existing) => existing.map((item) => item.id === saved.id ? saved : item));
      setActiveDraft(null);
      setNotice("草稿已保存，随时可以继续完善并发布");
    }} />}

  <div hidden={Boolean(activeDraft)}><div className="publish-workspace">
    <div className="publish-tabs" role="tablist" aria-label="发布方式">
      {([ ["single", "单件发布"], ["batch", "批量导入"], ["drafts", `待发布 ${drafts.length}`] ] as const).map(([key, label]) =>
        <button key={key} type="button" role="tab" aria-selected={tab === key}
          className={tab === key ? "active" : ""} disabled={busy || imageBusy}
          onClick={() => { setTab(key); setError(""); setConfirmBatch(false); }}>
          {label}
        </button>)}
    </div>
    <div hidden={tab !== "single"}><PublishForm meta={meta} onDone={onDone} /></div>
    <div hidden={tab !== "batch"}><div className="stack-form">
      {meta.vision_enabled && <VisionBatchImporter meta={meta} disabled={busy} onBusyChange={setImageBusy}
        onImported={imported => {
          setDrafts(existing => [...imported, ...existing.filter(draft => !imported.some(row => row.id === draft.id))]);
          setNotice(imported.length ? `已保存 ${imported.length} 件识图草稿。请确认价格、成色和校区，按需补充单件照片后发布。`
            : "这一批已经导入，请查看待发布列表或我的售卖。");
          setTab("drafts");
        }} />}
      <strong>按文字批量导入</strong>
      <div className="form-callout"><Sparkles size={22} /><p>一行写一件商品，可一次导入 1–10 件。系统会分别识别标题、价格等信息并保存为私人草稿，不会立即公开。</p></div>
      <label>每行一件待发布商品
        <textarea rows={8} maxLength={10000} value={source} onChange={(e) => setSource(e.target.value)}
          placeholder={"九成新罗技静音鼠标，50 元，万柳面交\n高数教材一本，20 元，燕园面交"} />
      </label>
      <p className="hint">已填写 {lines.length} 件。导入后请逐件检查识别结果，可以添加照片，再选择发布。最多保存 50 件待发布商品。</p>
      <button type="button" className="button primary full" disabled={busy || imageBusy || !lines.length} onClick={() => void importLines()}>
        {busy ? "正在逐件识别…" : "导入待发布商品"}
      </button>
    </div></div>
    {tab === "drafts" && <div className="draft-list">
      {drafts.length > 0 && <div className="batch-publish-bar">
        <span>已选 {selectedDrafts.length}/10 件 · 信息完整后可勾选</span>
        <button type="button" className="button secondary" disabled={busy || !selectedDrafts.length}
          onClick={() => setConfirmBatch(true)}>核对并批量发布</button>
      </div>}
      {confirmBatch && <section className="batch-publish-confirm" aria-label="批量发布核对">
        <strong>确认公开所选 {selectedDrafts.length} 件商品</strong>
        <p className="hint">请核对价格、成色和校区；没有单件照片的商品将以文字信息发布。</p>
        <ul>{selectedDrafts.map(draft => <li key={draft.id}>{draft.title} · ¥{draft.price} · {draft.campus} · {draft.condition_grade}
          {draft.images.length ? ` · ${draft.images.length} 张照片` : " · 暂无照片"}</li>)}</ul>
        <div className="batch-review-actions">
          <button type="button" className="button secondary" disabled={busy} onClick={() => setConfirmBatch(false)}>返回调整</button>
          <button type="button" className="button primary" disabled={busy || !selectedDrafts.length}
            onClick={() => void publishSelected()}>{busy ? "正在发布…" : `确认发布 ${selectedDrafts.length} 件`}</button>
        </div>
      </section>}
      {loading ? <p className="muted">正在加载待发布商品…</p> : drafts.length === 0 ?
        <div className="draft-empty"><p>还没有待发布商品</p><button type="button" className="button secondary" onClick={() => setTab("batch")}>写一段话批量导入</button></div> :
        drafts.map((draft) => <article className="draft-card" key={draft.id}>
          <div className="draft-card-main">
            <label className="batch-draft-check"><input type="checkbox" aria-label={`选择发布 ${draft.title || "待补充标题"}`}
              checked={publishIds.includes(draft.id)} disabled={busy || !ready(draft) || (!publishIds.includes(draft.id) && publishIds.length >= 10)}
              onChange={event => {
                setPublishIds(existing => event.target.checked ? [...existing, draft.id] : existing.filter(id => id !== draft.id));
                setConfirmBatch(false);
              }} />{ready(draft) ? "加入批量发布" : "请先完善信息"}</label>
            <span className="draft-status">待发布</span>
            <h3>{draft.title || "待补充标题"}</h3>
            <p>{draft.raw}</p>
            <small>{draft.price == null ? "待补充价格" : `¥${draft.price}`} · {draft.images.length ? `已上传 ${draft.images.length} 张照片` : "暂未添加照片（可选）"}</small>
            {draft.clarification && <small>请核对：{draft.clarification}</small>}
          </div>
          <div className="draft-card-actions">
            <button type="button" className="button secondary" disabled={busy} onClick={() => {
              setPublishIds(existing => existing.filter(id => id !== draft.id)); setConfirmBatch(false); setActiveDraft(draft);
            }}>完善并发布</button>
            <button type="button" className="icon-button" aria-label={`删除 ${draft.title || "待发布商品"}`} disabled={busy} onClick={() => void removeDraft(draft)}><Trash2 size={17} /></button>
          </div>
        </article>)}
    </div>}
    {notice && <p className="draft-notice" role="status">{notice}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </div></div></>;
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
  const uploadLock = useRef(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadProgress, setUploadProgress] = useState("");
  const [images, setImages] = useState<string[]>(editingItem?.images || draft?.images || []);
  const [error, setError] = useState("");
  const [raw, setRaw] = useState(draft?.raw || "");
  const [parsing, setParsing] = useState(false);
  const [title, setTitle] = useState(editingItem?.title || draft?.title || prefill?.title || "");
  const [description, setDescription] = useState(editingItem?.description || draft?.description || "");
  const [category, setCategory] = useState(editingItem?.category || draft?.category || prefill?.category || "");
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
    if (!files?.length || uploadLock.current || busy) return;
    const remaining = MAX_ITEM_IMAGES - images.length;
    if (files.length > remaining) {
      setUploadError(`还可添加 ${remaining} 张，本次选择了 ${files.length} 张，请重新选择。`);
      return;
    }
    uploadLock.current = true;
    setUploading(true);
    setUploadError("");
    const failures: string[] = [];
    try {
      const selected = Array.from(files);
      for (const [index, file] of selected.entries()) {
        setUploadProgress(`正在上传 ${index + 1}/${selected.length}：${file.name}`);
        try {
          if (file.size > 6 * 1024 * 1024) throw new Error("每张图片不得超过 6 MB");
          if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error("仅支持 JPG / PNG / WebP");
          const body = new FormData();
          body.append("file", file);
          const result = await api<{ url: string }>("/uploads", "POST", body);
          setImages((prev) => [...prev, result.url]);
        } catch (e) {
          failures.push(`${file.name}：${(e as Error).message}`);
          setUploadError(failures.join("；"));
        }
      }
    } finally {
      uploadLock.current = false;
      setUploading(false);
      setUploadProgress("");
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
    <form className="stack-form publish-form" onSubmit={submit}>
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
          商品照片 <small>选填，最多 9 张 · JPG / PNG / WebP · 每张不超过 6 MB</small>
        </span>
        <div className="upload-row">
          {images.map((url) => (
            <div className="upload-preview" key={url}>
              <img src={url} alt="已上传的商品照片" />
              <button
                type="button"
                aria-label="移除这张照片"
                disabled={uploading || busy}
                onClick={() => { setImages(images.filter((i) => i !== url)); setUploadError(""); }}
              >
                <X size={14} />
              </button>
            </div>
          ))}
            <label className={`upload-button ${images.length >= MAX_ITEM_IMAGES ? "upload-full" : ""}`}>
              <ImagePlus size={25} />
              <span>{uploading ? "上传中…" : images.length >= MAX_ITEM_IMAGES ? "已满 9 张" : "添加照片"}</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                aria-label="添加商品照片"
                disabled={uploading || busy || images.length >= MAX_ITEM_IMAGES}
                onChange={(e) => {
                  void upload(e.target.files);
                  e.target.value = "";
                }}
              />
            </label>
        </div>
        <p className="hint" aria-live="polite">已上传 {images.length}/9 张，还可添加 {MAX_ITEM_IMAGES - images.length} 张{uploadProgress && ` · ${uploadProgress}`}</p>
        {uploadError && <p className="form-error" role="alert">{uploadError}</p>}
      </div>
      {meta.vision_enabled && <VisionPublisher images={images} categories={meta.categories}
        values={{ title, description, category, tags }} disabled={busy || uploading || parsing}
        onApply={(values) => {
          if (values.title !== undefined) setTitle(values.title);
          if (values.description !== undefined) setDescription(values.description);
          if (values.category !== undefined) setCategory(values.category);
          if (values.tags !== undefined) setTags(values.tags);
        }} />}
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
            <option value="" disabled>请选择商品分类</option>
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
  const [parsing, setParsing] = useState(false);
  const [raw, setRaw] = useState("");
  const [title, setTitle] = useState(editingWanted?.title || initialIntent?.raw_query.split("\n")[0].slice(0, 120) || initial || "");
  const [description, setDescription] = useState(editingWanted?.description ?? initialIntent?.raw_query ?? "");
  const [category, setCategory] = useState(editingWanted?.category || initialIntent?.category || "");
  const [budget, setBudget] = useState(editingWanted?.budget != null ? String(editingWanted.budget) : initialIntent?.max_price != null ? String(initialIntent.max_price) : "");
  const [campus, setCampus] = useState(editingWanted?.campus || initialIntent?.campus || "不限校区");

  async function smartFill() {
    if (raw.trim().length < 2) {
      setError("请先输入一段求购描述");
      return;
    }
    setParsing(true);
    setError("");
    try {
      const result = await api<{ parsed: ParsedWanted }>("/wanted/parse", "POST", {
        raw: raw.trim(),
      });
      const p = result.parsed;
      if (p.title) setTitle(p.title);
      if (p.description) setDescription(p.description);
      if (p.category) setCategory(p.category);
      if (p.budget != null) setBudget(String(p.budget));
      if (p.campus) setCampus(p.campus);
      if (p.clarification) setError(p.clarification);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setParsing(false);
    }
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        title: title.trim(),
        description: description.trim(),
        category: category || null,
        budget: budget === "" ? null : Number(budget),
        campus,
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
      <div className="form-callout">
        <Sparkles size={22} />
        <p>
          一句话说出你想收的东西，点“智能识别并填充”，信息会自动填好，确认后即可发布。
        </p>
      </div>
      <label>
        一句话描述求购
        <textarea
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          maxLength={2500}
          rows={2}
          placeholder="例如：求一台九成新 iPad，预算 2000 元，燕园面交"
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
      <label>
        你想求购什么？
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          minLength={2}
          maxLength={120}
          placeholder="求一本离散数学教材"
        />
      </label>
      <label>
        具体要求
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={2500}
          rows={3}
          placeholder="型号、版本、能接受的成色、交接时间…"
        />
      </label>
      <div className="form-grid">
        <label>
          物品分类
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">不限分类</option>
            {meta.categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          最高预算（元）
          <input
            type="number"
            min="0"
            max="999999"
            step="0.01"
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            placeholder="不限预算"
          />
        </label>
        <label>
          交接校区
          <select value={campus} onChange={(e) => setCampus(e.target.value)}>
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
      <button className="button primary full" disabled={busy || parsing}>
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
