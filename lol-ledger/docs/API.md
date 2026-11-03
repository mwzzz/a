# 接口说明

统一前缀 `/api/v1`。除 `POST /auth/login` 和 `GET /api/health` 外都要带：

```
Authorization: Bearer <access_token>
```

金额字段一律是**整数分**，字段名以 `_cents` 结尾。错误统一返回 `{"detail": "中文提示"}`：
业务错误 400、未登录/过期 401、越权 403、不存在 404、AI 占位 501、登录试错过多 429。

所有业务接口都会自动按**当前账号所属商家**过滤，请求体不需要也不能传 `merchant_id`。
用别家的 id 访问玩家、批次、场次、流水、账号，一律返回 **404**（不暴露数据是否存在）。

商家和门店账号由**开发者账号**（`is_superadmin`）在 `/platform/*` 下管理；开发者账号只能用命令行引导一次：
`create-superadmin --username <账号>`。门店管理员仍然只在 `/users` 里管本店账号。

开发时 `DEBUG=true` 可以在 `/docs` 看到交互式文档（生产关闭）。

## 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/login` | `{username, password}` → `{access_token, token_type, expires_in, user}`，`user.merchant` 是本店信息 |
| GET | `/auth/me` | 当前用户，含 `merchant_id`、`merchant: {id, name}`、`is_superadmin` |
| POST | `/auth/password` | `{old_password, new_password}`，改完旧令牌立即失效 |
| POST | `/auth/logout` | 只写审计日志，前端清本地令牌 |

## AI 识别（需登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/ai/status` | `{enabled, model}`；未配置 Key 时 enabled=false |
| POST | `/ai/recognize-players` | `multipart/form-data`，字段 `file`；jpg/png/webp/gif，≤5MB |

返回：

```json
{
  "items": [
    {
      "raw_name": "山中刘德华、",
      "status": "matched",
      "confidence": 0.95,
      "team": 1,
      "matched_player": {
        "id": 12, "game_id": "山中刘德华、", "account": "", "deposit_cents": 5000
      },
      "candidates": []
    }
  ],
  "count": 9,
  "warnings": ["识别到 9 个玩家，请确认是否完整"],
  "elapsed_ms": 3800
}
```

- `status`：`matched` 精确匹配 / `ambiguous` 需要人工选候选 / `unmatched` 未匹配
- 只匹配当前商家未删除玩家，不写任何业务数据
- 每用户 10 次/分钟；超时 25 秒；未配置或模型异常时返回 503/504/502，前端降级为手动选人
- 模糊候选阈值 0.72，最多 3 个；`名字#tag` 会兼容匹配

## 平台（仅开发者账号）

开发者账号（`is_superadmin = 1`）挂在隐藏的「平台管理」系统商家下，只能管商家和账号，不读门店经营数据。
非开发者账号访问这些路径一律 **403**；平台商家本身不可改名/停用（404）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/platform/merchants` | 所有商家（不含平台商家），带 `user_count`、`player_count` |
| POST | `/platform/merchants` | `{name, note?, admin_username?, admin_password?, admin_display_name?}`，可同时建第一个管理员 |
| PATCH | `/platform/merchants/{id}` | 改 `name` / `note` / `status(active/disabled)`；停用后该店账号立即无法登录 |
| GET | `/platform/merchants/{id}/users` | 指定商家的账号（不含开发者账号） |
| POST | `/platform/merchants/{id}/users` | `{username, password, display_name?, role}`，商家停用时拒绝 |
| PATCH | `/platform/users/{id}` | 改显示名 / 角色 / 启停；最后一个启用的管理员不能降级或停用 |
| POST | `/platform/users/{id}/password` | 重置密码；目标为开发者账号时 404 |

## 账号（仅管理员）

只能看到并操作**本商家**的账号；用户名全平台唯一。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/users` | 本商家账号列表 |
| GET | `/users/options` | 本店启用账号（交班弹窗选接收人用，店员也可读） |
| POST | `/users` | `{username, password, display_name, role}`，自动归属当前商家 |
| PATCH | `/users/{id}` | 改显示名 / 角色 / 启停；别家账号 404 |
| POST | `/users/{id}/password` | 重置密码；别家账号 404 |

