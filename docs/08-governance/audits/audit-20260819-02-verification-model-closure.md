# ACLt 验证轮模型闭合与对拍审计报告

> 报告状态：`COMPLETE_LOCAL_PREPARED_CHANGE`
> 审计编号：`AUDIT-20260819-02`
> 审计类别：数学模型、反例、跨文档连续性与 conformance 资产审计
> 审计日期与时区：2026-08-19T21:10:20+02:00
> 审计者：Codex（本地修订与独立对拍）
> 程序版本：[`../audit-procedure.md`](../audit-procedure.md)
> 仓库与基线：`tenneidp/ACLt`，`main`
> 完整基线 commit SHA：`a99e344f29f58e61a22c1d0c1b304fd9191c6295`

## 1. 审计目标与权限

| 项目 | 内容 |
|---|---|
| 目标 | 闭合单任务、单候选、二元集群证据的有限总体序贯数学内核；保持递推/闭式/全枚举/DP 对拍；同步当前规范 |
| 范围 | 验证协议、TH/INV/PO/CLM/OQ、V1 Profile、ADR-0004、研究说明和 `tests/verification_model/` |
| 排除范围 | 不证明通用 permissionless 部署的 \(B/Q\)；不实现网络协议、RPR、验证器或多任务误差控制 |
| 输入处理 | 用户提供的 ZIP 只作为不可信参考读取；未执行其中脚本；关键数值由新实现独立复算 |
| 是否允许准备本地修订 | 是；用户要求自我闭合并保持对拍测试 |
| 禁止的仓库写操作 | 不提交、不推送、不创建分支或 PR |

## 2. 语义变更矩阵

| Change ID | 之前 | 之后 | 状态 |
|---|---|---|---|
| VM-001 | \(B\) 容易被解释为实际支持票数上界 | \(B\) 上界 draw 前固定且与排列独立的错误支持能力集合 | `DECIDED / conditional` |
| VM-002 | posterior 与 anytime-valid bound 是双真理闸门 | Bayesian 只作效率层；正确性接受由冻结 e-process 给出 | `DECIDED` |
| VM-003 | 所有验证方式共用重执行聚合语义 | 分为 DIRECT、PROOF、REEXEC_BOUNDED、REEXEC_AUDIT_ONLY | `DECIDED` |
| VM-004 | 活性预算依赖 KL/仿真近似 | 用精确有限总体 DP 求最小分位数预算；端到端界为 \(\delta_Q+\delta_L\) | `DECIDED / conditional` |
| VM-005 | 特殊状态可能混淆分量与终态 | 分量死亡局部归零且不重归一；\(p=0,X=0\) 普通更新；假设撤销为带外 `ASSUMPTION_INVALID` | `DECIDED` |

## 3. 条件定理与不能关闭的部分

闭合命题为：若候选错误时的支持能力集合 \(A^-(c)\) 在 draw 前固定、与随机排列独立、\(|A^-(c)|\le B\)，且 Snapshot/Bridge 有效，则冻结凸混合 e-process 的任意时刻错误接受概率不超过 \(\varepsilon_F\)。

以下不由该定理证明：

- permissionless 环境能建立有限 \(B\)；
- 正确候选至少获得 \(Q\) 个支持的校准覆盖率；
- RIR、RPR、validator、Source→RIR lowering 或 Requester 意图正确；
- 多候选、多任务、非二元结果与联合错误预算。

因此数学内核可以关闭，但通用 `REEXEC_BOUNDED` 部署不能关闭；缺少部署证据时只能使用 `REEXEC_AUDIT_ONLY`。

## 4. 对拍与反例结果

| 检查 | 独立路径 | 结果 |
|---|---|---|
| 逐步资本 | 递推似然比 vs 下降阶乘闭式，枚举全部二元路径 | `PASS` |
| 活性曲线 | 二维 DP vs 全部支持位置枚举 | `PASS` |
| 固定能力集自适应弃票 | Bellman 最坏策略 vs \(\varepsilon_F\) | `PASS` |
| 能力集事后选择反例 | 精确组合枚举，实际票数仍限 \(B\) | `PASS`（反例成立） |
| mixture 分量死亡 | 局部归零、冻结权重、不重归一 | `PASS` |
| 特殊状态 | \(p=0,X=1\)、\(p=0,X=0\)、平台段、假设撤销 | `PASS` |
| 资产完整性 | manifest SHA-256 自校验 | `PASS` |

