# StockMaster A 股强势股工作台

StockMaster 是一个面向 A 股短线交易者的私有化工作台。它把强势股筛选、早盘竞价雷达、竞价 Top3 模型试运行、板块资金流、短线情绪、自选股观察池和个股 K 线复盘整合到一个 Web 系统里。

它不是自动交易系统，也不是投资建议工具。它的定位很明确：把盘前、盘中、盘后的短线观察流程做成可追踪、可复盘、可验证的工作流。

> 风险提示：本项目只做数据整理、模型辅助和复盘记录，不下单，不保证收益。A 股短线交易波动大，请自行判断并控制仓位。

## 最新版本重点

- 竞价雷达接入早盘 Top3 模型试运行。
- Top3 模型支持本地缓存快读，早盘读取通常是毫秒级；重新生成模型结果才会触发全市场特征计算。
- Top3 候选加入流动性约束：流通市值低于 20 亿或近 3 日日均成交额低于 1 亿会被降级，不进入实盘 Top3 预览。
- Top3 卡片展示胜率、赔率、期望收益、流通市值、近 3 日日均成交额、前收和风险标签。
- 从 K 线详情页返回竞价页时，Top3 缓存结果会自动恢复。
- Docker 单容器镜像内置竞价模型 artifacts，可直接部署到 Docker Hub / Unraid。

## 功能模块

| 模块 | 说明 |
| --- | --- |
| 选股工作台 | 从强势股池中筛选趋势、量能、均线、200 日新高、板块强度和风险信号。 |
| 竞价雷达 | 聚合 09:20、09:23、09:24:50、09:25 快照，查看竞价强度榜、阶段时间轴、行业集中度和高开风险。 |
| 竞价 Top3 模型 | 基于 free-stockdb 五年日 K 训练的 LightGBM 模型，输出研究型 Top3 候选、历史胜率、赔率、期望收益和 10:00 守卫规则。 |
| 板块资金流 | 查看板块净流入、净流出、行业聚集和主线强度。东方财富不可用时可 fallback 到 TDX 或 TickFlow 聚合。 |
| 短线情绪 | 跟踪涨停、跌停、炸板、连板、高度板、涨跌分布和情绪温度。 |
| 自选股观察池 | 管理分组、标签、行业、加入理由、计划买点、失效条件、复盘结论和风险提示。 |
| 个股详情 | TickFlow K 线、均线、成交量、MACD/KDJ/RSI、自定义砖块指标和 GSGF 证据标注。 |
| 数据源设置 | 在 UI 中配置 TickFlow、iFinD、TDX、通知渠道和运行时健康检查。 |

## 页面入口

启动后访问 `http://localhost:3110`：

- `/`：强势股筛选工作台
- `/auction`：竞价雷达和 Top3 模型试运行
- `/watchlist`：自选股观察池
- `/sectors`：板块资金流
- `/sentiment`：短线情绪
- `/stock/{symbol}`：个股详情，例如 `/stock/300922.SZ`
- `/settings`：数据源、通知和运行状态

## 推荐部署：Docker 单容器

Docker Hub 镜像：

```text
icekale/strong-stock-screener:latest
```

单容器同时运行 FastAPI 后端和 Next.js 前端，对外只暴露 `3110`。

### 1. 准备目录

```bash
mkdir -p strong-stock-screener
cd strong-stock-screener
mkdir -p data
```

### 2. 创建 `.env`

```bash
# 必填：行情和 K 线核心源
STRONG_STOCK_TICKFLOW_API_KEY=你的_TickFlow_Key
STRONG_STOCK_TICKFLOW_BASE_URL=https://api.tickflow.org

# 可选：研究增强源
STRONG_STOCK_IFIND_API_KEY=你的_iFinD_MCP_Key
STRONG_STOCK_IFIND_BASE_URL=https://api-mcp.51ifind.com:8643
STRONG_STOCK_IFIND_SERVICE_ID=hexin-ifind-ds-stock-mcp

# 可选：竞价 Top3 重新生成依赖的 free-stockdb 服务
STRONG_STOCK_AUCTION_MODEL_FREE_STOCKDB_BASE_URL=http://你的free-stockdb地址:7899

# 基础配置
STRONG_STOCK_DATA_DIR=/app/data
STRONG_STOCK_CANDIDATE_PROVIDER=recent_limit_up
STRONG_STOCK_CORS_ALLOW_ORIGINS=http://localhost:3110,http://127.0.0.1:3110
TZ=Asia/Shanghai

# 数据保留策略
STRONG_STOCK_SCREEN_RUN_RETENTION_COUNT=120
STRONG_STOCK_GSGF_REVIEW_RETENTION_RECORDS=5000
STRONG_STOCK_SENTIMENT_SNAPSHOT_RETENTION_DAYS=30
STRONG_STOCK_MARKET_EMOTION_HISTORY_RETENTION_DAYS=30
STRONG_STOCK_MARKET_EMOTION_SAMPLES_PER_DAY=360
STRONG_STOCK_AUCTION_REVIEW_RETENTION_DAYS=120
```

