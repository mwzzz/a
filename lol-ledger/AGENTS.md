# AGENTS.md

给 AI 编码助手的开工说明。**改代码前先读完这一页**，它只写「不知道就会写错或搞坏数据」的事，其余看文档索引。

## 这是什么

网吧 / 电竞馆的开黑记账系统：记录每局游戏、玩家押金流水、店员分红与对账。
一套程序服务多个商家，**每家数据互相隔离**，店内多个店员共用本店数据。已经在真实门店跑生产数据。

## 红线（违反任何一条都要停下来问人）

1. **不碰生产库**。需要看数据只能 `sqlite3 .backup` 出只读快照，再在副本上分析。任何 `UPDATE/DELETE/INSERT` 打到线上都不允许。
2. **发布和回滚必须用户点头**。`deploy/` 下有 `push.ps1`、`rollback.sh`，能力清楚但不要自己执行；命令细节见 `deploy/部署说明.md`。
3. **迁移必须先确认是不是破坏性的**。v8 那次取消班次时清空过场次与班次历史（后来靠备份恢复）。新增迁移前先读 `migrations.py` 里对应函数，确认删了什么。
4. **不改 `audit_logs`**，不改历史分红结算记录，不手工改 `players.deposit_cents`（余额必须由流水推导）。
5. `.env`、SSH 私钥、任何账号密码与密钥，不进仓库、不进日志、不写进文档。
6. 不删 `.codebuddy/`。

## 开发与上线边界

- 所有代码修改和测试只在本机 `lol-ledger` 工作区进行。
- 未经用户明确说「上线 / 发布 / 同步服务器」，不得执行任何 `deploy/` 脚本，不得上传或替换服务器代码、`frontend/dist`。
- 服务器只允许只读排查；需要写服务器时必须先得到用户明确同意。

## 技术栈与目录

- 后端：FastAPI + SQLAlchemy 2.0 + SQLite（WAL），schema 版本化迁移，当前 **v15**
- 前端：Vue 3 + TypeScript + Element Plus + Pinia + Vite
- 目录：`backend/app`（`api/` 路由、`services/` 业务、`migrations.py` 建表与迁移）、`backend/tests`、`frontend/src`（`views/` 页面、`api/` 请求与类型）、`deploy/`、`docs/`

## 本地开发

```bash
# 后端（首次需 python -m venv .venv 并安装 backend/requirements.txt）
cd backend && DB_PATH=data/dev.db python -m app.cli init-db
DB_PATH=data/dev.db python -m uvicorn app.main:app --reload --port 8010

# 前端（代理默认指向 127.0.0.1:8010，见 frontend/vite.config.ts）
cd frontend && npm run dev

# 用生产数据副本开发（不碰线上）
powershell -File deploy/dev-from-backup.ps1              # 只准备数据
powershell -File deploy/dev-from-backup.ps1 -Run         # 直接起后端
```

提交前必须全绿：

```bash
cd backend && python -m pytest -q          # 后端全部用例
cd frontend && npm run typecheck && npm run build
```

**改完需求、本地测试全绿后，不要把服务停掉**：保持后端（8010）和前端 `npm run dev` 运行，交给用户手动点开页面验证。用户确认没问题之前，服务一直开着。
启动前先把遗留的旧后端和多余 vite 进程清掉（否则新接口会报假 404、端口被占）。

## 业务口径（最容易写错的地方）

| 概念 | 口径 |
| --- | --- |
| 金额 | 一律**整数分**，字段名带 `_cents`，展示时再除 100 |
| 茶水 | `sessions.tea_fee_cents` 是**每人**茶水，一局总额 = 每人 × `player_count` |
| 分红 | 两种模式：`percent`（茶水总额 × 比例）/ `fixed`（局数 × 每局金额），存在 `merchant_settings` |
| 差额 | 收押金 − 退押金，按 `operator_id` 汇总；**正数=店员应交，负数=店长应补**，划转不计入 |
| 时间归属 | 场次按 `played_at`，押金与分红按 `created_at`；统一东八区，字符串字典序即时序 |
| 赠金 | `players.bonus_cents`，只能被 `normal_deduct` 扣茶水消耗，先扣赠金再扣现金；不能退款、不能划押。误加的赠金可由管理员或店员撤销（reason `bonus_void`，写一条反向流水只回退赠金、不动现金），仅限**未被茶水消耗且未撤销过**的 `add_bonus` 流水；已被茶水消耗撤不掉时，**仅门店管理员**可对玩家一键删除全部剩余赠金（`POST /players/{id}/bonus/delete`，同样写 `bonus_void`，只清赠金、不动现金） |
| 充值活动 | `recharge_campaigns` 按商家配置多档，加押金自动取满足金额的最高档送一次；Excel 导入不触发 |
| 余额 | 现金 `players.deposit_cents` = 现金流水净额 = 末条 `deposit_after_cents`；赠金 `players.bonus_cents` = 赠金流水净额 = 末条 `bonus_after_cents`；界面总余额 = 两者相加 |
| 分红幂等 | **每一局只结算一次**：结算时把区间内未认领的场次逐局写进 `dividend_settlement_sessions`（未冲销行里 `session_id` 唯一，DB 级防重复发钱）；区间重叠不再整段清零。历史记录只存到日期，比较前统一用 `timeutil.bound_start_text` / `bound_end_text` 归一化 |
| 撤回一局 | 「场次记录」每行可「撤回」（**开这局的本人或门店管理员**）：删除该场 + 其 `session_players` 与 `normal_deduct` 流水，退回押金/赠金、局数 −1，**不写加押/退押、不影响操作人差额**，无迁移。护栏：该局**从未被任何分红结算认领**（含已冲销）、且这局扣费是**每位参与者当前最新一笔流水**，否则拒绝；这是**唯一允许删除流水行**的场景 |
| 发工资 | v15。店长在汇总页按区间一键给每人发工资：金额=本人 `dividend_cents`（服务端重算，与生成工资汇总一致），加押金到绑定的工资账户（`users.salary_player_id`），**`apply_campaign=False` 不触发充值活动赠金**；`salary_payments` 每人每「工资日」（区间开始日）只一条未冲销记录（DB 唯一索引防重复发），可整批撤销（退押金，受余额/赠金规则限制）；仅门店管理员可用 |

