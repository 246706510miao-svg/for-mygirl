# third_two Docker 运行

## 默认启动

```powershell
docker compose --profile app up -d --build
```

默认链路是：

```text
frontend -> backend -> third-two-api -> MySQL / Redis / 飞书
```

- `third-two-api`：宿主机 `http://localhost:8001`，调试台 `/debug`。
- `third-migration`：共享飞书字段缓存所需的数据库 migration。
- 原 `third-api`、`third-worker`、`third-prompt-seed` 默认不启动。

只重建 Agent：

```powershell
docker compose up -d --build third-two-api
```

## 启动旧 third 对照

只有明确做 legacy 对照时才运行：

```powershell
docker compose --profile third-legacy up -d --build third-api third-worker
```

旧 API 默认使用宿主机 `8002`，不会占用 `third_two` 的 `8001`。
