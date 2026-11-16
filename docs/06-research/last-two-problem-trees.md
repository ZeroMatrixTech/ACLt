# 最后两个问题的完整思路树

> 状态：`RESEARCH / DECISION SUPPORT`
> 更新日期：2026-08-21
> 关联：ADR-0005；VerificationProfile P0-1A；OQ-05、OQ-08、OQ-11、OQ-12

## 1. 两个问题的共同根因

这两个问题分别表现为“单值还是多值”和“两个绑定点还是三个绑定点”，但共享同一个根因：**谁拥有协议真相**与**工程上在哪里观察、记录和诊断**被混成了同一件事。

需要回答的问题不是“只能选左还是右”，而是：

```text
协议需要一个唯一、可复算的决定
├─ 是否意味着只能保存一个原因？             不是
└─ 是否意味着只能在一个组件里做检查？         也不是

正确拆法
├─ 真相/判决层：唯一、冻结、可重放
└─ 诊断/检查层：可以多原因、多检查点、多实现证据
```

## 2. 问题一：多个假设同时失效的表达方式

### 2.1 直观说明

一次任务可能同时发生三件事：许可证过期、运行范围不符、证据又被撤销。机器最终只需要知道“还能不能继续”，但工程人员还需要知道“到底坏了几处”。

如果只保存一个 verdict，机器简单，但诊断信息丢失；如果直接把所有 flag 都交给状态机，每个实现可能用不同顺序解释它们。

### 2.2 思路树

```text
多原因失效
├─ A. 只保存一个 verdict
│  ├─ 优点：编码小、比较简单、跨实现容易一致
│  ├─ 缺点：第二、第三原因消失，修复与审计困难
│  └─ 适用：资源极小、只关心立即停止的内部组件
│
├─ B. 只保存 flag set
│  ├─ 优点：信息完整，多个原因同时可见
│  ├─ 缺点：集合如何映射终态仍需规则；不能消除判决问题
│  └─ 风险：实现 A 看见 REVOKED 就停，实现 B 先处理 OUT_OF_SCOPE
│
├─ C. 保存有序原因链
│  ├─ 优点：能表达发现顺序和因果关系
│  ├─ 缺点：并发事件常常没有唯一线性顺序
│  └─ 适用：事故调查，不宜直接作为终态算法
│
├─ D. primary cause + contributing causes
│  ├─ 优点：兼顾单一归因和完整诊断
│  ├─ 缺点：primary 若由写入者选择，可能被操纵
│  └─ 修正：primary 必须由冻结函数派生，不能人工填写
│
└─ E. 事实集合 + 派生 verdict（推荐）
   ├─ CauseSet：保存全部可验证原因
   ├─ ReduceCauses：冻结、版本化的纯函数
   ├─ EffectiveVerdict：唯一状态机输入
   └─ 原始集合与派生值一起进摘要，可完整重放
```

### 2.3 推荐对象

```text
AssumptionObservation {
  cause_code       : CauseCode
  evidence_ref     : EvidenceRef
  observed_event   : EventRef
}

AssumptionEvaluation {
  cause_set         : Set<AssumptionObservation>  # 规范排序、去重
  reducer_version   : VersionedObjectRef
  effective_verdict : ValidityVerdict             # DERIVED
}

effective_verdict == ReduceCauses(cause_set, reducer_version)
```

V1 可使用保守归约：

```text
REVOKED > OUT_OF_SCOPE > WINDOW_EXPIRED > VALID
```

这个顺序只决定“当前能否继续”；事故报告中的根因排序不由它决定。事故归因、统计和用户解释读取完整 `CauseSet`。

### 2.4 备选路线与暂不采用的理由

| 路线 | 什么时候考虑 | 暂不作为 V1 主线的原因 |
|---|---|---|
| 格/偏序 verdict | 不同原因不能排成一条严重度链时 | 状态机和 Schema 成本明显上升 |
| 每类假设独立子状态机 | 假设类别长期稳定且相互独立时 | 组合状态爆炸，迁移困难 |
| 事件溯源后按需计算 | 日志后端成熟、查询成本可控时 | 终态验证仍需冻结 reducer 和完整 frontier |
| 概率化健康分数 | 只做运维预测时 | 不能进入协议正确性判决 |

### 2.5 工程试验和退出条件

先实现 E 路线，同时保留升级逃生口：

1. 用 30—50 个多原因组合向量验证两个实现逐位一致；
2. 故障注入同时触发撤销、越界和过期，确认原因不丢失；
3. 对旧单值格式提供确定迁移：`cause_set={旧 verdict 对应原因}`；
4. 如果出现无法由一条优先序安全归约的真实案例，再升级 schema version，引入格或方法特定 reducer；
5. 不因为“flag set 可能更完整”阻塞 V1，也不因为“单值更简单”永久丢掉诊断事实。

## 3. 问题二：第三个 Dispatch scope 绑定点的取舍

### 3.1 直观说明

