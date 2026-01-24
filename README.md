# SENTRA — Self-Governing Autonomous Data Center System

SENTRA 是一个面向微型数据中心场景的 **全自治智能运维系统原型**，旨在探索 AI + Automation 在真实动态环境中的自主决策、自我修正与安全控制能力。

本项目对应 TechNation AI Hackathon Track 2：

> **AI + Automation – Fully Autonomous Solutions
> “Removing the Human from the Loop”**

我们构建了一个可运行的虚拟数据中心环境，使系统能够在无人工干预的情况下完成异常检测、智能决策、自动执行与持续优化。

---

## 一、项目背景（Project Background）

传统数据中心运维高度依赖人工监控与人工决策：

* 工程师需要持续查看监控面板
* 异常发生后由人工分析原因
* 决策、执行、回滚均依赖人为参与
* 响应速度受限，人力成本高

随着系统规模扩大与复杂度上升，这种模式逐渐难以维持。

SENTRA 的目标是探索一种新范式：

> 构建具备自主感知、自主决策、自主执行与自我纠错能力的智能运维系统，使数据中心在多数场景下实现“无人值守运行”。

本项目通过模拟微型数据中心环境，实现完整的自治闭环，为未来大规模自治基础设施管理提供参考模型。

---

## 二、项目目标（Project Objectives）

SENTRA 的核心目标包括：

1. 构建可运行的虚拟数据中心环境
2. 实现连续状态监测与异常检测
3. 实现自动化决策与执行机制
4. 引入 AI 作为解释与规划层
5. 实现安全约束与自我修正机制
6. 构建可视化监控与事件回放系统

最终形成如下自治循环：

```
监测 → 判断 → 决策 → 执行 → 评估 → 修正 → 记录
```

---

## 三、系统总体架构（System Architecture）

整体采用前后端分离架构：

```
React Frontend
      ↓
Flask REST API
      ↓
Autonomous Core Engine
      ↓
SQLite Event Database
      ↓
AI Planning & Explanation Layer
```

各层职责如下：

* 前端：状态展示、交互控制、可视化
* 后端 API：统一业务入口
* 核心引擎：世界模拟与自治控制
* 数据库：事件时间线与历史记录
* AI 模块：异常解释与行动建议生成

---

## 四、技术栈（Technology Stack）

### 前端（Frontend）

* React + Vite
* TypeScript
* Tailwind CSS
* Axios / Fetch API

功能：

* 实时状态仪表盘
* 故障注入控制
* 自治状态管理
* 时间线展示

---

### 后端（Backend）

* Python
* Flask
* Requests
* python-dotenv

功能：

* REST API 服务
* 模拟调度
* 自治控制
* AI 调用封装

---

### 数据库（Database）

* SQLite

功能：

* 事件日志存储
* AI 输出存储
* 决策记录存档

---

### AI 服务（AI Service）

* OpenAI-compatible API
* Prompt Engineering
* JSON Schema 校验

功能：

* 异常原因分析
* 行动计划生成
* 风险与回滚提示

---

## 五、核心功能模块（Core Modules）

### 1. 数据中心模拟器（Simulator）

模拟三台服务器的运行状态：

* 负载（Load）
* 温度（Temperature）
* 错误率（Error Rate）
* 功耗（Power）
* 健康度（Health）

通过物理规则模拟真实因果关系。

---

### 2. 自治控制器（Controller）

负责：

* 异常检测
* 动作选择
* 自动执行
* 自我修正

结合规则控制与 AI 建议双层机制，确保稳定性。

---

### 3. AI 规划与解释层（AI Planner）

AI 不直接控制系统，而负责：

* 生成异常解释
* 推荐行动顺序
* 评估潜在风险
* 给出回滚建议

提高系统可解释性与安全性。

---

### 4. 事件时间线系统（Event Timeline）

记录完整运行历史：

* 异常事件
* 决策行为
* AI 输出
* 回滚记录

支持复盘与审计。

---

# 六、项目目录结构与文档治理体系（Repository Structure & Documentation Governance）

SENTRA 采用“**代码 + 文档双核心驱动**”结构设计，其中 `docs/` 目录不仅用于说明项目，还承担**项目记忆系统与协作治理中枢**的角色。所有 AI 执行代理与开发成员在进行任何修改前，必须优先阅读 `docs/00_PROJECT_CONTEXT.md`。

