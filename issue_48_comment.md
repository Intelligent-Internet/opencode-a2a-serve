## 实施方案

### 1. 核心逻辑修改
- **文件路径**：`src/opencode_a2a/agent.py`
- **逻辑设计**：
    - 将 `execute` 方法的起始部分（参数提取与校验）纳入 `try...except` 保护范围，或确保校验失败时显式调用 `self._emit_error`。
    - 对于 `task_id` 或 `context_id` 缺失的情况，如果 `RequestContext` 中能解析出部分信息，则尽力构造 `TaskStatusUpdateEvent(state=failed)`；如果完全无法解析，记录 Error 日志并确保 `event_queue` 优雅关闭（如适用）。
    - 统一所有业务校验（如 `user_text` 为空）的返回路径，确保不抛出导致请求挂起的未捕获异常。

### 2. 回归测试点
- **非法输入测试**：构造缺少 `context_id` 或 `task_id` 的原始请求，验证服务端是否返回了标准格式的 A2A failed 事件。
- **空输入测试**：发送不含 text 的消息，验证是否通过 `event_queue` 收到 "Only text input is supported" 错误。
