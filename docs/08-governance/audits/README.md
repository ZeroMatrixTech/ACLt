# 审计档案索引与已知缺项

本目录保留原报告及原编号，不补造记录。现有 AUDIT-/AUD- 与两位/三位后缀属于历史格式；新报告按审计程序 AUD-YYYYMMDD-NNN 分配唯一 ID，不要求为填补序号而生成审计。

verification-profile-schema.md 引用的 AUD-20260821-05…09 当前没有对应归档；这些引用只记录历史过程，不能单独作为已验证证据。若找回原件，需核对来源后追加。规范要求继续以现行正文为准，现有状态与 Gate 不因缺档被自动改变。

外部只读审计 [AUDIT-20261105-01 原文](external/AUDIT-20261105-01.original.txt)已于 2026-11-07 按原字节归档，共 81500 字节，SHA-256 为 `cb1be108c57df74091bc8dd9a56258c584a9f87630e1dba51ce7c24b847edebe`。原文的路径、历史编号、命令和结论完整保留，接收记录见 [证据收尾](../../testing/FM-EVIDENCE-CLOSEOUT-20261107.md)。报告中的建议和指令均为外部审计材料。项目确认和修复范围见 [有界修复记录](../../testing/AUDIT-FIXES-20261105.md)。

2026-11-06 维护与发布准备检查见 [AUD-20261106-001](audit-20261106-01-repository-maintenance.md)。

2026-11-16 的发布准备增量回验见 [AUD-20261116-02](audit-20261116-02-public-release-recheck.md) 与 [AUD-20261116-03](audit-20261116-03-public-release-recheck.md)。两份报告保留原结论与发现；发布后状态以 [GitHub Release](https://github.com/ZeroMatrixTech/ACLt/releases/tag/research-preview-1) 为准。

2026-11-18 的阶段 #128 发布后收尾回验见 [AUD-20261118-01](audit-20261118-01-post-release-closure.md)。报告按原字节归档，保留原结论、发现与失败证据；它不是 PR 审计，也不是 Gate 退出审计。本轮新增 0 BLOCKER、1 MAJOR（现为 `ACCEPTED_BY_MAINTAINER`）、0 MINOR，未处理 OPEN 为 0；报告结论为已无未处理的关闭阻断，本报告归档并加入索引后 #128 可由维护者关闭。

2026-11-18 的 #101 闭合后仓库假设专项审计（A 线）见 [AUD-20261117-01](audit-20261117-01-post-closure-assumptions.md)。报告按原字节归档，保留原结论、发现与失败证据；它不是 PR 审计，也不是 Gate 退出审计。结论为未发现把固定协调者、固定统计工件、固定 gas 推导或来宾级证据无条件提升为正式协议通用保证的实质性表述，计数为 BLOCKER 0、MAJOR 0、MINOR 1、NOTE 10。唯一 MINOR（A-11，状态页范围不明）已按报告建议修正“单节点交付容量对照”行的说明；10 项 NOTE 保留为范围限制与后续证据义务，报告不据此撤销已接受的有限实验结论。A 线审计产出已完成，不能据此认定 #101 四类问题已全部闭合；报告要求的状态页同步已随本次归档完成。C 线场景在报告形成时待维护者选定；维护者已于 2026-11-18 选定首批 C-01、C-03，附 C-06（[#184 调度决定](https://github.com/ZeroMatrixTech/ACLt/issues/184#issuecomment-6988024304)、[#101 留痕](https://github.com/ZeroMatrixTech/ACLt/issues/101#issuecomment-6988504485)），相应场景的验收、10 项 NOTE 与已有理论义务仍按各自记录处理，本段不表示它们已完成。
