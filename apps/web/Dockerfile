FROM node:22-slim AS deps

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:22-slim AS builder

WORKDIR /app

RUN corepack enable

COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL=http://localhost:8010
ENV NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL=$NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL
RUN pnpm build

FROM node:22-slim AS runner

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3110 \
    HOSTNAME=0.0.0.0

RUN corepack enable

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/pnpm-lock.yaml ./pnpm-lock.yaml
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.ts ./next.config.ts

EXPOSE 3110

CMD ["pnpm", "exec", "next", "start", "-p", "3110", "-H", "0.0.0.0"]
