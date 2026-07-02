# StockMaster A 股强势股选股工作台

StockMaster 是一个面向 A 股短线交易者的本地化选股工作台。它把强势股筛选、竞价雷达、板块资金流、短线情绪、自选股观察池和个股 K 线复盘放在一个独立 Web 系统里，帮助你把“看盘灵感”沉淀成可追踪、可复盘、可验证的交易流程。

它不是大而全行情软件，也不做自动交易。它更像一张短线作战台：盘前看竞价，盘中看板块和情绪，盘后复盘选股逻辑，长期维护自己的观察池。

> 风险提示：本项目只做数据整理、规则辅助和复盘记录，不构成投资建议。A 股交易风险高，请自行判断并控制仓位。

## 适合谁

- 想把强势股筛选规则固化下来，而不是每天靠手感翻股票。
- 需要维护自选股观察池，记录加入理由、计划买点、失效条件和复盘结论。
- 关注竞价强度、涨停情绪、板块资金流和个股 K 线结构。
- 希望 TickFlow、iFinD、东方财富、TDX 等数据源状态透明可见，知道本次结果是否可信。
- 想用 Docker / Unraid 快速部署一个私有选股工作台。

## 核心能力

| 模块 | 作用 |
| --- | --- |
| 选股工作台 | 按近 20 个交易日涨停池、趋势、量能、均线、200 日新高、板块强度和风险信号筛选强势股。 |
| GSGF 模型 | 将“股是股非”结构规则量化，输出三度、量时空、A/B/C 区、星线触发、确认买点和低吸观察等证据。 |
| 竞价雷达 | 聚合 09:20、09:23、09:24:50、09:25 等竞价快照，识别强势高开、过热风险、低开转强和行业集中度。 |
| 板块资金流 | 展示板块净流入/净流出排行；东方财富失效时可 fallback 到 TDX 或 TickFlow 全 A 实时行情行业聚合。 |
| 短线情绪 | 跟踪涨停、跌停、炸板、连板、高度板、涨跌分布等情绪指标，并支持后台采样和 Telegram 通知配置。 |
| 自选股观察池 | 支持分组、标签、多分组、状态、行业、加入理由、计划买点、失效条件、复盘结论和风险提示。 |
| 个股详情页 | 使用 TickFlow K 线，支持缩放、均线开关、十字光标、成交量、MACD/KDJ/RSI 等副图指标和 GSGF 证据标注。 |
| 数据源设置 | 在 UI 中配置 TickFlow、iFinD 等 key，查看权限、延迟、最近错误和 fallback 状态。 |

## 页面入口

启动后访问 `http://localhost:3110`：

- `/`：选股工作台
- `/watchlist`：自选股观察池
- `/sectors`：板块资金流
- `/auction`：竞价雷达
- `/sentiment`：短线情绪
- `/stock/{symbol}`：个股详情，例如 `/stock/002080.SZ`
- `/settings`：数据源和通知配置

## 快速部署

推荐使用 Docker Hub 单容器镜像。一个容器内同时运行 FastAPI 后端和 Next.js 前端，外部只需要暴露 `3110` 端口。

### 1. 创建目录

```bash
mkdir -p strong-stock-screener
cd strong-stock-screener
```

### 2. 编写 `docker-compose.yml`

```yaml
services:
  strong-stock-screener:
    image: icekale/strong-stock-screener:${STRONG_STOCK_IMAGE_TAG:-latest}
    container_name: strong-stock-screener
    pull_policy: always
    env_file:
      - .env
    environment:
      STRONG_STOCK_DATA_DIR: /app/data
      TZ: ${TZ:-Asia/Shanghai}
    ports:
      - "3110:3110"
    volumes:
      - ./data:/app/data
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test:
        [
          "CMD",
          "/opt/strong-stock-api-venv/bin/python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=3).read()",
        ]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

### 3. 编写 `.env`

```bash
STRONG_STOCK_TICKFLOW_API_KEY=你的_TickFlow_Key
STRONG_STOCK_TICKFLOW_BASE_URL=https://api.tickflow.org

STRONG_STOCK_IFIND_API_KEY=你的_iFinD_MCP_Key
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

TickFlow 是核心行情源，建议配置。iFinD 用于行业、公告、新闻、财务、估值和风险事件增强，不配置也可以使用主流程。

### 4. 启动

```bash
docker compose up -d
```

如果环境只有旧版 Compose：

```bash
docker-compose up -d
```

打开：

```text
http://localhost:3110
```

健康检查：

```bash
curl http://localhost:3110/health
```

### 5. 更新

```bash
docker compose pull
docker compose up -d
```

Unraid 推荐直接从 Docker Hub 拉取 `icekale/strong-stock-screener:latest`，不要在 NAS 上本地构建。项目数据挂载到容器内 `/app/data`，时区设置为 `Asia/Shanghai`。

## 首次使用流程

