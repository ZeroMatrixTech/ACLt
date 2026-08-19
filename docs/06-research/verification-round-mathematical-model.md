# 验证轮有限总体数学模型

> 数学内核状态：`DECIDED / DERIVED / conditional`
> 部署 Profile 状态：`CANDIDATE / P0`
> 适用范围：单任务、单候选、二元集群证据、不放回抽样
> 不适用范围：通用 permissionless 错误能力上界、多候选联合误差、非二元结果和未冻结能力集合

## 1. 结论边界

本模型闭合的是以下条件命题：

\[
\begin{aligned}
&BridgeValid(c)
\land |A^-(c)|\le B
\land A^-(c)\perp DrawOrder\\
&\land SnapshotValid
\Longrightarrow
P(\text{错误 TRUSTED})\le\epsilon_F
\end{aligned}
\]

其中，`A⁻(c)` 是候选 `c` 无效时，在某种允许策略下可能输出支持的集群集合。`B` 上界的是**错误支持能力集合**，不是运行后实际观察到的支持票数。

当前 ACLt 无法为通用 permissionless 总体证明 `|A⁻|≤B`，也没有完成 `Q` 的同适用域真值校准。因此数学内核可以条件性关闭，通用 `REEXEC_BOUNDED` 部署能力仍为 `OPEN/BLOCKER`。

## 2. VerificationProfile

每个 Profile 至少冻结：

- `VerifiedClaim` 与 `ExcludedClaims`；
- 总体大小 `G` 和集群级抽样单位；
- 错误支持能力上界 `B` 及其外生证据；
- 正确候选最低支持数 `Q` 及校准适用域；
- `epsilonF`、`deltaQ`、`deltaL`；
- 候选摘要、Snapshot、随机排列规则和 `Nmax`；
- e-process Algorithm ID、mixture 权重、数值编码和特殊状态；
- 成本模型、失效信号和终态映射。

必须满足：

\[
0\le B<Q\le G
\]

定义：

\[
\beta=\frac BG,\qquad
\underline q=\frac QG,\qquad
\Delta_{bound}=\underline q-\beta
\]

Profile 冻结 `DeltaMin`，并确定性检查 `DeltaBound≥DeltaMin>0`；不得把 `DeltaBound` 作为与 `B/Q` 独立的人工输入。

## 3. CorrectnessBridge

对冻结候选 `c`：

\[
A^-(c)=\{g:c\text{ 无效时，}g\text{ 在某种允许策略下可能支持 }c\}
\]

Profile 必须声明并提供外生依据：

1. `A⁻(c)` 的成员资格在抽样排列生成前确定；
2. 随机排列在给定 `A⁻(c)` 后仍为均匀不放回排列；
3. `|A⁻(c)|≤B`；
4. 移动腐化、共同控制和共因缺陷产生的全部可能支持者都包含在该集合中；
5. 攻击者可以观察全部历史并对已抽中的能力单位选择支持或弃权，但不能把支持能力转移给集合外单位。

只限制：

\[
\sum_t X_t\le B
\]

并不充分。若攻击者控制 `C>B` 个可能支持单位，再按抽样顺序选择其中 `B` 个投票，条件支持概率可以超过协议使用的 `p_t`。

运行时不能从同一批票推断真实 `|A⁻|`。正确流程是：

```text
SupportCapabilityBound 未建立
    → REEXEC_BOUNDED 不得启动

SupportCapabilityBound 被独立证据撤销
    → ASSUMPTION_INVALID → UNRESOLVED

SupportCapabilityBound 仍有效
    → 按冻结模型继续；不得用票数反向“自检”能力集合
```

## 4. 抽样与超鞅条件

设第 `t` 次抽样前：

- 已观察 `t-1` 个不同集群；
- 其中 `s_{t-1}` 个支持候选；
- 剩余总体 `R_t=G-t+1`。

零假设为：

\[
H_0(c):c\text{ 无效}
\]

在 CorrectnessBridge 下：

\[
P(X_t=1\mid\mathcal F_{t-1},H_0)
\le
p_t
=
\frac{B-s_{t-1}}{R_t}
\]

证明：设已抽中的能力单位数为 `a_{t-1}`。因为 `s_{t-1}≤a_{t-1}`，剩余能力单位数满足：

\[
|A^-\cap U_t|
\le B-a_{t-1}
\le B-s_{t-1}
\]

下一单位从 `U_t` 均匀抽取，故得到条件概率上界。该证明允许固定能力集内的对手观察全部历史后自适应弃票。

## 5. 边界似然比 e-process

对某个活性边界分量 `m>B`，定义：

\[
q_t^{(m)}=\frac{m-s_{t-1}}{R_t}
\]

单步因子为：

\[
E_t^{(m)}=
\begin{cases}
q_t^{(m)}/p_t,&X_t=1\\
(1-q_t^{(m)})/(1-p_t),&X_t=0
\end{cases}
\]

累计资本：

\[
M_t(m,B)=\prod_{j=1}^t E_j^{(m)}
\]

在普通可达状态下，它等于下降阶乘闭式：

\[
M_t(m,B)=
\frac{(m)_{s_t}(G-m)_{t-s_t}}
{(B)_{s_t}(G-B)_{t-s_t}}
\]

因为 `m>B`，单步因子关于实际条件支持概率单调递增；在实际条件支持概率不超过 `p_t` 时：

\[
E[E_t^{(m)}\mid\mathcal F_{t-1}]\le1
\]

因此 `M_t(m,B)` 是 `H0` 下的非负超鞅。

