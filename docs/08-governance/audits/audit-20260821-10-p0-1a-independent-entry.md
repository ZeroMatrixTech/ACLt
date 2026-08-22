# AUD-20260821-10：P0-1A VerificationProfile 独立入口审计

> 审计日期：2026-08-21（Europe/Budapest，UTC+02:00）  
> 初始被审文件：`artifacts/verification-profile-schema-draft-11.md`  
> 初始文件 SHA-256：`e4e0003ce9e879535f91fb3256819eed77037c2b909699af48f344e7c9ee5371`  
> 回验规范 SHA-256：`a62e20fe9124e4de587b47f79296f7bd7c456fc73c31b8f75855731780026a2a`  
> 仓库基线：`main` / `a99e344f29f58e61a22c1d0c1b304fd9191c6295`  
> 审计类别：语义连续性、文档变更、P0-1A 入口 Gate、P0-1B 启动审计  
> 修订权限：允许准备本地文件；未获授权提交、推送、建分支或创建 PR

## 1. 结论

初审为 `FAIL / REVISION_REQUIRED`。draft-11 存在会使两个 conforming 实现得到不同编码或不同判决的内部冲突；这些问题不能用“工程假设”绕过。

修订并回验后的标准结论：

> 语义连续性：`PASS`；P0-1A 退出：`PASS`；结构完整性：`PASS`。  
> 允许开展：P0-1B 的 L1a/L1b/L2、注册表、摘要、五相位向量和跨实现对拍。  
> 禁止宣称：P0-1 已关闭、119 项 Type A 已完成、Type B 已由 Schema 证明、`REEXEC_BOUNDED` 已可在通用 permissionless 主网产生 `TRUSTED`、系统已生产就绪。

其他维度：历史隔离 `PASS`；发布准备 `NOT_ASSESSED`。所有修复状态为 `RESOLVED_IN_PREPARED_CHANGE`，在合入目标分支前不得写成 `CLOSED_ON_MAIN`。

## 2. A0—A2：边界、盘点与时间

| 项目 | 记录 |
|---|---|
| 审计目标 | 判断 P0-1A 是否提供单义、可编码、可实现的 P0-1B 输入 |
| 规范基线 | draft-11，SHA-256 如报告头 |
| 决定基线 | ADR-0004、ADR-0005、INV-01—INV-16、当前验证数学模型 |
| Git 基线时间 | 2026-08-19T02:59:01+08:00 |
| 审计快照时间 | 2026-08-21T22:21:32+02:00 |
| 工作树 | 审计开始时已有未提交文档与测试变更；本轮不覆盖或回退无关修改 |
| 排除范围 | 具体生产 B/Q、身份自然人唯一性、日志底层共识正确性、OQ-04/OQ-05 状态机、OQ-08 集群识别正确性、发布许可 |

权威目录映射：

| 职责 | 仓库位置 |
|---|---|
| P0-1A 规范语义 | `docs/03-protocol/verification-profile-schema.md` |
| 工程闭合/主网边界决定 | `docs/05-decisions/ADR-0005-engineering-assumptions-and-mainnet-assurance.md` |
| 条件统计定理与反例 | `docs/06-research/verification-round-mathematical-model.md`、`tests/verification_model/` |
| P0-1B L1a 起始工件 | `schemas/verification-profile/` |
| P0-1B L1b 起始工件 | `tools/verification_profile/` |
| 注册表种子 | `registries/verification-profile/` |
| P0-1B 测试 | `tests/verification_profile/` |

## 3. A3：发现与修订矩阵

