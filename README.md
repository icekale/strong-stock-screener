# A 股强势股 / GSGF 选股工作台

一个面向 A 股短线交易复盘的独立选股工作台。它把强势股筛选、`股是股非` GSGF V2 结构模型、TickFlow 行情、自选股管理、自动复盘和真实样本校准整合在一个可本地部署的 Web 应用里。

项目目标不是做“大而全”的行情软件，而是把一套偏短线强势股的交易纪律固化成可解释、可复盘、可追踪、可部署的工作台。

> 风险提示：本项目只做数据整理和规则辅助，不构成投资建议。A 股交易风险高，请自行判断并控制仓位。

## 项目入口

- GitHub 仓库：https://github.com/icekale/strong-stock-screener
- GitHub Releases：https://github.com/icekale/strong-stock-screener/releases
- Docker Hub 单容器镜像：https://hub.docker.com/r/icekale/strong-stock-screener
- Docker Hub API 镜像（旧双容器模式）：https://hub.docker.com/r/icekale/strong-stock-screener-api
- Docker Hub Web 镜像（旧双容器模式）：https://hub.docker.com/r/icekale/strong-stock-screener-web
- Docker 标签：`latest`，并保留构建时的提交标签，例如 `4d3bf4a`

## 功能概览

- 强势股筛选：默认只从近 20 个交易日出现过涨停的股票中筛选。
- GSGF V2：把《股是股非》拆书后的结构规则转成量化评分，覆盖三度、量时空、均线归位、A/B/C 区、星线触发、确认买点、低吸观察和风险失效。
- 趋势规则：结合 K 线实体、量能、MA5/10/20/60、200 日新高、放量上涨、放量滞涨等指标评分。
- 板块强度：给强势行业/板块候选更高权重。
- 风险提示：展示严重异动、负面新闻、均线破位、实体阴线等风险信号。
- 自选股管理：支持分组、标签、行业、备注、批量移动、删除。
- K 线详情页：使用 TickFlow 日 K 数据，支持缩放、均线开关、十字定位线、成交量和 KDJ。
- GSGF 图表证据：在个股 K 线页展示策略命中的结构证据，辅助复盘“为什么选中 / 为什么回避”。
- 自动复盘：保存 GSGF 信号快照，定期复查确认买点、低吸观察、B 区 A 点、放量突破确认等分桶表现。
- 真实样本校准：用 TickFlow 数据跑真实样本，生成模型健康摘要和信号退化提醒。
- 数据源设置页：可在 UI 查看 TickFlow、iFinD key 状态、数据源健康检查、请求延迟和 fallback 情况。
- 独立部署：后端 FastAPI，前端 Next.js，默认使用 Docker Hub 单容器镜像，也保留双容器本地构建方式。

## 技术栈

- 后端：FastAPI、Pydantic、AKShare、TickFlow、httpx
- 前端：Next.js 15、React 19、Tailwind CSS
- 包管理：uv、pnpm
- 部署：Docker / Docker Compose

## 项目结构

```text
.
├── apps
│   ├── api          # FastAPI 后端，默认端口 8010
│   └── web          # Next.js 前端，默认端口 3110
├── Dockerfile       # 单容器镜像，内部同时启动 API 和 Web
├── docker-compose.yml
├── docker-compose.dual.yml
├── .env.example
└── README.md
```

## 数据源说明

默认数据源组合：

- 候选池：AKShare / 东方财富近 20 个交易日涨停池。
- 日 K：TickFlow 日 K。
- 实时行情/分钟线：TickFlow。
- 研究增强：iFinD MCP，用于后续接入行业板块、公告新闻、财务估值和风险事件。
- 新闻风险：东方财富个股新闻。

TickFlow key 和 iFinD MCP key 可以通过环境变量配置，也可以启动后在 UI 的“数据源设置”页面中配置。公开仓库不会提交 `.env`、历史筛选记录、自选股文件或 runtime 配置。
Docker Compose 默认把后端数据保存到项目目录的 `data/`，用于持久化 UI 保存的数据源配置、自选股和筛选记录。

## Docker Compose 部署

默认推荐使用单容器镜像：一个 Docker Hub 镜像内同时运行 FastAPI 和 Next.js。Unraid 只需要从 Docker Hub 拉取 `icekale/strong-stock-screener:latest`，不需要在 NAS 上本地构建。

### 1. 准备环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
STRONG_STOCK_TICKFLOW_API_KEY=你的_tickflow_key
STRONG_STOCK_TICKFLOW_BASE_URL=https://api.tickflow.org
STRONG_STOCK_IFIND_API_KEY=你的_ifind_mcp_key
STRONG_STOCK_IFIND_BASE_URL=https://api-mcp.51ifind.com:8643
STRONG_STOCK_IFIND_SERVICE_ID=hexin-ifind-ds-stock-mcp
STRONG_STOCK_CANDIDATE_PROVIDER=recent_limit_up
STRONG_STOCK_DATA_DIR=./data
STRONG_STOCK_CORS_ALLOW_ORIGINS=http://localhost:3110,http://127.0.0.1:3110
TZ=Asia/Shanghai
STRONG_STOCK_SCREEN_RUN_RETENTION_COUNT=120
STRONG_STOCK_GSGF_REVIEW_RETENTION_RECORDS=5000
STRONG_STOCK_SENTIMENT_SNAPSHOT_RETENTION_DAYS=30
STRONG_STOCK_MARKET_EMOTION_HISTORY_RETENTION_DAYS=30
STRONG_STOCK_MARKET_EMOTION_SAMPLES_PER_DAY=360
```

如果暂时不填 TickFlow key，后端会显示 `missing_key`，选股和 K 线能力会受限。
如果暂时不填 iFinD key，研究增强能力会显示 `missing_key`，但不会影响 TickFlow 行情和现有选股主流程。

单容器镜像内置同源 API 代理，浏览器访问 `http://服务器IP:3110` 即可，前端会通过 `/api/*` 代理到容器内部 FastAPI，不需要额外暴露 `8010` 端口。