## 6. Bayesian 效率混合

Bayesian 信息只用于选择备择分量的冻结混合：

\[
M_t^\pi=\sum_{m=Q}^{G}\pi(m)M_t(m,B)
\]

其中权重非负、和为一，并在观察前冻结。每个分量均为合法 e-process，故凸混合仍为合法 e-process。

单个分量若与观察历史不再相容，资本永久归零；其权重不得在观察后重新归一化。错误 prior 只影响效率和活性，不改变模型内 Type-I 上界。Provider 历史、CapabilityEstimate 和 FoundationReport 不得进入 `pi(m)`。

最小 Profile 可以只使用边界分量：

\[
\pi(Q)=1
\]

`PosteriorRisk≤epsilonB` 不再作为独立真理闸门；posterior 可以作为非规范性遥测，但不能授权或否决 `TRUSTED`。

## 7. 接受与特殊状态

接受条件：

\[
Accept(c)
\iff
BridgeValid(c)
\land SnapshotValid
\land M_t^\pi\ge1/\epsilon_F
\]

由 Ville 不等式：

\[
P\left(\sup_tM_t^\pi\ge1/\epsilon_F\mid c\text{ 无效}\right)
\le\epsilon_F
\]

特殊状态必须通过整数/有理数谓词识别，不得使用浮点无穷、NaN 或实现自选 `lambda cap`。

### `NULL_BOUND_EXACTLY_EXCEEDED`

若抽样前 `B-s_{t-1}=0` 且本轮 `X_t=1`，则在冻结 Bridge 下零假设不可能成立。该状态条件性映射为接受，不是能力集合的运行时自检。

### `COMPONENT_LIVENESS_INVALIDATED(m)`

若：

\[
m-s_t>G-t
\]

则分量 `m` 与观察历史不相容，资本置零。单个分量死亡不终止 mixture；只有全部分量归零或达到其他冻结终止条件时，验证轮才进入 `UNRESOLVED`。

### `p_t=0` 且 `X_t=0`

这不是特殊状态，正常计算：

\[
E_t^{(m)}=1-q_t^{(m)}
\]

## 8. 活性与精确 DP

活性结论严格条件于：

\[
c\text{ 有效}\Rightarrow M(c)\ge Q
\]

定义停止时间：

\[
\tau=\inf\{t:M_t^\pi\ge1/\epsilon_F\}
\]

精确活性预算为：

\[
N_{required}
=
\min\{n:P_{M=Q}(\tau\le n)\ge1-\delta_L\}
\]

由于资本由 `(t,s_t)` 唯一决定，可以用有限状态动态规划计算完整吸收概率曲线。曲线只要求单调非减，允许连续多个 draw 出现平台。

如果 `Q` 是覆盖概率 `1-deltaQ` 的同适用域校准下界，则端到端活性只能声明：

\[
P(\tau\le N_{required})\ge1-\delta_Q-\delta_L
\]

部署还必须满足：

\[
N_{required}\le
N_{max}=\min(N_{population},N_{budget},N_{policy})
\]

`3×KL`、平均对数增长或 Monte Carlo 分位数不得替代规范 DP；它们只能作为规划提示或独立对拍。

## 9. Profile 处置

| Profile | 允许的协议结论 |
|---|---|
| `DIRECT_VERIFIED` | 确定性 predicate/证书有效时可按其独立语义输出 `TRUSTED` |
| `PROOF_VERIFIED` | 在证明系统、statement binding 和 verifier 假设内输出条件性 `TRUSTED` |
| `REEXEC_BOUNDED` | 仅在 `B/Q`、能力集合和抽样条件成立时使用本模型 |
| `REEXEC_AUDIT_ONLY` | 无法建立 `B` 时只形成审计证据，不输出统计 `TRUSTED` |

通用 permissionless V1 当前只能把普通重执行放入 `REEXEC_AUDIT_ONLY`，除非某个具体部署或任务 Profile 独立建立全部前提。

## 10. 对拍与反证资产

可执行资产位于 [`../../tests/verification_model/`](../../tests/verification_model/)：

- 逐步有理数状态机对拍下降阶乘闭式；
- 精确 DP 对拍全排列枚举；
- 固定能力集下最坏自适应弃票策略；
- `C>B`、但实际票数仍不超过 `B` 的模型反例；
- mixture 分量局部死亡且不重新归一化；
- `p=0` 两个分支、平台段和假设撤销。

当前小总体反例使用 `G=10,B=3,Q=8,epsilonF=1/5`，精确结果包括：

| 能力集大小 `C` | 实际票数预算 | 错误接受概率 |
|---:|---:|---:|
| 3 | 3 | `1/12` |
| 4 | 3 | `4/21` |
| 5 | 3 | `43/126`，超过 `1/5` |
| 6 | 3 | `11/21` |
| 8 | 3 | `8/9` |
| 10 | 3 | `1` |

这些数值绑定 `finite-population-boundary-lr-v1`。未来算法变得更保守时，某个越界场景不再超过 `epsilonF` 不构成安全回归；算法改变必须使用新 ID、证明和向量。

## 11. 尚未关闭

- permissionless 环境中 `|A⁻|≤B` 的可证明来源；
- RPR/validator 共因故障如何进入能力集合；
- `Q` 的同任务类、同 Profile、同资源范围真值校准；
- 多候选、多终点、多任务联合错误预算；
- 非二元证据、容差结果和未知/缺失的其他编码；
- Proof/Direct Profile 的 statement、成本和 conformance。
