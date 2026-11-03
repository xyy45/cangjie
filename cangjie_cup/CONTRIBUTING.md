# CangSight 协作开发流程

本仓库（`nuptpisa/CangSight`）默认分支为 `main`，已开启分支保护：**所有改动必须通过 Pull Request（PR）合并；PR 需 1 名管理员（code owner）审批通过后才能合并，且只有管理员能执行合并。** 除管理员外，任何人不能直接 push 到 `main`。

本文档说明：环境准备 → 写代码 → 提交 PR → 审核 → 合并的全流程。

---

## 0. 角色与权限

| 角色 | 权限 | 能做什么 |
|---|---|---|
| 管理员（admin） | 仓库 admin | 审批 PR、合并 PR；应急时可绕过审批直推 / 直接合并 |
| 协作者（write） | 仓库 write | 创建分支、push 分支、提 PR；**审批不作数、不能合并** |
| 访客（无权限） | — | 只能看公开内容，不能改 |

- **只有管理员的 approve 才计入所需审批**：仓库根目录 `.github/CODEOWNERS` 把全路径 owner 设为管理员，并开启了"必须 code owner 审批"，write 用户点了 Approve 也不作数。
- **只有管理员能合并 PR**：main 的 push 权限被限制为管理员，write 用户的合并按钮是灰的。
- **提交者本人不能给自己的 PR 批 approve**（管理员给自己的 PR 也不行），需另一位管理员审批。
- 当前管理员：`Yuanxudong-dev`、`xyy45`。

> 如果你是新成员、还没有仓库权限：先让管理员把你加为协作者（write）。被邀请后会收到邮件，接受邀请后才能 push。

---

## 1. 环境准备（只需做一次）

### 1.1 安装工具
- **Git**：`git --version` 能输出版本即可。
- **GitHub CLI（gh）**：用于命令行开 PR / 审核。安装见 https://cli.github.com/
  - macOS：`brew install gh`
- **登录**：
  ```bash
  gh auth login
  ```
  按提示选 GitHub.com → HTTPS → 浏览器授权。

### 1.2 配置 git 身份（重要）
**务必配置真实的用户名和邮箱**，否则提交记录里会显示成 `Your Name / your_email@example.com`，无法追溯是谁提交的：
```bash
git config --global user.name  "你的姓名或学号"
git config --global user.email "你的邮箱"
```

### 1.3 克隆仓库
```bash
git clone https://github.com/nuptpisa/CangSight.git
cd CangSight
```

---

## 2. 开发流程（每次写代码都走一遍）

### 第 1 步：同步最新 main，拉一个 feature 分支
```bash
git switch main
git pull origin main                         # 拉取最新 main，避免基于旧代码开发
git switch -c feature/你的名字-简短描述        # 例如 feature/zhang-add-login
```
- **分支命名规范**：`feature/xxx`（新功能）、`fix/xxx`（修 bug）、`docs/xxx`（文档）、`refactor/xxx`（重构）。
- **绝不要在 main 上直接改**。main 被保护，非管理员 push 会被服务器拒绝。

### 第 2 步：写代码
按各子项目（`AH-SecAgent/`、`HW-CodeArts/`、`SF-SuperAgent/`、`Sympas-Nexus/`）的目录结构放置文件。改动尽量聚焦一个主题，便于审核。

### 第 3 步：本地提交
```bash
git status                       # 看改了哪些文件
git diff                         # 看具体改动
git add <文件>                   # 只 add 你要的文件；或 git add . 全加
git commit -m "feat: 简要说明这次改动"
```
- **commit message 规范**（推荐）：
  - `feat: 新增/升级功能`
  - `fix: 修复某 bug`
  - `docs: 文档改动`
  - `refactor: 重构，不改行为`
  - `test: 测试相关`
  - `chore: 杂项/配置`

### 第 4 步：推送到远端
```bash
git push -u origin feature/zhang-add-login
```
首次推送加 `-u`，之后这个分支直接 `git push` 即可。

### 第 5 步：开 Pull Request
```bash
gh pr create --base main --head feature/zhang-add-login \
  --title "feat: 新增登录功能" \
  --body "## 改动内容
- 新增 login 页面
- 接入 /api/login

## 自测
- [x] 本地运行通过
- [x] 手动验证登录流程

## 关联
无"
```
也可以用网页：推送后 GitHub 仓库主页会出现 "Compare & pull request" 按钮，点它开 PR。

提交后 PR 页面会显示 **"1 review required"**，进入等待审批状态。

---

## 3. 审核与合并流程

### 3.1 审批者怎么审核

