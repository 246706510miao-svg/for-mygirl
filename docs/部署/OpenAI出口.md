# OpenAI 出口部署说明

本文件说明本地项目里的 `third` LLM 出口口径。前端和 SpringBoot 不直接调用 OpenAI，也不配置 OpenAI 代理。

## 生产固定口径

生产 SH 服务器固定使用本机 mihomo 的主机入口和容器入口：

```text
SH 主机工具： http://127.0.0.1:7890
Docker 容器： http://host.docker.internal:7891
Docker bridge：172.18.0.1
```

`7890` 仅给主机 Git 和 Docker daemon 使用；`7891` 仅绑定 Docker bridge，并由 10 节点自动回退组提供容器出口。

生产私有文件在本地：

```text
deploy-private/prod/
```

服务器路径：

```text
/opt/for-mygirl/shared/prod/
```

生产上由 `deploy-private/prod/apply-openai-proxy-mode.sh` 写入 `third.env.prod`：

- `OPENAI_PROXY_ENABLED=0`：强制国内模型，`THIRD_LLM_ROUTE_MODE=domestic`，`THIRD_OPENAI_PROXY_URL=`。
- `OPENAI_PROXY_ENABLED=1`：OpenAI 主通道 + 国内兜底，`THIRD_LLM_ROUTE_MODE=auto`，`THIRD_OPENAI_PROXY_URL=http://host.docker.internal:7891`。

`THIRD_OPENAI_PROXY_URL` 只给 `third` 内部 OpenAI 主通道使用。DeepSeek 和 MiniMax 会显式使用不继承环境代理的 HTTP client，不走这个代理。MySQL、Redis、SpringBoot 内部 HTTP、飞书 OpenAPI 也不会因为这个配置自动走代理。

## 本地项目配置差异

tracked 的本地项目配置只保留通用模板，不保存生产真实密钥，也不保存服务器实际 `third.env.prod`。

| 位置 | 用途 | 和生产的差异 |
|---|---|---|
| `third/.env.example` | 本地 Python 直跑模板 | 代理默认留空；需要本机代理时手动填 `http://127.0.0.1:7890` 或自己的本地端口。 |
| `third/.env.docker.real.example` | 本地完整 third 容器真实联调模板 | 本地容器代理通常填 `http://host.docker.internal:7890`；SH 生产固定使用专用的 `7891`。 |
| `deploy-private/prod/third.env.prod` | 生产私有 env | 保存真实 key/provider，且 `THIRD_OPENAI_PROXY_URL` 由私有脚本维护；不进 git。 |
| `deploy-private/prod/openai-proxy.env` | 生产模型出口开关 | 只保留 `OPENAI_PROXY_ENABLED`，不再维护端口或 SSH 隧道配置。 |

对比本地私有生产目录和服务器实际目录时，运行：

```powershell
powershell -ExecutionPolicy Bypass -File deploy-private/prod/compare-prod-sync.ps1
```

报告会输出普通文件 hash/文本差异；`.env.prod` 和 `third.env.prod` 只输出 key 是否一致、值为空还是已设置，不打印真实密钥。

## third 需要什么

本地或生产启用 OpenAI 主通道时，`third` 需要：

```env
OPENAI_API_KEY=sk_xxx
THIRD_WORKFLOWAGENT_MODEL=gpt-4o-mini
THIRD_OPENAI_TIMEOUT_SECONDS=60
THIRD_OPENAI_MAX_RETRIES=2
```

代理配置按运行方式决定：

```env
# 本地 Python 直跑，需要走本机代理时：
THIRD_OPENAI_PROXY_URL=http://127.0.0.1:7890

# 本地容器联调：
THIRD_OPENAI_PROXY_URL=http://host.docker.internal:7890

# SH 生产容器：
THIRD_OPENAI_PROXY_URL=http://host.docker.internal:7891
```

如果强制只用国内模型：

```env
THIRD_LLM_ROUTE_MODE=domestic
THIRD_OPENAI_PROXY_URL=
```

国内兜底通道按 OpenAI-compatible 接口配置，默认 DeepSeek 优先、MiniMax 第二。配置不完整的 provider 会被跳过：

