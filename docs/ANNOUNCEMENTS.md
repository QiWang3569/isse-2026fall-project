# 发布公告与更新说明

> 说明：如何给「燕渡」发布系统公告和更新通知。公告会出现在左侧「系统公告」入口和小铃铛的「公告与更新」分区里。管理员也可以直接登录后在「审核工作台 → 公告管理」页签用表单发布与下线，无需使用下面的 curl。

## 数据字段

| 字段 | 说明 |
| --- | --- |
| `title` | 标题，2–200 字 |
| `body` | 正文，5–5000 字 |
| `kind` | `公告` 或 `更新` |
| `active` | `true` 显示 / `false` 下线 |
| `created_at` | 发布时间（自动） |

## 推荐方式：管理员接口（curl）

### 1. 登录管理员（本地演示账号）

```bash
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/v1/auth/demo \
  -H "Content-Type: application/json" \
  -d '{"profile":"admin"}'
```

### 2. 发布一条「公告」

```bash
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/v1/admin/announcements \
  -H "Content-Type: application/json" \
  -d '{"title":"系统维护通知","body":"今晚 22:00–23:00 系统维护，期间无法访问。","kind":"公告"}'
```

### 3. 发布一条「更新」

```bash
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/v1/admin/announcements \
  -H "Content-Type: application/json" \
  -d '{"title":"v0.2.0 更新说明","body":"新增人员招募分类，优化对比功能。","kind":"更新"}'
```

### 4. 编辑或下线一条公告

先通过管理员列表接口拿到公告 `id`（包含已下线公告）：

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/v1/admin/announcements
```

然后：

```bash
curl -b cookies.txt -X PATCH http://127.0.0.1:8000/api/v1/admin/announcements/<公告id> \
  -H "Content-Type: application/json" \
  -d '{"title":"新标题","body":"新正文","kind":"公告","active":false}'
```

`active:false` 即下线；只改个别字段时，其余字段可省略。

## 备选方式：直接写数据库（SQLite）

```sql
INSERT INTO announcements (id, title, body, kind, active, created_at)
VALUES (
  lower(hex(randomblob(16))),
  '标题',
  '正文内容',
  '公告',
  1,
  datetime('now')
);
```

数据库文件：`data/yandu.db`。

## 查看接口

公开列表（前端展示用）：

```bash
curl http://127.0.0.1:8000/api/v1/announcements
```

