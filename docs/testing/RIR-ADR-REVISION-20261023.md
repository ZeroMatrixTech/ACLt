# ADR-0006 审阅建议落实记录（2026-10-23）

本记录将 ADR-0006 的六条审阅建议（RIR-REV-01—06）落实到候选 ADR 的对应小节，并同步更新候选向量清单。基线为 21cfb4ab74103fa84510f4423e0bd61011d35328，修订前工作区干净。修订范围限于候选 ADR 和追踪文档；RIR validator/runtime 的实现在本轮范围之外，已接受规范、V1 处置与 Gate 保持不变。

| 发现 | 修订落点 | 候选预期 |
|---|---|---|
| RIR-REV-01 | ADR §4.2、§13.1 | 空 else 必须省略；显式空 else 为阶段 3 ENCODING |
| RIR-REV-02 | ADR §3.2—3.3、§4.4 | 仅解码 1.0 grammar；扩展无法解码为 ENCODING；可解码但禁用为 UNSUPPORTED；段数值边界只归阶段 6 |
| RIR-REV-03 | ADR §7、§13.1 | gas → 参数/地址 → 输出上限 → 效果，范围加法不回绕，零长度仍检查端点 |
| RIR-REV-04 | ADR §4.1、§4.4、§7 | input_arity 为 uint32 范围；Receipt 输入数必须相等；不等先于本阶段资源兼容性失败 |
| RIR-REV-05 | ADR §9、§13 | 只改执行上限保持工件摘要，改变 ReceiptID；规则/成本表通过新 RIRVersion 改变工件身份 |
| RIR-REV-06 | ADR §6.2 | 精确比较作为谓词，不新增 VerificationMethod，不由相等直接产生 TRUSTED |

候选向量见 [JSON 清单](rir-adr-revision-vectors-20261023.json)，含最小 Wasm 字节和宿主调用/绑定性质用例。字节来源为前次只读审阅的最小结构反例；前次现有 Wasm 引擎可验证/运行，不代表通过新的 RIR canonical 或 gas 规则。当前清单明确 NOT_RUN_AGAINST_RIR_IMPLEMENTATIONS；其余语义用例须在后续 RIR 双实现中落地。没有用 Python 临时哈希模拟正式 ReceiptID。

路线图只记录上述候选修订；ADR 仍为 PROPOSED，OQ-05 仍 OPEN，P0-1B/G0/G2 状态不变。本轮未重跑网络或 VM 实验；已有双机证据不替代 RIR 实现证据。原审阅反例和报告保存在工作区 outputs/rir-adr-review-20261023/，历史审阅结论保持原样。

校验范围限于结构/链接/交付清单核对与 make check；文档检查不构成 RIR conformance。后续先审查本轮候选边界，再开展最小双机 lowering 构建探针和双解释器验证。
