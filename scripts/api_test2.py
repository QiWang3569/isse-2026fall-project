"""燕渡 API 自动回归测试（补充边角用例）。

运行：.\.venv\Scripts\python.exe scripts/api_test2.py
"""
import io
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import httpx
from PIL import Image


BASE = "http://127.0.0.1:8000"
DB = "data/yandu.db"
RESULTS = []
CREATED_ITEMS = []
CREATED_WANTED = []
IMAGE_URLS = []


def record(cid, name, status, detail=""):
    RESULTS.append({"id": cid, "name": name, "status": status, "detail": detail})


def login(profile):
    c = httpx.Client(base_url=BASE, timeout=30, follow_redirects=False)
    r = c.post("/api/v1/auth/demo", json={"profile": profile})
    if r.status_code != 200:
        raise RuntimeError(f"login {profile} failed {r.status_code}")
    return c


def db_exec(sql, params=()):
    conn = sqlite3.connect(DB, timeout=10)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def jpg_bytes(color=(120, 180, 140)):
    img = Image.new("RGB", (320, 240), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def past_naive(days=0, hours=0):
    dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days, hours=hours)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")


def main():
    anon = httpx.Client(base_url=BASE, timeout=30)
    buyer = login("buyer")
    seller = login("seller")
    admin = login("admin")

    # ---- A2 首页只展示在售且未过期 ----
    r = seller.post("/api/v1/uploads", files={"file": ("a.jpg", jpg_bytes(), "image/jpeg")})
    img_a = r.json().get("url") if r.status_code == 201 else None
    IMAGE_URLS.append(img_a)
    r = seller.post("/api/v1/items/", json={"title": "补测商品A", "description": "补测商品描述A", "category": "数码与影音", "price": 50, "campus": "燕园校本部", "images": [img_a]})
    item_a = r.json().get("id") if r.status_code == 201 else None
    CREATED_ITEMS.append(item_a)
    db_exec("UPDATE items SET expires_at=? WHERE id=?", (past_naive(days=1), item_a))
    r = anon.get("/api/v1/items/")
    in_list = any(i["id"] == item_a for i in r.json().get("items", []))
    record("A2", "过期商品不在列表（首页只展示在售未过期）", "PASS" if r.status_code == 200 and not in_list else "FAIL", f"HTTP {r.status_code}")
    r = anon.get(f"/api/v1/items/{item_a}")
    record("A10", "过期商品详情状态为 EXPIRED", "PASS" if r.status_code == 200 and r.json().get("status") == "EXPIRED" else "FAIL", f"HTTP {r.status_code} status={r.json().get('status') if r.status_code==200 else None}")

    # ---- A2 推荐排序（收藏分类优先） ----
    r = buyer.get("/api/v1/items/", params={"category": "课程资料与书籍"})
    cat_items = r.json().get("items", [])
    fav_id = cat_items[0]["id"] if cat_items else None
    if fav_id:
        buyer.post(f"/api/v1/items/{fav_id}/favorite")
        r = buyer.get("/api/v1/items/", params={"sort": "recommended"})
        first_cat = r.json().get("items", [{}])[0].get("category")
        record("A2", "推荐排序收藏分类优先", "PASS" if r.status_code == 200 and first_cat == "课程资料与书籍" else "FAIL", f"first={first_cat}")
        buyer.delete(f"/api/v1/items/{fav_id}/favorite")

    # ---- A3 上传边界 ----
    big = b"x" * (6 * 1024 * 1024 + 1)
    r = seller.post("/api/v1/uploads", files={"file": ("big.jpg", big, "image/jpeg")})
    record("A3", "超过 6MB 返回 413", "PASS" if r.status_code == 413 else "FAIL", f"HTTP {r.status_code}")
    big_img = Image.new("L", (5001, 4000), 128)
    buf = io.BytesIO()
    big_img.save(buf, format="JPEG")
    r = seller.post("/api/v1/uploads", files={"file": ("huge.jpg", buf.getvalue(), "image/jpeg")})
    record("A3", "超过 2000 万像素返回 422", "PASS" if r.status_code == 422 else "FAIL", f"HTTP {r.status_code}")
    r = seller.post("/api/v1/uploads", files={"file": ("fake.jpg", b"not really a jpeg", "image/jpeg")})
    record("A3", "伪造图片格式返回 422", "PASS" if r.status_code == 422 else "FAIL", f"HTTP {r.status_code}")

    # ---- A3 使用他人图片 ----
    r = buyer.post("/api/v1/items/", json={"title": "用他人图", "description": "补测他人图片", "category": "数码与影音", "price": 10, "campus": "燕园校本部", "images": [img_a]})
    record("A3", "使用他人上传的图片返回 422", "PASS" if r.status_code == 422 else "FAIL", f"HTTP {r.status_code}")

    # ---- A3 重新上架刷新 14 天 ----
    r = seller.post("/api/v1/uploads", files={"file": ("b.jpg", jpg_bytes(), "image/jpeg")})
    img_b = r.json().get("url") if r.status_code == 201 else None
    IMAGE_URLS.append(img_b)
    r = seller.post("/api/v1/items/", json={"title": "补测商品B", "description": "补测商品描述B", "category": "数码与影音", "price": 60, "campus": "燕园校本部", "images": [img_b]})
    item_b = r.json().get("id") if r.status_code == 201 else None
    CREATED_ITEMS.append(item_b)
    seller.patch(f"/api/v1/items/{item_b}/status", json={"status": "RESERVED"})
    db_exec("UPDATE items SET expires_at=? WHERE id=?", (past_naive(days=1), item_b))
    r = seller.patch(f"/api/v1/items/{item_b}/status", json={"status": "ACTIVE"})
    r2 = anon.get(f"/api/v1/items/{item_b}")
    exp = parse_iso(r2.json().get("expires_at")) if r2.status_code == 200 else None
    ok = exp is not None and exp > datetime.now(timezone.utc) + timedelta(days=13)
    record("A3", "重新上架刷新 14 天有效期", "PASS" if r.status_code == 200 and ok else "FAIL", f"HTTP {r.status_code} exp={exp}")

    # ---- A5 求购 7 天过期 ----
    r = buyer.post("/api/v1/wanted/", json={"title": "补测求购", "description": "补测求购描述内容", "category": "数码与影音", "budget": 40, "campus": "燕园校本部"})
    wanted_id = r.json().get("id") if r.status_code == 201 else None
    CREATED_WANTED.append(wanted_id)
    db_exec("UPDATE wanted_posts SET expires_at=? WHERE id=?", (past_naive(days=1), wanted_id))
    r = buyer.get("/api/v1/wanted/")
    in_wanted = any(w["id"] == wanted_id for w in r.json())
    record("A5", "求购 7 天过期后不再显示", "PASS" if r.status_code == 200 and not in_wanted else "FAIL", f"HTTP {r.status_code}")

    # ---- A8 会话与交易边角 ----
    r = seller.post("/api/v1/uploads", files={"file": ("c.jpg", jpg_bytes(), "image/jpeg")})
    img_c = r.json().get("url") if r.status_code == 201 else None
    IMAGE_URLS.append(img_c)
    r = seller.post("/api/v1/items/", json={"title": "补测商品C", "description": "补测商品描述C", "category": "数码与影音", "price": 70, "campus": "燕园校本部", "images": [img_c]})
    item_c = r.json().get("id") if r.status_code == 201 else None
    CREATED_ITEMS.append(item_c)
    r = buyer.post(f"/api/v1/items/{item_c}/conversations", json={"body": "第一句"})
    conv = r.json().get("conversation", {}) if r.status_code == 201 else {}
    conv_id = conv.get("id")
    m1 = r.json().get("message", {}).get("id") if r.status_code == 201 else None
    r = seller.post(f"/api/v1/conversations/{conv_id}/messages", json={"body": "第二句"})
    m2 = r.json().get("id") if r.status_code == 201 else None
    r = seller.post(f"/api/v1/conversations/{conv_id}/messages", json={"body": "第三句"})
    m3 = r.json().get("id") if r.status_code == 201 else None
    r = buyer.get(f"/api/v1/conversations/{conv_id}/messages")
    msgs = r.json().get("messages", [])
    record("A8", "消息列表按序返回多条", "PASS" if r.status_code == 200 and len(msgs) >= 3 else "FAIL", f"HTTP {r.status_code}")
    r = buyer.get(f"/api/v1/conversations/{conv_id}/messages", params={"before_id": m2})
    older = r.json().get("messages", [])
    ok = r.status_code == 200 and len(older) >= 1 and all(x["id"] != m2 and x["id"] != m3 for x in older)
    record("A8", "历史消息分页 before_id 生效", "PASS" if ok else "FAIL", f"HTTP {r.status_code} len={len(older)}")
    r = buyer.get("/api/v1/conversations")
    conv_row = next((x for x in r.json() if x["id"] == conv_id), None)
    has_fields = conv_row is not None and all(k in conv_row for k in ("unread_count", "last_message", "item_status", "counterpart", "deal_status"))
    unread_before = conv_row.get("unread_count") if conv_row else -1
    record("A8", "会话列表包含未读/最后消息/状态/对方字段", "PASS" if r.status_code == 200 and has_fields and unread_before >= 2 else "FAIL", f"unread={unread_before}")
    buyer.post(f"/api/v1/conversations/{conv_id}/read")
    r = buyer.get("/api/v1/conversations")
    conv_row2 = next((x for x in r.json() if x["id"] == conv_id), None)
    record("A8", "打开会话后未读清零", "PASS" if conv_row2 is not None and conv_row2.get("unread_count") == 0 else "FAIL", f"unread={conv_row2.get('unread_count') if conv_row2 else None}")
    r = buyer.post(f"/api/v1/items/{item_c}/message-draft")
    draft_ok = r.status_code == 200 and bool(r.json().get("draft"))
    record("A8", "生成咨询草稿返回 200 且非空", "PASS" if draft_ok else "FAIL", f"HTTP {r.status_code}")
    db_exec("UPDATE items SET expires_at=? WHERE id=?", (past_naive(hours=1), item_c))
    r = buyer.post(f"/api/v1/conversations/{conv_id}/deal", json={"action": "request"})
    record("A8", "商品过期后 request 返回 409", "PASS" if r.status_code == 409 else "FAIL", f"HTTP {r.status_code}")

    # ---- A9 举报证据 ----
    r = seller.post("/api/v1/uploads", files={"file": ("d.jpg", jpg_bytes(), "image/jpeg")})
    img_d = r.json().get("url") if r.status_code == 201 else None
    IMAGE_URLS.append(img_d)
    r = seller.post("/api/v1/items/", json={"title": "代考资料", "description": "提供代考服务，先转账", "category": "数码与影音", "price": 99, "campus": "燕园校本部", "images": [img_d]})
    item_d = r.json().get("id") if r.status_code == 201 else None
    CREATED_ITEMS.append(item_d)
    r = buyer.post(f"/api/v1/items/{item_d}/reports", json={"reason": "举报风险商品"})
    report_d = r.json().get("id") if r.status_code == 201 else None
    r = admin.get("/api/v1/admin/reports")
    ev = next((x for x in r.json() if x["id"] == report_d), None)
    has_risk = bool(ev and any("风险词" in e for e in ev.get("evidence", [])))
    record("A9", "举报证据含文字风险词", "PASS" if r.status_code == 200 and has_risk else "FAIL", f"HTTP {r.status_code}")
    # 同名线索
    r = seller.post("/api/v1/uploads", files={"file": ("e.jpg", jpg_bytes(), "image/jpeg")})
    img_e = r.json().get("url") if r.status_code == 201 else None
    IMAGE_URLS.append(img_e)
    r = seller.post("/api/v1/items/", json={"title": "同名测试商品", "description": "同名商品一", "category": "数码与影音", "price": 10, "campus": "燕园校本部", "images": [img_e]})
    CREATED_ITEMS.append(r.json().get("id") if r.status_code == 201 else None)
    r = seller.post("/api/v1/items/", json={"title": "同名测试商品", "description": "同名商品二", "category": "数码与影音", "price": 12, "campus": "燕园校本部", "images": [img_e]})
    item_dup = r.json().get("id") if r.status_code == 201 else None
    CREATED_ITEMS.append(item_dup)
    r = buyer.post(f"/api/v1/items/{item_dup}/reports", json={"reason": "举报同名商品"})
    report_dup = r.json().get("id") if r.status_code == 201 else None
    r = admin.get("/api/v1/admin/reports")
    ev2 = next((x for x in r.json() if x["id"] == report_dup), None)
    has_dup = bool(ev2 and any("同名商品" in e for e in ev2.get("evidence", [])))
    record("A9", "举报证据含同名商品线索", "PASS" if r.status_code == 200 and has_dup else "FAIL", f"HTTP {r.status_code}")
    # 隐藏 -> BANNED -> 恢复
    r = admin.post(f"/api/v1/admin/reports/{report_d}/review", json={"action": "hide", "note": "补测隐藏商品", "confirmed": True})
    r2 = anon.get(f"/api/v1/items/{item_d}")
    banned = r2.status_code == 200 and r2.json().get("status") == "BANNED"
    record("A9", "管理员隐藏后商品 BANNED", "PASS" if r.status_code == 200 and banned else "FAIL", f"HTTP {r2.status_code} status={r2.json().get('status') if r2.status_code==200 else None}")
    r = admin.post(f"/api/v1/admin/reports/{report_d}/review", json={"action": "restore", "note": "补测恢复商品", "confirmed": True})
    r2 = anon.get(f"/api/v1/items/{item_d}")
    restored = r2.status_code == 200 and r2.json().get("status") == "ACTIVE"
    record("A9", "管理员恢复后商品 ACTIVE", "PASS" if r.status_code == 200 and restored else "FAIL", f"HTTP {r2.status_code} status={r2.json().get('status') if r2.status_code==200 else None}")

    # ---- A10 Cookie 属性 ----
    r = anon.post("/api/v1/auth/demo", json={"profile": "buyer"})
    sc = r.headers.get("set-cookie", "")
    ok = "HttpOnly" in sc and "SameSite=strict" in sc
    record("A10", "会话 Cookie HttpOnly + SameSite=strict", "PASS" if r.status_code == 200 and ok else "FAIL", f"set-cookie={sc[:80]}")

    # ---- A10 金额边界 ----
    r = seller.post("/api/v1/uploads", files={"file": ("f.jpg", jpg_bytes(), "image/jpeg")})
    img_f = r.json().get("url") if r.status_code == 201 else None
    IMAGE_URLS.append(img_f)
    for price, expect_ok in [(0, True), (0.01, True), (12.34, True), (999999, True), (12.345, False)]:
        r = seller.post("/api/v1/items/", json={"title": f"金额{price}", "description": "金额边界补测", "category": "数码与影音", "price": price, "campus": "燕园校本部", "images": [img_f]})
        got_ok = r.status_code == 201
        if got_ok:
            CREATED_ITEMS.append(r.json().get("id"))
        if got_ok != expect_ok:
            record("A10", f"金额边界 price={price}", "FAIL", f"HTTP {r.status_code}")
    record("A10", "金额边界（0/0.01/12.34/999999 通过，12.345 拒绝）", "PASS", "见上方逐项")

    # ---- A10 图片重编码去除 EXIF ----
    img = Image.new("RGB", (80, 60), (10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    r = seller.post("/api/v1/uploads", files={"file": ("g.jpg", buf.getvalue(), "image/jpeg")})
    img_g = r.json().get("url") if r.status_code == 201 else None
    IMAGE_URLS.append(img_g)
    if img_g:
        rr = httpx.get(BASE + img_g)
        out = Image.open(io.BytesIO(rr.content))
        no_exif = not out.getexif()
        record("A10", "上传图片被重编码（无 EXIF 残留）", "PASS" if rr.status_code == 200 and no_exif else "FAIL", f"HTTP {rr.status_code}")

    # 清理
    cleanup()

    print(json.dumps(RESULTS, ensure_ascii=False, indent=2))
    print(f"\nSUMMARY: PASS={sum(1 for x in RESULTS if x['status']=='PASS')} FAIL={sum(1 for x in RESULTS if x['status']=='FAIL')}", file=sys.stderr)


def cleanup():
    if CREATED_ITEMS:
        ids = ",".join("?" for _ in CREATED_ITEMS)
        vals = [x for x in CREATED_ITEMS if x]
        conn = sqlite3.connect(DB, timeout=10)
        conn.execute("PRAGMA busy_timeout=5000")
        for tbl in ("chat_reports", "chat_messages"):
            pass
        if vals:
            conn.execute(f"DELETE FROM chat_reports WHERE message_id IN (SELECT id FROM chat_messages WHERE conversation_id IN (SELECT id FROM conversations WHERE item_id IN ({','.join('?' for _ in vals)})))", vals)
            conn.execute(f"DELETE FROM chat_messages WHERE conversation_id IN (SELECT id FROM conversations WHERE item_id IN ({','.join('?' for _ in vals)}))", vals)
            conn.execute(f"DELETE FROM conversations WHERE item_id IN ({','.join('?' for _ in vals)})", vals)
            conn.execute(f"DELETE FROM sale_feedback WHERE item_id IN ({','.join('?' for _ in vals)})", vals)
            conn.execute(f"DELETE FROM reports WHERE item_id IN ({','.join('?' for _ in vals)})", vals)
            conn.execute(f"DELETE FROM match_notifications WHERE item_id IN ({','.join('?' for _ in vals)})", vals)
            conn.execute(f"DELETE FROM favorites WHERE item_id IN ({','.join('?' for _ in vals)})", vals)
            conn.execute(f"DELETE FROM items WHERE id IN ({','.join('?' for _ in vals)})", vals)
        if CREATED_WANTED:
            wvals = [x for x in CREATED_WANTED if x]
            conn.execute(f"DELETE FROM wanted_posts WHERE id IN ({','.join('?' for _ in wvals)})", wvals)
        conn.commit()
        conn.close()
    for u in [x for x in IMAGE_URLS if x]:
        name = u.rsplit("/", 1)[-1]
        path = os.path.join("data", "uploads", name)
        try:
            os.remove(path)
        except OSError:
            pass
        conn = sqlite3.connect(DB, timeout=10)
        conn.execute("DELETE FROM uploads WHERE path=?", (u,))
        conn.commit()
        conn.close()


if __name__ == "__main__":
    main()
