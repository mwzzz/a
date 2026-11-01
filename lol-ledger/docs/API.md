# 接口说明

统一前缀 `/api/v1`。除 `POST /auth/login` 和 `GET /api/health` 外都要带：

```
Authorization: Bearer <access_token>
```

金额字段一律是**整数分**，字段名以 `_cents` 结尾。错误统一返回 `{"detail": "中文提示"}`：
业务错误 400、未登录/过期 401、越权 403、不存在 404、AI 占位 501、登录试错过多 429。

所有业务接口都会自动按**当前账号所属商家**过滤，请求体不需要也不能传 `merchant_id`。
用别家的 id 访问玩家、批次、场次、流水、账号，一律返回 **404**（不暴露数据是否存在）。
商家本身不通过接口创建，用命令行：`create-merchant` / `list-merchants` / `set-merchant-status` / `rename-merchant`。

开发时 `DEBUG=true` 可以在 `/docs` 看到交互式文档（生产关闭）。

## 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/login` | `{username, password}` → `{access_token, token_type, expires_in, user}`，`user.merchant` 是本店信息 |
| GET | `/auth/me` | 当前用户，含 `merchant_id` 与 `merchant: {id, name}` |
| POST | `/auth/password` | `{old_password, new_password}`，改完旧令牌立即失效 |
| POST | `/auth/logout` | 只写审计日志，前端清本地令牌 |

## 账号（仅管理员）

只能看到并操作**本商家**的账号；用户名全平台唯一。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/users` | 本商家账号列表 |
| POST | `/users` | `{username, password, display_name, role}`，自动归属当前商家 |
| PATCH | `/users/{id}` | 改显示名 / 角色 / 启停；别家账号 404 |
| POST | `/users/{id}/password` | 重置密码；别家账号 404 |

## 玩家

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/players` | `keyword, level(low/warn/safe), sort, page, page_size` |
| GET | `/players/options` | `keyword, exclude_ids=1,2, limit`，给下拉框用 |
| POST | `/players` | `{game_id, account?, remark?}` |
| GET | `/players/{id}` | 详情，含累计充值/支出 |
| PATCH | `/players/{id}` | 改游戏名 / 账号 / 备注 |
| DELETE | `/players/{id}` | 软删除，押金必须为 0，仅管理员 |
| GET | `/players/{id}/ledger` | 个人流水，分页 |

`sort` 可选：`games_played_desc`（默认）、`deposit_desc`、`deposit_asc`、`last_active_desc`、`game_id_asc`。

## 押金

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/players/{id}/deposits` | 加押金，`{amount_cents, note?}`，必须 > 0 |
| POST | `/players/{id}/refunds` | 退押金，不能超过余额 |
| POST | `/players/{id}/deductions` | 手动扣押，可以扣成负数 |
| POST | `/transfers` | `{from_player_id, to_player_id, amount_cents, note?}` |

返回 `{entry, player}`，`entry.reason_label` 已经拼好中文（划转带对手名和箭头）。

## 批次

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/batches` | `status(all/open/closed), keyword, date_from, date_to, page, page_size, include_sessions` |
| GET | `/batches/current` | 进行中的批次，没有则 `{batch: null}` |
| POST | `/batches` | 开班 `{label?, note?}`，已有进行中批次会拒绝 |
| GET | `/batches/{id}` | 详情，含所有场次 |
| GET | `/batches/{id}/summary` | 汇总，已交班用快照，进行中实时算 |
| GET | `/batches/{id}/ledger` | 本批流水，分页 |
| POST | `/batches/{id}/close` | 交班，返回快照汇总 |
| GET | `/batches/{id}/export.csv` | 导出 CSV（带 BOM） |

汇总字段：`session_count, player_times, tea_total_cents, add_total_cents, refund_total_cents,
deduct_total_cents, transfer_out_total_cents, transfer_count, net_change_cents,
deposit_total_cents, opening_total_cents`。

## 场次

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/sessions` | `batch_id, keyword, date_from, date_to, page, page_size` |
| POST | `/sessions/preview` | `{player_ids, tea_fee_cents}` → 每人扣前/扣后/是否变负 |
| POST | `/sessions` | `{batch_id?, name?, played_at?, note?, tea_fee_cents, player_ids}` |
| GET | `/sessions/{id}` | 场次详情，含每人扣费 |

规则：1~10 人、自动去重、每人扣相同茶水、允许扣成负数、整局一个事务。

## 记录与总览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/records/deposits` | `keyword, player_id, batch_id, session_id, reason, date_from, date_to, sort, page, page_size` |
| GET | `/records/sessions` | 场次记录 |
| GET | `/records/transfers/{group_id}` | 一笔划转的两条流水 |
| GET | `/overview` | 总押金、在用玩家、低押金人数、今日统计、当前批次、最近 10 条 |
| GET | `/reconcile` | 对账，仅管理员 |
| GET | `/settings` | 读设置 |
| PATCH | `/settings` | 改设置，仅管理员 |
| POST | `/ai/recognize-players` | 本期固定 501（AI 识别占位） |

## 约定

- 时间格式 `2026-10-30T20:04:12+08:00`，字典序即时间序。
- 日期范围参数用 `YYYY-MM-DD`，按中国时区算起止。
- 分页返回 `{items, total, page, page_size}`，`page_size` 上限 200。
- 所有写操作都记 `operator_id`；`ledger` 里还存了 `balance_before/after` 快照。
- 商家隔离：所有查询都带 `merchant_id`，跨商家访问返回 404；`/settings` 的 `shop_name` 就是商家名（存在 `merchants.name`）。
- 账号停用、角色变更、商家停用都立即生效（每次请求重新查库），不用等令牌过期。
