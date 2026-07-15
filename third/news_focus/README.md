# 每日热门采集模块

`news_focus` 生成全体用户共享的 AI、中国大事、新闻、开源四类每日热门。它只负责公开 RSS 元数据、规则筛选、中文编辑和 third 私有 Redis 状态；Spring Boot 的 `newsfocus` 模块负责调度、业务库落库与用户接口。

## 固定来源目录

目录来自以下固定提交，而不是每日读取 GitHub 分支：

- `xiangyugongzuoliu/awesome-rss-feeds-list@2ab3b9b167853aca17b85d5bc820ca512b27e9f0` 的 `feeds.opml`；
- `plenaryapp/awesome-rss-feeds@3a7a9e28943d28b8acb6d9197fb168a8be5267f6` 的技术、新闻与各国新闻 OPML。
- 受版本控制的 `china-focus@2026-07-14-v2` 白名单：中国新闻网国内、财经 RSS，以及中国日报 China News RSS。来源必须提供可解析的发布时间；不含发布时间的 RSS 不会接入该栏目。

首次生成时将固定 OPML 导入 third Redis；之后每日任务只读取缓存目录。需要更新来源时，由 Docker 内部调用 `POST /internal/news-focus/sources/refresh` 明确刷新快照。来源规则会拒绝付费墙发布者、社交平台转 RSS、RSSHub、`xgo`、`wechat2rss`、播客和生活方式等非目标来源。

模块不会抓取候选 `sourceUrl` 的正文，也不接入付费搜索、网页富化或社交网页抓取。页面只提供原文外链。

生产环境可通过 `THIRD_NEWS_FOCUS_PROXY_URL` 为 RSS/OPML 客户端配置独立代理；留空时保持直连。该变量不会改变 LLM、MySQL、Redis、飞书或内部 HTTP 的出口。

## 生成规则与输出

- 每个 RSS 最多读取 3 条元数据，单源 6 秒超时、最多 16 个并发请求；连续失败源在 Redis 退避，其他源继续处理。
- 候选先按 URL、标题指纹和此前 7 日已展示指纹去重，再按 AI、中国大事、新闻、开源路由；同日覆盖生成不排除当天已有条目，避免重试时错误减少分类内容。中国大事只接收白名单来源，优先国家层面的政策、宏观经济、科技产业、公共事件与重要民生进展；非中国来源的政治候选直接排除。
- 每类优先近 24 小时；不足五条时补近 72 小时；每类最多给 LLM 20 条候选。
- LLM 每类只返回最多 5 条的顺序、中文标题、摘要、标签与主题键，不生成数值评分。

内部生成接口返回 `generatedAt`、`sourceCount`、`candidateCount`、`sourceErrors` 和 `groups`。每组固定含 `key`、`title`、`items`；条目含 `rank`、`title`、`summary`、`tags`、`source`、`sourceUrl`、`publishedAt` 与仅供后端去重使用的 `dedupeKey`。

## 失败行为与扩展

单一来源失败只进入 `sourceErrors`；所有分类均无法展示或 LLM 全部失败时，调用方保留前一天成功结果。新增来源必须先写入固定 OPML 导入范围或规则配置，并补测试证明：不会访问文章正文、不会绕过来源排除规则、不会突破并发和单源条数限制。中国大事新增来源还必须先列入该白名单并做 RSS 连通性核验，不接受网页抓取或付费源。
