# 第四项工作：正式对象与接口迁移路线

> 日期：2026-10-26；工程计划，不是协议规范。  
> 本轮范围：F0 候选路线与验收拆分。F0 方案已备齐，ADR-0007 仍 PROPOSED；F1–F5 未实施。  
> 起点：[19 项迁移缺口](formal-object-migration.md)；候选处置：[ADR-0007](../05-decisions/ADR-0007-formal-object-migration-foundation.md)。

## 1. 第四项交付目标

把三项实验收尾变为可审查的正式化路线：一个任务承诺、一个 Lease 授权权威、一套事件与终态、终态驱动结算。先把 D-1～D-6 的推荐选择、依赖和拒绝条件写清楚，再实施正式 schema；不靠旧对象改名获得完成状态。

本轮交付的是 F0 设计，不是全部迁移完成。没有运行新 guest、SSH 矩阵或正式协议入口；历史双机结果仍只支持原实验。未来网络/故障验收继续采用 DUALHOST-SSH-1。

## 2. 六个问题的本轮处置

| 问题 | 推荐路线 | 接受前仍需补齐 |
|---|---|---|
| D-1 | 统一 canonical 规则；对象 schema/tag 隔离，旧 codec 留实验 | 完整类型/限制/wire keys、编码与签名输入向量 |
| D-2 | REEXEC_AUDIT_ONLY；准确非 TRUSTED 终态下预声明过程费用 | 终态时序与全可达费用/退款/归因矩阵、Snapshot/Profile |
| D-3 | 非主网显式测试日志风险 contract | deployment 字段表达、commit/finality 消费、未知恢复与撤销 |
| D-4 | 测试沿用已有 RSA 适配，Requester/Provider 独立签署 | 精确 suite/envelope、角色责任、key 状态与生效规则 |
| D-5 | 冻结多维保守 cap，未知关联受共同池/全局 cap | 数值/窗口/单位、预留/释放性质及全局并发边界 |
| D-6 | 每 Assignment 一次 guest；有限消息恢复，无自动计算重试 | 各项数值上限、deadline/终态优先级和未知处置 |

推荐不是项目已接受决定。详细权衡、反例与接受条件集中在 ADR-0007，不在本文件复制另一份权威。

## 3. 后续三个实施切片

| 切片 | 范围 | 主要产物与退出条件 |
|---|---|---|
| 第 1 片：基础合约 | 原 F1 + F2 的政策前置；MG-03/05/07/08/13/14 的最小候选字段 | 编码/Principal 签名 envelope/LogicalObject、运行与等价绑定、Funding/Settlement/验证配置候选 schema、摘要 DAG；独立 Python/Rust 正负字节向量。先审查，未冻结不得启用正式入口 |
| 第 2 片：单一任务与执行权威 | F2/F3；MG-06/09/10/12/15/16 及 MG-04 的 provenance 接口 | 新部署串起 Receipt→WorkPlan/Assignment→原子资金+暴露预留→Provider 接受 Lease→派生 capability→持久 START/Attempt→统一事件。两条旧授权在新入口均不能旁路；对应授权/资金/重放双机矩阵覆盖 |
| 第 3 片：终态与结算 | F4/F5；MG-11/17/18/19 | 签名 ResultSubmission→Profile/Snapshot/Evidence/Decision→唯一终态→分项权利/退款→只读优先恢复；精确比较不直接付款。覆盖原 12 场景提交/重放与 12/14 场景结算/恢复，再补期限、旧 epoch、终态竞争与拒绝状态不变 |

MG-01/02 与 ADR-0006/RIR/RPR 完整合规单独并行推进；它们是正式端到端宣称的前置条件，不算本计划自动完成。候选 fixture 可以辅助早期接口向量，不能据此声称替换为正式对象。

第三片的费用矩阵**在第一片就准备并由 Receipt 绑定**，第三片才实现求值与事务。第二片使用的事件 contract/测试部署、签名与时序规则也必须在第一片明确；不能先占用资金，最后再商量退款。

## 4. 接口拒绝与验收包

每一片提交 schema/registry 变化、规范同步清单、golden/negative vectors、独立实现差分、性质检查、真实双机驱动和报告；仅文档候选阶段无须假装运行集成。以下编号是未来验收要求，不是已通过测试。

| ID | 场景/反例 | 必须观察到的结果 |
|---|---|---|
| W4-A01 | aclt.exp.*、旧 task/grant/policy 或未知对象送新入口 | 拒绝，业务状态/余额/attempt 不变 |
| W4-A02 | 非 canonical/重复键/溢出/非 NFC/尾字节/未知字段 | 两语言按冻结规则拒绝，不以 Python 预验证代替 Rust |
| W4-A03 | 同字段改 policy/Profile/资源/输入，或错网络/签署责任 | 新 ReceiptID 或拒绝；不得沿用原承诺 |
| W4-A04 | 政策依赖 ReceiptID，Receipt 又依赖该政策 | 候选摘要依赖审查发现环；禁止空 ID/运行时补写 |
| W4-A05 | 改 key/角色、伪造 acceptance/outcome、用 issuer 代签 Provider | 拒绝且不预留/启动/产生权利 |
| W4-A06 | funded-start/grant 双入口、超资金/暴露、多 Provider/簇并发 | 唯一 Lease 权威，超额或第二次启动拒绝，事务失败全部回滚 |
| W4-A07 | 同任务不同 epoch、同幂等键异内容、旧能力/迟到结果 | 原事实不覆盖；不能进入当前验证或结算 |
| W4-A08 | 相同两端 outcome 或 mismatch/HostFault | 不产生 TRUSTED；走冻结 Profile/原因集合/准确终态 |
| W4-A09 | 无终态、未声明矩阵格、客户端选金额/分支 | 拒绝；不新建 EntitlementKey 或转账 |
| W4-A10 | deadline 与提交/结算竞争，permit-only、断连未知 | 按冻结顺序唯一终态；无自动 guest 重试，恢复后按原政策释放/分配 |
| W4-A11 | 丢回复、COMMIT 前后终止、首次并发结算 | 取原权利/回执；至多一次、分桶守恒；保存失败证据 |
| W4-A12 | checkpoint 缺失/过旧/错误/冲突 | 不驱动新的安全终态/付款；有效旧签名不等于新鲜性或抗回滚 |

通用要求 R-G1～6、A-G1～6 仍见迁移清单；重传原已结算内容返回原结果，不应把 INV-05 误实现为“所有重复请求都报错”。未知 schema 不能当合法“不支持”终态写入尚不存在的任务。

## 5. 完成声明与下一动作

本轮：D-1～6 均有候选处置，X-1～8 均有接口/拒绝边界，MG-01～19 均有阶段归属；方案、路线和验收交付完成。尚未接受的规范细节、代码/双机实现进度明确保留为未完成。

下一动作是**第 1 片：基础合约候选 schema 与独立字节向量**。其首要审查点是签名精确输入、policy→Receipt 无环引用和最小可达终态/费用矩阵；无需先做真实资金、通用市场或生产部署。

[机器可读追踪表](formal-work4-traceability.json)覆盖全部 MG/X/D 与验收编号；其中 PLANNED_NOT_RUN 仅为工程跟踪标签，不是 SemanticStatus，也不是测试通过记录。

## 2026-10-26 工作范围更正

本文件保留为正式对象迁移的候选设计；此前 WORK4/F0 命名不计入原定第四项。原定第四项是 B/Q 的反例与校准研究，已由[第一片](../06-research/bq-boundaries-slice1.md)开始；本草案未被接受，不更改协议或其余工作状态。
