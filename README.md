# 通信基站运维管理平台

面向通信基站站点入网、动力环境监控、天馈巡检、发电保障与退网拆站的一体化基站运维管理后台。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/            每个业务模块一个页面
│   ├── src/api/              统一请求封装
│   ├── src/stores/           会话与筛选状态
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/          每个业务模块一组接口
│   ├── app/services/         业务规则与状态流转
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8000/api/health`

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 `http://127.0.0.1:5173/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8000`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 基站台账 | `site` | 基站 | 基站编号、基站名称、基站类型 |
| 铁塔管理 | `tower` | 铁塔 | 铁塔编号、铁塔类型、设计高度 |
| 动力配套 | `power` | 电源设备 | 设备编号、设备类型、额定功率 |
| 蓄电池组 | `battery` | 蓄电池组 | 电池组编号、电池类型、额定容量 |
| 发电机组 | `genset` | 发电机组 | 机组编号、机组型号、额定功率 |
| 开关电源 | `rectifier` | 开关电源 | 电源编号、额定功率、所属站点 |
| 空调管理 | `ac` | 空调 | 空调编号、空调类型、制冷量 |
| 天馈系统 | `antenna` | 天馈设备 | 天馈编号、天线类型、工作频段 |
| 传输设备 | `transmission` | 传输设备 | 设备编号、传输类型、带宽容量 |
| 馈线巡检 | `feeder` | 馈线 | 馈线编号、所属站点、馈线长度 |
| 防雷接地 | `lightningprot` | 防雷装置 | 装置编号、所属站点、接地电阻 |
| 消防设施 | `firealarm` | 消防设施 | 设施编号、设施类型、所属站点 |
| 门禁管理 | `dooraccess` | 门禁记录 | 门禁编号、所属站点、开门方式 |
| 巡检作业 | `patrol` | 巡检任务 | 任务编号、巡检站点、巡检人员 |
| 油料管理 | `fuel` | 油料记录 | 记录编号、所属站点、油料类型 |
| 场租合同 | `rental` | 场租合同 | 合同编号、站点名称、出租方 |
| 电费管理 | `electricbill` | 电费记录 | 记录编号、所属站点、电表读数 |
| 拆站管理 | `demolition` | 拆站任务 | 任务编号、拆除站点、拆除原因 |
| 应急通信 | `emergency` | 应急保障 | 保障编号、保障类型、保障地点 |
| 节能改造 | `energyeff` | 节能项目 | 项目编号、所属站点、改造内容 |

## 约定

- 每个模块的前端页面在 `frontend/src/views/<模块>/index.vue`，后端接口在
  `backend/app/routers/<模块>.py`，业务规则在 `backend/app/services/<模块>.py`。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。

## 拆站物资回收

拆站任务自带物资清单（物资类别、登记数量、单价），拆除中可批量登记回收：

- `POST /api/demolition/{id}/recycling`：一次提交多行物资（`values.items`），逐行校验
  回收数量与去向；缺去向等不合格行按行号退回（`rejected`），其余照常落记录（`settled`）。
- 回收数量少于登记数量时必须填差异说明；回收款按类别单价结算，同一批物资重复登记
  只结算一次（已登记类别再次提交会被退回）。
- 物资回收没登记完的任务执行「回收完成」会被拦下，不能标为已拆除；登记中断后重新
  打开面板会从第一个未登记的类别接着填。
- 回收结论写回拆站台账的「物资回收」字段，`GET /api/demolition/recycling` 返回
  物资去向清单，每登记一条清单里跟着多出一条。
