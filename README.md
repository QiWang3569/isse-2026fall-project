# 燕渡 YanDu

旧物渡新主，学海渡轻舟。一个正在构建中的校园二手交易应用，让用户发布闲置、浏览好物，并委托系统持续关注符合条件的商品。

当前版本为 **0.1.0 本地 MVP**，已有可运行前后端与持久化数据库。以 `ArvinHsu` 分支的需求文档为基础，结合 issues #8、#12、#13、#14、#15 实现。范围和取舍见 [需求与实现记录](docs/IMPLEMENTATION.md)。

## 可以体验的功能

- 上传 1–3 张图片发布商品，管理预订、售出、重新上架等状态。
- 分类、关键词搜索、校区与价格筛选、排序、分页；根据收藏分类与同校区优先进行基础推荐。
- 自然语言需求解析，确认并修改条件，立即匹配已有商品；新商品发布时自动再次匹配。
- 最多 5 个活跃代蹲任务，14 天有效期，可暂停、续期或结束。
- 匹配通知、匹配理由、去重、已读状态；10 秒轮询，失效商品标记为不在售。
- 收藏、最多 3 件商品对比、可编辑咨询草稿、商品分享链接。
- 求购看板，7 天有效期，可提前关闭；卖家可据此进入商品发布表单。
- 举报与管理员工作台：文字风险词和同名商品线索、人工确认隐藏或恢复、审计日志。

默认使用本地规则解析与关键词匹配，**无需模型密钥，也不会产生模型 API 费用**。这不是完整的语义智能体：否定、复杂偏好和未知品类的解析能力有限，因此保留了用户确认和修改条件的步骤。

## 获取代码

本实现位于 `feat/yandu-mvp` 分支。仓库目前为私有仓库，需要先使用有访问权限的 GitHub 账号登录 Git；没有权限时请联系仓库所有者添加协作者。

```shell
git clone --branch feat/yandu-mvp https://github.com/QiWang3569/isse-2026fall-project.git yandu
cd yandu
```

也可以在 GitHub 切换到该分支后下载 ZIP 并解压。源码包含简体中文需求文档、依赖锁文件和演示种子；无需复制开发者电脑上的数据库或图片。

## 启动（Windows）

首次配置需要 Node.js 22 和 Python 3.12（已验证版本）。在项目根目录运行：

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1 -SkipBuild
```

若 Python 不在 PATH，可运行 `setup.ps1 -Python '完整的 python.exe 路径'`。脚本也支持检测本机 Codex 自带的 Python。依赖安装到项目 `.venv` 和 `frontend/node_modules`。

打开 [燕渡本地应用](http://127.0.0.1:8000)。默认不需要 `.env` 或模型密钥，首次启动会自动创建数据库与演示数据。安装完成后再次启动只需运行 `start.ps1 -SkipBuild`。

若 Windows 提示不允许运行脚本，可在当前终端先执行 `Set-ExecutionPolicy -Scope Process Bypass`，只对当前终端临时生效。服务默认只监听本机；推送代码不会自动部署网站，其他人需在自己的电脑启动。

停止服务（保留数据）：

```powershell
.\scripts\stop.ps1
```

前端修改后，在 `frontend` 中执行 `npm run build` 并刷新页面；后端修改后重启服务。`start.ps1` 不带 `-SkipBuild` 时会先重新构建前端。日志位于 `data/server.log` 和 `data/server-error.log`。

## 开发模式

先停止后台服务，避免占用同一端口。在一个终端中运行前端：

```powershell
cd frontend
npm run dev
```

在另一个终端的项目根目录运行后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

开发页面：[http://127.0.0.1:5173](http://127.0.0.1:5173)；接口文档：[API 文档](http://127.0.0.1:8000/docs)。

## 启动（Linux / macOS）

安装 Python 3.12 与 Node.js 22 后，在项目根目录运行：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock.txt
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

打开同一个本地地址 `http://127.0.0.1:8000`，按 Ctrl+C 停止服务。macOS 尚未进行实际设备验证。

## 演示账号与数据

右上角“登录”可切换林同学（买家）、许同学（卖家）和管理员。默认生成 10 件演示商品与 1 条求购；商品插画是本地 SVG，并非真实商品照片。浏览器联调生成的商品名称带有“联调演示”。

演示登录不是校园认证，不应直接作为公开服务的登录方案。设置 `DEMO_MODE=false` 后不生成演示数据，并关闭演示登录，等待实际 SSO 接入。发布、收藏、任务、举报等操作绑定服务器会话，不接受客户端伪造用户 ID。

数据库在 `data/yandu.db`，图片在 `data/uploads`，重启不会丢失。`.env`、数据库、图片、日志和依赖目录已加入 Git 忽略规则。

## 可选：模型与 PostgreSQL

复制 `.env.example` 为 `.env`。`AI_MODE=local` 无密钥运行；改为 `AI_MODE=remote` 并配置 DeepSeek 与兼容 Embedding 接口的密钥后，才会调用外部服务。远程路径包括结构化解析、1536 维向量、硬条件过滤后余弦相似度匹配。模型返回内容须通过校验，失败时不会保存半完成的发布或任务。

**真实模型接口尚未带密钥实测。** 切换模式或模型后，旧数据不混用向量；应重建对应向量或使用新的开发数据库。默认演示种子没有远程向量，远程模式下应上传新商品验证匹配。

可选本地 PostgreSQL：

```powershell
docker compose up -d postgres
```

在 `.env` 中设置后重启：

```dotenv
DATABASE_URL=postgresql+psycopg://yandu:yandu-local-only@localhost:5432/yandu
```

服务创建初始表结构、`vector` 扩展及 HNSW 索引。SQLite 与 PostgreSQL 共用 SQLAlchemy 模型，金额保存为整数分，向量分别采用 JSON 与 `vector(1536)`。切换数据库不会迁移已有数据；后续结构升级还需加入版本化迁移。PostgreSQL 配置路径尚未连接真实实例验证。

## 检查

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm ci
npm run build
```

详情见 [验证记录](docs/VALIDATION.md)。GitHub Actions 会在推送及合并请求时执行后端测试与前端构建，运行结果见仓库的 Actions 页面。

## 文件组织

```text
backend/app/            API、数据库、解析与匹配服务
backend/tests/          业务流程与权限测试
frontend/src/           React + TypeScript 界面
scripts/                安装、启动、停止脚本
docs/requirements/      简体中文 PRD 与 TECH_SPEC
docs/sources/           issues 快照和原始需求记录
docs/IMPLEMENTATION.md  实现范围及后续工作
data/                   数据库、图片、日志（不提交）
```

校园认证、树洞/微信接入、站内聊天、降价通知、语义精筛、多模态发布、图片审核、完整推荐算法和生产性能验证仍待开发。本版不处理支付，不自动发送咨询消息。
