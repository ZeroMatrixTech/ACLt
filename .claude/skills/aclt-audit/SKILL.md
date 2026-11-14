---
name: aclt-audit
description: PARALLEL-1 第 3 步：在新的只读会话中，按计划卡与仓库规则审计一个 PR，本次复跑检查，并把结论发布为 PR 评论。参数为 PR 号。
argument-hint: <PR 号>
disable-model-invocation: true
---

# 审计 PR

PR：$ARGUMENTS

按 `docs/08-governance/parallel-workflow.md`（PARALLEL-1）第 7 节审计。

## 前提

- 本会话没有参与该条目的实现。如果参与过，停下，请调度会话另开一个新会话。
- 本会话只读：不编辑、不提交、不推送仓库内容，不改 PR 状态。唯一允许的写操作，是在该 PR 上发表审计评论。临时文件放在 scratchpad。
- 本会话在自己的 worktree 中，且 `git status --short` 为空。

## 1. 固定基线

1. 读取 PR：

   ```sh
   gh pr view <PR> --json number,title,body,headRefName,headRefOid,baseRefName,isDraft,files,commits,comments
   ```

2. 从正文的 `Closes #N` 找到计划卡：`gh issue view N --json title,body`。没有计划卡时，计划符合度记为 `FAIL`，其余检查照常进行。
3. 运行 `git fetch origin`，再运行 `git switch --detach <headRefOid>`。
4. 记录 PR 头部 SHA、`origin/main` SHA、审计时间与时区。
5. 如果 PR 评论中已有首行为 `PARALLEL-1 审计 @` 的结论，进入增量模式：只审上次审计的 SHA 到当前头部之间的 diff，并复核所有未关闭的发现项。

## 2. 读取规则

读取下列文件：

- `AGENTS.md` 指定的两份文件
- PARALLEL-1
- `CONTRIBUTING.md` 第 6–9 节
- `docs/08-governance/audit-procedure.md` 第 3 节与 A9

## 3. 检查

### 3.1 计划符合度

- 用 `git diff --name-only origin/main...HEAD` 列出实际改动的文件，与计划卡的文件集比对。逐个列出文件集之外的文件。
- 逐条核对验收标准，写出支持每一条的文件、测试或证据位置。
- 确认非目标没有被触碰。

### 3.2 仓库规则

- **审查问题：** 对 CONTRIBUTING §9 的每个审查问题，给出回答，或说明不适用的理由。
- **文档同步：** 按 CONTRIBUTING §7 与计划卡中的文档同步项，核对相应文档是否已更新；核对当前状态 §8 规定的更新义务。
- **措辞：** 检查是否有越界表述：
  - 候选结论写成事实；
  - VM 或同宿主证据当作物理双机证据；
  - 历史通过当作本次结果；
  - 由测试通过推出 Gate 退出或生产就绪。
- **历史：** 运行 `git diff --diff-filter=DR --name-status origin/main...HEAD`。其中的删除或改名必须有理由。失败证据和历史正文不得被静默改写。
- **隐私：** 在新增的行中查找 IPv4 地址、`/home/` 一类的绝对路径、真实用户名，以及像凭据的字符串。
- **提交说明：** 检查是否使用了 CONTRIBUTING §6 模板。
- **理论缺口（PARALLEL-1 第 5.6 节）：** 找出实现、验收标准或证据依赖的性质，逐项确认它有模型、推导、估计，或者已登记为 `theory-gap` Issue。未登记的缺口，或者为通过验收而挑选参数、阈值或近似的，判为 `MAJOR`，并在结论中列出出处与所需的数学对象。审计不替维护者建模。

### 3.3 代码正确性

有代码改动时，运行 `/code-review high <PR>`。逐项核实它的发现，再写入报告。

### 3.4 本次复跑

依次运行：

- `make check`；代码、测试或 `Makefile` 有改动时，运行 `make test`。
- `python3 -B scripts/update-manifests.py --check`
- `git diff --check origin/main...HEAD`
- 核对证据摘要中的 `source_revision` 能从 `main` 或 `evidence/*` 标签到达。下面两条命令中，满足任一条即可：
  - `git tag --list 'evidence/*' --contains <sha>` 有输出；
  - `git merge-base --is-ancestor <sha> origin/main` 成功。

多虚拟机与双机实验不重跑。用已有的离线检查器核对保留的证据，并在结论中写明“未重跑”。

每条命令都记录退出码。失败照实记录，不为了通过而修改仓库。

## 4. 结论

1. 按 PARALLEL-1 第 7.2 节的格式写成 Markdown。评论首行写 `PARALLEL-1 审计 @ <头部 SHA 前 12 位>`，供下次增量审计定位。
2. 保存到 scratchpad 中的文件，然后运行 `gh pr comment <PR> --body-file <文件>`。
3. 在会话中向维护者报告：建议合并还是退回修改；`BLOCKER` 与 `MAJOR` 的数量；评论链接。
