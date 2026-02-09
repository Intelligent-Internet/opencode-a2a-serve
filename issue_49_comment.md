## 实施方案

### 1. 身份提取与透传
- **修改文件**：`src/opencode_a2a/app.py`
- **设计说明**：
    - 更新 `bearer_auth` 中间件以解析 JWT（如有）。
    - 将提取的主体标识（如 `sub`）存入 `request.state.user_identity`。
    - 在 `StreamingCallContextBuilder` 中将其透传到 `ServerCallContext` 的 `user` 或 `state` 中。

### 2. 核心逻辑修改
- **文件路径**：`src/opencode_a2a/agent.py`
- **逻辑设计**：
    - 修改 `_TTLSessions`：将缓存 key 变更为 `(identity, context_id)` 复合键。
    - 在 `OpencodeAgentExecutor.execute` 中获取 `identity`。
    - `_get_or_create_session` 需支持按 `identity` 隔离缓存。
    - **所有权校验**：若 `metadata.opencode_session_id` 已存在于其他 identity 下，应拒绝绑定。

### 3. 回归测试点
- **多用户隔离**：验证 UserA 和 UserB 使用相同 `context_id` 时，后端指向不同的 OpenCode `session_id`。
- **非法绑定拦截**：验证 UserB 无法通过 metadata 强制恢复 UserA 的会话。