| ID | 等级 | 发现与影响 | 修复 | 状态 |
|---|---|---|---|---|
| AUD-20260821-101 | BLOCKER | ADR-0005 已接受，draft-11 仍称“未开始/待裁定”，D-02 没有最终权威 | ADR 增加 D-01—D-10 采纳矩阵；D-02 固定采用 (a) | `RESOLVED_IN_PREPARED_CHANGE` |
| AUD-20260821-102 | BLOCKER | ADR-0005 要求完整 `CauseSet`，draft-11 只保存单 verdict，会丢并发原因 | 冻结 `CauseSet + versioned reducer → EffectiveVerdict`，摘要绑定事实集与 reducer | `RESOLVED_IN_PREPARED_CHANGE` |
| AUD-20260821-103 | BLOCKER | `ConformanceManifest` 与 `RegistrySnapshot` 在注册表中声明嵌套 header，结构正文却是扁平字段 | 两对象统一为 `VersionedUVPHeader`，扁平重复编码不可表达 | `RESOLVED_IN_PREPARED_CHANGE` |
| AUD-20260821-104 | BLOCKER | `Rational` denominator、`VersionRange` 名称和 `TimeRange` 空区间存在两套定义 | 统一为 uint denominator、`min_inclusive`、非空半开范围 | `RESOLVED_IN_PREPARED_CHANGE` |
| AUD-20260821-105 | BLOCKER | MAP-3 要求运行中原地减权，但 UVP 注册对象不可变 | 新 Receipt 用新 MAP 版本；既有 Receipt 通过所需假设撤销 fail closed | `RESOLVED_IN_PREPARED_CHANGE` |
| AUD-20260821-106 | BLOCKER | 最新 ADR 要求 ExecutionCapability，draft-11 的 MAP 没有绑定其 contract | MAP 加入不可变 contract 引用，§13.1A.1 冻结最小 payload、失效语义和双点检查 | `RESOLVED_IN_PREPARED_CHANGE` |
| AUD-20260821-107 | BLOCKER | P0-1 关闭条件把日志 contract 写成 A/B 混合项，与“P0-1B 不关闭 Type B”冲突 | P0-1B 只关闭确定性 verifier/fixture；SV-100 继续留在 Type B，不作为 P0-1B 关闭项 | `RESOLVED_IN_PREPARED_CHANGE` |
| AUD-20260821-108 | MAJOR | `SV-51` 仍描述 condition→terminal 字段，而对象已删除 terminal | 改为 condition 在场，终态只由 `CanonicalTerminal` 派生 | `RESOLVED_IN_PREPARED_CHANGE` |
| AUD-20260821-109 | MAJOR | VPCV-S 使用“子集且全函数”的矛盾措辞 | 改为与方法适用集合精确相等，顺序为全局序列子序列 | `RESOLVED_IN_PREPARED_CHANGE` |
| AUD-20260821-110 | MAJOR | §17.8 把大整数运行时资本错误写成 Profile int64/uint64 `Rational` | 统一到 `finite-population-boundary-lr-v1` 无位宽 `n/d` 格式 | `RESOLVED_IN_PREPARED_CHANGE` |
| AUD-20260821-111 | MAJOR | 非规范示例仍使用旧 cost/claim 字段与错误基础排除项数量 | 示例同步到当前字段和 14 个基础排除项 | `RESOLVED_IN_PREPARED_CHANGE` |

初始失败证据保留在 draft-11 SHA 与本表；没有把修订后的干净结果倒写成“初审即通过”。

## 4. A4—A5：连续性与可实现性

| 链路 | 结果 | 说明 |
|---|---|---|
| ADR-0005 → CauseSet/reducer | PASS | 多事实供诊断，单 verdict 供状态机；两者均进入规范摘要 |
| ADR-0005 → MainnetAssuranceProfile | PASS | 基金会只做限域部署准入，不能进入个案权重或改写终态 |
| active Lease → ExecutionCapability → Dispatch/RPR | PASS / interface | 单一权威、多检查点；旁路性质明确归 Type B |
| finite-population model → Profile 参数 | PASS / conditional | 数学内核不被 Profile 重写；生产 B/Q 仍是部署前提 |
| 日志 contract → EventFrontier | PASS / interface | finality/inclusion/consistency 可确定验证；无旁路属 Type B |
| Claim → ExcludedClaims → Requester | PASS | `TRUSTED` 保持条件性，主网外不继承 assurance |
| P0-1A → P0-1B | PASS | 规范是实现输入；首批实现登记真实覆盖，未反向定义规范 |

