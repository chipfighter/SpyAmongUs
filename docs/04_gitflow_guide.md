# 四、Gitflow 工作流改善建议

## 4.1 当前 Git 状态分析

| 指标 | 现状 |
|------|------|
| 分支 | `main` + `dev`，有 `origin` 远程 |
| 提交数 | 约 3-5 个，单次变更量极大 |
| Commit message | 中英混合，无统一格式 |
| Tag | 仅 `v0.0.7` |

**核心问题：** 提交粒度太粗，一个 commit 包含了大量不相关的变更，无法追溯具体改动。

---

## 4.2 需要重新上传吗？

**不需要。** 不建议删除仓库重建或 `git rebase` 重写历史。原因：

1. 重写历史可能导致已有的 `origin` 远程出现冲突
2. 面试官/观察者关注的是**从某个时间点开始**的规范化趋势，而非完美历史
3. 在现有基础上 **从现在开始规范化** 即可，反而体现了你发现问题→改进的过程

**正确做法：** 在当前 `dev` 分支上继续开发，从下一个 commit 开始规范化。

---

## 4.3 推荐的分支策略

对于个人毕设项目，**不需要完整的 Gitflow**，采用简化版即可：

```
main          ●───────────────────────●───────────────●  (稳定版本)
               \                     /               /
dev            ●──●──●──●──●──●──●──●──●──●──●──●──●   (日常开发)
                   \     /       \       /
feature/xxx        ●──●──●       ●──●──●               (具体功能)
```

| 分支 | 用途 | 合并方向 |
|------|------|---------|
| `main` | 稳定可展示的版本 | 只接受 `dev` 的合并 |
| `dev` | 日常开发主线 | 接受 feature 分支的合并 |
| `feature/xxx` | 单个功能开发 | 完成后合并回 `dev` 并删除 |

### 什么时候开 feature 分支？

- 预计改动量 > 3个文件 或 > 100 行
- 例如：`feature/split-main-routers`、`feature/readme`、`feature/fix-gitignore`

### 什么时候直接在 dev 上提交？

- 小修小补（改1-2行配置、修个 typo）
- 文档更新

---

## 4.4 Commit Message 规范

采用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <description>

[optional body]
```

### 常用 type

| type | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(game): add secret chat voting` |
| `fix` | 修复 bug | `fix(auth): remove hardcoded JWT secret` |
| `docs` | 文档 | `docs: add README and architecture docs` |
| `refactor` | 重构 | `refactor(api): split main.py into routers` |
| `chore` | 杂项 | `chore: update .gitignore rules` |
| `style` | 格式 | `style: unify docstring format` |
| `test` | 测试 | `test(game): add voting logic tests` |

### scope 建议

- `game` / `room` / `auth` / `user` / `llm` / `frontend` / `api`

---

## 4.5 推荐的上线步骤（从现在开始）

按以下顺序在 `dev` 分支上执行，每步一个 commit：

### Step 1：修复安全隐患
```bash
# 修改 config.py 中的 JWT_SECRET_KEY
git add backend/config.py
git commit -m "fix(auth): move JWT secret to environment variable"
```

### Step 2：修复 .gitignore
```bash
# 修改 .gitignore 规则
git add .gitignore
git commit -m "chore: fix gitignore rules for json and docs"
```

### Step 3：添加被忽略的文档
```bash
# .gitignore 修复后，这些文件可以被追踪了
git add backend/docs/
git commit -m "docs: track existing backend documentation"
```

### Step 4：添加环境配置模板
```bash
# 创建 .env.example
git add .env.example
git commit -m "chore: add .env.example template"
```

### Step 5：添加分析文档
```bash
git add docs/
git commit -m "docs: add architecture analysis documentation"
```

### Step 6：撰写 README
```bash
git add README.md README_zh.md
git commit -m "docs: add project README in English and Chinese"
```

### Step 7：合并到 main 并打 tag
```bash
git checkout main
git merge dev
git tag -a v0.1.0 -m "First presentable version with docs"
git push origin main --tags
git checkout dev
```

---

## 4.6 Tag 版本建议

| 版本 | 含义 |
|------|------|
| `v0.0.7` | （已有）早期开发版本 |
| `v0.1.0` | 首个可展示版本（有 README + 文档） |
| `v0.2.0` | 路由拆分重构完成 |
| `v0.3.0` | 修复已知游戏逻辑漏洞 |
| `v1.0.0` | 功能完整 + 测试通过 |

---

## 4.7 快速参考卡

```
日常工作流：
1. git checkout dev
2. (小改动) 直接在 dev 上 commit
   (大功能) git checkout -b feature/xxx
3. 完成后: git checkout dev && git merge feature/xxx
4. 阶段性稳定: git checkout main && git merge dev && git tag vX.Y.Z
5. git push origin main dev --tags

Commit 模板：
feat(scope): 新增了什么功能
fix(scope): 修复了什么问题
docs: 文档相关改动
refactor(scope): 重构了什么
chore: 配置/构建相关
```
