# OpenAI 出口部署说明

本文件只说明 `third` 的 LLM 出口配置。前端和 SpringBoot 不直接调用 OpenAI，也不需要配置代理。

## third 需要什么

主通道仍然是 OpenAI + 日本代理：

```env
OPENAI_API_KEY=sk_xxx
THIRD_WORKFLOWAGENT_MODEL=gpt-4o-mini
THIRD_OPENAI_PROXY_URL=http://user:password@jp.example.com:3128
THIRD_OPENAI_TIMEOUT_SECONDS=60
THIRD_OPENAI_MAX_RETRIES=2
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

`THIRD_OPENAI_PROXY_URL` 只会传给 `third` 内部的 OpenAI 主通道。DeepSeek 和 MiniMax 会显式使用不继承环境代理的 HTTP client，不走日本代理。MySQL、Redis、SpringBoot 内部 HTTP、飞书 OpenAPI 也不会因为这个配置自动走代理。

## 日本服务器需要做什么

日本服务器提供一个受限 HTTP CONNECT 代理端口即可，例如 Squid、tinyproxy 或其他等价代理服务。代理服务应满足：

- 只允许你的部署服务器访问，不做开放代理。
- 尽量只允许 CONNECT 到 `api.openai.com:443`。
- 代理端口需要账号密码、IP 白名单、WireGuard 内网或其他访问控制。
- 不需要在代理层保存 OpenAI key；OpenAI key 仍放在部署 `third` 的环境变量里。

## 路由和兜底规则

`THIRD_LLM_ROUTE_MODE=auto` 时，业务调用前会按 `THIRD_LLM_PROBE_TTL_SECONDS` 使用缓存探测结果判断 OpenAI 代理链路是否健康。

- OpenAI 代理探测健康：优先使用 OpenAI 主通道。
- OpenAI 代理探测不健康：直接使用第一个配置完整的国内 provider。
- 主通道实际调用出现连接、代理、超时或上游 5xx：短期标记主通道不健康，并兜底到国内 provider。
- 鉴权错误、参数错误、限流、LLM 输出 JSON 不合法：不自动切换，直接暴露脱敏后的明确错误。
- 国内 provider 默认 `TIMEOUT_SECONDS=60`、`MAX_RETRIES=0`；如果你的 `third/.env` 仍是早期模板里的 `30/1`，DeepSeek 长 prompt 可能在收到 200 响应头后读正文超时并重复请求。

本地如果开启了系统 TUN 全局代理，想直接用国内模型，可以设置：

```env
THIRD_LLM_ROUTE_MODE=domestic
```

这个模式会跳过 OpenAI 主通道和主通道探测，直接按 `THIRD_LLM_FALLBACK_PROVIDERS` 使用国内 provider。它能绕开应用层 `THIRD_OPENAI_PROXY_URL` 和环境 HTTP 代理；如果 TUN 是系统路由层全流量转发，真实网络路径仍取决于 TUN 分流规则。

探测 prompt 是固定的最小无业务内容，不读取 workflow 输入，也不保存 artifact。

## Docker 部署配置

复制真实环境模板并填写私有值：

```powershell
Copy-Item third/.env.docker.real.example third/.env
```

在 `third/.env` 里填：

```env
OPENAI_API_KEY=sk_xxx
THIRD_OPENAI_PROXY_URL=http://user:password@jp.example.com:3128
THIRD_OPENAI_TIMEOUT_SECONDS=60
THIRD_OPENAI_MAX_RETRIES=2
THIRD_LLM_ROUTE_MODE=auto
THIRD_DEEPSEEK_API_KEY=xxx
THIRD_DEEPSEEK_BASE_URL=https://your-deepseek-compatible-endpoint/v1
THIRD_DEEPSEEK_MODEL=your-deepseek-model
THIRD_DEEPSEEK_TIMEOUT_SECONDS=60
THIRD_DEEPSEEK_MAX_RETRIES=0
```

仅修改这些环境变量后，重启 third 容器即可：

```powershell
docker compose --profile third-container --profile app restart third-api third-worker
```

如果同时修改了 `third/` Python 代码，则需要重建：

```powershell
docker compose --profile third-container --profile app up -d --build third-api third-worker
```

## 验证方式

1. 确认 `third/.env` 已设置 `OPENAI_API_KEY`，需要 LLM 时打开 `THIRD_WORKFLOWAGENT_USE_LLM=1`。
2. 设置 `THIRD_OPENAI_PROXY_URL` 和国内 provider 配置后重启 `third-api` 和 `third-worker`。
3. 执行出口探测脚本：

```powershell
python -m third.scripts.probe_llm_routes --samples 3 --json --refresh
```

4. 打开 `http://localhost:8001/debug`，确认 OpenAI key、LLM route 和 provider 配置状态。
5. 需要主动刷新探测结果时访问 `GET /debug/llm-routes/probe?refresh=1`。
6. 触发一次需要 LLM 的记录 workflow，观察 `third-api` / `third-worker` 日志是否还有代理连接或模型调用错误。

调试日志会脱敏 `OPENAI_API_KEY`、`THIRD_OPENAI_PROXY_URL`、国内 provider key、base URL 和带账号密码的 URL。不要把真实代理账号密码、国内模型 key 或真实生产 endpoint 提交到 git。
