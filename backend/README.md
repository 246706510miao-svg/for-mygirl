# backend 初始化说明

`backend` 是 SpringBoot 业务后端，面向前端提供 `/api` 接口，并通过 HTTP 调用 `third` workflow 服务。

third workflow 接入与 v1 强类型契约见 `../third/docs/外部调用契约.md`。

## 本地运行

先启动 MySQL、Redis、third API 和 worker：

```powershell
docker compose --profile third-container up -d --build
```

再运行后端：

```powershell
cd backend
mvn spring-boot:run
```

如果本机没有 Maven，可以用容器方式：

```powershell
docker compose --profile third-container --profile app up -d --build backend
```

默认端口：

- SpringBoot API：`http://localhost:8080`
- third API：`http://localhost:8001`
- MySQL：`127.0.0.1:3307`
- third 私有运行库：`third_service`
- third 测试库：`third_test`
- 后端业务逻辑库：`for_mygirl_app`

## 默认账号

| 角色     | loginName           | password | token               |
| -------- | ------------------- | -------- | ------------------- |
| 用户     | `user` 或 `fjl` | 任意非空 | `dev-user-token`  |
| 后台人员 | `admin`           | 任意非空 | `dev-admin-token` |

## 环境变量

| 变量                       | 默认值                                             | 说明                               |
| -------------------------- | -------------------------------------------------- | ---------------------------------- |
| `BACKEND_MYSQL_URL`      | `jdbc:mysql://127.0.0.1:3307/for_mygirl_app?...` | 后端业务表所在 MySQL 逻辑库。      |
| `BACKEND_MYSQL_USERNAME` | `backend_user`                                   | 只授权业务库的 MySQL 用户名。      |
| `BACKEND_MYSQL_PASSWORD` | `backend_password`                               | 业务库 MySQL 密码。                |
| `THIRD_BASE_URL`         | `http://127.0.0.1:8001`                          | SpringBoot 调用的 third API 地址。 |
| `BACKEND_CORS_ORIGIN`    | `http://localhost:5173`                          | 前端开发地址。                     |
| `BACKEND_USER_TOKEN`     | `dev-user-token`                                 | MVP 用户 token。                   |
| `BACKEND_ADMIN_TOKEN`    | `dev-admin-token`                                | MVP 后台人员 token。               |

## 验证

```powershell
mvn test
```

第一版重点验证接口闭环、Flyway 建表、记录追踪和 third 调用，不覆盖真实 JWT 或语音上传。

## 数据库边界

Compose 使用一个 MySQL 容器承载三个逻辑库：

- `for_mygirl_app`：由 SpringBoot Flyway 管理，只放 `APP_PERSON`、`RECORD_SESSION`、`DAILY_RECORD` 等业务表，只有 `backend_user` 可访问。
- `third_service`：由 `third-migration` 的 Alembic 管理，是 third 私有运行库，只放 workflow、prompt、tool 等表，SpringBoot 不直连。
- `third_test`：只给 third 的真实 MySQL 集成测试使用。

后续业务表按模块扩展：绑定和授权、风格、评论、积分、奖品、后台审计已在 Flyway V3 预留边界。新增功能先写 `../docs/future/<功能名>.md`，再改对应模块。

`mysql-init` 容器会在 MySQL healthy 后执行 `CREATE DATABASE IF NOT EXISTS` 和授权，因此不依赖空 volume 初始化。

Compose 内部会覆盖 `third` 容器的 `THIRD_MYSQL_DSN` 和 `THIRD_REDIS_URL`，让 third 使用 `mysql`、`redis` 服务名连接容器网络；`third/.env` 仍负责真实 OpenAI/飞书配置。
