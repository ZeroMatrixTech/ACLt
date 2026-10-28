# ADR-0006：RIR-0 以确定性 Wasm 核心子集为主体

> 状态：`PROPOSED`（草案，未接受）  
> 起草日期：2026-10-23  
> 最后修订：2026-10-23（审阅建议落实；仍为候选）
> 影响范围：RIR 编码、validator、RPR 执行语义、资源计量、Receipt 执行绑定与 Rust Profile lowering  
> 关联：ADR-0002、ADR-0003、ADR-0005；OQ-02、OQ-05；INV-01、INV-02、INV-09、INV-16；TH-14、TH-33、TH-34

## 0. 草案边界

- §2.1 的路线选择是 2026-10-23 用户明确作出的项目决定：RIR 主体采用 Wasm 子集，不自研指令集。本 ADR 负责把该决定落入文档。
- §3—§9 的子集、编码、计量、结果映射、宿主 ABI 与版本规则是助手起草的候选条款，SemanticStatus 为 `CANDIDATE`。按[审计程序](../08-governance/audit-procedure.md) §4，它们在接受前属于“未接受草案”，不得作为实现或 conformance 的规范依据。
- 本草案不修改协议规范、不变量、威胁模型或 V1 Profile；接受时的同步项见 §11。
- 本草案不改变任何 Gate 状态，不表示 G0、P0-1B 或 G2 有新的关闭证据。

## 1. 背景

ADR-0002 已决定 RIR 是 V1 的规范执行表示、Rust Profile 是参考前端，但 RIR 指令集、类型系统、canonical encoding、validator 与 runtime/effects/resource 语义仍为 `OPEN/P0`。

选择指令集时的硬约束是 Rust Profile 必须能降级到 RIR。自研 IR 需要自写 Rust 子集编译器，或依赖 rustc 不稳定的内部表示，工作量和供应链面都超过当前 G0 能承受的范围。rustc 已提供 Tier 2 目标 `wasm32v1-none`：只启用 WebAssembly Core 1.0 与 mutable-globals，`core`/`alloc` 按同一特性集合预编译，可在 stable 工具链上使用（S16）。

但 Wasm 不能原样作为 RIR。官方规范（S14、S15）至少留有以下实现自由或非确定性：

| 来源 | 规范行为 | 对 ACLt 的问题 |
|---|---|---|
| LEB128 | 在 \(\lceil N/7\rceil\) 字节内允许补零的非最短编码 | 同一模块可有多种字节，摘要不唯一 |
| 自定义段 | 可出现在任意位置且不影响语义 | 不改变语义却改变摘要 |
| `memory.grow` | 非确定：超过声明上限时必须失败，其他情况下也可以失败；官方确定性 profile 仍保留此项 | 两个 RPR 对同一 Receipt 给出不同结果 |
| 浮点 NaN | 结果 NaN 的符号与 payload 非确定；确定性 profile 只固定为正的规范 NaN | 字节级精确比较会因实现而异 |
| 运行时限制 | 栈帧数、值栈大小由实现决定，超限时报告实现特定错误 | 资源耗尽点不跨实现一致 |
| 宿主函数 | 调用宿主函数的行为是非确定的 | 宿主可注入隐藏输入 |

因此需要一层 ACLt 规则：选定 Wasm 子集，并把上述每一处自由改写为唯一行为、静态拒绝或 RPR 故障。

## 2. 决定

### 2.1 路线（项目决定，2026-10-23）

RIR 主体以 WebAssembly Core 1.0 的一个确定性子集为基础。RIR 的规范语义是“Wasm Core 1.0 执行语义在本 ADR 子集上的限制，再加本 ADR 的 ACLt 规则”；二者不一致或 Wasm 留给实现决定时，以本 ADR 为准。任何 Wasm 引擎、运行时或其维护组织都不是 RIR 语义来源，最多是 RPR 候选实现或差分 oracle。

### 2.2 候选条款摘要

1. RIR 工件 = 规范 CBOR 外壳 + 规范 Wasm 字节（§4）。
2. RIR-0 子集只含 Wasm 1.0 的整数指令，禁止浮点和全部 1.0 之后的特性（§3）。
3. 资源上限由 Receipt 绑定，指令计量使用规范成本表（§5）。
4. 结果分为三类：创建期拒绝、Task 语义结果、RPR/Host 故障；后者不得改写为前者（§6）。
5. 宿主 ABI 只有 5 个函数，没有时间、随机、文件、网络或环境输入（§7）。
6. RIRVersion 独立于 ProtocolVersion 演进，并一次性固定以上全部规则（§9）。

下文“RIR-0”指 RIRVersion `0.1.0` 拟冻结的候选规则集合。

## 3. 子集清单（候选）

### 3.1 类型