TickFlow 是核心行情源，建议配置。iFinD 用于公告、新闻、行业、财务、估值和风险事件增强，不配置也可以使用主要流程。

竞价 Top3 模型的缓存读取不依赖 free-stockdb；只有点击“重新生成”时才需要可访问的 free-stockdb 服务。

### 3. 创建 `docker-compose.yml`

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
    restart: unless-stopped
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

### 4. 启动和更新

```bash
docker compose up -d
docker compose logs -f strong-stock-screener
```

打开：

```text
http://localhost:3110
```

更新：

```bash
docker compose pull
docker compose up -d
```

## Unraid 部署

仓库提供 Docker Template：

```text
unraid/strong-stock-screener.xml
```

推荐配置：

- Repository：`icekale/strong-stock-screener:latest`
- WebUI：`http://[IP]:[PORT:3110]`
- Port：`3110`
- AppData：`/mnt/user/appdata/strong-stock-screener` 挂载到 `/app/data`
- TZ：`Asia/Shanghai`
- TickFlow Key：填入 `STRONG_STOCK_TICKFLOW_API_KEY`
- free-stockdb：如果需要重新生成竞价 Top3，填入 `STRONG_STOCK_AUCTION_MODEL_FREE_STOCKDB_BASE_URL`

Unraid 上建议直接拉 Docker Hub 镜像，不建议在 NAS 上本地构建。

## 竞价 Top3 模型说明

当前模型是研究型早盘辅助信号，不是自动买入信号。

### 数据和目标

- 数据源：free-stockdb 日 K。
- 训练窗口：2021-07-03 至 2026-07-03。
- 模型：LightGBM。
- 目标：T+1 收盘涨幅达到 3%。
- 当前版本主要使用上一交易日日 K 特征；若没有真实历史 09:25 竞价快照，会标记 `no_auction_snapshot`。

### 快路径和慢路径

| 操作 | 行为 |
| --- | --- |
| 读取缓存 | 只读本地 `data/auction_model/top3_YYYYMMDD.json`，用于早盘快速决策。 |
| 重新生成 | 拉取 free-stockdb 全市场日 K，构建 120 日特征并重新预测，通常需要 1 到 2 分钟。 |

### 实盘防守规则

模型候选必须同时通过流动性约束：

- 流通市值 >= 20 亿
- 近 3 日日均成交额 >= 1 亿

未通过的票会被降级，不进入 `Top3试运行`。页面会显示风险标签，例如：

- `流通市值低于20亿`
- `近3日日均成交额低于1亿`

Top3 卡片还会显示：

- 模型概率
- 历史胜率
- 赔率
- 期望收益
- 流通市值
- 近 3 日日均成交额
- 10:00 守卫规则

## 首次使用流程

1. 打开 `/settings`，配置 TickFlow 和可选 iFinD。
2. 点击数据源健康检查，确认 K 线、实时行情、分钟线、公告新闻和 fallback 状态。
3. 打开 `/`，运行强势股筛选。
4. 点击股票进入 `/stock/{symbol}`，查看 K 线结构、均线和风险证据。
5. 对关注股票加入自选，并补充计划买点、失效条件和复盘备注。
6. 交易日上午打开 `/auction`，先看竞价强度榜和行业集中，再看 Top3 模型缓存结果。
7. 如需更新 Top3，手动点击“重新生成”；实盘时优先使用缓存，不建议在 09:25 决策窗口等待重算。
8. 盘中使用 `/sectors` 和 `/sentiment` 确认主线板块和情绪状态。
9. 盘后回到观察池和个股页更新复盘结论。

## 数据源策略

