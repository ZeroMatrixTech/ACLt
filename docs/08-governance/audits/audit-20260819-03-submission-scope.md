# ACLt 新提交范围与远端连续性审计报告

> 报告状态：`COMPLETE_LOCAL_PREPARED_CHANGE`
> 审计编号：`AUDIT-20260819-03`
> 审计类别：远端同步、提交范围、结构连续性与回验审计
> 审计日期与时区：2026-08-19T21:17:42+02:00
> 审计者：Codex（GitHub 与本地工作树联合核查）
> 程序版本：[`../audit-procedure.md`](../audit-procedure.md)
> 仓库与基线：`tenneidp/ACLt`，`origin/main`
> 完整基线 commit SHA：`a99e344f29f58e61a22c1d0c1b304fd9191c6295`

## 1. 审计目标与权限

| 项目 | 内容 |
|---|---|
| 目标 | 拉取 GitHub 当前状态，排除已由 PR #23 合入的重复修改，确定下一次提交的最小完整范围 |
| 范围 | GitHub `main`、最近提交/PR、本地工作树、现行 Markdown、验证模型测试和审计记录 |
| 排除范围 | 不提交、不推送、不创建分支或 PR；不改写历史提交 |
| 允许的只读操作 | GitHub 仓库/提交/PR 查询，git fetch、diff、status、日志与机械检查 |
| 是否允许准备本地修订 | 是；仅补充本报告和远端处置记录 |
| 禁止的仓库写操作 | commit、push、merge PR、删除用户修改 |
| 偏离记录 | 无 |

## 2. 基线与文件盘点

GitHub 当前事实：

- 仓库：`tenneidp/ACLt`，private，默认分支 `main`；
- 远端 `main`：`a99e344`，`Docs/update all (#23)`；
- PR #23 已于 2026-08-18T18:59:02Z 合并；
- 当前没有 open Pull Request；
- 本地已 fetch/prune，并安全快进到该提交；工作树内容完整保留；
- 当前没有本地提交领先远端，也没有待合并远端提交。

下一提交范围在加入本报告后为：

| 类型 | 数量 | 说明 |
|---|---:|---|
| 修改 | 10 | 根 README、requirements、validation、V1 Profile、robustness、claims、roadmap 和 docs index |
| 新增 | 11 | ADR-0004、数学模型、3 份审计记录、6 个验证测试资产 |
| 删除 | 0 | 不删除任何现行或历史文件 |
| 合计 | 21 | 应作为一个语义闭合提交审阅 |

## 3. 需要提交的文件

### 修改文件（10）

| 目录 | 文件 | 提交理由 |
|---|---|---|
| 根目录 | `README.md` | 新增 ADR-0004、数学模型和 tests 入口 |
| `docs/01-requirements/` | `invariants.md`、`threat-model.md` | 冻结 \(B/Q\)、Profile、能力集合和失效处理 |
| `docs/03-protocol/` | `result-validation.md`、`v1-profile.md` | 落实四类 VerificationProfile 和有限总体 e-process |
| `docs/04-analysis/` | `robustness.md` | 更新 PO-14、相关性耦合失效和残余风险 |
| `docs/06-research/` | `claims-and-sources.md` | 更新 CLM-004/109，新增反例和 DP 论断 |
| `docs/07-roadmap/` | `current-status.md`、`open-questions.md` | 区分条件数学闭合与部署阻塞 |
| `docs/` | `README.md` | 修复/补全 ADR、模型、审计索引 |

### 新增文件（11）

| 目录 | 文件 | 提交理由 |
|---|---|---|
| `docs/05-decisions/` | `ADR-0004-verification-profiles-and-finite-population-e-process.md` | 记录已接受的验证 Profile 与数学边界 |
| `docs/06-research/` | `verification-round-mathematical-model.md` | 给出条件定理、状态、反例、DP 和适用边界 |
| `docs/08-governance/audits/` | `audit-20260818-01-semantic-structure.md` | 补交 PR #23 对应历史审计；同时修复远端索引指向不存在文件的问题 |
| 同上 | `audit-20260819-02-verification-model-closure.md` | 验证模型闭合审计 |
| 同上 | `audit-20260819-03-submission-scope.md` | 本次远端与提交范围审计 |
| `tests/verification_model/` | `README.md`、`recursive_model.py`、`closed_form_oracle.py`、`test_verification_model.py`、`conformance_vectors.json`、`manifest.json` | 精确递推/闭式/全枚举/DP 对拍与资产完整性 |

## 4. 语义差异矩阵