只允许值类型 `i32`、`i64`。`f32`、`f64` 不得出现在函数类型、局部变量、全局变量或块类型中。函数结果最多一个（Wasm 1.0 本身的限制）。

### 3.2 允许的指令

| 类别 | 指令 |
|---|---|
| 控制 | `unreachable`、`nop`、`block`、`loop`、`if`（含 `else`）、`br`、`br_if`、`br_table`、`return`、`call`、`call_indirect` |
| 参数 | `drop`、`select`（无类型注解形式） |
| 变量 | `local.get`、`local.set`、`local.tee`、`global.get`、`global.set` |
| 内存读 | `i32.load`、`i64.load`、`i32.load8_s/u`、`i32.load16_s/u`、`i64.load8_s/u`、`i64.load16_s/u`、`i64.load32_s/u` |
| 内存写 | `i32.store`、`i64.store`、`i32.store8`、`i32.store16`、`i64.store8`、`i64.store16`、`i64.store32` |
| 内存大小 | `memory.size`、`memory.grow` |
| 常量 | `i32.const`、`i64.const` |
| 比较 | `eqz`、`eq`、`ne`、`lt_s/u`、`gt_s/u`、`le_s/u`、`ge_s/u`（`i32` 与 `i64` 各一组） |
| 算术与位运算 | `clz`、`ctz`、`popcnt`、`add`、`sub`、`mul`、`div_s/u`、`rem_s/u`、`and`、`or`、`xor`、`shl`、`shr_s/u`、`rotl`、`rotr`（`i32` 与 `i64` 各一组） |
| 转换 | `i32.wrap_i64`、`i64.extend_i32_s`、`i64.extend_i32_u` |

Wasm 1.0 可以解码、但不在本表内的指令（包括全部 `f32`/`f64` 指令、浮点与整数之间的转换和 reinterpret）在 §4.4 阶段 4 返回 `RIR_REJECT_UNSUPPORTED`。Wasm 1.0 grammar 无法解码的字节在阶段 3 返回 `RIR_REJECT_ENCODING`；例如符号扩展指令 `i32.extend8_s` 的 opcode `0xc0`，不得要求 1.0 解码器先理解该扩展再返回 `UNSUPPORTED`。

Wasm 1.0 之后加入的符号扩展、非陷入浮点截断、multi-value、引用类型、bulk memory、SIMD、尾调用、异常、线程/原子、memory64、多内存和 GC 全部不在 RIR-0 内。具体拒绝代码依 §4.4 的首失败阶段确定；这不要求 parser 支持任何未来扩展。

### 3.3 模块结构

| 段/元素 | RIR-0 规则 |
|---|---|
| import | 只允许 §7 中模块名 `aclt` 的函数，名称与签名必须精确匹配，每个名称最多一次；禁止导入 table、memory、global |
| table | 0 或 1 个 `funcref` 表 |
| memory | 恰好 1 个模块内定义的内存，必须声明 `max`，且 `max` 不超过 §3.4 上限 |
| global | 仅 `i32`/`i64`；初始化表达式只能是单个 `i32.const`/`i64.const` |
| export | 必须恰有 `run`（类型 `[] → []` 的函数）；可选导出名为 `memory` 的内存；不允许其他导出 |
| start | 禁止 |
| element | 仅主动段，表索引 0，偏移为 `i32.const`；不得引用导入函数；必须静态落在表的初始大小内 |
| data | 仅主动段，内存索引 0，偏移为 `i32.const`；必须静态落在内存的初始大小内 |
| 自定义段 | 全部禁止，包括 `name`、`producers`、`target_features` |

element 与 data 段的结构限制（主动段、索引、常量偏移的表达式形式、不得引用导入函数）属于 §4.4 阶段 4；引用索引合法性和 Wasm 类型规则属于阶段 5；段是否落在表/内存初始大小内的数值边界检查只属于阶段 6。内存声明 `max` 的存在性属于阶段 4，其数值上限属于阶段 6。这些规则不在两个阶段重复裁定。

通过上述检查后，element/data 初始化不会因段越界而失败；宿主实际分配失败仍属于 §6.3 的 C 类故障，不属于 Task trap。

### 3.4 静态上限（RIRVersion 常量，数值待用 rustc 实际产物校准）

| 项目 | 上限 |
|---|---|
| Wasm 主体字节 | 4 MiB |
| 类型数 | 1,024 |
| 函数数（含导入） | 10,000 |
| 单函数参数数 | 64 |
| 单函数局部变量数（不含参数） | 4,096 |
| 单函数体字节 | 512 KiB |
| 单函数最大操作数栈高度（validator 计算） | 4,096 |
| 块嵌套深度 | 1,024 |
| `br_table` 目标数 | 65,536 |
| 表大小 | 65,536 |
| 全局变量数 | 1,024 |
| data 段数 | 1,024 |
| 内存声明 `max` | 4,096 页（256 MiB） |