1. 打开 `/settings`，填写 TickFlow 和 iFinD key。
2. 点击数据源健康检查，确认日 K、实时行情、分钟线、iFinD 状态和 fallback 状态。
3. 打开首页 `/`，点击运行筛选，查看选股结果和风险提示。
4. 点击股票名称进入个股详情，检查 K 线、均线、副图指标和 GSGF 证据。
5. 对感兴趣的股票点击加入自选，并补充加入理由、计划买点和失效条件。
6. 交易日上午打开 `/auction`，观察竞价强度榜、行业集中度和风险提示。
7. 盘中打开 `/sectors` 和 `/sentiment`，确认主线板块、情绪温度和涨跌分布。
8. 盘后回到自选股观察池和个股详情页，更新复盘结论。

## 选股规则概览

默认模型围绕短线强势股设计：

- 只从近 20 个交易日出现过涨停的股票中筛选。
- 趋势优先，重点看股价是否在关键均线上方，是否接近或突破 200 日新高。
- K 线要求红肥绿瘦，上涨时量能饱满，回调时缩量。
- 放量上涨继续观察，放量滞涨提高风险权重。
- 强势板块和高辨识度个股加分。
- 严重异动、负面新闻、均线破位、实体阴线、连板断板未修复等信号会进入风险提示。
- 空仓纪律只用于持仓或自选股风险判断，不用于初始选股过滤。

## 数据源策略

StockMaster 尽量让数据源透明，而不是把结果包装成黑盒结论。

| 数据类别 | 默认来源 | 说明 |
| --- | --- | --- |
| 日 K / 个股 K 线 | TickFlow | 个股详情页和策略计算优先使用。 |
| 实时行情 / 竞价 / 分钟线 | TickFlow | 用于竞价雷达、情绪、排行和盘中观察。 |
| 涨停候选池 | 东方财富 / AKShare | 默认从近 20 日涨停池构建候选。 |
| 板块资金流 | 东方财富行业资金流 | 直连失败时 fallback 到估算、TDX、TickFlow 行业聚合。 |
| 行业分类 | 东方财富 / 同花顺分类参考 / iFinD | 同花顺分类参考来自 `https://files.688798.xyz/ths/industries.json`。 |
| 研究增强 | iFinD MCP | 行业、公告、新闻、财务、估值、风险事件。 |
| 新闻风险 | 东方财富 / iFinD | 用于负面新闻和风险提示。 |

板块资金流的 fallback 顺序：

```text
东方财富行业资金流
→ 东方财富行业涨跌额估算
→ TDX MCP 涨停概念集中度
→ TickFlow 全 A 实时行情行业聚合
```

## 持久化数据

Docker Compose 默认挂载：

```text
./data:/app/data
```

这里保存：

- UI 保存的数据源配置
- 自选股和分组
- 选股记录
- GSGF 复盘记录
- 情绪和竞价快照

公开仓库已忽略 `data/`、`.env` 和运行时配置。不要把 key、自选股或历史记录提交到 Git。

## 本地开发

后端：

```bash
cd apps/api
uv sync
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

前端：

```bash
cd apps/web
corepack pnpm install
corepack pnpm dev -- -p 3110
```

也可以用脚本启动本地 Web：

```bash
python3 scripts/start-local-web.py
```

## 常用检查

后端：

```bash
cd apps/api
uv run pytest
```

前端：

```bash
cd apps/web
node ./node_modules/typescript/bin/tsc --noEmit
node --experimental-strip-types --test lib/*.test.ts
```

Docker：

```bash
docker compose up -d
curl http://localhost:3110/health
docker compose logs -f strong-stock-screener
```

## 镜像和仓库

- GitHub：https://github.com/icekale/strong-stock-screener
- Docker Hub：https://hub.docker.com/r/icekale/strong-stock-screener
- 默认镜像：`icekale/strong-stock-screener:latest`
- 可通过 `.env` 设置 `STRONG_STOCK_IMAGE_TAG` 固定版本。

旧双容器开发模式仍保留：

```bash
docker compose -f docker-compose.dual.yml up -d --build
```

双容器模式会暴露：

- Web：`http://localhost:3110`
- API：`http://localhost:8010/health`

## 常见问题

### TickFlow 没配置还能用吗？

可以打开系统，但 K 线、竞价、实时排行、情绪和部分板块能力会明显受限。建议至少配置 TickFlow。

### iFinD 是必须的吗？

不是。iFinD 用于研究增强和风险事件补充，不影响基本选股、K 线和自选股管理。

### 为什么板块页显示估算资金流？

当东方财富行业资金流不可用时，系统会自动 fallback。页面会显示当前数据口径，例如“东方财富行业板块资金净额”或“TickFlow全A实时行情行业聚合”。

### 数据会不会越积越多？

系统提供保留策略环境变量，例如筛选记录数量、GSGF 复盘记录数、情绪历史天数和单日样本数。默认配置已经限制长期运行的数据增长。

### 这是交易系统吗？

不是。它只做筛选、观察、复盘和提醒，不下单，不保证收益。

## 开源协议

MIT License。
