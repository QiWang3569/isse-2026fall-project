import { useState } from "react";
import { api, type Meta, type User } from "./api";
import { AuthMethods } from "./AccountAndChat";
import { Modal } from "./components";

export function SessionRecovery({ user, meta, onRecovered, onClose }: {
  user: User; meta: Meta; onRecovered: (user: User) => void; onClose: () => void;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function recovered(account: User) {
    if (account.id === user.id) { onRecovered(account); return; }
    // Keep account-owned drafts and private uploads attached to their original owner.
    try { await api("/auth/logout", "POST"); } catch { /* Retry sign-in replaces the session. */ }
    setError(`请登录原账号 ${user.email || user.nickname}，以继续编辑当前内容。`);
  }
  return <Modal title="重新登录，继续刚才的操作" onClose={onClose}>
    <p className="auth-description">已保留当前页面填写的内容，请登录 {user.email || user.nickname}。登录后可继续提交。</p>
    <AuthMethods meta={meta} initialMode={user.has_password ? "password" : "code"} initialEmail={user.email || ""}
      onSignedIn={(account) => { void recovered(account); }} />
    {meta.demo_mode && user.id.startsWith("demo-") && <button className="button secondary" disabled={busy} onClick={async () => {
      setBusy(true);
      try {
        const result = await api<{ user: User }>("/auth/demo", "POST", { profile: user.id.slice(5) });
        await recovered(result.user);
      } catch (e) { setError((e as Error).message); }
      finally { setBusy(false); }
    }}>继续当前演示身份</button>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </Modal>;
}