操作数栈高度和块嵌套在验证时静态有界，再加上 §5 的调用深度上限，整个执行栈就有确定上界。RIR 不使用 Wasm 实现自定的栈限制。

## 4. 规范编码与摘要（候选）

### 4.1 外壳

```text
RIRArtifact = {
  schema_version      : 1
  encoding_profile_id : "acl.enc.rir-0@1"
  rir_version         : SemVer            # RIR-0 为 0.1.0
  entry               : "run"             # RIR-0 只允许该值
  input_arity         : uint32            # 0 ≤ input_arity ≤ 2^32−1；Receipt 输入个数
  body                : bstr              # §4.2 的规范 Wasm 字节
}
```

`input_arity` 在阶段 2 先要求为无符号整数，在阶段 6 检查 uint32 上界。Receipt 创建时还必须在阶段 7 校验 `input_arity = |Receipt 的有序输入引用列表|`；不相等为绑定错误 `RIR_REJECT_INVALID`，不得截断、取模或从宿主补充隐藏输入。`0` 个输入合法。仅对独立工件做阶段 1—6 检查，不能声称已通过 Receipt 绑定检查。

`acl.enc.rir-0@1` 的 CBOR 原语与容器规则逐条沿用 `acl.enc.p0-1@1`（确定长度、最短整数、键按编码字节排序、禁止浮点/null/tag 等）。之所以另起标识，是因为 P0-1 规定新增 tag 必须提升其 `encoding_profile_id` 版本；RIR 的 tag 位于独立命名空间，不进入 P0-1 tag 集合。是否以后合并为全项目统一的编码 Profile，留给 OQ-02。

### 4.2 Wasm 主体的规范形式

令 `Decode` 为 Wasm 1.0 二进制解码，`CanonEncode` 为下述编码器；当且仅当 `body = CanonEncode(Decode(body))` 时，body 才是规范的：

1. 魔数 `\0asm`，版本 1；
2. 非自定义段按规范顺序出现，每种最多一次；省略空段；
3. 全部 LEB128（段长、向量长度、索引、`memarg`、常量立即数）取最短形式；有符号数取最短的符号一致形式；
4. 函数体局部变量声明把相邻同类型合并为一组，不出现计数为 0 的组；
5. `memory.size`、`memory.grow`、`call_indirect` 的保留字节为单个 `0x00`；
6. 无自定义段；
7. `if` 的 else 分支指令序列为空时，必须省略 `0x05`，编码为 `0x04 blocktype then_instr* 0x0b`；非空时必须使用 `0x05`。显式空 else 与省略空 else 解码为同一 AST，`CanonEncode` 只选择省略形式，前者在阶段 3 返回 `RIR_REJECT_ENCODING`。

`memarg` 的对齐值属于抽象语法，按原值保留，只要求满足 Wasm 验证规则。

### 4.3 摘要与 tag

\[
H_{\mathrm{tag}}(x)=\mathrm{SHA256}\big(\mathrm{u8}(|\mathrm{tag}|)\ \|\ \mathrm{tag}\ \|\ x\big)
\]

| 摘要 | tag | 输入 |
|---|---|---|
| `rir_digest` | `ACLt/RIR-0/Artifact/1` | `cbor(RIRArtifact)`，全部字段 |
| `outcome_digest` | `ACLt/RIR-0/ExecutionOutcome/1` | `cbor(RIRExecutionOutcome)`（§6.2） |

### 4.4 validator 阶段与拒绝优先级

validator 按以下顺序执行，返回第一个失败阶段对应的代码；各实现必须对同一输入给出相同代码。

1. 外壳 CBOR 解码与 canonical 检查 → `RIR_REJECT_ENCODING`
2. 外壳字段集合、类型及已知值（版本、`entry`、未知/缺失字段；`input_arity` 此时只检查无符号整数类型） → `RIR_REJECT_UNSUPPORTED`
3. **仅按 Wasm 1.0 grammar** 解码，再检查 §4.2 重编码一致性 → `RIR_REJECT_ENCODING`。未知 opcode、1.0 无法解码的扩展、截断及非规范表示均在本阶段终止；不做未来扩展探测。
4. 可解码模块的子集结构检查（§3.1—§3.3，排除阶段 3 已管的编码规则、阶段 5 的 Wasm 有效性和阶段 6 的数值上限/段边界） → `RIR_REJECT_UNSUPPORTED`
5. Wasm 1.0 有效性/类型验证，包括函数和其他引用索引合法性 → `RIR_REJECT_INVALID`
6. §3.4 静态数值上限、`input_arity ≤ 2^32−1`、element/data 相对于表/内存初始大小的数值边界 → `RIR_REJECT_LIMITS`
7. Receipt 绑定检查：先检查输入列表长度与 `input_arity` 相等，不等 → `RIR_REJECT_INVALID`；再检查 §5.1 执行上限兼容性 → `RIR_REJECT_LIMITS`。本阶段内部也按此顺序返回首个失败。