### 2. 启动

```bash
docker compose up -d
# 或者：docker-compose up -d
```

启动后访问：

- 前端工作台：http://localhost:3110
- 后端健康检查：http://localhost:3110/health
- 数据源设置：http://localhost:3110/settings
- 自选股管理：http://localhost:3110/watchlist

### 3. 固定镜像标签

`docker-compose.yml` 默认使用：

```yaml
image: icekale/strong-stock-screener:${STRONG_STOCK_IMAGE_TAG:-latest}
```

如需固定版本，可以在 `.env` 中设置：

```bash
STRONG_STOCK_IMAGE_TAG=提交短哈希
```

### 4. 查看日志

`docker-compose.yml` 已配置 Docker 日志滚动，默认单文件 10MB、最多 3 个文件，避免长期运行时容器日志占满磁盘。

```bash
docker compose logs -f strong-stock-screener
# 或者：docker-compose logs -f strong-stock-screener
```

### 5. 停止

```bash
docker compose down
# 或者：docker-compose down
```

如需清空筛选记录、自选股和 UI 保存的运行时配置，停止服务后删除项目目录下的 `data/`。公开仓库已忽略该目录，请不要把 key 或运行数据提交到 Git。

### 6. 旧双容器本地构建

如果需要回滚到 API/Web 双容器开发模式，可以使用：

```bash
docker compose -f docker-compose.dual.yml up -d --build
```

双容器模式会暴露：

- Web：http://localhost:3110
- API：http://localhost:8010/health

## 本地开发

### 后端

```bash
cd apps/api
uv sync
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

### 前端

```bash
cd apps/web
corepack pnpm install
corepack pnpm dev -- -p 3110
```

打开：http://localhost:3110

如果只是本机拉起工作台，推荐使用仓库脚本：

```bash
python3 scripts/start-local-web.py
```

该脚本会停止旧的 `3110` 前端进程、清理开发态 `.next-dev` 目录并后台启动 Web。生产构建仍使用 `.next`，本地开发使用 `.next-dev`，避免 `next build` 覆盖正在运行的开发服务资源。

## 常用检查

后端：

```bash
cd apps/api
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
```

前端：

```bash
cd apps/web
corepack pnpm test
```

Docker：

```bash
docker compose up -d
curl http://localhost:3110/health
# 如果你的环境只支持旧版命令，把 docker compose 换成 docker-compose
```

## 使用流程

1. 打开 `http://localhost:3110/settings`，确认 TickFlow 和数据源状态。
2. 回到首页，选择交易日和扫描候选数。
3. 点击“运行筛选”。
4. 查看候选决策表、板块强度、风险提示和 K 线详情。
5. 对感兴趣的股票点击“加入自选”。
6. 在自选股管理页维护分组、标签、行业和备注。

## 规则边界

- 新股筛选结果不会使用 `empty` 作为状态。
- 空仓纪律只用于自选股/持仓风险判断，对应 `risk_action = "empty"`。
- 当前版本不包含后台实时监控任务流，实时监控和提醒系统放在后续版本。
- 严重异动标记依赖候选源是否返回相关字段，后续可继续接入监管公告源增强。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `STRONG_STOCK_TICKFLOW_API_KEY` | 空 | TickFlow API Key |
| `TICKFLOW_API_KEY` | 空 | TickFlow API Key 兼容变量 |
| `STRONG_STOCK_TICKFLOW_BASE_URL` | `https://api.tickflow.org` | TickFlow API 地址 |
| `STRONG_STOCK_IFIND_API_KEY` | 空 | iFinD MCP Key |
| `IFIND_API_KEY` | 空 | iFinD MCP Key 兼容变量 |
| `STRONG_STOCK_IFIND_BASE_URL` | `https://api-mcp.51ifind.com:8643` | iFinD MCP API 地址 |
| `STRONG_STOCK_IFIND_SERVICE_ID` | `hexin-ifind-ds-stock-mcp` | 默认 iFinD MCP 服务 |
| `STRONG_STOCK_CANDIDATE_PROVIDER` | `recent_limit_up` | 候选池来源，可选 `recent_limit_up` / `thsdk` |
| `STRONG_STOCK_DATA_DIR` | `./data` | 后端数据目录 |
| `STRONG_STOCK_CORS_ALLOW_ORIGINS` | `http://localhost:3110,http://127.0.0.1:3110` | CORS 允许来源 |
| `TZ` | `Asia/Shanghai` | 容器系统时区，建议保持上海时间 |
| `STRONG_STOCK_SCREEN_RUN_RETENTION_COUNT` | `120` | 历史选股记录最多保留次数，不影响 `latest.json` |
| `STRONG_STOCK_GSGF_REVIEW_RETENTION_RECORDS` | `5000` | 股是股非复盘样本最多保留条数 |
| `STRONG_STOCK_SENTIMENT_SNAPSHOT_RETENTION_DAYS` | `30` | 情绪摘要快照最多保留交易日数 |
| `STRONG_STOCK_MARKET_EMOTION_HISTORY_RETENTION_DAYS` | `30` | 情绪分时历史最多保留交易日数 |
| `STRONG_STOCK_MARKET_EMOTION_SAMPLES_PER_DAY` | `360` | 单日情绪分时样本最多保留条数 |

## 开源协议

MIT License。
