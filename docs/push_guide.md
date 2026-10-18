# 怎么把本项目推成 repo 链接（逐步操作）

> ✅ **已完成（2026-10-18 17:10）**：已推送到 <https://github.com/JamesWei216/agentic-robotics>
> （public，12 个提交 / 8 个 tag / 79 个文件）。下面的步骤保留作为"重新推一遍"的参考。

目标链接：**https://github.com/JamesWei216/agentic-robotics**
（提交表要的是**仓库**链接，不是个人主页 `https://github.com/JamesWei216`）

本机仓库现状（已就绪，可直接推）：
- 路径 `/home/wei/work/g05/agentic-robotics`
- 分支 `master`，11 个提交，8 个 tag（`v0.1-main` … `v0.7-deliverables`、`v1.0-submit`）
- 78 个受控文件，最大文件 864 KB（PPTX），**不需要 Git LFS**
- 工作区干净（`git status` 无改动）

---

## 第 1 步：在 GitHub 网页建一个**空**仓库

1. 浏览器打开 <https://github.com/new>（需先登录 JamesWei216）
2. **Repository name** 填 `agentic-robotics`（必须一字不差，后面的命令和它对应）
3. **Description**（可选）填：`Agent 驱动的机械臂分拣流水线｜LIBERO/MuJoCo 仿真｜主任务 100/100`
4. **Public / Private**：建议 **Public**（评委要能直接打开；如果要保密就选 Private 并把评委账号加成 Collaborator）
5. **Initialization 三个勾选框全部不要勾**：
   - ☐ Add a README file
   - ☐ Add .gitignore
   - ☐ Choose a license
   （勾了会让远端先有一个提交，push 时会被拒绝，需要额外一步 rebase，见第 6 节）
6. Configure 其他（模板/template）都不用管 → 点绿色 **Create repository**
7. 创建后页面会显示 "…or push an existing repository from the command line"，复制那两行也行，
   但用下面第 3 步的命令更省事。**这个页面先别关**，第 5 步要回来刷新。

---

## 第 2 步：生成一个能 push 的 token（GitHub 已不支持账号密码）

1. 右上角头像 → **Settings**
2. 左侧最下方 → **Developer settings**
3. **Personal access tokens** → **Fine-grained tokens** → 右上 **Generate new token**
4. 填：
   - **Token name**：`agentic-robotics-push`
   - **Expiration**：7 days（够用；用完可以立刻删）
   - **Repository access**：选 **Only select repositories** → 勾 `agentic-robotics`
   - **Permissions** → Repository permissions → 找到 **Contents** → 改成 **Read and write**
     （其余保持 No access，够了）
5. 点 **Generate token** → 复制那串 `github_pat_xxxxxxxx`
   ⚠️ 只显示一次，页面关掉就看不到了；先粘到记事本

> 为什么不给 Classic token：Fine-grained 可以只授权这一个仓库、只给 Contents 权限，泄露面最小。

---

## 第 3 步：在本机执行 push

在**这台 Linux 机器**上（仓库就在本地）：

```bash
cd /home/wei/work/g05/agentic-robotics

# ① 关联远端（只做一次）
git remote add origin https://github.com/JamesWei216/agentic-robotics.git
#   如果提示 "remote origin already exists"，改用：
#   git remote set-url origin https://github.com/JamesWei216/agentic-robotics.git

# ② 推主分支 + 所有 tag
git push -u origin master --tags
```

推送时会提示：
```
Username for 'https://github.com': JamesWei216
Password for 'https://JamesWei216@github.com': ← 这里粘 PAT（输入时不会显示字符，粘贴后直接回车）
```

预期输出（大意）：
```
Enumerating objects: 120, done.
...
To https://github.com/JamesWei216/agentic-robotics.git
 * [new branch]      master -> master
 * [new tag]         v0.1-main -> v0.1-main
 ...（共 8 个 tag）
branch 'master' set up to track 'origin/master'.
```

> 不想每次输 token：`git config --global credential.helper store`（会把 token 明文存在 `~/.git-credentials`，
> 用完记得 `git credential-cache exit` 或手动删掉那行）。更稳的是用 SSH（第 7 节）。

---

## 第 4 步：验证（30 秒）

命令行：

```bash
git ls-remote --heads --tags origin | head -12
# 应看到 refs/heads/master + 8 个 refs/tags/*
```

再把远端拉一份全新副本，确认别人 clone 下来是能用的：

```bash
cd /tmp && rm -rf check && git clone https://github.com/JamesWei216/agentic-robotics.git check
cd check
git tag -l                     # 8 个
git ls-files | wc -l           # 79
ls                             # README.md  agent  config  docs  reports  scripts  taskbooks ...
```

网页上刷新第 1 步那个页面，应该能看到：
- 文件列表里有 `README.md`（开头就是四组数字）、`agent/`、`docs/`（4 份文档）、`taskbooks/`、`scripts/`
- 右侧 **Releases/Tags** 或 `Code ▾ → Tags` 里能看到 8 个 tag

---

## 第 5 步：把链接填进提交表

```
https://github.com/JamesWei216/agentic-robotics
```

如果仓库是 **Private**：在 Settings → Collaborators 里把评委/赛题组账号加进来（或用提交表里的大赛指定方式）。

---

## 第 6 节：可能遇到的报错与处理

| 报错 | 原因 | 处理 |
|---|---|---|
| `remote: Support for password authentication was removed` | 用了账号密码 | 回到第 2 步用 PAT |
| `remote: Permission to ... denied to ...` | PAT 没给 **Contents: Read and write**，或仓库没选中 | 重新生成 token，勾这个仓库 + Contents 写权限 |
| `! [rejected] master -> master (fetch first)` | 建仓库时勾了 README/license，远端已有提交 | `git pull --rebase origin master` 然后重新 `git push -u origin master --tags`；或 `git push -f origin master`（远端只有自动生成的 README 时安全）|
| `fatal: remote origin already exists` | 已经加过 origin | `git remote set-url origin <新地址>` |
| tag 没上去 | 只推了分支 | 补一句 `git push origin --tags` |
| 想在网页上看到报告 PDF | 默认不入库（生成物） | 报告 PDF 在 `05_report/` 提交包里；也可在 Releases 上传 |

---

## 第 7 节：可选——改用 SSH（以后不用每次输 token）

```bash
ssh-keygen -t ed25519 -C "james@local"      # 一路回车
cat ~/.ssh/id_ed25519.pub                    # 复制这一行
# GitHub → Settings → SSH and GPG keys → New SSH key → 粘贴 → Add
git remote set-url origin git@github.com:JamesWei216/agentic-robotics.git
git push -u origin master --tags
```

---

## 第 8 节：如果不在本机、想在自己电脑上推

用提交包里的 bundle（含全部历史与 tag）：

```bash
mkdir agentic-robotics && cd agentic-robotics
git clone /path/to/01_repo/agentic-robotics.bundle .
git remote set-url origin https://github.com/JamesWei216/agentic-robotics.git
git push -u origin master --tags
```

---

## 加分 c 的量化证据（可直接贴进提交说明）

```bash
git diff v0.1-main v0.2-variant --stat -- agent/     # 空 → 变体任务对控制链路 0 行改动
git diff v0.1-main v0.2-variant --stat               # 1 file changed, 68 insertions(+) → 只加了一份任务书
```