实现不得把阶段 4/6 的语义条件提前当成阶段 3 的解码失败。存在多项错误时，只返回最早失败阶段的代码：例如可解码的非法导入与 data 越界同时存在时为阶段 4 `UNSUPPORTED`；Wasm 类型错误与 data 越界同时存在时为阶段 5 `INVALID`；非规范显式空 else 即使同时带有非法导入，也先返回阶段 3 `ENCODING`。

阶段 7 需要 Receipt 的输入列表和绑定上限，因此在 Receipt 创建时执行；RPR 执行前对阶段 1—7 全部复验。这里规定的是候选 validator 的规范拒绝码。

## 5. 资源上限与计量（候选）

### 5.1 执行上限由 Receipt 绑定

同一 RIR 工件可以在不同上限下执行，所以上限属于 Receipt 的 Environment，不属于工件本身：

```text
RIRExecutionLimits = {
  gas_limit          : uint64   # 1 ≤ gas_limit ≤ 2^63−1
  memory_pages_limit : uint     # ≤ 模块内存声明的 max
  call_depth_limit   : uint     # 1 ≤ call_depth_limit ≤ 4,096
  output_bytes_limit : uint64
}
```

Receipt 创建时必须满足：模块初始页数 ≤ `memory_pages_limit`，且实例化成本（§5.3）≤ `gas_limit`；否则在创建期拒绝，不会进入执行。有效内存上限 = min(声明 `max`, `memory_pages_limit`)。

RPR 必须在 Lease 接受前声明自己支持的上限范围；超出范围的 Receipt 不得被接受执行，也不得在执行中途以宿主资源不足为由改判 Task 结果。

### 5.2 计量规则

每条被执行的指令按以下顺序处理：

1. 按 §5.3 计算成本；需要操作数的成本（`memory.grow`、宿主调用）先用操作数计算；
2. 若剩余 gas 小于成本，以 `TRAP_GAS_EXHAUSTED` 终止，该指令不产生任何效果，也不计入 `gas_used`；
3. 扣除成本；
4. 按 Wasm 语义和本 ADR 规则执行，此时仍可能 trap（已扣除的成本保留在 `gas_used`）。

`else`、`end` 是语法分隔符，不是被执行的指令，不计费。`gas_used` 是确定值，计入执行结果（§6.2）。

调用深度：`run` 的栈帧计为深度 1。`call`/`call_indirect` 扣费后，若当前深度已等于 `call_depth_limit`，则 `TRAP_CALL_DEPTH`。直接调用导入函数不压入 Wasm 栈帧，不检查深度。

`memory.grow n`：设当前页数为 `cur`。若 `cur + n` ≤ 有效内存上限则成功，返回 `cur`；否则失败，返回 `−1`。成败先确定，再计算成本。RPR 若因宿主内存不足而无法提供确定应成功的页，必须报告 `HOST_RESOURCE_EXHAUSTED`（§6.3），不得返回 `−1`。

### 5.3 成本表（RIR-0 候选数值）

| 类别 | 指令 | 成本 |
|---|---|---|
| 结构与参数 | `nop`、`block`、`loop`、`if`、`drop`、`select`、`unreachable` | 1 |
| 分支 | `br`、`br_if`、`return` | 1 |
| 多路分支 | `br_table` | 2 |
| 常量与变量 | `i32.const`、`i64.const`、`local.*`、`global.*` | 1 |
| 整数基本运算 | 加减、位运算、移位、旋转、比较、`eqz`、`clz`、`ctz`、`popcnt`、转换 | 1 |
| 乘法 | `i32.mul`、`i64.mul` | 3 |
| 除法与取余 | `div_s/u`、`rem_s/u`（32/64 位） | 8 |
| 访存 | 全部 load/store | 2 |
| 内存大小 | `memory.size` | 1 |
| 内存增长 | `memory.grow`：成功 `8 + 4096·n`，失败 `8` | 见左 |
| 调用 | `call`（目标为模块内函数） | 4 |
| 间接调用 | `call_indirect` | 6 |
| 宿主调用 | `call` 到导入函数 | 仅按 §7 计费 |
| 实例化 | `4096 × 初始页数 + ⌈data 段总字节 / 8⌉ + element 条目总数` | 在 `run` 前一次性扣除 |

这些数值只是初始候选。校准（G1）不影响确定性要求，但任何数值变化都必须产生新的 RIRVersion。

## 6. 结果与 trap 映射（候选）

