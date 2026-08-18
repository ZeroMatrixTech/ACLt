# ADR-0002：RIR 作为规范执行表示，Rust Profile 作为 V1 参考前端

> 状态：`ACCEPTED`  
> 日期：2026-08-18  
> 影响范围：任务语义、Receipt、执行、验证、兼容性与 conformance  
> 关联：INV-01、INV-02、INV-09、INV-16；TH-01、TH-02、TH-03、TH-12、TH-14、TH-18、TH-33—TH-35

## 1. 背景

如果协议直接把 Rust 源码、某个编译器输出、本机二进制或宿主 OS 行为当作执行真相，则不同编译器、平台、运行时和硬件可能对“同一任务”产生不同语义。这样既无法形成稳定 Receipt，也无法允许未来语言前端在不分叉协议的情况下加入。

项目需要一个位于源语言与分布式执行/验证之间的规范边界，同时不能把编译器或运行时误设为新的 Principal 或真理权威。

## 2. 决定

1. **RIR 是 V1 的规范性机器/网络执行表示。** 协议执行语义在 RIR 层冻结，不由源语言或本机指令集定义。
2. **Rust Profile 是 V1 的 reference frontend。** 它提供首个受约束的源语言入口，但 Rust 不是 ACLt Protocol 的唯一或规范语言。
3. **未来允许其他 conforming frontends。** C++23 等前端可以在未来加入，条件是其受支持子集降级到同一 RIR 语义并通过统一 conformance suite。
4. **Receipt 必须绑定规范执行上下文。** 至少需要无歧义绑定 RIRVersion、RIR 工件摘要、输入、执行 Profile、资源/effects 边界及验证语义；准确字段名与编码仍为 `OPEN/P0`。
5. **不允许静默原生回退。** 不受 V1 Profile 支持的程序或 effect 必须在创建、lowering 或验证阶段被拒绝/标为 `UNSUPPORTED`。
6. **V1 暂不支持或不验证以下能力：** unsafe Rust、完整 `std`/宿主 OS effects、原生执行、GPU/专用加速器及非确定性任务。未来引入任何一项都需要独立 Profile、威胁更新、兼容性规则和 ADR。

## 3. 状态边界

该决定关闭“V1 以什么表示作为规范执行边界”以及“首个参考前端是什么”两个架构选择，但不关闭：

- RIR 指令集、类型系统、canonical encoding 或 validator；
- Rust Profile 的准确语法/语义子集与 lowering 规则；
- runtime、effects、资源计量、浮点或并发语义；
- 编译器/运行时正确性证明；
- 结果验证、相关性、资金、结算或分布式容错证明；
- RIR 的计算完备性、性能或任意工作负载适用性主张。

因此本 ADR 不表示 G0 已完成，也不授权生产或公共网络部署。

## 4. 后果

### 正面后果

- 源语言演进与协议语义解耦；
- Receipt 可以绑定可交换、可验证的规范工件；
- Rust 与未来 C++23 等前端可共享执行、验证和测试基础；
- 原生平台差异不能静默改变任务义务；
- 不新增编译器、语言委员会或运行时权威实体。

### 成本与风险

- 必须设计 RIR parser、validator、canonical encoding、runtime 和资源/effects 模型；
- 前端 lowering 与 runtime 会成为供应链和共因故障面；
- 多个前端需要持续的差分、等价和负例测试；
- 受限 V1 Profile 会牺牲完整 Rust/OS/GPU 兼容性；
- 同一 RIR 并不自动意味着结果确定或验证廉价。

## 5. 被拒绝或延期的替代方案

| 方案 | 当前处理 | 原因 |
|---|---|---|
| Rust 源码直接作为规范语义 | `REJECTED` | 编译器、版本和平台差异进入协议真相 |
| 本机二进制/ISA 作为规范语义 | `REJECTED for V1` | 可移植性、审计和跨 Provider 等价性不足 |
| 容器镜像即规范语义 | `REJECTED as sufficient` | 镜像仍包含宿主、架构、内核和运行时差异 |
| V1 同时支持 Rust 与 C++23 原生路径 | `DEFERRED` | 扩大 G0 状态空间与供应链面 |
| V1 直接支持完整 OS/GPU/非确定性任务 | `DEFERRED` | effects、计量、复现和验证边界尚未冻结 |

## 6. 最低验证要求

G0/G1 至少需要产出：

1. RIR grammar/schema、canonical encoding、validator 和正反 golden vectors；
2. Rust Profile 的允许/禁止构造及确定的诊断结果；
3. source → RIR lowering 的版本、摘要和可复现构建规则；
4. RIR runtime 的 effects、资源、终止、错误和 checkpoint 语义；
5. 至少两个独立实现或一个实现加差分 oracle 的 conformance 结果；
6. 对恶意 RIR、编译器差异、隐藏宿主 effect、计量分歧和运行时崩溃的故障注入；
7. 将 RIRVersion/Profile/Digest 变化映射为新 ReceiptID 的测试。

## 7. 连续性结论

本 ADR 扩展 v0.5 的任务语义与实现中立原则，不改变两类 Principal、permissionless functions、验证不确定性、FundingPolicy、证据—能力—暴露链条或 Maintenance 最小权限。V1 是工程一致性目标；v0.5 仍是当前协议语义基线。