对账不通过（`/api/v1/reconcile`）说明有人绕过接口改过余额，找管理员，不要自行修数据。

## 数据与迁移

- 表结构以 `backend/app/migrations.py` 为准，模型只是映射；`SCHEMA_VERSION` 每次加表 / 加列都要 +1。
- 每个 `_upgrade_vN_to_vM` 的结构：`_backup(conn, db_path, "pre-vM")` → `PRAGMA foreign_keys=OFF` → `BEGIN IMMEDIATE` → 改表 → `PRAGMA user_version = M` → `_assert_foreign_keys` → `COMMIT`。
- 迁移必须幂等（`IF NOT EXISTS`、判重后再插），测试里的 `_ddl_for(version)` 要同步加「旧版本跳过新表」的分支。
- 事务边界由 `deps.get_write_db` 控制，服务层用 `session.flush()`，不要自己 `commit()`。

## 已知坑（踩过一次就别再踩）

- **备份不能用 `cp`**：WAL 模式下直接复制会得到不一致副本，必须 `sqlite3 db ".backup out.db"`。
- **`deploy/*.sh` 必须 755**：权限掉了 systemd 报 `status=203/EXEC`，备份会静默失败。
- **PowerShell 脚本存 UTF-8 with BOM**：PS 5.1 按 GBK 读会报语法错。
- **前端 `el-date-picker` 用 `value-format="YYYY-MM-DDTHH:mm:ss"`**（汇总/报表/分红结算都精确到秒），后端 `timeutil.moment_bounds` 同时吃纯日期、分钟和秒。
- **区间右边界一律走 `timeutil.parse_end_moment`/`bound_end_text`**：纯日期补 `23:59:59`、分钟补 `:59`、秒原样。自己 `parse_moment(date_to)` 会把分钟边界变成 `23:59:00`，那一分钟的场次两头都不在任何区间里。秒精度下相邻区间要从「上一段结束 +1 秒」起，否则同一秒的场次被两段都算。
- 单机 1.6G 内存，别起多余进程；uvicorn 单 worker 足够。

## 历史包袱（不要试图「修好」，先问）

- **v8 取消了开班/交班**，`sessions.batch_id` 已删除，场次与班次的归属**永久丢失**；`batches` 表残留 6 条孤儿数据，新代码完全不读它。
- **v9 的查战绩（`zj_*` 五张表、`api/zj*.py`）是另一个会话加的模块**，与记账主流程无关，改别的功能时别动。
- v14 之前那两条历史分红结算（`11-01~11-05` 极光电竞、`11-01~11-06` 面包人）曾把同区间的人整段跳过；v14 迁移已把它们按场次回填成认领记录，之后补录进同区间的局回到待结算。**不要**再手工改这两行或删认领记录。
- `services/batches.py` 已随死代码清理删除；`services/custody.py` 只剩 `is_holder()`，仍在用（停用账号时拦截当前保管人），不是死代码。

## 小工具约定

`frontend/src/views/ToolsView.vue` 是工具入口，加新工具 = 加一张卡片 + 一个 `/tools/xxx` 路由 + 一个 `services/xxx.py`。
已有：排队登记（`/tools/queue`）、常用名单（`/tools/name-lists`）。

## 文档索引

| 文件 | 什么时候看 |
| --- | --- |
| `README.md` | 项目全貌、功能清单 |
| `docs/规则.md` | 改业务逻辑前，金额与统计口径 |
| `docs/API.md` | 加接口、改参数 |
| `deploy/部署说明.md` | 部署、备份、回滚、恢复（含所有连接信息） |
| `docs/店员操作手册.md` | 需求里的「店员怎么用」 |

## 改完记得

- 加表 / 加页面 / 加小工具时，同步更新本文件的「技术栈与目录」「小工具约定」对应段落。
- 动了业务口径，同步 `docs/规则.md` 与相关测试；口径只写在代码里等于没写。
- 不写「临时脚本」留在仓库：分析用的脚本用完就删。