---

## 6.1 项目总体结构

```
SENTRA/
├── README.md
├── docs/
│   ├── 00_PROJECT_CONTEXT.md
│   ├── 01_VISION_AND_SCOPE.md
│   ├── 02_SYSTEM_ARCHITECTURE.md
│   ├── 03_API_CONTRACT.md
│   ├── 04_DATA_MODEL.md
│   ├── 05_AUTONOMY_POLICY.md
│   ├── 06_AI_INTERFACE.md
│   ├── 07_TASK_REGISTRY.md
│   ├── 08_DECISION_LOG.md
│   ├── 09_RISK_AND_FALLBACK.md
│   ├── 10_RELEASE_PLAN.md
│   ├── 11_DEMO_PLAYBOOK.md
│   └── _templates/
│       ├── task_template.md
│       ├── decision_template.md
│       └── prompt_template.md
│
├── frontend/
│   ├── package.json
│   └── src/
│       ├── api/
│       ├── pages/
│       ├── components/
│       ├── state/
│       └── main.tsx
│
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── web/
│       │   └── routes.py
│       ├── services/
│       │   ├── tick_service.py
│       │   ├── autonomy_service.py
│       │   └── event_service.py
│       ├── core/
│       │   ├── simulator/
│       │   ├── controller.py
│       │   └── ai/
│       └── persistence/
│           └── db.py
│
├── data/
│   └── dev.sqlite3
│
└── scripts/
    └── dev_all.sh
```

---

## 6.2 docs/：项目治理与 AI 上下文系统（Project Memory & Governance）

`docs/` 是 SENTRA 的**核心治理目录**，用于维护项目的长期记忆、决策历史与协作规范。所有 AI 与成员必须遵循此目录内容进行开发。

---

### 6.2.1 文档职责与 Ownership

| 文件                        | 作用              | Owner    | 是否允许 AI 修改 |
| ------------------------- | --------------- | -------- | ---------- |
| 00_PROJECT_CONTEXT.md     | 项目全局上下文入口       | 系统集成负责人  | ⚠️ 需人工审核   |
| 01_VISION_AND_SCOPE.md    | 项目目标与边界         | 全体       | 否          |
| 02_SYSTEM_ARCHITECTURE.md | 系统结构与数据流        | 后端负责人    | 否          |
| 03_API_CONTRACT.md        | API 契约规范        | 前端负责人    | ⚠️ 需审核     |
| 04_DATA_MODEL.md          | 状态/数据库模型        | 后端负责人    | 否          |
| 05_AUTONOMY_POLICY.md     | 自治安全与伦理规则       | 架构负责人    | 否          |
| 06_AI_INTERFACE.md        | AI Prompt 与格式规范 | AI 模块负责人 | ⚠️ 受限      |
| 07_TASK_REGISTRY.md       | 任务注册表           | 全体       | 是          |
| 08_DECISION_LOG.md        | 技术决策记录          | 架构负责人    | 是（记录用）     |
| 09_RISK_AND_FALLBACK.md   | 风险与应急方案         | 全体       | 否          |
| 10_RELEASE_PLAN.md        | 发布计划与时间轴        | 项目负责人    | 否          |
| 11_DEMO_PLAYBOOK.md       | 演示与视频脚本         | 演示负责人    | 否          |

说明：

* ⚠️：表示 AI 只能在人工监督下修改
* “否”：禁止 AI 自动更改，避免战略漂移
* “是”：允许 AI 更新（任务/记录类文档）

---

### 6.2.2 docs/_templates/

模板目录用于规范 AI 与成员生成内容格式，避免文档结构失控。

| 文件                   | 用途             |
| -------------------- | -------------- |
| task_template.md     | 标准任务描述格式       |
| decision_template.md | 决策记录格式         |
| prompt_template.md   | AI Prompt 标准结构 |

---

## 6.3 frontend/：用户交互与系统可视化层

`frontend/` 负责所有 UI 与交互逻辑，仅关注展示与控制，不承载业务决策。

### Ownership

* 主负责人：系统集成负责人
* 协作：全体成员

### 目录说明

| 子目录         | 职责       |
| ----------- | -------- |
| api/        | 后端接口封装   |
| pages/      | 页面级组件    |
| components/ | 通用 UI 组件 |
| state/      | 轮询与状态管理  |
| main.tsx    | 入口文件     |

