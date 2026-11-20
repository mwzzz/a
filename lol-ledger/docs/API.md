# 接口说明

统一前缀 `/api/v1`。除 `POST /auth/login` 和 `GET /api/health` 外都要带：

```
Authorization: Bearer <access_token>
```

金额字段一律是**整数分**，字段名以 `_cents` 结尾。错误统一返回 `{"detail": "中文提示"}`：
业务错误 400、未登录/过期 401、越权 403、不存在 404、登录试错过多 429。

所有业务接口都会自动按**当前账号所属商家**过滤，请求体不需要也不能传 `merchant_id`。
用别家的 id 访问玩家、场次、流水、账号，一律返回 **404**（不暴露数据是否存在）。

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
        "id": 12, "game_id": "山中刘德华、", "account": "",
        "deposit_cents": 5000, "is_blacklisted": false
      },
      "candidates": []
    }
  ],
  "count": 9,
  "warnings": ["识别到 9 个玩家，请确认是否完整"],
  "elapsed_ms": 3800
}
```

- `status`：`matched` 匹配（精确或相似度 ≥0.8）/ `ambiguous` 需要人工选候选 / `unmatched` 未匹配
- 只匹配当前商家未删除玩家，不写任何业务数据
- 每用户 10 次/分钟；超时 25 秒；未配置或模型异常时返回 503/504/502，前端降级为手动选人
- 模糊候选阈值 0.72，最多 3 个；相似度 ≥0.8 直接按匹配返回；`名字#tag` 会兼容匹配

## 平台（仅开发者账号）

开发者账号（`is_superadmin = 1`）挂在隐藏的「平台管理」系统商家下，只能管商家和账号，不读门店经营数据。
非开发者账号访问这些路径一律 **403**；平台商家本身不可改名/停用（404）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/platform/merchants` | 所有商家（不含平台商家），带 `user_count`、`player_count` |
| POST | `/platform/merchants` | `{name, note?, admin_username?, admin_password?, admin_display_name?}`，可同时建第一个管理员 |
| PATCH | `/platform/merchants/{id}` | 改 `name` / `note` / `status(active/disabled)`；停用后该店账号立即无法登录 |
| GET | `/platform/merchants/{id}/purge-preview` | 清空前预览：各表将删除的行数、当前在库现金、保留项、风险提示。只读 |
| POST | `/platform/merchants/{id}/purge` | `{confirm_name, note?}`，清空该店玩家/场次/流水/分红结算（旧版班次、交接残留一并清理）；`confirm_name` 必须与商家名完全一致，删除前自动整库备份，写审计 |
| GET | `/platform/merchants/{id}/users` | 指定商家的账号（不含开发者账号） |
| POST | `/platform/merchants/{id}/users` | `{username, password, display_name?, role}`，商家停用时拒绝 |
| PATCH | `/platform/users/{id}` | 改显示名 / 角色 / 启停；最后一个启用的管理员不能降级或停用 |
| POST | `/platform/users/{id}/password` | 重置密码；目标为开发者账号时 404 |

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
| GET | `/players` | `keyword, level(low/warn/safe), sort, blacklisted(true/false), page, page_size` |
| GET | `/players/options` | `keyword, exclude_ids=1,2, limit`，给下拉框用，返回含 `is_blacklisted`、`deposit_cents`、`bonus_cents`、`balance_cents` |
| POST | `/players` | `{game_id, account?, remark?, is_blacklisted?}` |
| POST | `/players/import` | `multipart/form-data`，字段 `file`；仅 `.xls/.xlsx`，第一列玩家 id，第二列押金（元，可空）；导入不触发充值活动 |
| GET | `/players/export` | 导出玩家库 `.xlsx`，两列：游戏名、押金(元)；押金只含现金部分，当前商家全部未删除玩家 |
| GET | `/players/{id}` | 详情，含现金押金、赠金、总余额、累计充值/支出 |
| PATCH | `/players/{id}` | 改游戏名 / 段位 / 备注 / 黑名单标记 `is_blacklisted` |
| DELETE | `/players/{id}` | 软删除，现金押金和赠金都必须为 0，仅管理员 |
| GET | `/players/{id}/ledger` | 个人流水，分页 |

`account` 字段现在用于存段位（常玩位置），例如「钻石II / 中单、打野」；前端表单、玩家列表和 AI 识别结果都按「段位」展示。

`sort` 可选：`games_played_desc`（默认）、`deposit_desc`、`deposit_asc`、`last_active_desc`、`game_id_asc`。

批量导入说明：取第一个工作表，第一行可以是表头；押金按元转成分，最多两位小数；整批校验通过才写入，任何一行重复/非法都会返回 400 和 `errors: [{row, message}]`，不会导入一半。单文件上限 5MB、1000 行。

## 押金

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/players/{id}/deposits` | 加押金，`{amount_cents, note?}`，必须 > 0；命中充值活动时同事务追加 `add_bonus` 流水，返回 `{entry, bonus_entry, campaign, player}` |
| POST | `/players/{id}/bonus` | 手动加赠金，`{amount_cents, note?}`，必须 > 0；管理员和店员都可用 |
| POST | `/ledger/entries/{entry_id}/void-bonus` | 撤销一笔误加的赠金，`{note?}`，**管理员和店员都可用**；写一条反向 `bonus_void` 流水只回退赠金、不动现金；要求该笔 `add_bonus` 未被茶水消耗且未撤销过，否则 400；跨商家 404 |
| POST | `/players/{id}/refunds` | 退押金，不能超过现金押金；玩家有赠金时拒绝，赠金为 0 后才能退 |
| POST | `/transfers` | `{from_player_id, to_player_id, amount_cents, note?}`；只动现金押金，有赠金时不能超过现金部分 |