当前标准库测试共 13 项，全部通过；其中参数网格持续检查递推/闭式一致性，以及固定能力集内最坏自适应弃票不超过 Type-I 界。固定反例中 \(G=10,B=3,Q=8,\varepsilon_F=1/5\)：\(C=3\) 的错误接受率为 \(1/12\)，\(C=4\) 为 \(4/21\)，\(C=5\) 为 \(43/126>1/5\)，\(C=10\) 为 1。\(C=B+1\) 未超过阈值只说明该向量不足以构成反例，不证明放宽后的模型安全。

## 5. 连续性核查

| 核查面 | 结果 | 证据 |
|---|---|---|
| ADR / Profile | `PASS` | ADR-0004 与 V1 Profile 明确 Profile 前置、审计降级和条件 bounded path |
| Threat / Invariants | `PASS` | TH-17/19、INV-12 明确能力集合、冻结参数和带外撤销 |
| Protocol | `PASS` | `result-validation.md` 给出公式、状态、VerifiedClaim 和 ExcludedClaims |
| Analysis / Claims | `PASS` | PO-14、CLM-004/109/110/111 与新边界一致 |
| Roadmap | `PASS` | OQ-07 拆分数学闭合与部署开放；G0 仍进行中 |
| 历史审计隔离 | `PASS` | AUDIT-20260818-01 保留当时结论；其 CHG-007 已由 ADR-0004 和本报告替代 |

## 6. 发现项

| Finding ID | 等级 | 状态 | 影响 | 必需处理 |
|---|---|---|---|---|
| `AUD-20260819-001` | BLOCKER | `OPEN` | 通用 permissionless 总体无法证明 \(|A^-|\le B\) | 不得启用通用 `REEXEC_BOUNDED`；建立部署级能力集合证据或维持审计模式 |
| `AUD-20260819-002` | BLOCKER | `OPEN` | \(Q\) 缺少同任务类锚定校准，活性/成本不可承诺 | 建立带来源和外推标记的 \(Q,\delta_Q\) 校准 |
| `AUD-20260819-003` | MAJOR | `OPEN` | 当前两套 oracle 同为 Python，尚非真正跨语言实现 | G1/G2 增加第二语言实现并消费同一 JSON 向量 |
| `AUD-20260819-004` | MAJOR | `OPEN` | 多候选/多任务错误预算未定义 | 新增 profile/ADR 后才能扩展安全主张 |

## 7. 机械检查结果

| 检查 | 实际 | 结果 |
|---|---|---|
| 标准库 unittest | 13/13 通过 | `PASS` |
| JSON 解析 | vectors、manifest 均有效 | `PASS` |
| Markdown 相对链接 | 全部目标存在 | `PASS` |
| Git whitespace | `git diff --check` 无错误 | `PASS` |
| 精确算术 | 模型、oracle、向量均无浮点断言 | `PASS` |

## 8. 审计结论

> 验证轮条件数学内核：`PASS / CLOSED_CONDITIONAL`；通用 permissionless `REEXEC_BOUNDED`：`FAIL / BLOCKED`；G0 退出：`FAIL`；结构连续性：`PASS`。

允许开展精确算术 reference implementation、第二语言 conformance、DIRECT_VERIFIED Profile 和部署级 \(B/Q\) 证据工作。禁止宣称 ACLt 已解决通用 Sybil、普通重执行已经可靠产生 `TRUSTED`、G0 已关闭或 V1 已生产就绪。

## 9. 交付与残余风险

- 新增：ADR-0004、数学模型说明、6 个对拍资产、本审计报告；
- 修改：结果验证、威胁模型、不变量、鲁棒性、claims、V1 Profile、roadmap 和索引；
- 输入 ZIP SHA-256：`bf8e6da25723adb15e676fe13ed01ee45106640cc2ed582306c46173c2a730c7`；
- 仓库写操作：仅本地文件修订；未 commit、push 或创建 PR；
- 下一次审计触发：第二语言实现、\(B/Q\) 部署证据、Profile Schema 或多任务扩展任一完成。