### 6.1 A 类：创建期拒绝

代码为 §4.4 的 `RIR_REJECT_ENCODING`、`RIR_REJECT_UNSUPPORTED`、`RIR_REJECT_INVALID`、`RIR_REJECT_LIMITS`。它们对应 ADR-0002 的“创建、lowering 或验证阶段拒绝/`UNSUPPORTED`”，不产生 Receipt。

### 6.2 B 类：Task 语义结果

B 类结果是确定的，可以通过适用重执行 Profile 引用的精确结果等价谓词（本草案为 §6.2 的 `acl.rir.eq.exact@0`）复核。它不是新的 `VerificationMethod`：当前方法仍是 `DIRECT_VERIFIED | PROOF_VERIFIED | REEXEC_BOUNDED | REEXEC_AUDIT_ONLY`。结果相等只构成对应 Profile 的比较输入；它不自动满足 `REEXEC_BOUNDED` 的假设/接受条件，也不能让 `REEXEC_AUDIT_ONLY` 产生 `TRUSTED`。

| outcome | 触发条件 |
|---|---|
| `OK` | `run` 正常返回 |
| `TRAP_UNREACHABLE` | 执行 `unreachable` |
| `TRAP_MEMORY_OOB` | load/store 的有效地址加访问宽度超过当前内存大小 |
| `TRAP_DIV_ZERO` | `div_s/u`、`rem_s/u` 的除数为 0 |
| `TRAP_INT_OVERFLOW` | `div_s` 计算 \(-2^{N-1}/(-1)\)；`rem_s` 的同一输入定义为 0，不 trap |
| `TRAP_TABLE_OOB` | `call_indirect` 的索引 ≥ 表大小 |
| `TRAP_NULL_ELEMENT` | `call_indirect` 指向未初始化的表项 |
| `TRAP_SIGNATURE_MISMATCH` | `call_indirect` 的类型与目标函数类型不一致 |
| `TRAP_GAS_EXHAUSTED` | §5.2 |
| `TRAP_CALL_DEPTH` | §5.2 |
| `TRAP_HOST_ARGUMENT` | 宿主调用参数越界或无效（§7） |
| `TRAP_OUTPUT_LIMIT` | 累计输出超过 `output_bytes_limit` |
| `ABORT` | 程序调用 `aclt.abort(code)` |

```text
RIRExecutionOutcome = {
  outcome    : OutcomeCode            # 上表封闭枚举，文本编码
  abort_code : uint32                 # 仅当 outcome = ABORT 时出现
  gas_used   : uint64
  output     : bstr                   # 仅当 outcome = OK 时出现；为全部 output_write 的顺序拼接
}
```

非 `OK` 时丢弃部分输出。默认结果等价为 `acl.rir.eq.exact@0`：`outcome_digest` 逐位相等。trap 是否满足 Receipt 的成功语义、如何结算，不由 RIR 决定。

### 6.3 C 类：RPR/Host 故障

C 类不是 Task 结果，不进入 `RIRExecutionOutcome`，也不能通过重执行复核；按 Lease/Attempt 规则处理。

| 代码 | 含义 |
|---|---|
| `HOST_RESOURCE_EXHAUSTED` | 宿主内存、磁盘或其他资源不足 |
| `HOST_DEADLINE` | 墙钟期限或 Lease 到期 |
| `HOST_CANCELLED` | 外部取消 |
| `RPR_INTERNAL_ERROR` | RPR 自身不变量失败 |
| `RPR_REVALIDATION_MISMATCH` | 已登记的 Receipt 在 RPR 复验时失败，说明 validator 之间存在分歧 |

RPR 不得把 C 类改写为 B 类：宿主内存不足不得报告为 `memory.grow` 返回 `−1` 或 `TRAP_GAS_EXHAUSTED`；墙钟超时不得报告为 gas 耗尽。

## 7. 宿主 ABI（候选，RIR-0）

导入模块名为 `aclt`。`i32` 指针和长度按无符号 32 位解释，`i64` 偏移和长度按无符号 64 位解释。第 `index` 个输入即 Receipt 输入列表中的第 `index` 个 Logical Object 的规范内容字节，执行期间不可变。

| 函数 | 签名 | 语义 | 成本 |
|---|---|---|---|
| `input_count` | `() → i32` | 返回 `input_arity` 的无符号 32 位位模式；不截断，§4.4 已保证数量可表示 | 4 |
| `input_len` | `(index: i32) → i64` | 返回该输入的字节长度；`index ≥ input_arity` 时 `TRAP_HOST_ARGUMENT` | 4 |
| `input_read` | `(index: i32, offset: i64, dst: i32, len: i32) → ()` | 精确复制 `len` 字节；`index` 越界、`offset + len` 超过输入长度或 `dst + len` 超过内存大小时 `TRAP_HOST_ARGUMENT`；`len = 0` 合法 | `16 + ⌈len/8⌉` |
| `output_write` | `(src: i32, len: i32) → ()` | 先检查源地址范围，越界时 `TRAP_HOST_ARGUMENT`；仅在地址合法后检查累计输出上限，超过时 `TRAP_OUTPUT_LIMIT`；全部检查成功后追加输出 | `16 + ⌈len/8⌉` |
| `abort` | `(code: i32) → ()` | 以 `ABORT(code)` 立即终止 | 1 |