手动扣押已取消，历史数据在 v4 迁移时并入 `refund`。

玩家对象金额字段：

- `deposit_cents`：现金押金，可退款/划押；
- `bonus_cents`：赠金，只能扣茶水；
- `balance_cents = deposit_cents + bonus_cents`：界面显示的总余额。

流水新增 `bonus_amount_cents`（本笔赠金抵扣额）、`deposit_after_cents`（变动后现金）、`bonus_after_cents`（变动后赠金）；`balance_after_cents` 为总余额。`reason` 取值集合含 `bonus_void`（撤销加赠金，赠金减少、现金不变），撤销流水用 `reverses_ledger_id` 指回被撤销的 `add_bonus` 行；`/records/deposits` 与玩家流水里的 `add_bonus` 行会带 `voided`（是否已被撤销）。

流水 `reason` 取值：`add_deposit`、`add_bonus`、`bonus_void`、`normal_deduct`、`refund`、`transfer_out`、`transfer_in`。

返回 `{entry, player}`；加押金命中活动时还返回 `bonus_entry` 和 `campaign`。`entry.reason_label` 已经拼好中文（划转带对手名和箭头）。

## 场次

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/sessions` | `keyword, date_from, date_to, page, page_size` |
| POST | `/sessions/preview` | `{player_ids, tea_fee_cents}` → 每人扣前/扣后/是否变负 |
| POST | `/sessions` | `{name?, played_at?, note?, tea_fee_cents, player_ids}` |
| GET | `/sessions/{id}` | 场次详情，含每人扣费 |

规则：1~10 人、自动去重、每人扣相同茶水、允许扣成负数、整局一个事务。常用名单「免茶水」分类里的玩家会被自动排除（按游戏 id，忽略 `#后缀` 和大小写）；黑名单玩家不能开局，返回 400。

## 记录与总览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/records/deposits` | `keyword, player_id, session_id, operator_id, reason, date_from, date_to, sort, page, page_size` |
| GET | `/records/sessions` | 场次记录，支持 `operator_id` |
| GET | `/records/operators` | 本店操作人（含已停用），供筛选下拉 |
| GET | `/records/operator-summary` | `operator_id, date_from, date_to`；返回收押金、退押金、差额、笔数，划转不计入 |
| GET | `/records/transfers/{group_id}` | 一笔划转的两条流水 |
| GET | `/overview` | 现金押金合计、赠金合计、在用玩家、低押金人数、今日统计、最近 10 条 |
| GET | `/reconcile` | 对账，仅管理员；同时校验现金押金和赠金两条恒等式 |
| GET | `/settings` | 读设置，含 `dividend_rate_percent`、`dividend_mode`、`dividend_fixed_cents` |
| PATCH | `/settings` | 改设置，仅管理员；`dividend_rate_percent` 0~100；`dividend_mode` 为 `percent`/`fixed`；`dividend_fixed_cents` 0~1000000，`fixed` 模式下必须大于 0 |
| GET | `/settings/recharge-campaigns` | 充值活动档位列表，任意登录账号可读 |
| POST | `/settings/recharge-campaigns` | 新增档位 `{threshold_cents, bonus_cents}`，仅管理员 |
| PATCH | `/settings/recharge-campaigns/{id}` | 修改档位，仅管理员 |
| DELETE | `/settings/recharge-campaigns/{id}` | 删除档位，仅管理员；已产生的赠金流水不变 |

