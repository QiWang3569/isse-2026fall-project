import { useEffect, useRef, useState, type PointerEvent } from "react";
import { ChevronLeft, ChevronRight, Minus, Plus, RotateCcw } from "lucide-react";
import { type Item } from "./api";
import { Modal, ProductArt } from "./components";

export function ProductGallery({ item }: { item: Item }) {
  const [opened, setOpened] = useState<number | null>(null);
  return <>
    {item.images.length ? <button type="button" className="product-photo-open" aria-label={`放大${item.title}的第 1 张图片`} onClick={() => setOpened(0)}>
      <ProductArt item={item} /><span>点击查看大图</span>
    </button> : <ProductArt item={item} />}
    {item.images.length > 1 && <div className="detail-photos">{item.images.slice(1).map((url, index) =>
      <button type="button" key={url} className="product-photo-open" aria-label={`放大第 ${index + 2} 张图片`} onClick={() => setOpened(index + 1)}>
        <img src={url} alt={`${item.title}的补充照片 ${index + 2}`} loading="lazy" />
      </button>)}</div>}
    {opened !== null && <ImageViewer images={item.images} title={item.title} initialIndex={opened} onClose={() => setOpened(null)} />}
  </>;
}

function ImageViewer({ images, title, initialIndex, onClose }: {
  images: string[]; title: string; initialIndex: number; onClose: () => void;
}) {
  const [index, setIndex] = useState(initialIndex);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const stage = useRef<HTMLDivElement>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef({ x: 0, y: 0, distance: 0, scale: 1, offset: { x: 0, y: 0 }, pinched: false });
  const reset = () => { setScale(1); setOffset({ x: 0, y: 0 }); };
  const change = (next: number) => {
    setIndex((next + images.length) % images.length); reset(); setFailed(false); setLoaded(false);
    pointers.current.clear();
  };
  const zoom = (next: number) => {
    const bounded = Math.max(1, Math.min(4, next)); setScale(bounded);
    setOffset((value) => boundOffset(value, bounded));
  };
  function boundOffset(value: { x: number; y: number }, zoomLevel: number) {
    const width = stage.current?.clientWidth ?? 0, height = stage.current?.clientHeight ?? 0;
    return { x: Math.max(-width * (zoomLevel - 1) / 2, Math.min(width * (zoomLevel - 1) / 2, value.x)),
      y: Math.max(-height * (zoomLevel - 1) / 2, Math.min(height * (zoomLevel - 1) / 2, value.y)) };
  }
  useEffect(() => {
    function key(event: KeyboardEvent) {
      const dialogs = document.querySelectorAll('[aria-modal="true"]');
      if (stage.current?.closest('[aria-modal="true"]') !== dialogs[dialogs.length - 1]) return;
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        if (images.length > 1) change(index + (event.key === "ArrowRight" ? 1 : -1));
      }
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [index, images.length]);

  function begin(event: PointerEvent<HTMLDivElement>) {
    if (failed || !loaded || (event.pointerType === "mouse" && event.button !== 0)) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const points = [...pointers.current.values()];
    if (points.length === 1) gesture.current = { x: event.clientX, y: event.clientY, distance: 0, scale,
      offset, pinched: false };
    if (points.length === 2) gesture.current = { ...gesture.current, scale, offset, pinched: true,
      distance: Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y) };
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    if (!pointers.current.has(event.pointerId)) return;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const points = [...pointers.current.values()], start = gesture.current;
    if (points.length === 2 && start.distance > 0) {
      zoom(start.scale * Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y) / start.distance);
    } else if (points.length === 1 && !start.pinched && scale > 1) {
      setOffset(boundOffset({ x: start.offset.x + event.clientX - start.x, y: start.offset.y + event.clientY - start.y }, scale));
    }
  }
  function end(event: PointerEvent<HTMLDivElement>) {
    if (!pointers.current.has(event.pointerId)) return;
    const start = gesture.current, dx = event.clientX - start.x, dy = event.clientY - start.y;
    pointers.current.delete(event.pointerId);
    if (event.type !== "pointercancel" && !start.pinched && scale === 1 && images.length > 1 && Math.abs(dx) > 55 && Math.abs(dy) < 70) change(index + (dx < 0 ? 1 : -1));
    if (pointers.current.size === 1) {
      const remaining = [...pointers.current.values()][0];
      gesture.current = { ...start, ...remaining, offset, scale, pinched: true };
    }
  }

  return <Modal title={`${title} · 商品图片`} onClose={onClose} style={{ width: 1100 }}>
    <div className="image-viewer-controls">
      <button type="button" className="icon-button" aria-label="上一张图片" disabled={images.length < 2} onClick={() => change(index - 1)}><ChevronLeft /></button>
      <span aria-live="polite">{index + 1} / {images.length}</span>
      <button type="button" className="icon-button" aria-label="下一张图片" disabled={images.length < 2} onClick={() => change(index + 1)}><ChevronRight /></button>
      <button type="button" className="icon-button" aria-label="缩小图片" disabled={scale <= 1 || failed} onClick={() => zoom(scale - 0.5)}><Minus /></button>
      <span aria-live="polite">{Math.round(scale * 100)}%</span>
      <button type="button" className="icon-button" aria-label="放大图片" disabled={scale >= 4 || failed} onClick={() => zoom(scale + 0.5)}><Plus /></button>
      <button type="button" className="icon-button" aria-label="重置图片大小" onClick={reset}><RotateCcw /></button>
    </div>
    <div className={`image-viewer-stage ${scale > 1 ? "zoomed" : ""}`} ref={stage}
      onPointerDown={begin} onPointerMove={move} onPointerUp={end} onPointerCancel={end}
      onDoubleClick={() => { if (loaded && !failed) zoom(scale === 1 ? 2 : 1); }}>
      {failed ? <div role="alert">图片加载失败 <button type="button" onClick={() => { setFailed(false); setLoaded(false); setAttempt((n) => n + 1); }}>重新加载</button></div>
        : <img key={`${index}:${attempt}`} src={images[index]} alt={`${title}，第 ${index + 1} 张图片`} draggable={false}
          onLoad={() => setLoaded(true)} onError={() => setFailed(true)}
          style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})` }} />}
      {!loaded && !failed && <span className="image-loading" role="status">正在加载图片…</span>}
    </div>
    <p className="hint">左右切换图片；双击或使用按钮缩放，放大后拖动查看。手机支持滑动切图和双指缩放。</p>
    <div className="image-viewer-thumbnails">{images.map((url, position) => <button type="button" key={url}
      aria-label={`查看第 ${position + 1} 张图片`} aria-pressed={position === index} onClick={() => { if (position !== index) change(position); }}>
      <img src={url} alt={`缩略图 ${position + 1}`} loading="lazy" />
    </button>)}</div>
  </Modal>;
}
