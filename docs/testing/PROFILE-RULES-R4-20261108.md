# 共同注册规则第四片（R4）

本片按 VerificationProfile §7、§8.4、§9.3、§5.2.1、§17.4 实现共同 Phase R 规则与静态假设集合摘要，145 条固定向量在 A/B 两台物理机上全部通过且结果流 SHA-256 一致，完整 `make test` 退出码为 0，119 条 Type A 由 **15/36/68** 变为 **24 implemented / 30 partial / 65 not implemented**。基线 main `723681c`，日期 2026-11-08，修改前含尚未提交的 R3 全部改动；R3 的测试源码包保留其独立证据，最终提交组合 R3/R4，R3 的旧哈希按原值保留。

## 规则交付

| 规则 | 已实现范围 |
|---|---|
| SV-03、SV-32 | 四元方法枚举及类型检查；拒绝已删除的顶层 post_execution_predicate，并给出专用诊断 |
| SV-33、SV-37 | 每份假设的三阶段撤销映射完整、封闭；SAFETY_CRITICAL 只能使用 AR-1 固定三元值 |
| SV-59 | ScopeSpec 六维齐备且无额外维度；不把 Phase I 的非空集合/包含关系检查提前到 R |
| SV-38 | AR-2 方法必需 class/role 矩阵：Direct 一项、Proof 一项、Bounded 五项、Audit 无必需项；同类不同角色不能代替必需项 |
| SV-22 | DegradationDecl.triggers 是冻结三种触发条件的子集；数组不强加规范未声明的排序/去重条件 |
| SV-84 | supersedes 若存在必须是完整 Profile 三元引用，并在已核对的 RegistrySnapshot 的 VERIFICATION_PROFILE 域逐位解析 |
| SV-73 | 按 `ACLt/P0-1/AssumptionSet/1` 对编码排序的 `[assumption_id,statement_digest]` 行摘要；提供显式 claimed digest 比较 |

九项升级中六项由 partial 变为 implemented，三项由 not implemented 变为 implemented。119 Type A 从 **15/36/68** 变为 **24 implemented / 30 partial / 65 not implemented**；18 个摘要为 6 implemented、2 partial、10 not implemented。

这是规则级完成，不是完整 Phase R / SchemaValid。方法参数变体、claim 绑定、版本差异/迁移（SV-61）、WeakeningEdge/目标降级资格（SV-21）、正式 import 与日志后端来源等仍有未完成项；A0/A1 整体验收、Type B、Gate 和主网资格不变。

## 输入与集成

Python `registration_rules.py` 与 Rust `registration.rs` 分别实现共同规则与 SHA；复用双方各自的 codec 和既有声明式类型表。Rust 不调用 Python。所有 schema lock、文档、快照都是显式输入，可信 lock pin 在输入之外传入；仍为现有测试 import 合约，不升级为官方 schema 注册。

- **规则专用适配器**：`{profile,registry_snapshot,schema_lock,schema_documents,assumption_set_digest}`。其中最后一个字段只是 helper 的显式预期值/测试输入，不是新增 Profile wire 字段；helper 校验 Profile 摘要、上述共同规则并核对派生摘要。
- **固定 audit 集成**：沿用 R3 的 `{envelope,schema_lock,schema_documents,registry_objects}`，接通 R3 引用链和 R4 共同规则，输出派生 `assumption_set_digest_hex`，不向 Profile 插入该派生值。该路线拒绝非 audit 方法及任何 degradation 声明；通用 helper 的触发条件通过不授予降级执行资格。

**非 audit 正例的边界：** 四种方法的规则专用向量只表示本片规则通过。未检验的 method_parameters / failure_mapping / claim 块使用明确的测试占位，不能把这些对象称为完整 SchemaValid、V1Admissible 或已启用的 Direct/Proof/Bounded 路线。`full_schema_valid:false`、`source_authentication:false` 与生产强制拒绝保持不变。

静态集合摘要包含全部冻结假设行的 ID/statement（包括 INFORMATIONAL），不绑定 evidence_version、scope、role 或运行期原因；这些信息分别受 Profile 内容和运行期状态/快照摘要约束。不能用静态集合替代 `assumption_state_digest` 或据此影响终态。R 期不读取时钟，也不把过期/范围不含任务误作注册失败；I/F/B 的适用性检查另行接入。

```sh
python3 -B -m tools.verification_profile.validator rules.cbor \
  --registration-rules-cbor --schema-lock-sha256 TRUSTED_LOCK_SHA256
python3 -B -m tools.verification_profile.validator audit.cbor \
  --registration-r4-cbor --schema-lock-sha256 TRUSTED_LOCK_SHA256
make test-registration-rules
```

Rust 行模式为 `registration-rules:<pin><TAB><CBOR-hex>` 和 `phase-r4:<pin><TAB><CBOR-hex>`。旧 R1/R2/R3 入口、向量、报告和结果流保持原各自限域含义。

## 验证与复现

固定 145 条（40 正例、105 反例），覆盖四种方法、AR-2 必需项缺失/错角色、六维逐项缺失、三阶段缺失、全部 12 种撤销组合在非关键/关键角色下的处理、静态集合排序/元数据不变性、supersedes 三元身份、闭合触发条件、旧字段迁移与固定 audit 守卫。14 项新增默认回归另直接解析规范 AR-2 表、独立 hashlib/OpenSSL 核对 preimage、区分 R 与 I/F 的 scope/时效判定，并逐文件验证尚未提交 R3 的公开源码包与其旧 pin 一致。

完整 `make test` 退出码为 0：默认 23 组 526 项（R3 512 + 本片 14），另 25 项执行器测试，共 551 项；20 次 sanitizer、既有 Claim/FM/RIR 对拍通过。R1/R2/R3 的 66/74/104 条结果流 SHA-256 均与各自原记录一致；24 套公开历史快照的 249 条事件重放通过。

两台物理机各自构建并通过 145 条，结果流 SHA-256 均为 `fd6fce4a40ec608cdfd44e9a97ed8a0ba0af795bdd4c2b420003d3b2e81161e4`，逐文件源码 pin 相同。环境与结果见[机器摘要](PROFILE-RULES-R4-20261108.summary.json)。[公开最小源码包](public-evidence/PROFILE-RULES-R4-source.tar.gz)已在新目录核对 pin、复跑 145 条和 14 项新增单元测试，结果一致；R3 的原始源码包/pin 亦逐文件通过。全量日志、A/B 原报告、部署记录和修改前的完整源码备份保留在操作者证据目录。双机范围是静态构建/编码/规则核对，新增任务协议运行数为 0；两台物理机与 SSH 约定不提供身份/统计独立保证。

后续按剩余 Phase R 缺口逐项推进，再接固定 Profile 的 I/F 创建/绑定；官方 import 的未冻结内部结构不能靠本片 helper 或测试占位补成事实。
