# 为 ACLt Protocol 作出贡献

> 文档状态：Living contribution policy  
> 语义基线：v0.5  
> 最后更新：2026-11-15

ACLt Protocol 当前处于 G0 规格化阶段。贡献的首要目标不是快速增加功能，而是让协议的前提、对象、状态转换、不变量、证明义务和失败边界更清晰、更可测试。

## 1. 可以贡献什么

- 协议对象、Schema、canonical encoding 和测试向量；
- SemanticStatus registry、V1 Profile、Abstract Machine 和 Logical Object Schema；
- 状态机、并发模型、性质测试和形式化验证；
- RIR parser/validator、canonical encoding、Rust Profile lowering、RPR/Host OS capability 和差分 conformance 测试；
- Lowering/Decomposition/Packing、Provider Dispatch 与 TaskGraph/Lease 合法性；
- 验证统计、相关性模型和攻击仿真；
- FundingPolicy、SettlementPolicy 和账务状态机；
- 威胁建模、故障注入、适配器一致性和供应链安全；
- 文献核查、论断—来源映射和相关系统比较；
- 术语、文档结构、图表和可复现实验；
- 对既有假设、候选算法或安全主张的反例。

反例、失败结果和“不足以支持结论”的实验与正结果同等重要。

## 2. 贡献前必须理解的边界

贡献不得重新引入以下旧语义：

- Rank/Reputation 作为实体、等级或权威；
- 固定 Broker、Planner、Verifier 或 Scheduler 身份；
- Foundation 作为运行时 Principal 或个案最终裁判；维护组织可以按 ADR-0005 发布限主网、版本化 assurance；
- Provider 数量代表独立控制实体；
- `Nmax = 51% × Provider 数量`；
- 履约能力自动提高验证权；
- 验证资金默认来自发行；
- 区块链自动提供 ACLt Protocol 安全性；
- `TRUSTED` 表示绝对正确。
- 让某个源语言、编译器或原生二进制定义协议执行语义；
- 未经新 Profile/ADR 就把 unsafe Rust、完整宿主 effects、原生执行、GPU 或非确定性任务纳入 V1。
- 把 Logical Object Memory 解释为跨 Provider 共享可变 RAM，或让 RPR 读取隐藏 Host OS 状态；
- 把 FoundationReport、维护报告或付款记录写入验证真理权重。

若要重新讨论已拒绝语义，必须提供新的威胁模型、反例、净风险分析和 ADR，不得仅替换名称。

## 3. 状态与版本处置

所有实质性文档变更必须分别处理：

- `SemanticStatus`：`OPEN`、`CANDIDATE`、`DECIDED`、`INVARIANT`、`SUPERSEDED`、`REJECTED`；
- 指定 ConformanceTarget 的 `VersionDisposition`：`CORE`、`DEFERRED`、`REJECTED`。

`DERIVED`、`ASSUMPTION` 和 `HYPOTHESIS` 是 ClaimQualifier，`P0–P2` 是 Priority。不得用斜杠把这些字段合并，也不得把 V1 `CORE` 写成已经完成的系统事实。V1 处置只更新 `docs/03-protocol/v1-profile.md`；语义状态只更新对应权威来源。

## 4. 变更类型

### 4.1 文档澄清

不改变协议语义的拼写、链接、排版和解释改进，可以直接提交，但仍应确认没有改变 MUST/MUST NOT 的含义。

### 4.2 规范变更

改变对象字段、函数、状态机、终态、资金、验证、暴露或权限的变更必须包含：

1. 问题陈述和可复现反例；
2. 当前行为与拟议行为；
3. 受影响的不变量和 Threat ID；
4. 新增假设、信任根和行政成本；
5. 兼容性、迁移、撤销和安全退出；
6. 正例、负例、边界和并发测试；
7. ADR 或对现有 ADR 的更新；
8. `current-status.md` 与 `open-questions.md` 的同步修改。

### 4.3 新实体或特权组件

新增 Principal、组织、中介或特殊权限前，必须证明：

- 该职能不可缺少；
- 现有 Principal 或 permissionless function 无法合理承担；
- 净安全收益大于权限扩张、行政成本和新单点故障；
- 权限、责任、退出和失陷影响已经机器可测试。

