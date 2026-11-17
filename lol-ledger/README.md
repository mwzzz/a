# LOL 记录管理

开黑场次 + 押金记账的 Web 系统。一套程序服务多个商家，**每家数据互相隔离**，店内多个店员共用本店数据，按日期区间对账（无开班/交班），部署在自有服务器上。

## 技术栈

- 后端：FastAPI + SQLAlchemy 2.0 + SQLite(WAL) + JWT，Python 3.11
- 前端：Vue 3 + Vite + TypeScript + Element Plus（暗色）
- 部署：nginx `:80` 静态托管 + `/api` 反代 uvicorn `127.0.0.1:8010`

## 本地开发

```bash
# 后端
cd backend
python -m venv ../.venv
../.venv/Scripts/pip install -r requirements.txt     # Windows
# source ../.venv/bin/activate && pip install -r requirements.txt   # macOS/Linux

cp .env.example .env                                  # 改掉 JWT_SECRET
../.venv/Scripts/python -m app.cli init-db            # 建表 + 默认商家 + 平台商家
../.venv/Scripts/python -m app.cli create-superadmin --username admin   # 开发者账号
../.venv/Scripts/python -m app.cli create-admin --username shop-boss --merchant 默认商家
../.venv/Scripts/python -m app.cli create-merchant --name "极光电竞"   # 需要多商家时
../.venv/Scripts/python -m uvicorn app.main:app --reload --port 8010

# 前端（另开一个终端）
cd frontend
npm install
npm run dev                                           # http://localhost:5173
```

开发时 `DEBUG=true` 会打开 `/docs` 和跨域；生产默认关闭。

演示数据（可选，只在本地看界面用）：

```bash
cd backend
DB_PATH=data/dev.db python tools/seed_demo.py
```

## 开发者账号（平台管理）

开发者账号（`users.is_superadmin = 1`）只有你本人使用，挂在隐藏的「平台管理」系统商家下，不参与任何门店经营：

- 登录后自动进入「平台管理」，看不到总览、场次、玩家等门店页面
- 可以开通 / 改名 / 停用商家，可以给任意商家建管理员和店员、改角色、启停、重置密码
- 商家管理员看不到也改不了开发者账号；开发者账号也不能在平台里改自己（改密码走右上角）
- 每个商家至少保留一个启用的管理员，最后一个不能降级或停用

首次引导（只需一次，密码交互输入；已有同名账号会被升级并迁到平台商家）：

```bash
cd /opt/lol-ledger/backend
sudo -u lol env DB_PATH=/opt/lol-ledger/data/ledger.db \
  /opt/lol-ledger/venv/bin/python -m app.cli create-superadmin --username admin
```

之后商家和账号都在网页里点，不用再敲命令。如果同名账号是某店唯一的管理员，命令会拒绝，先给该店补一个管理员或换个用户名。

## AI 截图识别玩家

「新增场次」里支持粘贴/拖入 LoL 对局截图，自动识别双方玩家名并匹配本店玩家库。识别结果只作为候选，必须点「填入玩家」才会写入场次；不会自动建房或扣茶水。

配置（只放服务端，绝不提交）：

```bash
AI_ENABLED=true
AI_API_KEY=sk-你的key
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-flash
AI_TIMEOUT_SECONDS=25
# 仅千问等混合思考模型需要：AI_ENABLE_THINKING=false 关闭思考
```

本地写 `backend/.env`，生产写 `/opt/lol-ledger/.env` 后重启服务。`AI_ENABLED=false` 或没有 Key 时，前端显示「AI 识别未启用」，手动选人不受影响。

实现要点：
- 后端代理调用 DeepSeek，Key 不出现在前端；图片只在内存转发，不落盘。
- 单图 ≤5MB，每用户 10 次/分钟；超时 25 秒自动降级。
- 只有精确匹配才默认勾选；模糊匹配给候选，由人确认；未匹配可一键新建玩家。
- AI 结果不会自动覆盖已选玩家：先填空位，空位不足时二次确认。

## 测试

```bash
cd backend
../.venv/Scripts/pip install -r requirements-dev.txt   # 含生成 .xls 测试文件的 xlwt
../.venv/Scripts/python -m pytest tests -q
```

覆盖金额规则、事务回滚、余额恒等式、批次快照、现金交接、操作人分红、分红结算、Excel 批量导入、权限、并发不丢更新，以及**跨商家越权隔离**和 v2/v3/v4→v5 迁移。

