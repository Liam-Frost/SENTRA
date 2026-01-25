# SENTRA Front端

这是 SENTRA（Self-Governing Autonomous Data Center System）原型的前端控制台：用于展示 3 台模拟服务器（S1/S2/S3）的实时遥测、事件时间线，以及触发仿真操作（tick、注入故障、重置、切换自治）。

## 技术栈

- React 18 + TypeScript
- Vite 5
- TailwindCSS（配合 `src/index.css` 的 CSS 变量与组件样式）

## 本地运行

在 `frontend/` 下：

```bash
npm install
npm run dev
```

默认地址：`http://localhost:5173`

### API 代理

开发环境下，`vite.config.ts` 会把 `/api/*` 代理到：`http://localhost:5000`。

## 主要功能

- Hash 路由（`#/dashboard`、`#/fleet`、`#/control`、`#/events`）
- 底部 Dock 导航（含主题切换、时钟）
- 主题模式：`light | dark | system`（LocalStorage key: `sentra-theme-mode`）
- 事件通知托盘：新 incident 弹出提示，点击跳转到事件页

## 页面

- `Dashboard`：关键指标总览（流量、均值环形图、稳定窗口、负载分布、健康指标、功耗、近期事件）
- `ServerFleet`：单机维度的指标概览
- `ControlDeck`：手动推进 tick、切换自治、注入故障、重置
- `EventTimeline`：事件流列表

## API（前端期望）

封装在 `src/api/sentra.ts`，由 `src/state/useSentra.ts` 轮询与驱动：

- `GET /api/state` -> `WorldState`
- `GET /api/events?limit=&since_tick=&type=&target=` -> `EventsResponse`
- `POST /api/tick` `{ steps? }` -> `WorldState`
- `POST /api/autonomy` `{ enabled }`
- `POST /api/fault` `{ type, target }`
- `POST /api/reset` `{ reset_events? }` -> `WorldState`

## 目录结构（简版）

```
frontend/
  src/
    api/              # fetch 封装
    components/       # Dock、Ring、Ticker、事件卡片等
    pages/            # 四个页面
    state/            # useSentra：轮询与动作
    utils/            # 格式化与指标聚合
    types.ts          # 前后端共享的类型契约
    index.css         # 主题变量 + 组件样式
```
