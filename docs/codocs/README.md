# ACLt 历史文档档案

> 文档状态：历史索引  
> 最后复审：2026-08-18  
> 权威性：本目录中的文件仅用于版本、论证和决策追踪，不构成当前协议规范。

## 使用规则

- 历史文件保留其原始名称、正文和时间戳；不得通过回写旧版本制造“当时已经决定”的假象。
- 与当前语义冲突时，以较新的明确项目决定、当前规范性文档和已接受 ADR 为准。
- 已发现会被误读为当前前提的历史文件，应在开头添加 `SUPERSEDED` 标记，但不改写其历史正文。
- 历史名称 DistributedCompute、DCP、RUDCP 和 BigMind 仅用于追踪；当前名称为 ACLt Protocol。
- v0.5 是当前协议语义基线；本目录内标为 v0.5 的历史材料并不自动取得当前权威性。

## 当前权威入口

1. [仓库 README](../../README.md)
2. [当前文档中心](../README.md)
3. [当前状态](../07-roadmap/current-status.md)
4. [待决问题](../07-roadmap/open-questions.md)
5. [ADR-0001：如无必要勿增实体](../05-decisions/ADR-0001-no-unnecessary-entities.md)
6. [ADR-0002：RIR 与 V1 Rust Profile](../05-decisions/ADR-0002-normative-rir-and-v1-rust-profile.md)

## 已确认的历史冲突

`v0.5/ACLt_v0.5_Unresolved_Issues.md` 将 `Requester + Broker + Provider` 和 Foundation 职能描述为当前冻结前提，与现行最小本体不一致，已标记为 `SUPERSEDED`。其正文继续保留，作为语义演进证据。

v0.2 DOCX 及其他早期材料中的中心控制、Rank、51% 阈值、默认发行或 Foundation 权限等描述均不得作为当前设计依据，除非后续 ADR 明确重新接受。


v0.3 的 51%/默认发行文本已加历史横幅。v0.4 的 ADR-001…014 属旧编号空间，不能作为现行 ADR-0001…0007 的引用；保留历史正文。
