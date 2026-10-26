# B/Q 第三片：证据审阅与失效边界

`make check-bq-readiness` 运行 18 项回归。14 个 requirement、12 个 inventory 场景、8 个创建前降级场景与 19 个 lifecycle 投影均是本地只读研究；不是 R/I/F/B/D validator、能力配置器或 P0-5 实现。

- hypothetical-complete.json 的有效记录全部是人工假定，正例最多输出 REVIEW_CANDIDATE；从不输出 ENABLED 或授权 TRUSTED。
- project-gaps.json 的缺口是正式部署证据尚未建立；其中既有工程材料通过 project-evidence-index.json 与真实文件摘要绑定，不等于来源审核通过。
- scope/window/当前时间是显式输入，规范半开窗口；不访问网络、系统时钟或活数据库。
- 创建后的 Receipt 不换 Profile；终态不改判；安全撤销、自然到期、来源 unknown 和 LIVENESS mapping 分开。

`make test-bq-readiness BQ_READINESS_REPORT=/existing-parent/new.json` 写新报告并保存 input/source/旧材料 pin。拒绝覆盖、重复 JSON key、浮点、未知/重复清单项和伪造项目通过状态。

[方法与权威边界](../../docs/06-research/bq-readiness-slice3.md)。
