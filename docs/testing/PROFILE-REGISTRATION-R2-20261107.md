# Profile 注册上下文第二片（R2）

> 2026-11-08 更正：R2 的 map TimeRange 与 opaque ExternalTypedObject 是限域测试输入，不能作为正式线上 conformance 证据。§17.3 要求 TimeRange 二元数组，§11.3 已定义三字段 ExternalTypedObject；新入口及反例见 [R3](PROFILE-REFERENCES-R3-20261108.md)。以下保留当时实现和运行记录。

基线 main `41f0ee9`，2026-11-07；工作区包含尚未提交的 R1。本片沿用 §3.2.1、§3.5、§8.4、§13.0 与 §17.4，补 audit Profile 嵌套类型、显式不可变导入绑定、Phase R 注册上下文和两个快照。

## 已实现范围

Python `registration.py` 与 Rust `registration.rs` 各自执行类型遍历、CBOR 编解码、引用绑定、摘要和 DAG 校验；两端共享声明式类型表 `rust/audit_types.json`，不调用对方的 validator。类型表属于被钉住的源码，当前覆盖 `REEXEC_AUDIT_ONLY`。

- 嵌套结构使用封闭字段，检查必填/可选字段、枚举、原生标量、SemVer/VersionRange/Rational、六维 ScopeSpec、三阶段撤销及安全假设的固定撤销值。
- `RegistrySnapshot` 使用唯一嵌套版本化 header。六类注册对象、四种状态、合法三元组、按编码字节排序和按身份去重；身份不进入内容摘要，context 另绑定完整三元组。
- `EventFrontierSnapshot` 使用无 version 的运行期 header，id 进入摘要；检查 context 引用、事件/父引用顺序与去重、父边闭合、无环、frontier 存在及 kind/subject 配对。新增两个 verification kind 只允许 schema v2，旧 schema v1 保留原枚举。检查 proof/event 数量，未认证 proof 内容。
- Phase R 必须显式提供 context、registry 和 frontier；不按 `evaluation_instant` 决定假设是否过期，不读取墙钟或取得远程对象；`supersedes` 在所给 registry 中按三元组解析。

## 导入与入口

调用适配器接受 CBOR `{envelope, schema_lock, schema_documents}`；其中 `envelope` 是规范 `{phase:"R", bundle, object}`。后两项是本实现显式提供的校验资产，不是新增协议字段。调用方必须在编码输入外传入可信 lock SHA-256，不能把待检输入的自述摘要当成可信 pin。

lock 固定 alias 到 `(SchemaID, Version, Digest)`；每份 schema 文档以原始 canonical CBOR 携带，重算 SHA-256 并绑定 alias/ID/version。当前解析器只支持 `@1`、`[1,0,0]`、`OPAQUE_BSTR`；未知版本/表示、文档篡改、缺失/额外/重复文档或未解析 alias 均拒绝。§3.2.1 已定义的 import ID 按原值核对。

**测试绑定边界：** 固定向量中的导入文档由本片提供，不构成官方 schema 注册或发布。未冻结内部结构的 `ResourceBounds`、`RetentionPolicyRef`、`DocBlock`、`EffectID` 和 `ExternalTypedObject` 使用显式 `acl.schema.test-*` ID 与不透明 bstr，不猜测内部字段。其他跨文档别名也在本轮以钉住的 opaque 测试 schema 绑定。正式导入 schema/注册域、ExcludedClaims 内容与引用、其他方法的参数及完整五相位仍待完成；不输出完整 `SchemaValid` 或来源认证。

```sh
python3 -B -m tools.verification_profile.validator registration.cbor \
  --registration-cbor --schema-lock-sha256 TRUSTED_LOCK_SHA256
make test-profile-registration
```

Rust 行入口为 `phase-r:<trusted-lock-sha256-hex><TAB><canonical-CBOR-hex>`。已有 JSON bootstrap、R1 raw Profile 与 FM/RIR 模式保持兼容；`--production` 继续拒绝。

## 覆盖登记

| 规则 | 登记与范围 |
|---|---|
| SV-75b、SV-108 | IMPLEMENTED：两个正式 ContentMap/tag 的纯摘要重算；完整相位调用另验收 |
| SV-79、SV-90 | IMPLEMENTED：完整六类 RegistryEntry 的排序、身份去重、封闭枚举及合法版本化引用 |
| SV-33/37/59/66/75a/84/91/109 | PARTIAL：audit Phase R 的嵌套假设、信封、引用及快照结构检查；其他方法/相位接线待完成 |

119 Type A 从 R1 的 **7/28/84** 变为 **11 implemented / 36 partial / 72 not implemented**。18 个摘要为 3 implemented、2 partial、13 not implemented。规则计数不授予完整 A0/A1、P0-1B、Gate、主网或生产资格。

## 证据与复现

固定向量 74 条（20 正例、54 反例），涵盖所有注册对象/状态和事件类型、非平凡 diamond DAG、多节点闭环、身份与内容摘要分离、错误/缺失/多余嵌套字段、过期时点不参与注册判定、schema 版本/内容/可信 pin、引用与摘要冲突。17 项默认回归另检查 hashlib/OpenSSL preimage、命令行/生产拒绝、输入不变及旧部署的传递依赖。

两台物理机各自构建并通过全部 74 条向量，结果流 SHA-256 同为 `52398f0836bba2891d959be13487855030ada910e12485b2d982c9dc381b8907`；环境与逐文件 pin 见[机器摘要](PROFILE-REGISTRATION-R2-20261107.summary.json)。[本片源码包](public-evidence/PROFILE-REGISTRATION-R2-source.tar.gz)保存实际对拍所用源码、向量、类型表及 source-sha256.json，已在新目录复核 pin 并独立复跑 74 条。该包为最小对拍源码包，仓库全量交付使用正常 package 入口。

完整 `make test` 退出码为 0：默认 23 组 497 项（R1 480 + R2 17），另 25 项执行器测试；20 次 sanitizer、Claim/FM-S1a/FM-S1b/RIR/R1/R2 对拍通过。24 套公开历史快照的 249 条事件重新用当前实现重放通过。原始全量日志、两次开发期失败及源码部署记录保留在操作者本地证据根。本轮双机范围限于静态编码和注册检查，新增任务协议运行数为 0，不提供日志 finality 或身份/统计独立的保证。

R1 先前在未提交工作区上运行；本片归档其机器摘要列出的全部原始源码，见 [R1 源码包](public-evidence/PROFILE-DIGEST-R1-source.tar.gz)，每份文件按 R1 已有摘要核对。R1 报告/摘要保留原值，当前源码的复跑不能替代其历史运行。

开发期新增测试后首次完整检查遇到清单过期；随后补入新报告时发现文档链接尚未落盘。两次失败均保留在操作者证据目录，修正清单和报告后重新运行，不改动断言降低标准。