宿主调用同样遵循 §5.2，并明确以下顺序：计算成本 → gas 不足则 `TRAP_GAS_EXHAUSTED` 且不扣该次成本 → 扣费 → 检查输入索引及内存/输入地址参数（失败为 `TRAP_HOST_ARGUMENT`）→ 仅对 `output_write` 检查输出额度（失败为 `TRAP_OUTPUT_LIMIT`）→ 复制/追加等效果。同一次调用只返回首个失败；无部分复制或追加。`abort` 在扣费后产生 `ABORT`。

所有范围加法（`offset + len`、`dst + len`、`src + len` 与累计输出加 `len`）都使用数学非负整数，不按机器位宽回绕。`len = 0` 不跳过索引/地址检查，端点恰等于对象或内存长度合法，端点大于长度仍为参数错误。

例如初始内存为 1 页、`output_bytes_limit = 0`，且在扣除本次成本后 gas 足够时，`output_write(65536, 1)` 必须为 `TRAP_HOST_ARGUMENT`，而非 `TRAP_OUTPUT_LIMIT`；若 gas 不足则先为 `TRAP_GAS_EXHAUSTED`。RIR-0 不提供时间、随机数、环境变量、命令行参数、文件、网络、线程或日志。调试输出通道作为不影响语义的诊断能力，留待以后单独评估。

## 8. 对 Rust Profile 的约束（候选，细则另行起草）

1. 目标为 `wasm32v1-none`（S16）。用户 crate 使用 `#![no_std]` 与 `#![forbid(unsafe_code)]`；SDK crate 以安全接口封装 §7 的导入，其摘要属于 lowering provenance，SDK 内部的 `unsafe` 属于 Profile 的受信 lowering 基础。
2. 源码层面禁止 `f32`/`f64` 以便尽早诊断，但最终以 validator 为准：通过 §4.4 阶段 3 的产物若仍含浮点指令，则在阶段 4 返回 `RIR_REJECT_UNSUPPORTED`；较早的编码错误仍按首失败优先级处理。
3. 该目标启用 mutable-globals；RIR-0 禁止全局变量的导入/导出，产物若包含此类导入/导出即被拒绝。
4. 如果默认工具链产物包含自定义段（如 `producers`、`target_features`）或 `run`/`memory` 以外的导出，必须由一个固定且带版本的链接后处理步骤去除；该步骤属于 lowering provenance，validator 不为此放宽。
5. lowering provenance 至少包括：rustc 版本与提交、目标、完整编译和链接参数、SDK 摘要、源码包摘要、`Cargo.lock` 摘要、后处理工具版本。
6. 可复现性证据：两次独立构建得到相同 `rir_digest`，例如在 [DUALHOST-SSH-1](../08-governance/dualhost-ssh-validation.md) 的 A、B 两台主机上分别构建。这只证明 lowering 可复现，不证明 lowering 正确（`EXC-BASE-LOWERING` 不变）。
7. 环境缺项（2026-10-23 观测）：A 主机 rustc 1.93.1 的目标列表包含 `wasm32v1-none`，但 sysroot 中只有 `x86_64-unknown-linux-gnu`，缺少该目标的 `core`/`alloc`。B 主机按[双机报告](../testing/DUALHOST-SSH-20261023.md)已有 Rust/Cargo 1.93.1，其 wasm 目标库尚未核查。
8. 后续构建探针：A/B 已在独立实验 prefix 安装固定官方 Rust 1.93.1 及 wasm32v1-none 库和 rust-lld；四次最小空 run 构建的 raw/后处理/候选工件均一致。用户库保持 forbid(unsafe_code)，no_mangle 导出放在单独受信入口层，并保留直接在用户库导出的预期编译失败。系统 sysroot 缺项仍是事实；实验 prefix 可用不等于系统已补齐。见 [切片 1 报告](../testing/RIR-BUILD-SLICE1-20261023.md)。该探针不是已接受实现依据、完整 SDK 允许集合或 RIR conformance 证据。

9. I/O 候选探针：安全 SDK 与受信入口已在固定 16 字节原样输出负载上实现；候选外壳、局部类型检查与受限 Python 解释器在双机运行通过，并有现有 Wasm 引擎对拍语义。该引擎不核对 gas/调用深度/绑定，尚无独立 Rust RPR，不替代本 ADR §13 的接受证据。见 [切片 2](../testing/RIR-IO-SLICE2-20261023.md)。

