# 模板与 claim 编码切片：Python / Rust 对拍

日期：2026-10-23。基线 `6750c18`。本轮完成下一轮计划的第二、第三项，在明确的候选切片内实现编码、摘要及独立语言对拍。P0-1B、G0/G2 不关闭，原生产 validator 的 `--production` 继续拒绝。

## 实现与信任边界

[候选 wire 合约](../../schemas/verification-profile/claim-codec-slice.json) 固定本轮字段、类型、排序、测试 import 与资源界限。规范已经给出对象和摘要公式，但完整 wire-key 表及官方 external schema import 尚未落地；本轮以文本字段名作 identity wire-key 表，VersionRange 按规范用整数键 0/1。这个候选不能由“实现已通过”反向变成正式协议决定。

Python 实现在 [codec.py](../../tools/verification_profile/codec.py)，独立 Rust 实现在 [rust/](../../tools/verification_profile/rust/README.md)。两者分别完成原始 CBOR 解析、typed Schema View 投影与逆投影、对象校验、重新编码和 SHA-256。Rust 无第三方 crate，不调用 Python。输入始终以原始字节为准，不先用 JSON 重编码来掩盖非法原始表示。

支持确定长度、最短整数/长度、编码字节字典序 map、禁止重复键、禁止 tags/bignum/float/null/undefined、int64/uint64 边界、既约 Rational、SemVer、VersionRange 的省略上界，以及限定对象的有序 pair-array。Unicode NFC 输入必须已经规范化，非 NFC 拒绝；不静默改写已签名/已摘要的输入。Python 使用 Unicode 16.0.0 标准库；Rust 使用固定同版本数据和独立算法。CBOR 帧最多 1 MiB，嵌套深度最多 48，解码项最多 10,000；超限拒绝，属于本地运行限制，不宣称完整协议资源政策。

对象链：`ClaimTemplate → template_digest → VersionedObjectRef → [ref, concrete_bindings] → rendered_claim_digest`。测试链 envelope 显式核对模板身份三元组、槽位集合与两级摘要；不依赖远程读取。

- 模板 ContentMap 只包含 schema_version、encoding_profile_id、normative_text、slot_decls；id/version/digest 与 translations 被排除。
- claim 摘要散列结构化二元组，完整 ref 中的 id/version/digest 都被绑定；不是渲染文本的 SHA。
- 域分离严格使用 `SHA256(u8(tag length) || ASCII tag || canonical CBOR)`；两个 tag 与规范 §17.4 一致。
- ExternalTypedObject 仅接受固定本地测试 import `acl.schema.claim-test-bytes@1`，其声明文件、版本和 SHA 已锁定；未知/变更 import 拒绝。此测试 schema 规定 payload 为 CBOR bstr，object_digest 为其原始 canonical_bytes 的 SHA-256，不将它升级为官方 external schema。
- 不支持 ENUM 槽位形状、完整 Profile/Decision、注册表授权、STATIC 槽位与 Profile 等式、槽位值的完整语义和 claim 文本渲染。translations 只作为 advisory 数据处理；将来展示时仍须遵守非规范翻译标记。

## 证据

106 个固定字节向量（34 个正例、72 个负例），每个正例同时携带 Schema View，复杂对象另带预期摘要。原始 hex 是 fixture 权威输入。基本整数/容器向量人工固定；复杂对象字节由 Python 初次生成后固定，并通过独立 Rust 重新编码/散列及 OpenSSL 摘要复核，不能把这当成独立第三方审计。

`scripts/check-claim-codec.py` 在临时目录用 rustc 构建并运行对拍，开启 overflow checks，固定随机种子 20261023。报告计数为 **29,766**：106 原始向量、34 反向 Schema View、8 项绑定变异、400 整数、27,325 Unicode、663 次逐前缀截断、400 字节变异、800 随机字节、13 非法视图、4 非法 JSON、13 SHA-256 样例。另由 OpenSSL 复核两个固定对象摘要。

拒绝测试覆盖最短编码、截断/超长声明、重复/逆序键、整数溢出、非法 UTF-8、非 NFC、缺失/null/未知字段、扁平 header、错误版本、模板与 claim 篡改、错误/裸摘要引用、未知 import、payload/object_digest 不一致。性质测试区分模板身份/advisory 排除与 claim 完整引用绑定；重绑定后的合法对象也必须成功，不能靠“全部拒绝”通过。

SHA-256 另对空输入、abc、55/56/63/64/65/127/128/129 字节及一百万字节等边界与 Python hashlib 对拍；OpenSSL 独立复核的是上述两个固定对象摘要。Unicode 数据生成器只共享标准数据；没有共享两语言的规范化实现。字节 fuzz 是固定样本，不是穷尽证明。

## 覆盖登记与勘误

[coverage.json](../../schemas/verification-profile/coverage.json) 与 [inventory.json](../../schemas/verification-profile/inventory.json) 现为：119 Type A = **3 局部 implemented + 19 partial + 97 not implemented**。18 摘要中 **2 partial、16 not implemented**。新增 partial 为 SV-25/35/42/46/52/60/62/70/86a/86c/118，没有将任何规则升级为完整 implemented。

§17.4 表后 SV-42 历史说明已按 §13.2 现有 owner 分工勘误：SV-25 管 primitive 禁令，SV-52 管整数范围/最短整数/bignum，SV-42 管容器与既约 Rational；摘要仍由各自唯一 owner 负责。未更改 tag、算法或协议状态。

## 复现与下一步

```sh
make check
make test-claim-codec
```

前者运行模型/配置/交付与清单/盘点检查；后者构建 Rust、运行对拍，并写 `artifacts/claim-codec/cross-language.json`。它已纳入 `make test` 与独立 `claim-codec` 流程分组。`make check` 不要求 Rust；新编码测试要求 Python 提供 Unicode 16.0.0。现有环境基线 CPython 3.14.4 / rustc 1.93.1 已验证，不引入下载依赖。

下一步审查候选 wire 表与 import 边界，冻结 ENUM/完整模板类型和外部 schema 合约，再接入正式注册/Phase D 输入。现有实验接纳端 JSON wire 与历史 VM 证据不迁移到这套候选编码；本轮没有改动实验运行代码。

本轮本地 `make check` 共 74 项通过（模型 13、验证配置/编码 34、流程/交付 27），盘点与交付清单检查通过。构建和结果日志保存在项目工作区 `outputs/profile-codec-20261023/`。
