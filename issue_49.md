## 实施清单 (Implementation Checklist)
- [ ] 在 `src/opencode_a2a/agent.py` 的 `OpencodeAgentExecutor.execute` 中提取用户身份（identity）。
- [ ] 身份来源：`context.call_context.state.get("identity")`，若无则默认为 `"anonymous"`。
- [ ] 修改 `self._sessions.get/set` 的调用，使用 `(identity, context_id)` 复合键或拼接字符串键（如 `f"{identity}:{context_id}"`）。
- [ ] 增加单元测试：
    - 验证同一 `context_id` 在不同 `identity` 下隔离。
    - 验证 `metadata.opencode_session_id` 的绑定逻辑同样受到 `identity` 校验（方案 B）。

## 核心逻辑 / 修改说明
```python
# src/opencode_a2a/agent.py

# 在 execute 方法中：
identity = context.call_context.state.get("identity") or "anonymous"
session_key = f"{identity}:{context_id}"

# 获取 session 时使用 session_key
session_id = await self._get_or_create_session(
    session_key, # 替换原有的 context_id
    user_text,
    preferred_session_id=bound_session_id,
)
```

## 回归测试点
- 匿名用户（无 JWT）仍能通过 `contextId` 正常聊天（不影响现有流程）。
- 具备 `identity` 的用户切换后，即使用同一 `contextId` 也应启动新会话，不看到前一用户的内容。
