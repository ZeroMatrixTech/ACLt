# 第三方材料与依赖清单

**状态：** P1-a（阶段 #128）实现记录，2026-11-15。OQ-01 仍为 OPEN；本文件提供关闭证据之一，不关闭 OQ-01。

**范围：** 当前交付范围（`DELIVERY-SCOPE.json`）内可识别的第三方材料，以及构建、运行和 CI 使用的第三方依赖。历史证据包中的材料按原样保留；本文件不重写历史证据。

**依据：** 公开发布审计 `audit-20261115-01-public-release.md` 的 A7.3，根目录 `LICENSE`，`README.md` 的“开源与许可”，`CONTRIBUTING.md` §11，以及 OQ-01。仓库自身的许可范围见这些文件；本文件只记录第三方材料与 NOTICE 核对事实。

**性质：** 这是对当前仓库材料的工程核对，不是法律意见，也不是完整的供应链审计。它不判断外部审计原文中 AI 产出的权利状态，不代替名称或商标检索，也不宣称已经穷尽所有可能的外部材料。

## 1. 第三方材料

| 材料 | 位置与使用方式 | 许可或权利状态 | 处理与备注 |
|---|---|---|---|
| Unicode 16.0.0 规范分解数据（生成数据） | `tools/verification_profile/rust/unicode_data.rs`；由 `generate_unicode.py` 从 CPython 3.14.4 `unicodedata` 的 Unicode 16.0.0 数据生成 | `Unicode-3.0`；`unicode_data.rs` 文件头带 SPDX 标识；同目录 `UNICODE-LICENSE.txt` 保存许可全文 | 数据随源码包分发，许可全文与数据同目录；生成器中的字符串也记录 `Unicode-3.0`。未把该数据改标为 Apache-2.0。 |
| Google Fonts：Press Start 2P、ZCOOL KuaiLe、Noto Sans SC | `docs/00-overview/aclt-theater.html` 通过 `fonts.googleapis.com` 的样式表在运行时加载 | 字体文件未纳入仓库，也不随交付物分发；页面使用系统字体作为回退 | 打开该页面会向 Google 发出网络请求。这里不复制字体文件，也不声称已满足字体再分发相关的全部条件；若将来本地化或打包字体，需重新核对许可并更新本文件。 |
| Linux 内核启动输出 | MULTIVM 证据包中的来宾串口日志 | 运行日志；本仓库不随交付物分发内核源码或内核二进制 | 作为实验证据原样保留。日志中的内核版本和配置以对应证据包为准；本文件不改变内核自身的许可。 |
| 外部审计原文（DeepSeek 输出） | `docs/08-governance/audits/external/AUDIT-20261105-01.original.txt` | 按 `README.md` 的仓库范围声明，仓库内工件采用 Apache-2.0；AI 产出的权利状态不在本轮判断范围 | 作为历史审计证据保留，不重写原文。若未来需要再分发或改编，应单独确认权利状态。 |
| 文献引用 | `docs/06-research/`、`docs/codocs/` 中的引用与链接 | 以引用和链接为主；未发现大段逐字转载，但未逐篇核对 | 本轮只做抽查；引用材料的许可仍归原作者。新增长段引文或图片时应单独记录来源与许可。 |

本轮核对范围内未发现随仓库分发的、带独立 `NOTICE` 的第三方 Apache 组件，也未发现 vendored 的第三方源代码。Unicode 数据是上表中唯一随交付物分发的第三方数据；字体只在运行时请求，不进入仓库。

## 2. 依赖许可