工程假设没有被误列为理论 BLOCKER：身份自然人唯一性不再是 V1 目标；日志来源、capability 旁路和主网组件正确性以 Type B/部署证据管理，相应能力在证据缺失时保持 `DISABLED/AUDIT_ONLY` 或 fail closed。

## 5. A6—A7：历史与发布边界

- §20—§28 保留旧审计响应和原结论，§29 明确其历史地位；没有删除失败证据。
- Rank、51%、Foundation 真理权、资金蕴含正确性等旧语义未重新进入当前规范。
- 根许可证未由本轮改写；发布准备、名称、规范/文档许可与第三方许可不在本次 P0-1A Gate 范围，判定 `NOT_ASSESSED`。

## 6. A8：机械与可执行回验

| 检查 | 结果 |
|---|---|
| draft-11 SHA-256 | 与交接值逐位相同 |
| SV 表 | 127 行、127 个唯一 ID；119 Type A、6 Type B、1 DEFERRED、1 作废 |
| VPCV / VPR | 52 个唯一 VPCV ID；50 个 VPR |
| Markdown | 规范文件围栏成对；围栏外恰有一个 H1 |
| 相对链接 | 仓库 47 个 Markdown 文件中未发现缺失目标 |
| JSON | Schema、coverage 与 3 个种子文件均可解析 |
| P0-1B 单元测试 | 9/9 PASS |
| 既有验证模型 | 13/13 PASS（递推/闭式、DP/全枚举、反例与 manifest） |

机械检查不能证明语义安全；其作用是确认修订没有制造结构漂移。

## 7. A9：Gate 边界

| Gate/能力 | 判定 |
|---|---|
| P0-1A | `PASS / CLOSED` |
| P0-1B | `STARTED / NOT CLOSED` |
| P0-1 | `OPEN` |
| G0 退出 | `NOT_ASSESSED`；P0-1A 通过不等于 G0 退出 |
| `REEXEC_BOUNDED` 官方主网启用 | 默认 `DISABLED`；需要后续 MAP 部署证据 |
| 通用 permissionless 正确性 | 未证明，禁止宣称 |

## 8. A10：提交目录映射

本轮新增或直接更新的 P0-1A/P0-1B 文件：

```text
docs/03-protocol/verification-profile-schema.md
docs/05-decisions/ADR-0005-engineering-assumptions-and-mainnet-assurance.md
docs/08-governance/audits/audit-20260821-10-p0-1a-independent-entry.md
schemas/verification-profile/verification_profile.schema.json
schemas/verification-profile/coverage.json
schemas/verification-profile/README.md
tools/verification_profile/__init__.py
tools/verification_profile/validator.py
registries/verification-profile/excluded_claims.seed.json
registries/verification-profile/claim_templates.seed.json
registries/verification-profile/mainnet_assurance.disabled.seed.json
tests/verification_profile/__init__.py
tests/verification_profile/test_validator.py
tests/verification_profile/README.md
```

为仓库入口与状态同步更新：

```text
README.md
docs/README.md
docs/03-protocol/protocol-spec.md
docs/03-protocol/result-validation.md
docs/03-protocol/v1-profile.md
docs/07-roadmap/current-status.md
docs/07-roadmap/open-questions.md
```

工作树还包含本轮开始前已经准备的 ADR-0004、数学模型、工程闭合和跨仓库同步文件。提交时应按本报告与前序审计报告共同覆盖，不能只提交本节新增文件而遗漏其依赖，也不能把缓存、`__pycache__`、下载草稿或工作环境元数据加入版本控制。

## 9. 偏离记录

无。审计按 A0—A10 执行；本地修订获得用户授权，未执行 commit、push、分支删除或 PR 操作。
