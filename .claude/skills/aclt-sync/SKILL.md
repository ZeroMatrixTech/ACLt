---
name: aclt-sync
description: PARALLEL-1 第 4 步：合并前把最新 origin/main merge 进条目分支，按热点规则解决冲突，重新生成清单，本次重跑检查并推送。轮到该 PR 合并时，在条目会话中使用。
disable-model-invocation: true
---

# 合并前同步

按 `docs/08-governance/parallel-workflow.md`（PARALLEL-1）第 5.4 节与第 6.2 节执行。

不使用 rebase，也不 force push。

## 1. 前提

1. 当前在本条目分支上，且 `git status --short` 为空。
2. 证据提交的 `evidence/*` 标签已推送：用 `git ls-remote --tags origin 'evidence/*'` 核对。
3. 运行 `git fetch origin`。如果 `git merge-base --is-ancestor origin/main HEAD` 成功，说明分支已经包含最新 `main`，跳到第 4 步。

## 2. 合并

```sh
git merge --no-ff --no-commit origin/main
```

使用 `--no-commit`，是为了在提交前重新生成清单并运行检查。

## 3. 解决冲突

用 `git diff --name-only --diff-filter=U` 列出冲突文件，按下表处理：

| 文件 | 处理 |
|---|---|
| `SINGLEHOST-SHA256SUMS`、`WORKFLOW-SHA256SUMS` | 运行 `git checkout --theirs -- <文件>`，第 4 步统一重新生成 |
| `docs/07-roadmap/current-status.md` 状态日志 | 双方的行都保留，本分支的行放在 `main` 的行上方，不改他人的行 |
| `current-status.md` 文末日期小节 | 双方小节都保留，`main` 的在前，本分支的在后 |
| `docs/README.md`、`Makefile` | 取并集，保持原有的排列方式 |
| 其他文件 | 运行 `git merge --abort`，然后停下，报告冲突文件与原因，交调度会话处理 |

解决后，逐个运行 `git add <文件>`。

## 4. 生成与检查

1. 运行 `make manifests`，审阅清单的 diff：其中只应出现本分支与新 `main` 改动的文件对应的行。
2. 运行 `make check`。如果同步带入了代码、测试或 `Makefile` 的变化，改为运行 `make test`。
3. 运行 `git diff HEAD --check`，同时覆盖已暂存和未暂存的改动。

检查失败时，不提交合并。保留现场，报告失败的命令和输出，交维护者决定。

## 5. 提交与推送

1. 逐个 `git add` 重新生成的清单。
2. 运行 `git commit`。说明写 `Merge origin/main into <分支>`，正文列出解决的冲突文件，以及本次运行的命令与退出码。
3. 运行 `git push`（普通推送）。
4. 用 `gh pr checks <PR>` 确认 CI 通过。

## 6. 报告

向维护者和调度会话报告以下内容：

- 合并提交的 SHA
- 冲突文件及处理方式
- 本次运行的命令与退出码
- CI 状态

如果同步带入的变化落在本条目文件集内的非热点文件上，请求审计会话补审这次合并提交。
