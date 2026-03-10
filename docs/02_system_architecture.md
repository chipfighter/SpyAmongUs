# 二、系统架构与核心发现

## 2.1 整体架构

```
Browser (Vue 3 SPA)
    ├── HTTP/Axios ──→ FastAPI HTTP 路由
    └── WebSocket  ──→ FastAPI WS 端点
                          │
                    ┌─────┴──────┐
                    │ Service 层  │
                    │ Game/Room/  │
                    │ Message/User│
                    └─────┬──────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
         Redis(实时)  MongoDB(持久)  LLM API(AI)
```

## 2.2 后端分层分析

### API 层 (`main.py` — 1754 行)

| 职责 | 行数范围 | 说明 |
|------|---------|------|
| 导入 + 初始化 + 服务注入 | 1-110 | 所有服务实例化 + 双向引用注入 |
| Token 验证中间件 | 111-184 | 拦截所有非公开路径的请求 |
| WebSocket 端点 | 272-668 | **~400 行**，处理所有 WS 消息类型 |
| 认证 API | 672-931 | 注册/登录/登出/Token 刷新/轮换 |
| 房间 API | 935-1076 | 创建/删除/加入/退出/准备 |
| 投票 API | 1079-1130 | 提交投票 |
| 用户管理 API | 1133-1183 | 修改密码/头像 |
| 反馈 API | 1186-1283 | 提交/获取/更新反馈 |
| 管理员 API | 1306-1749 | 玩家管理/禁言/封禁/反馈管理 |

### Service 层 — 依赖关系

```
GameService(3091行) ←→ MessageService(924行)  [双向依赖]
GameService ──→ LLM_Pipeline ──→ GameService   [双向依赖]
GameService ──→ UserService(760行)
RoomService(952行) ──→ UserService
RoomService ──→ MessageService
```

> **注：** `GameService ↔ MessageService` 和 `GameService ↔ LLM_Pipeline` 存在双向循环依赖，通过延迟注入（`set_xxx_service`）解决。可行但暗示职责边界划分不够清晰。

### 数据层 — 双数据库分工

| 维度 | Redis | MongoDB |
|------|-------|---------|
| **定位** | 实时状态缓存 | 持久化存储 |
| **存储内容** | 房间状态、用户会话、消息列表、投票记录 | 用户账号、密码哈希+盐值、统计、画像 |
| **TTL** | 与 JWT Access Token 对齐 (25min) | 永久 |
| **键模式** | 12 种（Hash/Set/Sorted Set/List） | 单集合 `users` |

Redis 12 种键模式：

```
room:{code}                       — Hash，房间基本信息（17个字段）
room:{code}:users                 — Sorted Set，房间用户
room:{code}:ready_users           — Set，已准备用户
room:{code}:alive_players         — Sorted Set，存活玩家
room:{code}:roles                 — Hash，用户→角色映射
room:{code}:messages              — List，房间消息
room:{code}:secret_chat:messages  — List，秘密聊天消息
room:{code}:votes:{round}        — Hash，投票记录
room:{code}:secret_votes:{round} — Hash，秘密投票
room:{code}:poll_state            — String/JSON，轮询状态
public_rooms                      — Set，公开房间集合
user:{id}                         — Hash，用户缓存（12个字段）
```

## 2.3 前端架构

### 页面组件结构

```
App.vue
├── LoginView.vue (6.5KB)
├── RegisterView.vue (8KB)
├── LobbyView.vue (66KB) ⚠️ 过大
│   └── FeedbackModal.vue
├── RoomView.vue (71KB) ⚠️ 过大
│   ├── RoomHeader / RoomSidebar
│   ├── UserList (42KB) ⚠️
│   ├── ChatMessageList + ChatInput
│   ├── AiStreamMessage
│   ├── CountdownOverlay / GameLoadingOverlay
│   ├── GameResultModal
│   ├── GodRoleInquiry[Status]Modal
│   ├── GodWordSelection[Status]Modal
│   ├── SecretChatModal
│   └── MiniChat + FloatingBall
├── ProfileView.vue (22KB)
└── AdminView.vue (28KB)
```

### 状态管理

| Store | 大小 | 职责 |
|-------|------|------|
| `websocket.js` | **49KB** | WS 连接管理、消息路由、游戏事件处理 |
| `room.js` | 30KB | 房间数据、玩家列表 |
| `userStore.js` | 14KB | 用户信息、认证状态 |
| `chat.js` | 3KB | 聊天消息管理 |

## 2.4 游戏生命周期

```
创建房间 → 等待中(玩家加入/准备)
    → 全员准备 → 倒计时
    → 上帝轮询（有人接受 / 无人接受由AI分配词语）
    → 词语分配 → 游戏初始化
    → [发言阶段] → 逐个发言(含AI流式输出)
    → [投票阶段] → 有人被淘汰 → [遗言阶段]
                 → 平票且卧底≥2 → [秘密聊天] → [秘密投票]
    → 检查胜负条件
        → 所有卧底被淘汰 → 平民胜
        → 卧底≥平民 → 卧底胜
        → 达到最大轮数 → 平局
    → 未结束 → 下一轮 → [发言阶段]...
    → 结束 → 广播结算 → 清理数据 → 回到等待中
```

## 2.5 AI 玩家系统

7 种 LLM 调用场景：

| 场景常量 | 触发时机 | Prompt 策略 |
|---------|---------|------------|
| `normal_chat` | 游戏前 @AI 聊天 | 诙谐幽默的游戏助手 |
| `game_playing` | 轮到 AI 发言 | 按角色(平民/卧底)差异化描述 |
| `voting` | AI 投票 | function_call 返回 target_id |
| `last_words` | AI 被淘汰遗言 | 点名可疑玩家 + 混淆策略 |
| `secret_chat` | 卧底密谋聊天 | 紧迫冷静的队友协作 |
| `secret_vote` | 秘密投票 | 暗杀策略 |
| `god_words` | 上帝分配词语 | 输出 JSON {civilian_word, spy_word} |

AI 发言通过**流式输出**（SSE 风格），前端 `AiStreamMessage.vue` 逐字渲染。
