# 强势股选股工作台

一个独立的 A 股强势股筛选与自选股管理工具。项目目标不是做“大而全”的行情软件，而是把一套偏短线强势股的交易纪律固化成可复盘、可追踪、可部署的工作台。

> 风险提示：本项目只做数据整理和规则辅助，不构成投资建议。A 股交易风险高，请自行判断并控制仓位。

## 功能概览

- 强势股筛选：默认只从近 20 个交易日出现过涨停的股票中筛选。
- 趋势规则：结合 K 线实体、量能、MA5/10/20/60、200 日新高、放量上涨、放量滞涨等指标评分。
- 板块强度：给强势行业/板块候选更高权重。
- 风险提示：展示严重异动、负面新闻、均线破位、实体阴线等风险信号。
- 自选股管理：支持分组、标签、行业、备注、批量移动、删除。
- K 线详情页：使用 TickFlow 日 K 数据，支持缩放、均线开关、十字定位线、成交量和 KDJ。
- 数据源设置页：可在 UI 查看 TickFlow key 状态、数据源健康检查、请求延迟和 fallback 情况。
- 独立部署：后端 FastAPI，前端 Next.js，支持 Docker Compose 一键启动。

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
├── docker-compose.yml
├── .env.example
└── README.md
```

## 数据源说明

默认数据源组合：

- 候选池：AKShare / 东方财富近 20 个交易日涨停池。
- 日 K：TickFlow 日 K。
- 实时行情/分钟线：TickFlow。
- 新闻风险：东方财富个股新闻。

TickFlow key 可以通过环境变量配置，也可以启动后在 UI 的“数据源设置”页面中配置。公开仓库不会提交 `.env`、历史筛选记录、自选股文件或 runtime 配置。

## Docker Compose 部署

### 1. 准备环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
STRONG_STOCK_TICKFLOW_API_KEY=你的_tickflow_key
STRONG_STOCK_TICKFLOW_BASE_URL=https://api.tickflow.org
STRONG_STOCK_CANDIDATE_PROVIDER=recent_limit_up
STRONG_STOCK_DATA_DIR=./data
STRONG_STOCK_CORS_ALLOW_ORIGINS=http://localhost:3110,http://127.0.0.1:3110
```

如果暂时不填 TickFlow key，后端会显示 `missing_key`，选股和 K 线能力会受限。

### 2. 启动

```bash
docker compose up --build
# 或者：docker-compose up --build
```

启动后访问：

- 前端工作台：http://localhost:3110
- 后端健康检查：http://localhost:8010/health
- 数据源设置：http://localhost:3110/settings
- 自选股管理：http://localhost:3110/watchlist

### 3. 后台运行

```bash
docker compose up -d --build
# 或者：docker-compose up -d --build
```

### 4. 查看日志

```bash
docker compose logs -f api
docker compose logs -f web
# 或者：docker-compose logs -f api
# 或者：docker-compose logs -f web
```

### 5. 停止

```bash
docker compose down
# 或者：docker-compose down
```

如果需要同时删除数据卷：

```bash
docker compose down -v
# 或者：docker-compose down -v
```

注意：`-v` 会删除容器内保存的筛选记录、自选股和运行时配置。

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
corepack pnpm exec next dev -p 3110
```

打开：http://localhost:3110

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
docker compose build
docker compose up -d
curl http://localhost:8010/health
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
| `STRONG_STOCK_CANDIDATE_PROVIDER` | `recent_limit_up` | 候选池来源，可选 `recent_limit_up` / `thsdk` |
| `STRONG_STOCK_DATA_DIR` | `./data` | 后端数据目录 |
| `STRONG_STOCK_CORS_ALLOW_ORIGINS` | `http://localhost:3110,http://127.0.0.1:3110` | CORS 允许来源 |

## 开源协议

MIT License。