| Change ID | 之前（`a99e344`） | 下一提交之后 | 影响追踪 | Gate |
|---|---|---|---|---|
| SUB-001 | Bayesian posterior 与 anytime-valid bound 仍是候选双闸门 | Bayesian 仅作效率层；正确性由条件有限总体 e-process 给出 | TH-19、PO-14、CLM-109、OQ-07 | G0/G1 |
| SUB-002 | \(B\) 未区分能力集合与实际票数 | \(B\) 明确上界 draw 前固定且独立的错误支持能力集合 | TH-17/19、INV-12、CLM-004/110 | G0/G1 |
| SUB-003 | 验证类型没有统一 Claim/成本边界 | DIRECT、PROOF、REEXEC_BOUNDED、REEXEC_AUDIT_ONLY 由 VerificationProfile 前置 | ADR-0004、OQ-06 | G0 |
| SUB-004 | 活性预算仍是开放的抽象问题 | 精确 DP 计算条件活性；端到端界为 \(\delta_Q+\delta_L\) | CLM-111、OQ-07 | G1 |
| SUB-005 | 远端 docs index 引用未提交的审计文件 | 补交历史审计并增加当前模型/提交审计 | 文档连续性 | G0 |

## 5. 连续性核查

| 核查面 | 结果 | 冲突或证据 |
|---|---|---|
| GitHub / 本地基线 | `PASS` | HEAD 与 `origin/main` 均为 `a99e344` |
| Overview / terminology | `PASS` | PR #23 已合入，本轮不重复修改 |
| ADR / Profile | `PASS` | ADR-0004 与 V1 Profile 同步 |
| Threat / invariants | `PASS` | 能力集合、冻结参数和失效处理一致 |
| Protocol / research | `PASS` | 公式、Claim、Profile 和边界一致 |
| Roadmap / Gate | `PASS` | 数学内核条件关闭；G0 与部署阻塞仍开放 |
| 文件名 / 索引 | `PASS_AFTER_SUBMIT` | 提交 3 份 audit 文件后所有相对链接闭合 |

## 6. 威胁—不变量—实现证据

| Threat | Invariant | 证明义务 | Test/conformance | 状态 |
|---|---|---|---|---|
| TH-15/16 | INV-11/12 | 冻结 Snapshot、随机顺序、不放回 | JSON vectors、路径枚举 | `PASS_CONDITIONAL` |
| TH-17/19 | INV-10/12/14 | 固定能力集合 \(|A^-|\le B\) | 自适应弃票 DP、\(C>B\) 反例 | 数学 `PASS`；部署 `BLOCKED` |
| 活性尾部 | INV-09/12 | \(M(c)\ge Q\) 条件下分位数预算 | DP 对拍全排列 | `PASS_CONDITIONAL` |
| 跨实现分歧 | INV-12/16 | 精确算术和特殊状态唯一 | 递推/闭式网格、manifest | Python 内 `PASS`；第二语言 `OPEN` |

## 7. 发现项

| Finding ID | 等级 | 状态 | 影响 | 必需处理 |
|---|---|---|---|---|
| `AUD-20260819-005` | MAJOR | `RESOLVED_IN_PREPARED_CHANGE` | 远端 `docs/README.md` 引用缺失的 `audit-20260818-01` | 将该审计文件纳入本提交 |
| `AUD-20260819-006` | BLOCKER | `OPEN` | 通用 permissionless 环境仍不能证明 \(B\) | 不得宣称 `REEXEC_BOUNDED` 普遍可部署 |
| `AUD-20260819-007` | BLOCKER | `OPEN` | \(Q\) 缺少同任务类锚定校准 | 只能作条件活性结论 |
| `AUD-20260819-008` | MAJOR | `OPEN` | 两套 oracle 仍同属 Python | 后续加入第二语言 conformance |

## 8. 机械检查结果

| 检查 | 实际 | 结果 |
|---|---|---|
| 标准库 unittest | 13/13 | `PASS` |
| JSON | vectors、manifest 可解析 | `PASS` |
| SHA-256 manifest | 4 个核心资产匹配 | `PASS` |
| Markdown H1 / 围栏 | 合法 | `PASS` |
| 相对链接 | 工作树全部存在 | `PASS` |
| `git diff --check` | 无 whitespace error | `PASS` |
| 临时文件 | 无 `__pycache__` | `PASS` |

## 9. 审计结论

> 远端同步：`PASS`；提交范围：`PASS`；语义连续性：`PASS`；G0 退出：`FAIL`；通用 `REEXEC_BOUNDED`：`BLOCKED`。

建议使用一个原子提交，因为 ADR、规范、claims、roadmap、测试和审计互为闭合证据。推荐提交标题：

```text
docs(verification): close conditional finite-population model
```

禁止在提交或 PR 中声称通用 Sybil 已解决、普通重执行已经无条件产生 `TRUSTED`、G0 已关闭或 V1 已生产就绪。

## 10. 修订与交付

| 目标目录 | 文件数 | 操作 |
|---|---:|---|
| 仓库根与 `docs/` | 15 | 修改 10、新增 5 |
| `tests/verification_model/` | 6 | 新增 |

- 建议提交文件数：21；
- 删除文件数：0；
- 基线：`a99e344f29f58e61a22c1d0c1b304fd9191c6295`；
- 仓库写操作：已 fetch/prune 并将本地 `main` 安全快进；未 commit、push 或创建 PR；
- 下一步：审阅 21 个文件后，以单一提交进入新分支/PR。
