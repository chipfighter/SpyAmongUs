# 一、项目概览与现状分析

## 1.1 项目定位

SpyAmongUs 是一个基于 Web 的 **"谁是卧底"在线多人对战游戏**，作为毕业设计项目开发。核心玩法为：玩家在房间内通过文字发言描述各自拿到的词语，通过投票找出持有不同词语的"卧底"玩家。项目的亮点在于引入了 **LLM 驱动的 AI 玩家**，可以与真人玩家混合对战。

## 1.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **前端** | Vue 3 + Vite + Pinia + Vue Router | SPA 架构，Axios 处理 HTTP 请求 |
| **后端** | Python FastAPI + Uvicorn | 异步 Web 框架，处理 HTTP + WebSocket |
| **实时通信** | WebSocket (原生) | 游戏内消息、状态同步 |
| **缓存/实时状态** | Redis | 房间状态、用户会话、消息队列、投票记录 |
| **持久化存储** | MongoDB (Motor 异步驱动) | 用户账号、密码哈希、统计数据、用户画像 |
| **认证** | JWT (Access + Refresh Token) | 双令牌机制，25min/7day 过期策略 |
| **AI 集成** | LLM API (HTTP 流式调用) | AI 玩家发言/投票/遗言，7 种场景 Prompt |

## 1.3 代码规模统计

### 后端 (`backend/`)

| 模块 | 文件 | 行数 | 大小 | 职责 |
|------|------|------|------|------|
| `main.py` | 1 个 | **1,754** | 72KB | API 路由 + WebSocket 端点 + 中间件 |
| `services/game_service.py` | 1 个 | **3,091** | 147KB | 游戏全部核心逻辑 |
| `services/room_service.py` | 1 个 | 952 | 42KB | 房间 CRUD + 倒计时 |
| `services/message_service.py` | 1 个 | 924 | 39KB | 消息处理 + AI @提及 |
| `services/user_service.py` | 1 个 | 760 | 28KB | 用户管理 + 统计 |
| `services/auth_service.py` | 1 个 | 145 | 4.5KB | JWT 认证 |
| `utils/redis_utils.py` | 1 个 | 640 | 25KB | Redis 数据操作封装 |
| `utils/mongo_utils.py` | 1 个 | 297 | 10KB | MongoDB 操作封装 |
| `utils/websocket_manager.py` | 1 个 | 213 | 9KB | WS 连接池管理 |
| `llm/` | 4 个 | ~630 | 36KB | Prompt 管理 + API 调用 |
| **后端合计** | **~15 个** | **~9,400+** | **~415KB** | — |

### 前端 (`frontend/src/`)

| 模块 | 文件数 | 大小合计 | 职责 |
|------|--------|---------|------|
| `views/` | 6 个 | ~203KB | 页面级组件（Room 70KB, Lobby 66KB 最大） |
| `components/Room/` | 17 个 | ~152KB | 游戏房间子组件 |
| `stores/` | 4 个 | ~97KB | Pinia 状态管理（websocket.js 49KB 最大） |
| `router/` | 1 个 | 2KB | 路由配置 + 导航守卫 |

## 1.4 Git 仓库现状

| 指标 | 现状 | 问题 |
|------|------|------|
| 分支 | `dev` + `main`，有 `origin` 远程 | 仅有基本分支，无 feature/release 分支 |
| 提交数 | 约 3-5 个 | 提交过少，单次提交变更量过大 |
| Commit message | 中英混合，格式不规范 | 缺少 Conventional Commits 规范 |
| Tag | `v0.0.7` | 仅一个标签，版本管理不完善 |
| README | 两个文件均为 **空** | 项目无任何说明 |

## 1.5 现有文档盘点

| 文件 | 位置 | 状态 |
|------|------|------|
| `redis_schema.txt` | 根目录 | ✅ 完整，12 种 Redis 键模式详细描述 |
| `redis_user_schema.txt` | 根目录 | ✅ 完整，用户数据结构说明 |
| `CHANGELOG.md` | `backend/docs/` | ⚠️ 存在但被 `.gitignore` 忽略 |
| `todo.md` | `backend/docs/` | ⚠️ 存在但被 `.gitignore` 忽略 |
| `游戏规则.md` | `backend/docs/` | ⚠️ 存在但被 `.gitignore` 忽略 |
| `数据存储+功能说明.md` | `backend/docs/` | ⚠️ 存在但被 `.gitignore` 忽略 |
| `README.md` | 根目录 | ❌ 空文件 |
| `README_zh.md` | 根目录 | ❌ 空文件 |

> **⚠️ 注意：** `.gitignore` 中的 `backend/docs/*.md` 规则导致 `backend/docs/` 下的所有 Markdown 文档被忽略，这些文档（CHANGELOG、游戏规则等）实际上是有价值的，不应被排除在版本控制之外。同时 `**/*.json` 规则过于宽泛，会影响 `package.json` 等关键文件的追踪。

## 1.6 当前状态总结

- ✅ **可运行的核心**：游戏生命周期（创建房间→发言→投票→结算）基本完整
- ✅ **有亮点**：LLM AI 玩家系统、7 种场景 Prompt、流式响应
- ⚠️ **半成品标记**：存在已知逻辑漏洞（作者自述）
- ❌ **GitHub 展示就绪度极低**：README 为空、无测试、无部署文档、Git 历史简陋