切片 3 补记：[stats-int-v1 候选双机报告](../testing/RIR-STATS-SLICE3-20261023.md)已增加独立 Rust Wasm 解码/执行器，四组构建与 276 条 Python/Rust 执行记录一致，160 次 C++ 统计行比较通过。输入/输出使用显式候选二进制适配器。Rust 仍依赖 Python 预验证；完整外壳/类型/规范验证器、全指令 conformance 与正式 Receipt 尚缺，不把本轮视为 §13 全部接受证据。上文“尚无独立 Rust RPR”为切片 2 的历史范围。

## 9. 版本与 Receipt 绑定（候选）

- RIRVersion 使用 SemVer，独立于 ProtocolVersion 演进。一个 RIRVersion 同时固定：子集、规范编码、静态上限、成本表、结果枚举、宿主 ABI 与默认等价谓词。其中任何一项变化都产生新的 RIRVersion、新的 `rir_digest` 和新的 ReceiptID（ADR-0002 §6 第 7 项）。
- `0.x` 为实验系列，各次版本之间不承诺兼容。
- Receipt 的 Computation 部分绑定 `rir_digest` 与输入 Logical Object 引用；Environment 部分绑定 `RIRExecutionLimits`，并按 REF-6 以 `ExternalVersionedObjectRef` 绑定 RPR。
- **工件身份与执行实例身份分开。** 在 RIRVersion 与工件字节不变时，只改变 `RIRExecutionLimits` 不改变 `rir_digest`，但改变 Receipt 的绑定内容并必须产生新的 ReceiptID；不得把执行上限搬入工件以满足错误的摘要测试。只有规则/成本表变化导致 RIRVersion 改变，或工件内容本身改变时，才要求新 `rir_digest`。

## 10. 不关闭的事项

- Logical Object Schema、Receipt Schema、ExecutionCapability contract；
- RPR 的 capability 声明格式、计量性能与部署机制；
- 成本表校准、跨 Provider 计价与结算；
- checkpoint：本草案建议 V1 不支持，Attempt 失败后从头执行，粒度由 Decomposition 控制；
- 浮点、Wasm 1.0 之后的确定性特性、JIT/AOT backend；
- Rust Profile 的完整源码子集与 lowering golden vectors；
- RIR、validator 或 RPR 的正确性证明（`EXC-BASE-RIR-SPEC`、`EXC-BASE-RPR-SPEC`、`EXC-BASE-COMMON-MODE` 不变）。

## 11. 接受前需要同步的文档

按 [CONTRIBUTING](../../CONTRIBUTING.md) §7 中“RIR、前端或执行 Profile”一行：

| 文件 | 同步内容 |
|---|---|
| `terminology.md` | `RIRArtifact`、`RIRExecutionLimits`、`RIRExecutionOutcome` 与 A/B/C 三类结果 |
| `system-architecture.md` §1.4 | RPR 上限声明、C 类不得改写为 B 类 |
| `protocol-spec.md` | Computation/Environment 的 RIR 字段 |
| `task-lifecycle.md` | checkpoint 处置；C 类故障进入 Attempt 处理 |
| `v1-profile.md` | 浮点、Wasm 1.0 之后的特性、checkpoint、JIT 的 V1 处置 |
| `threat-model.md` | 计量分歧、validator 分歧、宿主故障被误判为 Task 结果 |
| `invariants.md` | INV-16 到 RIR conformance 测试的映射 |
| conformance 测试 | §13 的向量与差分资产 |

## 12. 被拒绝或延期的替代方案

下表“处置”只是本 ADR 的拟议；V1 VersionDisposition 在接受时登记到 `v1-profile.md`。

| 方案 | 拟议处置 | 原因 |
|---|---|---|
| 自研 IR | 拒绝（项目决定） | Rust lowering 需要自写编译器或依赖 rustc 不稳定内部表示 |
| 原样使用完整 Wasm 3.0 或官方确定性 profile | 拒绝 | `memory.grow` 与栈限制仍非确定；浮点与后续特性扩大规范面 |
| 以某个 Wasm 引擎的行为为规范 | 拒绝 | 违反 INV-16；共因故障 |
| 引擎私有的 fuel 计量 | 拒绝 | 跨实现不一致 |
| `wasm32-unknown-unknown` 加 `target-cpu=mvp` | 不采用 | 预编译 `core` 带有该目标的默认特性，完全收窄需要 nightly 的 `-Zbuild-std`（S16） |
| WASI | V1 拒绝 | 引入文件、时钟、随机等宿主 effects，违反默认拒绝 |
| 符号扩展、bulk memory、multi-value 等 1.0 之后的确定性特性 | 延期 | 语义确定，但扩大规范面；`wasm32v1-none` 默认不生成 |
| 浮点（规范 NaN） | 延期 | 需要跨实现逐位一致的浮点与结果等价规则 |
| JIT/AOT RPR | 延期 | 共因风险；参考 RPR 先用解释器 |
| checkpoint | 延期 | 跨实现的快照可移植性难以证明 |

