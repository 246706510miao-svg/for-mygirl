# for-mygirl

给 fjl 做的自律记录项目。

## 文档入口

- docs 总入口：[docs/codex.md](./docs/codex.md)
- 后续功能模板：[docs/future/codex.md](./docs/future/codex.md)
- UI 页面说明：[docs/ui/codex.md](./docs/ui/codex.md)
- UI 页面流程图：[docs/ui/页面流程图.md](./docs/ui/页面流程图.md)
- 总架构图：[docs/架构图/01_总架构图.md](./docs/架构图/01_总架构图.md)
- 部署边界图：[docs/架构图/02_部署边界图.md](./docs/架构图/02_部署边界图.md)
- 数据库：[docs/数据库/codex.md](./docs/数据库/codex.md)
- 运行与刷新：[docs/运行与刷新.md](./docs/运行与刷新.md)
- 接口文档：[docs/接口文档.md](./docs/接口文档.md)
- 序列图：[docs/序列图/codex.md](./docs/序列图/codex.md)
- 业务后端：[backend/codex.md](./backend/codex.md)
- 正式前端：[frontend/codex.md](./frontend/codex.md)
- 第三方服务模块：[third/README.md](./third/README.md)

## 初始化运行

完整本地容器链路：

```powershell
docker compose --profile third-container --profile app up -d --build
```

代码改动后的刷新方式见 [docs/运行与刷新.md](./docs/运行与刷新.md)。重点：只重启容器不会把新代码打进 Docker 镜像；改 `backend/`、`frontend/` 或 migration 后，如果当前用 Docker 跑应用，需要重新 `--build` 对应服务。MySQL/Redis 默认使用 volume 保留数据，不要随手执行 `docker compose down -v`。

常用地址：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8080`
- third 调试台：`http://localhost:8001/debug`
- MySQL：`127.0.0.1:3307`，包含 `third_service` 和 `for_mygirl_app` 两个逻辑库

数据库边界：

- `third_service` 给 Python `third` 服务和 Alembic 使用。
- `for_mygirl_app` 给 SpringBoot 后端和 Flyway 使用。

后续功能按模块增加：先写 `docs/future/<功能名>.md`，再分别更新 `backend/`、`frontend/`、数据库 migration 和对应 `codex.md`。

Compose 会在 `third` 容器内覆盖数据库和 Redis 地址：

- `THIRD_MYSQL_DSN=mysql+pymysql://third_user:third_password@mysql:3306/third_service`
- `THIRD_REDIS_URL=redis://redis:6379/0`

因此 `third/.env` 可以继续保存真实 OpenAI/飞书配置；容器内部连接 MySQL/Redis 时使用 Compose 服务名，不使用宿主机 `127.0.0.1`。