## 小工具 · 排队登记（店员和管理员都可用）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/queue` | `day=YYYY-MM-DD`（默认今天）；返回 `entries`（按登记先后）、`counts`（waiting/playing/done/cancelled）、`shop_name` |
| GET | `/queue/snapshot` | 生成阵容图用的同一份数据，字段与 `/queue` 一致 |
| POST | `/queue` | `{game_id, note?}`；同一天同一名字在排队中/进行中时不能重复登记（400） |
| PATCH | `/queue/{id}` | `{status}`；只允许 `waiting→playing/cancelled`、`playing→done/cancelled`，其余 400 |

状态：`waiting` 排队中、`playing` 上机中、`done` 已完成、`cancelled` 已取消。日期按 `created_at` 的自然日（东八区）过滤。

## 小工具 · 常用名单（店员和管理员都可用）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/tools/name-lists` | 全部分类及其条目（按 `sort_order` 排好） |
| POST | `/tools/name-lists` | `{name}` 新建分类，同店重名返回 400 |
| PATCH | `/tools/name-lists/{id}` | `{name}` 改名 |
| DELETE | `/tools/name-lists/{id}` | 删分类，连同条目一起删 |
| POST | `/tools/name-lists/{id}/move` | `{direction: up\|down}` 调整分类顺序 |
| POST | `/tools/name-lists/{id}/items` | `{content, note?}` 新增条目 |
| PATCH | `/tools/name-lists/{id}/items/{item_id}` | `{content?, note?}` 修改条目 |
| DELETE | `/tools/name-lists/{id}/items/{item_id}` | 删除条目 |
| POST | `/tools/name-lists/{id}/items/{item_id}/move` | `{direction}` 调整条目顺序 |

新商家会自动预置「打手 / 免茶水 / 每天up / 免押金」四类及条目。

## 时间参数（重要）

`date_from` / `date_to` 同时接受两种写法，后端统一成带 `+08:00` 的闭区间：

- `2026-11-06`：当天 00:00:00 至 23:59:59
- `2026-11-06T09:30` 或 `2026-11-06 09:30`：精确到该分钟

涉及接口：`/summary/operators`、`/records/*`、`/sessions`、`/reports/dividends/*`。

右边界一律补到该精度的最后一秒：`2026-11-06` → `23:59:59`，`2026-11-06T09:30` → `09:30:59`。

## 分红结算的幂等口径（重要）

幂等发生在**场次**上，不在区间上：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/reports/dividends/preview` | 返回区间内每位操作人「未被认领」的场次与分红；`totals.claimed_session_count` 是本区间已结算过的局数 |
| POST | `/reports/dividends/settle` | 结算并逐局写入 `dividend_settlement_sessions`；未冲销的认领行里 `session_id` 唯一（DB 级唯一索引），同一局不可能发两次 |
| GET | `/reports/dividends/settlements?status=all\|live\|voided` | 结算记录；每行带 `status`、`voided_at/by`、`void_note`、`claimed_session_count` |
| POST | `/reports/dividends/settlements/{id}/void` | `{note}`，仅管理员。软冲销：把该笔结算的金额保持原样、只标记 `voided_at`，同时释放它认领的场次回到待结算，写审计 `dividend_settlement_void` |

因此区间重叠不再返回 0：已发过的局被跳过，剩下的（含结算之后补录进同一区间的）照常待结。历史结算行只存到日期时，比较前用 `timeutil.bound_start_text` / `bound_end_text` 归一化；解析不了的行跳过，不影响整页。

## 约定

- 时间格式 `2026-10-30T20:04:12+08:00`，字典序即时间序。
- 日期范围参数用 `YYYY-MM-DD`，按中国时区算起止。
- 分页返回 `{items, total, page, page_size}`，`page_size` 上限 200。
- 所有写操作都记 `operator_id`；`ledger` 里还存了 `balance_before/after` 快照。
- 商家隔离：所有查询都带 `merchant_id`，跨商家访问返回 404；`/settings` 的 `shop_name` 就是商家名（存在 `merchants.name`）。
- 账号停用、角色变更、商家停用都立即生效（每次请求重新查库），不用等令牌过期。