不满足以上条件的提议应改写为公开函数、协议对象或实现组件。

### 4.4 统计或经济主张

提交必须明确：模型、总体、随机性、依赖结构、误差目标、时间窗口、外部收益、参数来源和反证条件。只给模拟均值、单组参数或“攻击看起来不划算”不足以支持安全结论。

### 4.5 工程假设与实现证据

现实输入来源、日志无旁路、部署组件和运行环境可以用工程证据建立，不要求全部改写为形式定理。此类变更必须：

1. 标明属于结构、算法、来源忠实性或部署风险接受哪一层；
2. 绑定版本、网络、组件、有效期和撤销路径；
3. 提供日志、权限、集成、故障恢复或 conformance 证据；
4. 在证据缺失时有 `DISABLED/AUDIT_ONLY` 或 fail-closed 路径；
5. 不让 FoundationReport、实现健康分数或历史履约进入个案真理权重。

## 5. 推荐工作流

工程操作统一见[开发与维护指南](docs/development.md)：先审阅变更并用 `make manifests` 刷新清单，`make check` 运行 Python 回归与校验，`make test` 运行当前全部本地检查。打包不再自动刷新清单。

开发与交接前按 [运行与协作环境规范](docs/08-governance/environment-standard.md)核对 ENV-1、工具链版本、代码基线及验收记录。

1. 先在 `docs/07-roadmap/open-questions.md` 中找到对应 Issue ID；
2. 写明假设、候选方案、拒绝条件和证据层；
3. 更新相应规范或分析文件；
4. 为变更添加确定性测试、性质测试、模型检查或仿真；
5. 更新 `docs/06-research/claims-and-sources.md` 中的论断状态；
6. 运行全部现有检查；
7. 提交小而可审查的变更，每个提交按 §11 签署 DCO（`git commit -s`）；
8. 在证据不足时保留 `OPEN/CANDIDATE`，不提前关闭问题。
9. 按 `docs/08-governance/audit-procedure.md` 执行连续性、结构与 Gate 回验。

## 6. 提交说明模板

```text
Change:
Problem / counterexample:
Status before:
Status after:
Affected objects/functions:
Affected invariants:
Affected threats:
New assumptions:
Compatibility/migration:
Tests or proofs:
Residual risk:
Documents updated:

Signed-off-by: 姓名 <邮箱>
```

最后一行由 `git commit -s` 自动添加，签署规则见 §11。

## 7. 文档同步矩阵

| 变更 | 必须同步检查 |
|---|---|
| Principal / function / authority | terminology、identities-and-roles、system-context、threat-model、ADR |
| 对象或状态机 | protocol-spec、task-lifecycle、invariants、test vectors |
| RIR、前端或执行 Profile | terminology、system-architecture、protocol-spec、threat-model、ADR、conformance tests |
| SemanticStatus 或 VersionDisposition | terminology、ADR-0003、v1-profile、current-status、audit report |
| Abstract Machine、Logical Object、Compile、RPR 或 Dispatch | system-architecture、task-lifecycle、protocol-spec、threat-model、invariants、robustness |
| 验证或统计 | result-validation、robustness、claims-and-sources、open-questions |
| 能力或暴露 | reputation、threat-model、robustness、simulations |
| 资金或结算 | protocol-spec、task-lifecycle、invariants、open-questions |
| 维护或治理 | administrative-cost、ADR、threat-model、current-status |
| Adapter / 区块链 | system-architecture、invariants、robustness、conformance tests |
| 主网 assurance 或工程假设 | design-principles、ADR-0005、threat-model、v1-profile、current-status、audit-procedure |
| 假设原因/reducer 或 Dispatch scope | verification-profile、task-lifecycle、invariants、threat-model、问题思路树、vectors |

## 8. 质量要求

- 使用 `terminology.md` 中的规范术语；
- 使用 **ACLt Protocol**，不得展开 ACLt；
- 每个外部事实优先引用原始论文、官方规范或一手实现文档；
- 明确写出文献支持范围，不能让外部成果替 ACLt Protocol 证明组合系统；
- 不提交无法复现的实验结果；
- 测试必须覆盖合法路径、直接反例、边界、并发、重放和故障恢复；
- 前端/编译器变更必须证明其输出满足同一 RIR 语义；不能以“Rust 编译成功”替代 RIR validator、golden vector 与跨实现差分测试；
- 隐私或控制关联数据必须最小化并说明用途；
- 不得静默删除失败实验、反例或被取代的决定。
- 一个协议权威值可以有多个工程检查点，但实现不得复制并允许检查点改写第二套真相；
- 多原因诊断必须保留完整事实集合，状态机只消费冻结函数派生的唯一结果。