| 依赖类别 | 当前状态 | 许可处理 |
|---|---|---|
| Rust crates | 3 个 `Cargo.lock` 都只包含本仓库的 crate，没有外部 crate；当前 state3 的 `Cargo.toml` 声明 `license = "Apache-2.0"`；state1/state2 的历史 `Cargo.toml` 保持基线字节，由 `REUSE.toml` 外部声明覆盖 | 不产生第三方 crate 的 NOTICE 义务；Cargo 元数据可解析当前 state3 的许可，历史清单由外置声明覆盖。 |
| Python | 只使用标准库和仓库内本地模块；没有第三方 Python 包，也没有 vendored 的 Python 依赖 | 不产生第三方 Python 包许可文件；本地模块按仓库许可处理。 |
| Node 脚本 | `.cjs` 文件只使用 Node 内置模块 | 不产生第三方 npm 包许可文件。 |
| 外部工具链 | rustc/cargo、g++、OpenSSL CLI、Python、e2fsprogs、QEMU、Node 等由环境提供，不随仓库再分发 | 工具链自身的许可不因本仓库的源码交付而改变；环境版本要求见 `environment-standard.md`。 |
| CI action 与容器 | `actions/checkout` 固定到 SHA；容器镜像 `ubuntu:26.04` 使用可变标签，apt 包未固定版本 | action 的许可随其发布方；容器与 apt 包的可复现性问题由 P1-e 处理，本文件不把它们当作已固定的第三方材料。 |

## 3. NOTICE 判断

Apache License 2.0 第 4(d) 条规定：如果被再分发的作品包含 `NOTICE` 文本文件，则任何再分发的 Derivative Work 必须在以下至少一处包含该 `NOTICE` 中适用于该作品的归属声明：随附的 `NOTICE` 文件、随作品提供的源码或文档、或作品生成的显示（且该显示通常出现第三方声明之处）；该条还允许在再分发作品中添加自己的归属声明，只要不修改许可。因此，是否存在该条义务，取决于是否实际分发包含 `NOTICE` 的第三方作品，而不取决于本仓库采用 Apache-2.0。

就本轮核对的范围：

- 在本次核对范围内，未发现随附 `NOTICE` 的第三方 Apache 组件；
- 在本次核对范围内，未发现 vendored 的第三方源代码；
- 仓库当前没有 `NOTICE` 文件；在本次核对范围内，也未识别出需要复制到 `NOTICE` 的第三方归属声明；
- Unicode 数据的 `Unicode-3.0` 许可全文 `UNICODE-LICENSE.txt` 与数据同目录并随源码包交付；本文件只记录这一事实，不对 Unicode 许可的全部合规要求作法律结论；
- Google Fonts 只在运行时请求，字体文件不随交付物分发。

**当前结论（限于本次核对）：** 在本次核对的材料与依赖范围内，未识别出 Apache-2.0 第 4(d) 条要求随附的第三方 `NOTICE`。这是对当前仓库材料的事实核对，不是法律意见，也不表示未来不会产生义务。

**触发重新核对的条件：** 新增带 `NOTICE` 的第三方 Apache 组件；vendored 第三方代码或数据；本地化或打包字体；新增需要保留归属/许可声明的第三方材料；改变交付范围或再分发方式。触发后应更新本文件、必要的 `NOTICE`、OQ-01，以及 README/CONTRIBUTING 中相应的许可陈述；涉及权利状态判断时由维护者决定是否取得法律意见。

## 4. 相关文档

- 公开发布审计：`docs/08-governance/audits/audit-20261115-01-public-release.md`（A7.3、AUD-20261115-013）
- 开放问题 OQ-01：`docs/07-roadmap/open-questions.md`
- 仓库许可：根目录 `LICENSE`
- 许可范围陈述：`README.md` 的“开源与许可”；`CONTRIBUTING.md` §11
- Unicode 许可全文：`tools/verification_profile/rust/UNICODE-LICENSE.txt`
- 环境基线：`docs/08-governance/environment-standard.md`

本文件不宣称：完整 REUSE 合规、官方 REUSE 工具认证、法律审查、第三方清单穷尽、OQ-01 关闭、名称或商标已清理、README 成熟度声明已完成，或公开发布就绪。