| 数据类别 | 默认来源 | 说明 |
| --- | --- | --- |
| 日 K / 个股 K 线 | TickFlow | 个股详情和策略计算优先使用。 |
| 实时行情 / 竞价 / 分钟线 | TickFlow | 用于竞价雷达、情绪、排行和盘中观察。 |
| 涨停候选池 | 东方财富 / AKShare | 默认从近 20 日涨停池构建候选。 |
| 板块资金流 | 东方财富行业资金流 | 不可用时 fallback 到估算、TDX 或 TickFlow 行业聚合。 |
| 行业分类 | 东方财富 / 同花顺参考 / iFinD | 用于行业聚集、板块筛选和归因。 |
| 研究增强 | iFinD MCP | 公告、新闻、财务、估值和风险事件。 |
| 竞价模型训练/预测 | free-stockdb | 用于重新生成 Top3 模型结果。 |

板块资金流 fallback 顺序：

```text
东方财富行业资金流
→ 东方财富行业涨跌额估算
→ TDX MCP 涨停概念集中度
→ TickFlow 全 A 实时行情行业聚合
```

## 持久化数据

默认挂载：

```text
./data:/app/data
```

这里保存：

- 运行时配置
- 自选股和分组
- 筛选记录
- GSGF 复盘记录
- 竞价快照和竞价模型缓存
- 短线情绪历史
- 板块采样数据

不要提交 `.env`、`data/` 或任何包含 API Key、持仓、自选股的文件。

## 本地开发

后端：

```bash
cd apps/api
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
```

前端：

```bash
cd apps/web
corepack enable
corepack prepare pnpm@9.15.0 --activate
pnpm install --frozen-lockfile
npm run dev -- --hostname 127.0.0.1 --port 3110
```

全量检查：

```bash
cd apps/api
uv run pytest -q

cd ../web
./node_modules/.bin/tsc --noEmit
node --experimental-strip-types --test lib/*.test.ts
```

Docker 本地构建：

```bash
docker build -t icekale/strong-stock-screener:local .
docker run --rm -p 3110:3110 -v "$PWD/data:/app/data" --env-file .env icekale/strong-stock-screener:local
```

双容器开发模式仍保留：

```bash
docker compose -f docker-compose.dual.yml up -d --build
```

## 重要环境变量

| 变量 | 用途 |
| --- | --- |
| `STRONG_STOCK_TICKFLOW_API_KEY` | TickFlow 行情和 K 线 key。 |
| `STRONG_STOCK_TICKFLOW_BASE_URL` | TickFlow API 地址。 |
| `STRONG_STOCK_IFIND_API_KEY` | iFinD MCP key。 |
| `STRONG_STOCK_AUCTION_MODEL_FREE_STOCKDB_BASE_URL` | free-stockdb 服务地址，用于重新生成竞价 Top3。 |
| `STRONG_STOCK_DATA_DIR` | 持久化数据目录，容器内建议 `/app/data`。 |
| `STRONG_STOCK_CORS_ALLOW_ORIGINS` | 允许访问 API 的前端地址。 |
| `STRONG_STOCK_SCREEN_RUN_RETENTION_COUNT` | 筛选记录保留数量。 |
| `STRONG_STOCK_AUCTION_REVIEW_RETENTION_DAYS` | 竞价复盘保留天数。 |

## 仓库和镜像

- GitHub：https://github.com/icekale/strong-stock-screener
- Docker Hub：https://hub.docker.com/r/icekale/strong-stock-screener
- 镜像：`icekale/strong-stock-screener:latest`

## 常见问题

### 没有 TickFlow 能用吗？

系统可以启动，但 K 线、竞价、实时排行、情绪和部分板块能力会受限。建议至少配置 TickFlow。

### iFinD 是必须的吗？

不是。iFinD 是研究增强源，不影响基本筛选、K 线和观察池。

### free-stockdb 是必须的吗？

不是。读取已有 Top3 缓存不需要 free-stockdb。只有点击“重新生成”竞价模型结果时才需要。

### 为什么 Top3 有时不是概率最高的前三只？

因为模型结果会先做实盘约束。低流通市值或低成交额的高分票会降级为风险观察，不进入 `Top3试运行`。

### 这是交易系统吗？

不是。它不接券商、不下单、不做自动交易。它只是短线筛选、观察和复盘工作台。

## License

MIT License.
