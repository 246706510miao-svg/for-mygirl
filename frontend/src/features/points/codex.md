# points 模块入口

`features/points` 承载签到积分、记录打分积分、奖品、兑换和兑换提示。

## 当前入口

- `api.ts`：`/api/points/summary`、`/api/points/checkins`、`/api/rewards`、`/api/rewards/{rewardId}/redeem`、`/api/reward-redemptions`。
- 页面状态目前由 `src/App.tsx` 编排：用户/角色页展示和兑换奖品，绑定管理员积分奖品页添加奖品并查看兑换提示。

## 接入规则

- 签到每天一次，固定 10 分。
- 记录打分积分由后端 `comment` 保存打分后触发，前端只展示结果。
- 绑定管理员视角添加奖品必须先通过 relationship 视角切换。
- 用户兑换奖品后奖品从列表消失，绑定管理员视角通过兑换记录看到提示。
- 积分问题先查后端 `POINT_LEDGER`，不要只看前端余额。
