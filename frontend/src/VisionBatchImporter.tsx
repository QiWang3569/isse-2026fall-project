import { useEffect, useRef, useState } from "react";
import { ImagePlus, ScanLine, Trash2, X } from "lucide-react";
import { api, type ItemDraft, type Meta } from "./api";

type Suggestion = { title: string | null; category: string | null; description: string | null;
  tags: string[]; photo_indices: number[]; uncertainties: string[] };
type Result = { status: "ready" | "unclear"; items: Suggestion[]; uncertainties: string[] };
type Review = { id: string; selected: boolean; title: string; category: string; description: string;
  tags: string; price: string; campus: string; condition: string; photos: number[]; questions: string[] };

export function VisionBatchImporter({ meta, disabled, onBusyChange, onImported }: {
  meta: Meta; disabled: boolean; onBusyChange: (busy: boolean) => void; onImported: (drafts: ItemDraft[]) => void;
}) {
  const [images, setImages] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [rows, setRows] = useState<Review[]>([]);
  const [questions, setQuestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const abort = useRef<AbortController | null>(null);
  const revision = useRef(0);
  const uploadLock = useRef(false);
  const saveLock = useRef(false);
  const alive = useRef(true);
  const receipt = useRef<{ body: string; id: string } | null>(null);
  useEffect(() => { onBusyChange(uploading || loading || saving); }, [uploading, loading, saving, onBusyChange]);
  useEffect(() => { alive.current = true; return () => {
    alive.current = false; revision.current++; abort.current?.abort(); onBusyChange(false);
  }; }, [onBusyChange]);

  function invalidate() {
    revision.current++;
    abort.current?.abort();
    setLoading(false); setRows([]); setQuestions([]); setError(""); setNotice("");
  }

  async function upload(files: FileList | null) {
    if (!files?.length || uploadLock.current || saving || disabled) return;
    if (files.length + images.length > 3) { setError("每次最多上传 3 张合照，请减少本次选择的照片。"); return; }
    invalidate();
    uploadLock.current = true; setUploading(true);
    const failures: string[] = [];
    try {
      for (const file of Array.from(files)) {
        if (!alive.current) break;
        try {
          if (file.size > 6 * 1024 * 1024) throw new Error("每张图片不得超过 6 MB");
          if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error("仅支持 JPG / PNG / WebP");
          const body = new FormData(); body.append("file", file);
          const result = await api<{ url: string }>("/uploads", "POST", body);
          if (alive.current) setImages(previous => [...previous, result.url]);
        } catch (e) { failures.push(`${file.name}：${(e as Error).message}`); }
      }
    } finally {
      uploadLock.current = false;
      if (alive.current) { setUploading(false); setError(failures.join("；")); }
    }
  }

  async function generate() {
    if (disabled || loading || uploading || saving || !images.length) return;
    if (rows.length && !window.confirm("重新识别会替换当前未保存的卡片，继续吗？")) return;
    invalidate();
    const id = ++revision.current;
    const controller = new AbortController(); abort.current = controller;
    let timedOut = false;
    const timer = window.setTimeout(() => { timedOut = true; controller.abort(); }, 65000);
    setLoading(true);
    try {
      const result = await api<Result>("/items/vision-batch", "POST", { images, note: note.trim() }, controller.signal);
      if (id !== revision.current) return;
      setQuestions(result.uncertainties);
      setRows(result.items.map(item => ({ id: crypto.randomUUID(), selected: true,
        title: item.title || "", category: item.category || "", description: item.description || "",
        tags: item.tags.join("，"), price: "", campus: meta.campuses[0], condition: "95新",
        photos: [...new Set(item.photo_indices)], questions: item.uncertainties })));
      setNotice(result.status === "unclear" ? "未能识别出商品，请换一张清晰合照或使用下方文字导入。"
        : `识别出 ${result.items.length} 件候选商品，请核对、删除或合并后保存。`);
    } catch (e) {
      if (id === revision.current) setError(timedOut ? "识图超时，请重试；照片已保留。" : (e as Error).message);
    } finally {
      window.clearTimeout(timer);
      if (id === revision.current) setLoading(false);
    }
  }

  const selected = rows.filter(row => row.selected);
  function edit(id: string, fields: Partial<Review>) {
    setRows(previous => previous.map(row => row.id === id ? { ...row, ...fields } : row));
    setError("");
  }
  function merge() {
    if (selected.length < 2) return;
    const first = selected[0];
    const combined: Review = { ...first, id: crypto.randomUUID(), selected: true,
      title: selected.map(row => row.title || "待确认商品").join("、").slice(0, 120),
      description: selected.map(row => row.description).filter(Boolean).join("\n").slice(0, 3000),
      category: selected.every(row => row.category === first.category) ? first.category : "",
      tags: [...new Set(selected.flatMap(row => row.tags.split(/[，,\s]+/).filter(Boolean)))].slice(0, 8).join("，"),
      price: "", photos: [...new Set(selected.flatMap(row => row.photos))],
      questions: [...new Set(["请确认整套的总价、成色和实际包含的物品。", ...selected.flatMap(row => row.questions)])].slice(0, 8) };
    setRows(previous => [combined, ...previous.filter(row => !row.selected)]);
    setNotice(`已将 ${selected.length} 件合成一张卡片，请修改套装名称并填写总价。`);
  }

  async function save() {
    if (disabled || saving || saveLock.current || !selected.length) return;
    const items = selected.map(row => ({ raw: `${row.title || "待确认商品"}\n${row.description || "请核对照片中的商品信息"}`.slice(0, 3000),
      title: row.title.trim() || null, description: row.description.trim() || null, category: row.category || null,
      tags: row.tags.split(/[，,\s]+/).filter(Boolean), price: row.price === "" ? null : Number(row.price),
      campus: row.campus, condition_grade: row.condition, images: [],
      clarification: ["来自合照识别，请核对商品信息并按需补充单件照片。", ...row.questions].join("\n").slice(0, 2000) }));
    const body = JSON.stringify(items);
    if (receipt.current?.body !== body) receipt.current = { body, id: crypto.randomUUID() };
    saveLock.current = true; setSaving(true); setError("");
    try {
      const imported = await api<ItemDraft[]>("/item-drafts/import-vision", "POST", { request_id: receipt.current.id, items });
      if (!alive.current) return;
      setRows(previous => previous.filter(row => !row.selected));
      if (selected.length === rows.length) { setImages([]); setNote(""); setQuestions([]); }
      setNotice("");
      onImported(imported);
    } catch (e) { if (alive.current) setError((e as Error).message); }
    finally { saveLock.current = false; if (alive.current) setSaving(false); }
  }

  function changeInput(change: () => void) {
    if (rows.length && !window.confirm("修改照片或说明会清除当前未保存的识别卡片，继续吗？")) return;
    invalidate(); change();
  }

  return <section className="vision-publisher batch-vision" aria-label="批量识图导入">
    <strong>用合照批量导入</strong>
    <p className="hint">把几本书或几件闲置一起拍下来，每次最多 3 张照片、10 件商品。书名和封面尽量拍清楚。</p>
    <div className="upload-row">
      {images.map((url, index) => <div className="upload-preview" key={url}>
        <img src={url} alt={`批量识图合照 ${index + 1}`} />
        <button type="button" aria-label={`移除合照 ${index + 1}`} disabled={disabled || uploading || saving}
          onClick={() => changeInput(() => setImages(images.filter(image => image !== url)))}><X size={14} /></button>
      </div>)}
      <label className="upload-button"><ImagePlus size={24} /><span>{uploading ? "上传中…" : "添加合照"}</span>
        <input type="file" aria-label="添加批量识图合照" accept="image/jpeg,image/png,image/webp" multiple
          disabled={disabled || uploading || saving || images.length >= 3}
          onChange={event => {
            const files = event.target.files;
            if (!rows.length || window.confirm("添加照片会清除当前未保存的识别卡片，继续吗？")) void upload(files);
            event.target.value = "";
          }} />
      </label>
    </div>
    <label>批量识图补充说明（选填）
      <textarea rows={2} maxLength={500} value={note} disabled={disabled || uploading || saving}
        placeholder="例如：每本书分别出售；第二张是第一张合照的细节"
        onChange={event => changeInput(() => setNote(event.target.value))} />
    </label>
    <p className="hint">点击后，照片及说明将发送至识图服务。合照仅供识别核对，不会自动裁切或用作每件商品的封面。</p>
    <button type="button" className="button secondary" disabled={disabled || loading || uploading || saving || !images.length}
      onClick={() => void generate()}><ScanLine size={17} />{loading ? "正在逐件识别…" : "批量识图"}</button>
    {notice && <p role="status" className="vision-notice">{notice}</p>}
    {questions.length > 0 && <ul className="vision-questions">{questions.map((question, index) => <li key={index}>{question}</li>)}</ul>}
    {rows.length > 0 && <>
      <p className="hint">AI 建议，请逐件核对。价格、成色和校区由你填写或确认；保存后可补充单件照片。当前卡片尚未保存。</p>
      <div className="batch-review-actions"><span>已选 {selected.length}/{rows.length} 件</span>
        <button type="button" className="text-button" disabled={disabled || saving || selected.length < 2} onClick={merge}>将所选合为一件</button>
      </div>
      {rows.map((row, index) => <article className="batch-review-card" key={row.id} aria-label={`识图候选 ${index + 1}`}>
        <div className="batch-review-actions"><label className="vision-check">
          <input type="checkbox" checked={row.selected} disabled={disabled || saving}
            onChange={event => edit(row.id, { selected: event.target.checked })} />选择第 {index + 1} 件</label>
          <button type="button" className="icon-button" aria-label={`删除候选 ${index + 1}`} disabled={disabled || saving}
            onClick={() => { setRows(previous => previous.filter(item => item.id !== row.id)); setNotice("已移除候选，可继续核对其余卡片。"); }}><Trash2 size={16} /></button>
        </div>
        <small>识别来源：照片 {row.photos.join("、")} · 请对照上方合照核对</small>
        <label>候选标题 {index + 1}<input value={row.title} maxLength={120} disabled={disabled || saving}
          placeholder="未看清书名，请手动补充" onChange={event => edit(row.id, { title: event.target.value })} /></label>
        <label>候选描述 {index + 1}<textarea value={row.description} rows={2} maxLength={3000} disabled={disabled || saving}
          onChange={event => edit(row.id, { description: event.target.value })} /></label>
        <div className="form-grid">
          <label>候选分类 {index + 1}<select value={row.category} disabled={disabled || saving}
            onChange={event => edit(row.id, { category: event.target.value })}>
            <option value="">待确认分类</option>{meta.categories.map(category => <option key={category}>{category}</option>)}</select></label>
          <label>价格 {index + 1}（元，选填）<input type="number" min="0" max="999999" step="0.01" value={row.price}
            disabled={disabled || saving} onChange={event => edit(row.id, { price: event.target.value })} /></label>
          <label>校区 {index + 1}<select value={row.campus} disabled={disabled || saving}
            onChange={event => edit(row.id, { campus: event.target.value })}>{meta.campuses.map(campus => <option key={campus}>{campus}</option>)}</select></label>
          <label>成色 {index + 1}<select value={row.condition} disabled={disabled || saving}
            onChange={event => edit(row.id, { condition: event.target.value })}>{meta.conditions.map(condition => <option key={condition}>{condition}</option>)}</select></label>
        </div>
        <label>候选标签 {index + 1}<input value={row.tags} maxLength={247} disabled={disabled || saving}
          onChange={event => edit(row.id, { tags: event.target.value })} /></label>
        {row.questions.length > 0 && <ul className="vision-questions">{row.questions.map((question, i) => <li key={i}>{question}</li>)}</ul>}
      </article>)}
      <button type="button" className="button primary full" disabled={disabled || saving || !selected.length}
        onClick={() => void save()}>{saving ? "正在保存…" : `保存所选 ${selected.length} 件到待发布`}</button>
    </>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </section>;
}
