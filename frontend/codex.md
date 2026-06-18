# frontend Codex 入口

本目录是正式前端工程，使用 Vite React TypeScript。Codex 修改前端时先读这里，再看 `docs/ui/codex.md` 和 `docs/接口文档.md`。

## 模块划分

| 模块 | 位置 | 作用 |
|---|---|---|
| shared/api | `src/shared/api` | 统一 API client、token、`X-Request-Id` 和错误处理。 |
| shared/types | `src/shared/types` | 根据接口文档维护 DTO 类型。 |
| features/user | `src/features/user` | 用户端首页、记录输入、草稿确认和最近记录。 |
| features/admin | `src/features/admin` | 管理员统计、记录列表、详情和追踪。 |
| styles | `src/styles.css` | iPhone-first 样式、安全区、触控目标和后台基础布局。 |

## 实现口径

- 第一版以接口为准，组件细节和视觉内容后续再补。
- 用户端优先适配 iPhone 宽度，按钮最小高度保持 44px。
- 管理员端保留 PC 后台基础布局。
- API 调用必须经过 `shared/api/client.ts`，不要在页面里直接写 fetch。
- 新增 hook、API helper 和页面级函数前保留简短中文注释。

## 相关文档

- 接口文档：`../docs/接口文档.md`
- UI 页面说明：`../docs/ui/codex.md`
- 页面流程：`../docs/ui/页面流程图.md`
