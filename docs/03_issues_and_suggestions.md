# 三、现有问题与修改建议

## 3.1 架构层面

### 问题 A：`main.py` 过于臃肿 (1754行)
**严重度：⭐⭐⭐ 中**

API 路由、WebSocket 端点、中间件、数据模型全部塞在一个文件里。

**建议：** 使用 FastAPI 的 `APIRouter` 拆分为模块：
```
backend/
├── routers/
│   ├── auth.py          # 认证相关
│   ├── room.py          # 房间 CRUD
│   ├── game.py          # 投票等游戏API
│   ├── user.py          # 用户信息修改
│   ├── admin.py         # 管理员API
│   ├── feedback.py      # 反馈API
│   └── websocket.py     # WebSocket 端点
├── main.py              # 仅保留 app 初始化 + 中间件 (~100行)
```

### 问题 B：`GameService` 上帝类 (3091行)
**严重度：⭐⭐⭐ 中**

**建议：** 按游戏阶段拆分（中期优化）：
```
services/game/
├── game_manager.py      # 生命周期协调
├── speaking_handler.py  # 发言阶段
├── voting_handler.py    # 投票阶段
├── ai_player_handler.py # AI 玩家逻辑
└── elimination.py       # 淘汰 + 遗言
```

### 问题 C：循环依赖
**严重度：⭐⭐ 低**

`GameService ↔ MessageService ↔ LLM_Pipeline` 三方互相持有引用。当前 `set_xxx_service()` 延迟注入可工作。

**建议：** 短期不用改，长期可抽取事件总线或中介者模式。

### 问题 D：前端大文件
**严重度：⭐⭐ 低**

`RoomView.vue`(71KB)、`LobbyView.vue`(66KB)、`websocket.js`(49KB) 单文件过大。

**建议：** 继续拆分子组件，将 `websocket.js` 中的消息处理按类型拆分。

---

## 3.2 安全隐患

### 问题 E：JWT Secret 硬编码 🔴
**严重度：⭐⭐⭐⭐⭐ 最高 — 上 GitHub 前必须修改！**

`config.py` 第 44 行密钥直接写死在源码中，推送到 GitHub 即**永久泄露**。

**修改方法：**
```python
# config.py 改为：
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-unsafe-key")
```
然后在 `.env` 中配置真实密钥（`.env` 已在 `.gitignore` 中）。

### 问题 F：`api_keys.json` 安全风险
**严重度：⭐⭐⭐⭐ 高**

LLM API 密钥文件 `llm/api_keys.json` 被 `**/*.json` 规则"碰巧"忽略，非有意设计。

**建议：** 在 `.gitignore` 中明确添加：
```gitignore
**/api_keys*
**/*secret*
```

---

## 3.3 代码规范

### 问题 G：依赖版本

`requirements.txt` 问题：

| 问题 | 现状 | 建议 |
|------|------|------|
| `fastapi==0.68.1` | 2021年版本，过旧 | 升级到 `>=0.100.0` |
| `pydantic==1.8.2` | v1 版本 | 升级到 `>=2.0` |
| `websockets` 重复 | `==10.0` 和 `>=10.3` 共存 | 保留一个 `>=10.3` |
| 缺少 `PyJWT` | `auth_service.py` 使用了 `jwt` | 添加 `PyJWT>=2.0` |

### 问题 H：注释风格不一致
**严重度：⭐ 低**

部分用 `"""docstring"""`，部分用 `# 注释` 替代 docstring，中英混合。

**建议：** 统一为 `"""docstring"""` + Google Style，上 GitHub 前不急改。

---

## 3.4 `.gitignore` 问题 🔴

**严重度：⭐⭐⭐⭐⭐ 最高 — 直接影响仓库内容**

当前两个严重规则：

```gitignore
**/*.json          # ← 忽略了 ALL json，包括 package.json!
backend/docs/*.md  # ← 忽略了所有有价值的文档!
```

**建议修改：**
```diff
- **/*.json
- backend/docs/*.md
- backend/*.md
+ # API keys and secrets
+ **/api_keys*.json
+ **/*secret*.json
+
+ # Backend temp docs (keep docs/ tracked)
+ backend/*.md
+ !backend/docs/
```

---

## 3.5 优先级总结

| 优先级 | 问题 | 改动量 | 何时做 |
|--------|------|--------|--------|
| 🔴 P0 | JWT Secret 硬编码 | 改 1 行 | **上 GitHub 前必做** |
| 🔴 P0 | `.gitignore` 规则修复 | 改几行 | **上 GitHub 前必做** |
| 🟡 P1 | `.env.example` 模板 | 新建 1 文件 | 上 GitHub 前建议做 |
| 🟡 P1 | `requirements.txt` 修正 | 改几行 | 上 GitHub 前建议做 |
| 🟢 P2 | `main.py` 路由拆分 | 中等 | 中期优化 |
| 🟢 P2 | 前端大文件拆分 | 中等 | 中期优化 |
| ⚪ P3 | `GameService` 拆分 | 大工程 | 长期重构 |
| ⚪ P3 | 循环依赖优化 | 中等 | 长期重构 |
