import { useEffect, useRef, useState } from "react";
import { ScanLine } from "lucide-react";
import { api } from "./api";

type Fields = { title: string; category: string; description: string; tags: string };
type Field = keyof Fields;
type Draft = {
  status: "ready" | "unclear" | "multiple_items";
  title: string | null;
  category: string | null;
  description: string | null;
  tags: string[];
  uncertainties: string[];
};
const fields: Field[] = ["title", "category", "description", "tags"];
const labels: Record<Field, string> = { title: "标题", category: "分类", description: "描述", tags: "标签" };

export function VisionPublisher({ images, categories, values, disabled, onApply }: {
  images: string[]; categories: string[]; values: Fields; disabled: boolean;
  onApply: (values: Partial<Fields>) => void;
}) {
  const [selected, setSelected] = useState<string[]>(images.slice(0, 1));
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Draft | null>(null);
  const [suggestions, setSuggestions] = useState<Fields>({ title: "", category: "", description: "", tags: "" });
  // Each selection approves replacement of one specific value, never a later edit.
  const [approved, setApproved] = useState<Partial<Fields>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const request = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const latestValues = useRef(values);
  latestValues.current = values;
  const imageKey = JSON.stringify(images);
  const latestImageKey = useRef(imageKey);
  latestImageKey.current = imageKey;

  function invalidate() {
    request.current++;
    controller.current?.abort();
    setLoading(false);
    setResult(null);
    setApproved({});
    setError("");
    setNotice("");
  }

  useEffect(() => {
    invalidate();
    setSelected((previous) => {
      const kept = previous.filter((url) => images.includes(url));
      return kept.length ? kept : images.slice(0, 1);
    });
    // The complete photo set invalidates results, including unselected photo changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageKey]);

  useEffect(() => () => { request.current++; controller.current?.abort(); }, []);

  useEffect(() => {
    setApproved((previous) => Object.fromEntries(Object.entries(previous)
      .filter(([field, value]) => values[field as Field] === value)));
  }, [values.title, values.category, values.description, values.tags]);

  async function generate() {
    if (disabled || loading || !selected.length) return;
    invalidate();
    const id = ++request.current;
    const photoSet = imageKey;
    const baseline = { ...values };
    const abort = new AbortController();
    controller.current = abort;
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; abort.abort(); }, 65000);
    setLoading(true);
    try {
      const draft = await api<Draft>("/items/vision-draft", "POST", { images: selected, note: note.trim() }, abort.signal);
      if (id !== request.current || photoSet !== latestImageKey.current) return;
      const next = { title: draft.title || "", category: draft.category || "",
        description: draft.description || "", tags: draft.tags.join("，") };
      setSuggestions(next);
      setResult(draft);
      setApproved(Object.fromEntries(fields.filter((field) => next[field]
        && !baseline[field].trim() && baseline[field] === latestValues.current[field])
        .map((field) => [field, baseline[field]])));
    } catch (e) {
      if (id !== request.current) return;
      setError(timedOut ? "识图超时，请重试或继续手动填写。" : (e as Error).message);
    } finally {
      window.clearTimeout(timeout);
      if (id === request.current) setLoading(false);
    }
  }

  const checked = (field: Field) => approved[field] !== undefined && approved[field] === values[field];
  function apply() {
    if (disabled || loading || result?.status !== "ready") return;
    const chosen = fields.filter(checked);
    if (!chosen.length) return;
    const next = Object.fromEntries(chosen.map((field) => [field, suggestions[field].trim()])) as Partial<Fields>;
    if ((next.title !== undefined && next.title.length < 2)
      || (next.description !== undefined && next.description.length < 5)
      || (next.category !== undefined && !categories.includes(next.category))) {
      setError("请补全所选建议：标题至少 2 字、描述至少 5 字，并选择有效分类。");
      return;
    }
    const tags = next.tags?.split(/[，,\s]+/).filter(Boolean);
    if (tags && (tags.length > 8 || tags.some((tag) => tag.length > 30))) {
      setError("标签最多 8 个，每个不超过 30 字。");
      return;
    }
    onApply(next);
    setApproved({});
    setError("");
    setNotice("所选建议已填入下方表单，请核对价格、成色和校区后发布。");
  }

  return <section className="vision-publisher" aria-label="识图发布助手">
    <div className="vision-heading">
      <div><strong>照片也能帮你写</strong><p>根据图片生成商品信息，确认后发布。</p></div>
      <button type="button" className="button secondary" disabled={disabled || loading || !selected.length}
        onClick={() => void generate()}><ScanLine size={17} />{loading ? "识别中…" : "识图发布"}</button>
    </div>
    {images.length > 0 ? <>
      <fieldset className="vision-photos" disabled={disabled}>
        <legend>选择同一件商品的 1–3 张照片 <small>已选 {selected.length}/3 张</small></legend>
        <div>{images.map((url, index) => <label key={url} className={selected.includes(url) ? "is-selected" : ""}>
          <img src={url} alt={`商品照片 ${index + 1}`} />
          <input type="checkbox" aria-label={`用照片 ${index + 1} 识图`} checked={selected.includes(url)}
            disabled={!selected.includes(url) && selected.length >= 3}
            onChange={(event) => {
              invalidate();
              setSelected(event.target.checked ? [...selected, url] : selected.filter((image) => image !== url));
            }} />
          <span>{index + 1}</span>
        </label>)}</div>
      </fieldset>
      <label className="vision-note">补充说明（选填）
        <textarea rows={2} maxLength={500} value={note} disabled={disabled}
          placeholder="例如：只卖鼠标，不包含背景中的键盘"
          onChange={(event) => { invalidate(); setNote(event.target.value); }} />
      </label>
      <p className="hint">点击后，所选照片及补充说明将发送至识图服务。建议选择整体照、文字标签和细节照。</p>
    </> : <p className="hint">先添加商品照片，即可使用识图发布。</p>}
    {loading && <p role="status" className="hint">正在生成建议，你可以继续填写下方信息…</p>}
    {result && <div className="vision-results">
      <strong>AI 建议，请核对后使用</strong>
      {result.status === "ready" ? <>
        <p className="hint">已有内容默认不替换；修改原表单后，对应选项会取消勾选。</p>
        {fields.map((field) => <div className="vision-suggestion" key={field}>
          <label className="vision-check">
            <input type="checkbox" checked={checked(field)} disabled={disabled}
              onChange={(event) => setApproved((previous) => {
                const next = { ...previous };
                if (event.target.checked) next[field] = values[field];
                else delete next[field];
                return next;
              })} />
            应用{labels[field]}{values[field].trim() && <small>将替换已有内容</small>}
          </label>
          {values[field].trim() && <p className="vision-existing">当前：{values[field]}</p>}
          {field === "category" ? <select aria-label="分类建议" value={suggestions.category} disabled={disabled}
            onChange={(event) => setSuggestions({ ...suggestions, category: event.target.value })}>
            <option value="">请选择分类</option>{categories.map((category) => <option key={category}>{category}</option>)}
          </select> : field === "description" ? <textarea aria-label="描述建议" rows={3} maxLength={3000}
            value={suggestions.description} disabled={disabled}
            onChange={(event) => setSuggestions({ ...suggestions, description: event.target.value })} />
            : <input aria-label={`${labels[field]}建议`} maxLength={field === "title" ? 120 : 247}
              value={suggestions[field]} disabled={disabled}
              placeholder={field === "tags" ? "用逗号分隔标签" : "未识别到，可手动补充"}
              onChange={(event) => setSuggestions({ ...suggestions, [field]: event.target.value })} />}
        </div>)}
        <button type="button" className="button secondary" disabled={disabled || !fields.some(checked)}
          onClick={apply}>应用所选建议</button>
      </> : <p>{result.status === "multiple_items" ? "照片可能包含不同商品，请重新选择或说明要卖哪一件。" : "这组照片暂时无法识别，请换一张清晰照片或手动填写。"}</p>}
      {result.uncertainties.length > 0 && <div className="vision-questions"><span>需要你确认</span>
        <ul>{result.uncertainties.map((text, index) => <li key={index}>{text}</li>)}</ul></div>}
    </div>}
    {notice && <p className="vision-notice" role="status">{notice}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </section>;
}
