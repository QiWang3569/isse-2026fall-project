export type User = {
  id: string;
  nickname: string;
  campus: string;
  role: string;
  email?: string | null;
};
export type Item = {
  id: string;
  title: string;
  description: string;
  category: string;
  price: number;
  campus: string;
  condition_grade: string;
  tags: string[];
  images: string[];
  art: string;
  status: string;
  seller: User;
  created_at: string;
  expires_at: string;
  is_favorite: boolean;
  is_owner: boolean;
  is_demo: boolean;
};
export type Meta = {
  categories: string[];
  campuses: string[];
  conditions: string[];
  demo_mode: boolean;
  ai_mode: string;
  embedding_mode: string;
  active_items: number;
  email_auth_ready: boolean;
};
export type ChatMessage = {
  id: string;
  conversation_id: string;
  sender_id: string;
  body: string;
  created_at: string;
  read_at: string | null;
};
export type Conversation = {
  id: string;
  item_id: string;
  item_title: string;
  item_status: string;
  item_image: string | null;
  counterpart: User;
  last_message: ChatMessage | null;
  unread_count: number;
  updated_at: string;
};
export type Parsed = {
  category: string | null;
  max_price: number | null;
  campus: string;
  keywords: string[];
  excluded_keywords: string[];
  preferences: string[];
  condition_grade: string | null;
  clarification: string | null;
};
export type Intent = Parsed & {
  id: string;
  raw_query: string;
  status: string;
  match_count: number;
  created_at: string;
  expires_at: string;
  matching_mode: string;
  matching_state: "PENDING" | "RUNNING" | "DONE" | "FAILED";
};
export type Notice = {
  id: string;
  intent_id: string;
  item: Item;
  score: number;
  reason: string;
  verdict: "MATCH" | "UNCERTAIN";
  questions: string[];
  evidence: { criterion: string; quote: string }[];
  review_mode: string;
  score_kind: string;
  is_read: boolean;
  available: boolean;
  created_at: string;
};
export type Wanted = {
  id: string;
  title: string;
  description: string;
  category: string;
  budget: number;
  campus: string;
  buyer: User;
  is_owner: boolean;
  created_at: string;
  expires_at: string;
};
export type Report = {
  id: string;
  item: Item;
  reason: string;
  risk: string;
  evidence: string[];
  status: string;
  created_at: string;
};
export type Log = {
  id: string;
  action: string;
  actor: User;
  target_id: string;
  detail: string;
  created_at: string;
};

export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    method,
    credentials: "include",
    ...(data instanceof FormData
      ? { body: data }
      : data !== undefined
        ? {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
          }
        : {}),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = result?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((d: { msg: string }) => d.msg.replace("Value error, ", ""))
              .join("；")
          : "服务连接失败，请稍后重试",
    );
  }
  return result as T;
}
export const money = (n: number) =>
  n.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
export const campusShort = (v: string) =>
  v.replace("校本部", "").replace("学区", "").replace("新校区", "");
export const statusText: Record<string, string> = {
  ACTIVE: "在售",
  RESERVED: "已预订",
  SOLD: "已售出",
  EXPIRED: "已过期",
  BANNED: "审核隐藏",
  PAUSED: "已暂停",
  COMPLETED: "已结束",
};
export function ago(date: string) {
  const hours = Math.max(0, (Date.now() - new Date(date).getTime()) / 3600000);
  return hours < 1
    ? "刚刚发布"
    : hours < 24
      ? `${Math.floor(hours)} 小时前`
      : `${Math.floor(hours / 24)} 天前`;
}
