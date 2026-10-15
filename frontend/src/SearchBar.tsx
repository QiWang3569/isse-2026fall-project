import type { FormEvent } from "react";
import { Search, Sparkles, X } from "lucide-react";

type SearchBarProps = {
  mobile?: boolean;
  target: "market" | "wanted";
  value: string;
  showClear: boolean;
  smartMode: boolean;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  onClear: () => void;
  onToggleSmart: () => void;
};

export function SearchBar({ mobile = false, target, value, showClear, smartMode,
  onChange, onSubmit, onClear, onToggleSmart }: SearchBarProps) {
  const wanted = target === "wanted";
  const label = wanted ? "搜索求购" : "搜索校园好物";
  return (
    <form className={mobile ? "mobile-search" : "global-search"}
      role="search" aria-label={label} onSubmit={onSubmit}>
      <Search size={18} aria-hidden="true" />
      <input aria-label={label} maxLength={120} value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={wanted ? "搜索求购标题或描述…" : smartMode
          ? "说人话就能搜：如“2000左右能记笔记的平板”"
          : "搜搜你需要的校园好物…"} />
      {showClear && <button type="button" className="text-button" aria-label="清空搜索" onClick={onClear}>
        <X size={16} />
      </button>}
      {!mobile && <button type="submit" className="search-submit" aria-label="搜索"><kbd>Enter</kbd></button>}
      {!wanted && <button type="button" className={`smart-toggle ${smartMode ? "active" : ""}`}
        aria-pressed={smartMode} title={smartMode ? "关闭智能搜索" : "开启智能搜索"} onClick={onToggleSmart}>
        <Sparkles size={16} /><span>智能</span>
      </button>}
      {mobile && <button type="submit" className="text-button">搜索</button>}
    </form>
  );
}