## 目录

```
backend/app
├── api/         路由（auth/users/platform/players/deposits/batches/sessions/records/overview/settings/ai）
├── services/    业务规则（money/players/deposits/batches/sessions/records/reports/reconcile/options/platform/ai）
├── models.py    SQLAlchemy 模型（含 Merchant / User / CashHandover）
├── migrations.py 建表 DDL + v1~v4→v5 迁移（唯一结构来源，含分红结算表）
├── scope.py     商家作用域助手（越权统一 404）
├── db.py        读写两个 engine，写事务 BEGIN IMMEDIATE
└── cli.py       建库、建商家、建账号、引导开发者账号、重置密码
frontend/src
├── views/       总览、场次、玩家、记录、账本、分红结算、设置、小工具（排队登记）、平台管理
├── components/  玩家弹窗、场次弹窗、通用组件
└── api/         接口封装与类型
deploy/          systemd、nginx、备份、安装与上传脚本
```

## 关键规则

- 金额一律整数分存储，界面两位小数；前端字符串解析，不做浮点乘法。
- 开局每人扣相同茶水，允许扣成负数；退押金不能超过现金押金。手动扣押已取消，历史数据并入退押金。
- 划转两边各一条流水，共用 `transfer_group_id`；可以划成负数（前端二次确认）。
- 管理员可在「设置 → 充值活动」配置多档「充 X 送 Y」；加押金自动按最高档送赠金，导入玩家不触发。
- 赠金只能扣茶水，不能退款或划押；扣茶水先扣赠金再扣现金。有赠金时禁止退款，赠金为 0 后可正常退现金。
- 有赠金时玩家显示「总余额（押金 现金部分）」，押金颜色、押金不足提醒和排序都按总余额判断，负数标红。
- 押金颜色：低于 30 元红、30~60 元黄、高于 60 元绿（阈值可在设置里改）。
- 玩家软删除，现金押金和赠金都必须为 0，流水永久保留。
- 玩家支持 Excel 批量导入（仅 `.xls/.xlsx`，第一列玩家 id、第二列押金）；整批校验通过才写入，不做部分导入。
- 不设班次：场次直接记在商家名下，按日期区间统计；没有开班/交班操作，钱统一由店长保管。
- 关班时把汇总写进快照，并在同一事务里跑本商家对账，不一致直接回滚。
- 「汇总」按日期区间统计每位店员的：新增场次、人次、茶水、收押金、退押金。**差额 = 收押金 − 退押金**，正数是店员应交、负数是店长应补；划转不计入。
- 分红支持两种方式（管理员在设置里选）：按茶水比例（默认 50%）或每局固定金额，按区间统计，结算后该区间不再重复结算。
- 账号绑定唯一商家，用户名全平台唯一；玩家、批次、场次、流水、设置、导出、对账全部按商家隔离。
- 访问别家数据一律返回 404（不暴露存在性），划转只能在同商家内进行。
- 开发者账号是唯一的例外：只跨商家管商家和账号，不读门店经营数据，也不出现在任何门店的账号列表里。
- 平台管理支持「清空数据」：删除该店玩家、班次、场次、押金流水、现金交接与分红结算，保留账号、店铺设置和店名；删除前自动整库备份到 `data/backups/pre-purge-*.db`，并要求逐字输入商家名确认。
- 「小工具」是可扩展的工具入口：**排队登记**（登记等位、叫号、一键生成排队阵容图发群）和**常用名单**（打手 / 免茶水 / 每天up / 免押金，分类和条目都能改）。
- 玩家列表默认按**押金升序**，欠费的人排最前面；汇总、流水、分红的时间筛选**精确到分钟**。

## 文档

- [店员操作手册](docs/店员操作手册.md)：开一局、对账、分红怎么看，带截图
- [业务规则](docs/规则.md)：金额、押金、对账差额、分红的计算口径
- [接口文档](docs/API.md)
- [部署说明](deploy/部署说明.md)

## 部署

见 [deploy/部署说明.md](deploy/部署说明.md)。目标是阿里云 ECS `116.62.242.2`。改完代码在本机跑：

```bash
# Windows
powershell -ExecutionPolicy Bypass -File deploy/push.ps1

# Git Bash / macOS / Linux
bash deploy/push.sh
```

## 这一期没做

玩家自助端、跨商家汇总看板、商家自助注册与计费、撤销已确认开局、每人不同金额、按时长计费、HTTPS/域名。
