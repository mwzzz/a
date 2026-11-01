# LOL 记录管理

开黑场次 + 押金记账的 Web 系统。一套程序服务多个商家，**每家数据互相隔离**，店内多个店员共用本店数据，按班次（批次）对账，部署在自有服务器上。

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
../.venv/Scripts/python -m app.cli init-db            # 建表 + 默认商家
../.venv/Scripts/python -m app.cli create-admin --username admin --merchant 默认商家
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

## 测试

```bash
cd backend
../.venv/Scripts/python -m pytest tests -q
```

覆盖金额规则、事务回滚、余额恒等式、批次快照、权限、并发不丢更新，以及**跨商家越权隔离**和 v1→v2 迁移。

## 目录

```
backend/app
├── api/         路由（auth/users/players/deposits/batches/sessions/records/overview/settings/ai）
├── services/    业务规则（money/players/deposits/batches/sessions/records/reports/reconcile/options）
├── models.py    SQLAlchemy 模型（含 Merchant）
├── migrations.py 建表 DDL + v1→v2 迁移（唯一结构来源）
├── scope.py     商家作用域助手（越权统一 404）
├── db.py        读写两个 engine，写事务 BEGIN IMMEDIATE
└── cli.py       建库、建商家、建账号、重置密码
frontend/src
├── views/       总览、场次、玩家、记录、账本、设置
├── components/  玩家弹窗、场次弹窗、通用组件
└── api/         接口封装与类型
deploy/          systemd、nginx、备份、安装与上传脚本
```

## 关键规则

- 金额一律整数分存储，界面两位小数；前端字符串解析，不做浮点乘法。
- 开局每人扣相同茶水，允许扣成负数；退押金不能超过余额。
- 划转两边各一条流水，共用 `transfer_group_id`；可以划成负数（前端二次确认）。
- 押金颜色：低于 30 元红、30~60 元黄、高于 60 元绿（阈值可在设置里改）。
- 玩家软删除，押金必须为 0，流水永久保留。
- **每个商家**同时只能有一个进行中的批次；交班后该批次不能再开局。
- 关班时把汇总写进快照，并在同一事务里跑本商家对账，不一致直接回滚。
- 账号绑定唯一商家，用户名全平台唯一；玩家、批次、场次、流水、设置、导出、对账全部按商家隔离。
- 访问别家数据一律返回 404（不暴露存在性），划转只能在同商家内进行。

## 部署

见 [deploy/部署说明.md](deploy/部署说明.md)。改完代码在本机跑：

```bash
bash deploy/push.sh
```

## 这一期没做

AI 截图识别（只留入口和 501 接口）、玩家自助端、手机适配、跨商家汇总看板、商家自助注册与计费、撤销已确认开局、每人不同金额、按时长计费、HTTPS/域名。