审批者必须是**管理员**（`.github/CODEOWNERS` 里列的人）——只有管理员的 approve 才计入所需审批。write 用户虽能点 Approve，但不作数。管理员也不能给自己的 PR 批 approve，需另一位管理员审。

**方式 A：网页**
1. 打开 `https://github.com/nuptpisa/CangSight/pulls`，点进待审 PR。
2. 点 **Files changed** 查看改动，可在具体行点 `+` 留评论。
3. 右上角 **Review** → 选 **Approve**（通过）/ **Request changes**（要求改）/ **Comment**（仅评论）→ 写评语 → **Submit review**。

**方式 B：命令行**
```bash
gh pr list                              # 列出待处理 PR
gh pr view 12                           # 看 12 号 PR 概况
gh pr diff 12                           # 看完整 diff

gh pr review 12 --approve  -b "LGTM"    # 通过
gh pr review 12 --request-changes -b "请改 xxx"   # 要求修改
gh pr review 12 --comment -b "有个疑问"            # 仅评论
```

> 只有 **Approve** 才算那 1 个 required approving review。

### 3.2 合并 PR

PR 经管理员（code owner）approve 后，**只有管理员**能合并（write 用户的合并按钮仍是灰的）：

```bash
gh pr merge 12 --squash --delete-branch
```
- `--squash`：把 feature 分支上的多个 commit 压成一个干净 commit 进 main（推荐）。
- `--delete-branch`：合并后顺手删掉 feature 分支。

网页上则点 **Merge pull request** → **Confirm merge**。

### 3.3 管理员应急（绕过审批）

紧急情况下管理员可不等审批直接合并：
```bash
gh pr merge 12 --squash --admin
```
> 这是应急口子，日常请走"1 人 approve → merge"。

---

## 4. 常见问题

### 4.1 push 到 main 被拒绝
```
! [remote rejected] main -> main (protected branch hook declined)
```
说明你试图直接推 main。**正确做法**：在 feature 分支上改，开 PR。管理员若必须直推，可用 `git push origin main`（会绕过保护），但请慎用。

### 4.2 PR 有冲突，合并按钮变灰
作者需要把 main 合进自己的分支解决冲突：
```bash
git switch feature/zhang-add-login
git fetch origin
git merge origin/main          # 或 git rebase origin/main
# 手动解决冲突文件中的 <<<< ==== >>>> 标记
git add .
git commit                    # rebase 的话用 git rebase --continue
git push
```
冲突解决并推送后，PR 会自动更新。

### 4.3 之前的 approve 没了
本仓库开启了"自动撤销过期审批"：PR 被 approve 之后又推了新 commit，原 approve 会失效，需重新审批。这是防止"批完之后又塞改动"。**正确做法**：尽量在 PR 就绪后再请人审；要补改就推新 commit 后重新请人 approve。

### 4.4 找不到人审批
- 审批只能找管理员（当前 `Yuanxudong-dev`、`xyy45`），群里 @ 一下。
- 管理员若赶时间，可用 `--admin` 绕过审批直接合并（仅管理员可执行）。

### 4.5 不小心在 main 上改了
```bash
git switch main
git stash                     # 暂存改动
git pull origin main
git switch -c feature/xxx     # 建分支
git stash pop                 # 把改动挪到分支上
git add . && git commit -m "..." && git push -u origin feature/xxx
```

---

## 5. 命令速查

```bash
# —— 日常开发 ——
git switch main && git pull origin main        # 同步 main
git switch -c feature/xxx                      # 建分支
git add . && git commit -m "feat: ..."         # 提交
git push -u origin feature/xxx                 # 推送

# —— PR ——
gh pr create --base main --head feature/xxx --title "..." --body "..."  # 开 PR
gh pr list                                     # 待处理 PR
gh pr view 12                                  # 看 PR
gh pr diff 12                                  # 看 diff
gh pr review 12 --approve -b "LGTM"            # 审批
gh pr merge 12 --squash --delete-branch        # 合并并删分支（仅 admin）

# —— 同步与冲突 ——
git fetch origin && git merge origin/main      # 把 main 合进当前分支
git pull --rebase origin main                  # rebase 方式同步

# —— 查看状态 ——
git status                                     # 工作区状态
git log --oneline -10                          # 最近提交
gh pr status                                   # 与我相关的 PR
```

---

## 6. 一句话流程

**提交者**：拉分支 → 改代码 → `git push` → `gh pr create`
**审批者（管理员）**：`gh pr diff N` → `gh pr review N --approve` → `gh pr merge N --squash --delete-branch`（仅管理员）

有问题在群里 @ 管理员。