## 玩家

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/players` | `keyword, level(low/warn/safe), sort, page, page_size` |
| GET | `/players/options` | `keyword, exclude_ids=1,2, limit`，给下拉框用 |
| POST | `/players` | `{game_id, account?, remark?}` |
| POST | `/players/import` | `multipart/form-data`，字段 `file`；仅 `.xls/.xlsx`，第一列玩家 id，第二列押金（元，可空） |
| GET | `/players/{id}` | 详情，含累计充值/支出 |
| PATCH | `/players/{id}` | 改游戏名 / 账号 / 备注 |
| DELETE | `/players/{id}` | 软删除，押金必须为 0，仅管理员 |
| GET | `/players/{id}/ledger` | 个人流水，分页 |

`sort` 可选：`games_played_desc`（默认）、`deposit_desc`、`deposit_asc`、`last_active_desc`、`game_id_asc`。

批量导入说明：取第一个工作表，第一行可以是表头；押金按元转成分，最多两位小数；整批校验通过才写入，任何一行重复/非法都会返回 400 和 `errors: [{row, message}]`，不会导入一半。单文件上限 5MB、1000 行。

## 押金

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/players/{id}/deposits` | 加押金，`{amount_cents, note?}`，必须 > 0 |
| POST | `/players/{id}/refunds` | 退押金，不能超过余额 |
| POST | `/transfers` | `{from_player_id, to_player_id, amount_cents, note?}` |

手动扣押已取消，历史数据在 v4 迁移时并入 `refund`。

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
| POST | `/batches/{id}/close` | 交班，见下方请求体，返回快照汇总 |
| GET | `/batches/{id}/export.csv` | 导出 CSV（带 BOM，含操作人分红） |

交班请求体：

```json
{
  "tea_to_user_id": 2,
  "deposit_to_user_id": 3,
  "tea_method": "wechat",
  "deposit_method": "wechat",
  "note": "交给晚班"
}
```

- 茶水营业款只能上缴给本店管理员；押金余额可以交给本店任意启用账号
- 只有当前保管人能交班，否则 400
- `tea_method` / `deposit_method`：`wechat / alipay / cash / bank / other`
- 交班后 `custodian_user_id` 切换为押金接收人，并在 `cash_handovers` 留一条交接记录

批次详情还会返回 `dividend_rate_percent`、`operators`（按建局人统计局数/人次/茶水/分红）、
`handover`（交班交接记录）、`custody`（当前保管人与在库现金）。

汇总字段：`session_count, player_times, tea_total_cents, add_total_cents, refund_total_cents,
transfer_out_total_cents, transfer_count, net_change_cents, deposit_total_cents,
opening_total_cents`。

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
| GET | `/overview` | 玩家押金余额、在用玩家、低押金人数、**本班统计**、在库现金/保管人、最近 10 条 |
| GET | `/reconcile` | 对账，仅管理员 |
| GET | `/settings` | 读设置，含 `dividend_rate_percent` |
| PATCH | `/settings` | 改设置，仅管理员；分红比例 0~100 |
| POST | `/ai/recognize-players` | 本期固定 501（AI 识别占位） |

## 约定

- 时间格式 `2026-10-30T20:04:12+08:00`，字典序即时间序。
- 日期范围参数用 `YYYY-MM-DD`，按中国时区算起止。
- 分页返回 `{items, total, page, page_size}`，`page_size` 上限 200。
- 所有写操作都记 `operator_id`；`ledger` 里还存了 `balance_before/after` 快照。
- 商家隔离：所有查询都带 `merchant_id`，跨商家访问返回 404；`/settings` 的 `shop_name` 就是商家名（存在 `merchants.name`）。
- 账号停用、角色变更、商家停用都立即生效（每次请求重新查库），不用等令牌过期。
