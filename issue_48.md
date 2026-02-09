## 实施清单 (Implementation Checklist)
- [ ] 审计 `src/opencode_a2a/agent.py` 中所有显式 `raise RuntimeError` 的位置。
- [ ] 在 `execute` 和 `cancel` 入口处加强校验：若 `task_id` 或 `context_id` 缺失，通过 Logger 报错并尝试最小化返回。
- [ ] 对于业务逻辑内（如 OpenCode 响应异常、输入为空等）的错误，统一调用 `self._emit_error`。
- [ ] 确保 `_emit_error` 产生的 `failed` 事件符合 A2A 协议规范。

## 核心逻辑 / 修改说明
```python
# src/opencode_a2a/agent.py

async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
    task_id = context.task_id
    context_id = context.context_id
    
    if not task_id or not context_id:
        # 这种情况下无法通过 event_queue 发送特定 task 的 failed 事件
        # 建议记录 Error 日志，并由底层框架/Middleware 拦截处理
        logger.error("Invalid request context: missing task_id/context_id")
        return

    # 其他业务校验错误
    if not user_text:
        await self._emit_error(event_queue, task_id, context_id, "Empty input", ...)
        return
```

## 回归测试点
- 模拟发送缺失 `task_id` 的 JSON-RPC 请求，验证服务端不发生未捕获异常崩溃。
- 输入为空或 OpenCode 超时时，客户端应能收到 `TaskStatusUpdateEvent` 状态为 `failed` 的事件。