## 13. 接受所需的最低证据

1. 外壳与 Wasm 规范编解码器的 Python、Rust 两份独立实现，不引入第三方依赖；正例向量，以及覆盖每个拒绝代码的负例：补零 LEB128、段乱序、空段、自定义段、未合并的局部变量、`f32` 类型、浮点指令、符号扩展指令、未知导入、全局导入、start 段、第二个内存、缺少 `max`、data 段越界、表中出现导入函数等。
2. Python 参考解释器作为 oracle，Rust 解释器作为 RPR：在向量和随机生成的合法程序上对拍，`RIRExecutionOutcome` 逐位一致（含 `gas_used`）；覆盖每种 trap 的边界：gas 恰好够与差 1、调用深度恰到上限、`memory.grow` 恰到上限、`div_s` 与 `rem_s` 在 \(-2^{N-1}, -1\) 上的差异。
3. 可选的第三方 Wasm 引擎只对拍不计量的语义（outcome 与 output，不含 `gas_used`）；引入前需要依赖许可。
4. 用 RIR 重写现有 `stats-int-v1` 负载，并与 C++ worker 的结果对拍。
5. 故障注入：宿主内存不足不得表现为 B 类结果；能检测到 validator 分歧。
6. 分开验证身份变化：RIRVersion/成本表变化必须通过新 RIRVersion 产生新 `rir_digest` 和新 ReceiptID；工件和版本不变、只变 Receipt 执行上限时，`rir_digest` 必须相同，ReceiptID 必须不同。该条在正式 Receipt 编码实现后做实际 ID 测试，不能用临时对象哈希冒充 ReceiptID。

### 13.1 本次审阅必须保留的边界向量

候选向量清单见 [RIR ADR 修订向量](../testing/rir-adr-revision-vectors-20261023.json)，修订映射见 [记录](../testing/RIR-ADR-REVISION-20261023.md)。这些是实现前的候选预期，不是已通过 conformance：

- 同 AST 的省略/显式空 else：前者通过规范形式检查，后者阶段 3 `ENCODING`；不要求所有语义等价程序具有相同摘要。
- post-1.0 opcode `0xc0` → 阶段 3 `ENCODING`；1.0 可解码的浮点指令 → 阶段 4 `UNSUPPORTED`；data/element 越初始边界 → 阶段 6 `LIMITS`；另测上述多错误的首失败优先级。
- `output_write` 同时地址越界与输出超限时，先返回 `HOST_ARGUMENT`；若 gas 不足则先 `GAS_EXHAUSTED`。另测地址合法但输出超限、零长度端点与数学加法不回绕。
- `input_arity` 的 0、`2^32−1`、`2^32` 边界；最大值可通过工件数量范围检查，不要求在测试中实际分配数十亿输入。Receipt 输入列表与工件数量不等为阶段 7 `INVALID`，与资源上限不兼容同时存在时也先返回它。
- 工件摘要/ReceiptID 分离，以及当前 MethodEnum 不因精确结果比较而扩展。

## 14. 连续性结论

本草案在 ADR-0002 的范围内细化 RIR，不改变以下内容：RIR 是规范执行表示，Rust Profile 是参考前端，不允许静默原生回退，V1 不支持 unsafe Rust、完整宿主 effects、原生执行、GPU 和非确定性任务。它在此基础上进一步收窄：RIR-0 不含浮点。它不新增 Principal 或权威实体；Wasm 规范、引擎及其维护组织都不进入 ACLt 的真理权重。G0 未通过退出。

工程证据补记（2026-10-23）：[第一项三切片收尾](../testing/RIR-WORK1-CLOSEOUT-20261023.md)完成统一双机复现与证据连续性核对。该工程状态不接受本 ADR，§13 的完整独立编解码、验证与 conformance 要求仍适用。

工程补记（2026-10-28）：[独立 stats-core](../testing/RIR-INDEPENDENT-CORE-20261028.md)已新增 Rust raw-artifact 外壳、受限 canonical/type/binding 检查及独立结果 CBOR/摘要，旧执行入口原字节保留。该局部入口不调用 Python 预验证或后处理；支持范围小于本草案，不完成 §13 全证据或完整七阶段拒绝优先级。本 ADR 继续 PROPOSED，§11 同步与正式 ReceiptID 条件不变。
