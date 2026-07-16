# 部署说明

## Docker Compose

优先使用：

```bash
docker compose up --build
```

如果环境里只有旧版命令：

```bash
docker-compose up --build
```

## 端口

- API: `8010`
- Web: `3110`

`docker-compose.dual.yml` 使用 `apps/web-vue` 构建 Vue 3 + Vite + Ant Design Vue 前端；Web 容器提供 Vue Router history fallback，并将同源 `/api/*` 请求代理到 API 容器。生产单容器镜像仍通过 `3110` 同时提供 FastAPI 和 Vue 前端。

## 本地前端预览

```bash
cd apps/web-vue
corepack enable
corepack prepare pnpm@9.15.0 --activate
pnpm install --frozen-lockfile
pnpm dev --host 127.0.0.1 --port 3110
```

开发模式默认直连 `http://127.0.0.1:8010` 的 API；生产构建使用同源 `/api/*`，由静态服务器通过 `API_INTERNAL_URL` 代理到 FastAPI。

## 持久化数据

默认通过 Docker volume 持久化：

- 筛选记录
- 自选股
- 运行时配置

删除 volume 会清空这些数据。

## 常见问题

### 1. TickFlow Key 不显示

先检查 `.env` 或在页面 `/settings` 中保存。

### 2. 构建命令报 credential helper

使用干净的 `DOCKER_CONFIG` 再构建，或者修复本机 Docker Desktop 的凭据助手配置。
