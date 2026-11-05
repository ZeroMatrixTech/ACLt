# REVIEW-20261028：ADR-0006 分层评审记录

日期：2026-10-28；基线 `d669b02`。这是范围与证据评审，不是新的接受决定。
唯一决定载体仍为 [ADR-0006](../ADR-0006-rir-deterministic-wasm-core-subset.md)。

## 结论

- **路线**：§2.1 的 Wasm 子集路线已由维护者在 2026-10-23 接受，无需重问。
- **规则**：§3–9 的指令范围、编码/拒绝顺序、计量、ABI、结果与版本仍为 CANDIDATE；本轮未得到新的规则接受授权，ADR 整体保留 PROPOSED。
- **实现**：stats-core 是局部实现证据，完成不等于全 RIR/RPR conformance。
- **准入**：正式执行仍关闭；FM-S2 的固定任务/固定工件限定测试集成可以推进，不必等待与该路径无关的所有指令实现。但它不能宣称正式 CreateReceipt/Lease/RPR 已验收。

不建议仅更换 ADR 头部状态来解除阻塞。若后续选择“规则先接受、实现后验收”，必须由维护者明确接受条目、保留数值/字段与证据边界，并显式同步 §0/§11/§13；本轮不暗改原接受条件。

## 待决规则包

| 规则包 | 已有基础 | 具体未决/验收门槛 | 当前处置 |
|---|---|---|---|
| §3 子集/模块结构 | 整数、有限宿主 effects 的路线已有原型 | 全允许指令/模块 grammar 与实现支持范围分开；不得从“stats 用不到”推导恶意输入无需拒绝 | 保留候选，准备逐项接受 |
| §4 外壳/规范编码/七阶段 | 独立 Rust 外壳、受限 canonical/type 检查与四类负例 | table/element/data/typed block 等 grammar、全错误优先级、量化界限与 guard 的先后关系仍缺 | 保留候选，不宣称全 validator |
| §5 上限/计量 | 工件身份与执行实例上限分开；有 gas 边界证据 | 初始成本数值校准、完整成本表与边界向量；RPR 可声明较窄范围但不能改写 RIR 语义 | 接受方向不等于冻结所有数值 |
| §6/§7 结果与 ABI | A/B/C、五个 ABI 及 exact outcome 的局部实现 | 全 ABI/资源/故障分类和来源保真；注入 memory fault 不等于整机 OOM 容错 | 保留候选与完整故障门槛 |
| §8 lowering | 固定 Rust 构建、受信入口和双机复现 | SDK 允许集合、完整 lowering 正确性与直接提交 RIR 的 provenance 表达 | 复现证据不作正确性证明 |
| §9 版本/身份 | 候选 artifact 版本/字节变化与限额独立 | 正式 ReceiptID 变化测试；不能用 FM 候选 content hash 代替正式对象 | 保留正式身份验收 |

以上“准备接受”是评审建议，不是维护者已经接受。

## §13 逐项证据核对

| 条款 | 已有证据 | 仍缺 | 判定 |
|---|---|---|---|
| 1 两语言规范编解码/拒绝 | [独立核心](../../testing/RIR-INDEPENDENT-CORE-20261028.md)，38 固定向量；两机各 161 项 | 全 module grammar/七阶段顺序/全部列举负例与静态范围 | PARTIAL |
| 2 解释器/gas/trap 对拍 | stats、80 seeded 程序、exact/short gas、div/rem、输出/深度等 | memory.grow/call_indirect/typed control 与完整指令/边界套件 | PARTIAL |
| 3 可选第三方引擎 | 旧 I/O/stats 已有部分 oracle 报告 | 可选项；本轮不引入依赖，也不把它当 gas/绑定 oracle | OPTIONAL，非统一阻塞项 |
| 4 stats-int 与 C++ | [Work 1 收尾](../../testing/RIR-WORK1-CLOSEOUT-20261023.md)保留构建与结果比较证据 | 仅支持原报告范围；新正式对象集成后重跑相应路径 | 已有受限证据，非本轮新跑 |
| 5 宿主故障/validator 分歧 | 内存路径注入、实际输入 I/O 丢失、step ceiling 不产生 Task 摘要 | 全分配点/进程故障容纳；同一工件上实际 validator 判定分歧的故障注入 | PARTIAL |
| 6 版本/成本/上限与正式 ID | 限额变化保持 rir_digest；候选 Receipt 可重绑定 | 真正正式 ReceiptID 的正负变化向量、RIRVersion/成本变化联动 | OPEN |

特别区分：现有 `RPR_REVALIDATION_MISMATCH` 测试改变的是调用方保留的**工件 pin**，不能冒充已验证两个 validator 对同一工件的语义判定分歧。

## §11 同步与 FM-S2 边界

术语、架构、protocol-spec、生命周期、V1 处置、威胁、不变量和 conformance 资产的正式同步仍待接受范围明确后执行。本轮不把实验段落追加到 00–03 的规范正文。

FM-S2 当前只应连接固定 stats 工件/显式支持范围、单一 Lease/epoch、原子资金+暴露预留和统一事件。触及的工件/输入/上限/复验故障路径必须验收，未知工件或范围应拒绝；未触及的完整指令可以保留后续工作。不能用 opaque component pin、文件签名或本评审记录替代运行合规、正式对象和非主网接口审查。
