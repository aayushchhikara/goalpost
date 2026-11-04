FROM node:24-slim AS build
RUN corepack enable
WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM node:24-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./
EXPOSE 3000
# Run Next directly: starting through pnpm would need corepack to download pnpm at runtime.
CMD ["node_modules/.bin/next", "start", "-H", "0.0.0.0"]
