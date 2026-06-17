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