```env
THIRD_LLM_ROUTE_MODE=auto
THIRD_LLM_FALLBACK_PROVIDERS=deepseek,minimax
THIRD_LLM_PROBE_ENABLED=1
THIRD_LLM_PROBE_TTL_SECONDS=60
THIRD_LLM_PROBE_SAMPLES=3
THIRD_LLM_PROBE_MIN_SUCCESSES=2
THIRD_LLM_UNHEALTHY_TTL_SECONDS=120

THIRD_DEEPSEEK_API_KEY=
THIRD_DEEPSEEK_BASE_URL=
THIRD_DEEPSEEK_MODEL=
THIRD_DEEPSEEK_TIMEOUT_SECONDS=60
THIRD_DEEPSEEK_MAX_RETRIES=0
THIRD_MINIMAX_API_KEY=
THIRD_MINIMAX_BASE_URL=
THIRD_MINIMAX_MODEL=
THIRD_MINIMAX_TIMEOUT_SECONDS=60
THIRD_MINIMAX_MAX_RETRIES=0
```

## 路由和兜底规则

`THIRD_LLM_ROUTE_MODE=auto` 时，业务调用前会按 `THIRD_LLM_PROBE_TTL_SECONDS` 使用缓存探测结果判断 OpenAI 代理链路是否健康。

- OpenAI 代理探测健康：优先使用 OpenAI 主通道。
- OpenAI 代理探测不健康：直接使用第一个配置完整的国内 provider。
- 主通道实际调用出现连接、代理、超时或上游 5xx：短期标记主通道不健康，并兜底到国内 provider。
- 鉴权错误、参数错误、限流、LLM 输出 JSON 不合法：不自动切换，直接暴露脱敏后的明确错误。
- 国内 provider 默认 `TIMEOUT_SECONDS=60`、`MAX_RETRIES=0`。

`THIRD_LLM_ROUTE_MODE=domestic` 会跳过 OpenAI 主通道和主通道探测，直接按 `THIRD_LLM_FALLBACK_PROVIDERS` 使用国内 provider。

探测 prompt 是固定的最小无业务内容，不读取 workflow 输入，也不保存 artifact。

## 本地 Docker 配置

复制真实环境模板并填写私有值：

```powershell
Copy-Item third/.env.docker.real.example third/.env
```

本地容器如果要通过宿主机 mihomo 调 OpenAI，填：

```env
OPENAI_API_KEY=sk_xxx
THIRD_OPENAI_PROXY_URL=http://host.docker.internal:7890
THIRD_OPENAI_TIMEOUT_SECONDS=60
THIRD_OPENAI_MAX_RETRIES=2
THIRD_LLM_ROUTE_MODE=auto
THIRD_DEEPSEEK_API_KEY=xxx
THIRD_DEEPSEEK_BASE_URL=https://your-deepseek-compatible-endpoint/v1
THIRD_DEEPSEEK_MODEL=your-deepseek-model
THIRD_DEEPSEEK_TIMEOUT_SECONDS=60
THIRD_DEEPSEEK_MAX_RETRIES=0
```

仅修改这些环境变量后，重启默认 Agent 容器即可：

```powershell
docker compose restart third-two-api
```

如果同时修改了 `third_two/` 或共享 `third/` Python 代码，则需要重建：

```powershell
docker compose up -d --build third-two-api
```

## 验证方式

1. 确认 `third/.env` 已设置 `OPENAI_API_KEY`，需要 LLM 时打开 `THIRD_WORKFLOWAGENT_USE_LLM=1`。
2. 设置 `THIRD_OPENAI_PROXY_URL` 和国内 provider 配置后重启 `third-two-api`。
3. 执行出口探测脚本：

```powershell
python -m third.scripts.probe_llm_routes --samples 3 --json --refresh
```

4. 打开 `http://localhost:8001/debug`，确认 OpenAI key、LLM route 和 provider 配置状态。
5. 需要主动刷新探测结果时访问 `GET /debug/llm-routes/probe?refresh=1`。
6. 触发一次需要 LLM 的记录 workflow，观察 `third-api` / `third-worker` 日志是否还有代理连接或模型调用错误。

调试日志会脱敏 `OPENAI_API_KEY`、`THIRD_OPENAI_PROXY_URL`、国内 provider key、base URL 和带账号密码的 URL。不要把真实代理账号密码、国内模型 key 或真实生产 endpoint 提交到 git。