Requester 先声明允许在哪些条件下执行；Lease 激活时系统确定这次实际执行条件；Snapshot 冻结时系统确定从哪些验证单位抽样。Dispatch 最后真正把任务发出去。

风险在于 Dispatch 可能悄悄替换机器、RPR 或环境；再复制一份 scope 给 Dispatch 会产生三份“真相”，彼此可能漂移。

### 3.2 思路树

```text
Dispatch 时可能发生执行条件漂移
├─ A. 不增加任何检查
│  ├─ 最简单
│  └─ 风险：实现可绕过 Lease，直到事后才发现
│
├─ B. Dispatch 再保存第三份 scope
│  ├─ 优点：表面上最明确
│  ├─ 缺点：三份值谁更权威？同步、竞态和恢复更复杂
│  └─ 结论：不推荐；复制真相不等于加强真相
│
├─ C. Dispatch 读取 active Lease 并做等值检查
│  ├─ 优点：没有新权威，改动小
│  ├─ 缺点：必须审计实现没有绕过读取
│  └─ 适用：V1 最小实现
│
├─ D. Lease 派生不可伪造 ExecutionCapability（推荐）
│  ├─ capability 绑定 receipt/lease epoch/RPR/environment/resource tuple
│  ├─ Dispatch 只能传递，RPR 启动时再次验证
│  ├─ 元组改变立即使 token 无效
│  └─ 没有第三份 scope，只有两个消费检查点
│
├─ E. 远程证明/TEE attestation
│  ├─ 优点：能证明部分运行环境属性
│  ├─ 缺点：供应商、硬件、隐私和成本引入新信任面
│  └─ 适用：高价值、特定硬件 Profile，不是通用 V1 前提
│
└─ F. 连续运行时策略监控
   ├─ 优点：启动后漂移也能发现
   ├─ 缺点：监控器本身成为关键组件
   └─ 适用：后续高保证 Profile；结果只能撤销/作废，不能改写旧 Lease
```

### 3.3 推荐结构：一个权威，多处验证

```text
Requester DeclaredScope
        │  只给允许上限
        ▼
Lease.ActualBoundScope + ExecutionTuple
        │  唯一执行授权
        ├──────────────► Dispatch 验证 capability
        │                    │
        │                    ▼
        │               RPR 再验证 capability
        │                    │
        ▼                    ▼
EligibilitySnapshot     ExecutionRecord
验证总体权威             实际消费记录
```

建议的 capability：

```text
ExecutionCapability = SignOrMAC(
  receipt_id,
  lease_id,
  lease_epoch,
  execution_tuple_digest,
  actual_bound_scope_digest,
  expiry,
  issuer_key_id
)
```

它不是新 Principal，也不是第三个 scope。它只是 active Lease 权威值的不可伪造携带形式。

### 3.4 失败语义

| 情形 | 处理 |
|---|---|
| Dispatch 无 capability | 不得发起执行 |
| capability 过期、epoch 不符或摘要不符 | 拒绝 Dispatch，旧 Lease 不产生权利 |
| RPR 观察到环境与 token 不符 | 终止 Attempt，追加 `EXECUTION_BINDING_INVALID` |
| 执行中资源/环境变化 | 按 Profile 决定 Attempt 作废或 Lease 撤销；不得就地改写 scope |
| 新环境确实需要执行 | 创建新 Lease，重新经过 scope 和暴露检查 |
| 日志或验证器不可用 | fail closed；不得把“暂时无法检查”当作匹配 |

### 3.5 工程试验和退出条件

1. 两个实现分别生成和消费同一 capability golden vectors；
2. 测试换 RPR、换环境、旧 epoch、重放、过期、并发撤销和崩溃恢复；
3. 通过静态数据流审计确认 Dispatch API 没有第二套可覆盖字段；
4. 用事件日志对账 Lease、Dispatch、RPR start 和 Result 的 digest 链；
5. 如果实际平台无法保证 Dispatch/RPR 强制验证 capability，则该部署不能启用需要 scope 保证的 Profile，而不是再增加第四份 scope；
6. 只有发现 Lease 不能表达某个真实授权维度时，才扩展 Lease schema，而不是在 Dispatch 私建字段。

## 4. 两棵树汇合后的统一答案

```text
不复制协议真相
├─ 多原因：保存多个事实，派生一个判决
└─ 多组件：执行多次检查，消费一个权威值

不要求 Schema 证明现实
├─ Schema/纯函数：证明输入到输出唯一
└─ 日志/权限/集成测试：证明实现尽量忠实提供输入

不等待开放世界完美证明
├─ 条件不成立：能力关闭或 AUDIT_ONLY
├─ 条件建立：在官方主网 assurance 范围内 ENABLED
└─ 条件撤销：fail closed，追加事件，不追溯改写历史
```

这两个问题因此不再是 P0-1B 的理论阻塞项。它们转化为：

- `CauseSet + EffectiveVerdict` 的 Schema/向量工作；
- `ExecutionCapability + Dispatch/RPR enforcement` 的接口与 Type B 集成审计工作。