---

## 6.4 backend/：自治引擎与业务核心

`backend/` 是 SENTRA 的运行核心，负责世界模拟、自治决策、AI 调用与数据持久化。

---

### 6.4.1 web/：HTTP API 层

负责前后端通信，不包含业务逻辑。

Owner：系统集成负责人 + 后端负责人

---

### 6.4.2 services/：业务调度层

连接 API 与核心模块，封装执行流程。

| 文件                  | 职责   | Owner   |
| ------------------- | ---- | ------- |
| tick_service.py     | 推进模拟 | 系统集成负责人 |
| autonomy_service.py | 自治调度 | AI 负责人  |
| event_service.py    | 日志管理 | AI 负责人  |

---

### 6.4.3 core/：自治系统内核

#### simulator/

负责虚拟世界建模与状态演化。

Owner：模拟引擎负责人

#### controller.py

自治控制逻辑。

Owner：自治负责人

#### ai/

AI 接口封装与验证。

Owner：AI 模块负责人

---

### 6.4.4 persistence/：数据层

负责 SQLite 读写。

Owner：后端负责人

---

## 6.5 data/：运行时数据

用于存储开发与演示阶段数据库文件。

* 默认不参与核心逻辑开发
* 重要数据需备份

---

## 6.6 scripts/：自动化工具

包含本地开发、联调、初始化脚本。

Owner：全体成员

---

## 6.7 文档与代码协作规范（Governance Rules）

为保证 AI 协作稳定性，SENTRA 规定：

1. 所有 AI 执行必须先读取：

   ```
   docs/00_PROJECT_CONTEXT.md
   ```

2. API 变更必须同步更新：

   ```
   docs/03_API_CONTRACT.md
   ```

3. 自治策略修改必须记录：

   ```
   docs/08_DECISION_LOG.md
   ```

4. 新任务必须登记：

   ```
   docs/07_TASK_REGISTRY.md
   ```

5. 风险发现必须更新：

   ```
   docs/09_RISK_AND_FALLBACK.md
   ```

---

## 6.8 设计目标总结

该目录结构的目标是：

* 为 AI 提供长期工作记忆
* 为团队提供清晰责任边界
* 为项目提供稳定演化轨迹
* 为比赛交付提供高可靠性保障

通过该结构，SENTRA 实现了代码、文档与智能代理之间的协同治理。

---

## 七、团队分工（Team Responsibilities）

本项目采用“垂直切片式协作”，确保每位成员覆盖完整链路。

---

### 成员 A（系统集成 / 前后端协同）

职责：

* 前端 Dashboard 主体开发
* API 契约设计
* 状态轮询机制
* Flask 核心路由
* 系统集成测试

负责模块：

```
frontend/
backend/app/web/
backend/app/services/tick_service.py
docs/api-contract.md
```

---

### 成员 B（模拟引擎 / 世界模型）

职责：

* 数据中心状态建模
* 物理规则设计
* 故障注入系统
* 状态更新引擎

负责模块：

```
backend/app/core/simulator/
backend/app/core/simulator/world.py
backend/app/core/simulator/rules.py
backend/app/core/simulator/faults.py
```

---

### 成员 C（自治控制 / AI / 数据层）

职责：

* 自治决策逻辑
* 动作执行模块
* AI 接口封装
* 数据库存储
* 事件时间线系统

负责模块：

```
backend/app/core/controller.py
backend/app/core/ai/
backend/app/persistence/
backend/app/services/autonomy_service.py
backend/app/services/event_service.py
```

---

## 八、安全与伦理设计（Safety & Ethics）

SENTRA 在设计中重点考虑：

* AI 不直接控制执行
* 高风险动作受约束
* 自动回滚机制
* 全流程审计日志
* 可解释性输出

确保自治不等于失控。

---

## 九、未来拓展方向（Future Work）

* 引入强化学习控制器
* 多集群协同自治
* 联邦学习优化策略
* 云端真实数据接入
* 权限与审计系统增强

---

## 十、项目定位总结（Project Positioning）

SENTRA 并非简单的自动化工具，而是一个完整的：

> 自感知、自决策、自执行、自修正、自解释的自治基础设施原型系统。

本项目展示了 AI + Automation 在复杂系统管理中的可行路径。