## 9. 审查标准

变更只有在以下问题得到回答后才可合并：

- 是否缩小了歧义或证明义务？
- 是否保持全部相关不变量？
- 是否引入新的身份、权限、假设或行政成本？
- 在 Sybil、串谋、分区、重放、崩溃和资金耗尽下会怎样？
- 是否存在安全终态和回滚路径？
- 是否把候选结论误写为事实？
- 是否把来源忠实性误写成 Schema/定理，或反过来用实现结果定义协议语义？
- 能力未获 assurance 时是否确实关闭或 fail closed？
- 是否同步更新全部权威文档？

## 10. 行为与安全问题

参与者在所有项目空间中的行为要求见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。技术讨论保持可审计、具体并针对论证，不针对个人。涉及未公开漏洞、密钥或可直接利用细节时，按 [SECURITY.md](SECURITY.md) 的私密渠道报告，不在公开 Issue、PR 或讨论中先行披露。

## 11. 许可

本仓库的代码、参考实现、协议规范、文档、研究文稿、测试向量与证据均采用 **Apache License 2.0**（SPDX：`Apache-2.0`），根目录已经包含相应 `LICENSE`。代码许可于 2026-08-17 确定，其余工件于 2026-11-14 决定沿用。源码须带 `SPDX-License-Identifier`，或由仓库的文件外机器可读许可声明覆盖（维护者 2026-11-15 决定，见 OQ-01）。第三方材料保留原许可，并在文件内或同目录标注；目前包括 Unicode 生成数据（`Unicode-3.0`）和 `docs/00-overview/fonts/` 下的五个字体子集（`OFL-1.1`，随附三份 `OFL-*.txt`），完整清单见 [第三方材料清单](docs/08-governance/third-party-materials.md)。Apache-2.0 不授予名称或商标使用权；ACLt 是项目名称，不是商标，项目不声明商标；维护者已于 2026-11-16 决定放弃名称冲突检索并接受同名风险（见 OQ-01），名称、商标与兼容性声明不再作为公开发行的阻断项。

### 贡献签署（DCO）

维护者于 2026-11-15 决定采用 [Developer Certificate of Origin 1.1](https://developercertificate.org/)（DCO）作为贡献许可机制，不使用 CLA。签署表示签署者按 DCO 的条款，确认有权以本仓库的许可证提交该贡献。

- **外部贡献**（来自 fork 的 PR）：每个提交都要在提交说明末尾的 trailer 区带有 `Signed-off-by: 姓名 <邮箱>`，邮箱与提交作者一致，合并提交也不例外；写在正文中间的签署行不算数。用 `git commit -s` 即可自动添加。`.github/workflows/dco.yml` 在 PR 上检查，检查脚本与工作流取自目标分支，不会运行 PR 中的任何内容。**在仓库公开后用一次 fork PR 实测确认“缺签时合并受阻、补签后最新头部通过”之前，这项检查对外部 PR 只作提示**；维护者合并外部 PR 前，须在本地独立核验：`python3 -B scripts/check-dco.py pr --base <目标分支提交> --head <PR 头部提交> --fork true`（需要先 `git fetch origin pull/<编号>/head`）。
- **本仓库分支上的工作**（维护者与 AI 代理）：代理产生的提交不加 `Signed-off-by`。维护者在 squash 合并时，在合并提交说明末尾加上自己的 `Signed-off-by`，代为签署。`dco.yml` 在推送到 `main` 时检查。
- **起算点：** 自引入 `scripts/check-dco.py` 的提交之后开始检查，此前的历史提交不追溯，也不改写。

第三方代码与依赖的接受规则、`NOTICE` 维护规则另行确定，见 OQ-01。在规则完成前，外部贡献应逐项确认来源、版权归属和许可证兼容性，不得合入来源或授权不明的内容。
