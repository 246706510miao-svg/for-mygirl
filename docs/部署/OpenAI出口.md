# OpenAI 出口部署说明

本文件只说明 `third` 访问 OpenAI 时需要的出口配置。前端和 SpringBoot 不直接调用 OpenAI，也不需要配置代理。

## third 需要什么

`third` 只需要两个关键信息：

```env
OPENAI_API_KEY=sk_xxx
THIRD_OPENAI_PROXY_URL=http://user:password@jp.example.com:3128
```

可选运行参数：

```env
THIRD_OPENAI_TIMEOUT_SECONDS=60
THIRD_OPENAI_MAX_RETRIES=2
```

`THIRD_OPENAI_PROXY_URL` 只会传给 `third` 内部的 OpenAI client。MySQL、Redis、SpringBoot 内部 HTTP、飞书 OpenAPI 不会因为这个配置自动走代理。

## 日本服务器需要做什么

日本服务器提供一个受限 HTTP CONNECT 代理端口即可，例如 Squid、tinyproxy 或其他等价代理服务。代理服务应满足：

- 只允许你的部署服务器访问，不做开放代理。
- 尽量只允许 CONNECT 到 `api.openai.com:443`。
- 代理端口需要账号密码、IP 白名单、WireGuard 内网或其他访问控制。
- 不需要在代理层保存 OpenAI key；OpenAI key 仍放在部署 `third` 的环境变量里。

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
2. 设置 `THIRD_OPENAI_PROXY_URL` 后重启 `third-api` 和 `third-worker`。
3. 打开 `http://localhost:8001/debug`，确认 OpenAI key 显示为 configured。
4. 触发一次需要 LLM 的记录 workflow，观察 `third-api` / `third-worker` 日志是否还有代理连接或 OpenAI 调用错误。

调试日志会脱敏 `OPENAI_API_KEY` 和 `THIRD_OPENAI_PROXY_URL`。不要把真实代理账号密码提交到 git。
