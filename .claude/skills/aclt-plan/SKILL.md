---
name: aclt-plan
description: PARALLEL-1 第 1 步：为一个 ACLt 开发条目核对在途冲突、起草计划卡；维护者批准后创建 work-item Issue 并建立条目分支。在新的条目会话开始时使用。
argument-hint: <条目描述或 OQ 编号>
disable-model-invocation: true
---

# 规划开发条目

条目：$ARGUMENTS

按 `docs/08-governance/parallel-workflow.md`（PARALLEL-1）第 5.1 节规划。

维护者批准计划卡之前，不修改任何文件，不建分支，也不建 Issue。

## 1. 读取与基线

1. 读取下列文件：
   - `AGENTS.md` 指定的两份文件
   - `docs/08-governance/parallel-workflow.md`
   - `CONTRIBUTING.md` 第 5–9 节
   - `docs/07-roadmap/current-status.md` 第 7 节
   - `docs/07-roadmap/open-questions.md` 中与本条目相关的 OQ
2. 运行 `git fetch origin`，记录 `git rev-parse origin/main` 的完整 SHA。
3. 确认本会话在自己的 worktree 中：`git rev-parse --show-toplevel` 位于 `.claude/worktrees/` 下，且 `git status --short` 为空。不满足时停下，告诉维护者。

## 2. 在途条目

运行：

- `gh issue list --label work-item --state open --json number,title,body`
- `gh pr list --state open --json number,title,headRefName,files`
- `git worktree list`

从每个在途条目的计划卡或 PR 文件列表，得出它的文件集。

## 3. 起草计划卡

按 `.github/ISSUE_TEMPLATE/work-item.md` 的字段起草计划卡。

- 文件集写到具体路径。
- 热点文件单独列出：`SINGLEHOST-SHA256SUMS`、`WORKFLOW-SHA256SUMS`、`docs/07-roadmap/current-status.md`、`docs/README.md`、`Makefile`。
- 验收标准要能由审计会话逐条检验。
- **理论依赖：** 列出本条目依赖、但尚无模型、推导或估计支撑的性质（PARALLEL-1 第 5.6 节）。每一项都先用 `gh issue list --label theory-gap --state all` 查找已有 Issue；没有的，在计划卡中写明出处、所需数学对象和它阻塞什么，批准后按 `.github/ISSUE_TEMPLATE/theory-gap.md` 建 Issue。验收依赖某个缺口时，把相应部分写成“等待建模”，不自行建模，也不挑选参数。
- 不写入凭据、真实 IP、用户名或本地路径。

## 4. 并行判定

在计划卡的“并行判定”一节，从下面三项中选一项：

- **可并行**：文件集与在途条目除热点文件外无交集，且没有未合入的依赖。
- **排队**：与某个在途条目的非热点文件相交，或依赖未合入的条目。写明在等哪个 Issue 或 PR。
- **需排期**：需要多虚拟机、物理双机或 B 机运行。写明预计时段，由调度会话安排。

## 5. 等待批准

把计划卡全文发给维护者，等待明确批准。有修改意见时，回到第 3 步。

## 6. 批准后

1. **建 Issue：** 把计划卡写入 scratchpad 中的文件，然后运行：

   ```sh
   gh issue create --title "<type>: <topic>" --label work-item --body-file <文件>
   ```

   如果 `work-item` 标签不存在，不带标签创建，并提醒维护者按 PARALLEL-1 第 8 节创建该标签。
2. **建分支：** 判定为“排队”时，到此为止，不建分支。否则运行：

   ```sh
   git switch --no-track -c <type>/<topic> origin/main
   ```

   worktree 原先自动生成的分支如果没有提交，可以用 `git branch -d` 删除。
3. **回复与开始实现：** 回复 Issue 链接、分支名和基线 SHA，然后按 PARALLEL-1 第 5.2 节开始实现。
