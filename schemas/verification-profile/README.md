# VerificationProfile Schema 工件

状态：`P0-1B STARTED / NOT CLOSED`。

- `verification_profile.schema.json`：`ACLt Schema View v1` 的首批 L1a 骨架；
- `coverage.json`：唯一实现覆盖登记，区分完整、部分、未实现、Type B 与 DEFERRED；
- 权威语义：[`../../docs/03-protocol/verification-profile-schema.md`](../../docs/03-protocol/verification-profile-schema.md)。

当前 Schema 只固定顶层字段、基础 ID、方法枚举及部分参数块在场性。它尚不是完整 P0-1B Schema，不能用于主网准入。新增覆盖时必须同时更新 `coverage.json`、对应测试和审计证据；不得仅因 JSON Schema 能解析就把规则标为完成。
