# OpenCode Session Query Extension

本扩展用于在不增加自定义 REST 端点的前提下，通过标准 A2A `message:send` 传输通道，查询 OpenCode serve 的会话列表与指定会话的历史消息。

## Extension URI

`urn:opencode-a2a:opencode-session-query:1`

## 鉴权

复用 A2A 服务本身的鉴权方式（本仓库默认 `Authorization: Bearer <A2A_BEARER_TOKEN>`）。

## 请求格式

客户端调用标准 `POST /v1/message:send`，在 `message.content` 中携带一个 `Part.data`：

```json
{
  "data": {
    "data": {
      "op": "opencode.sessions.list",
      "params": {}
    }
  }
}
```

约定字段：

- `data.data.op`：操作名（字符串），以 `opencode.sessions.` 前缀标识本扩展
- `data.data.params`：参数对象（可选）
- `data.data.params.query`：可选；透传给 OpenCode server 的 query params（对象，key/value 均建议为字符串）

## 支持的操作

### 1) `opencode.sessions.list`

列出 OpenCode server 的 sessions。

`params`：

- `query`（可选）：透传 query params

### 2) `opencode.sessions.messages.list`

列出指定 session 的消息历史。

`params`：

- `session_id`（必填）：OpenCode session id
- `query`（可选）：透传 query params

## 响应格式

服务会返回标准 A2A `Task`，并在 `artifacts.parts` 中包含一个 `Part.data`，其 `data`（即 `data.data`）形如：

```json
{
  "op": "opencode.sessions.list",
  "result": {
    "...": "OpenCode serve JSON payload (透传)"
  }
}
```

其中 `result` 为 OpenCode serve 的 JSON 响应 **原样透传**（schema 以 OpenCode server 为准）。

## 日志与隐私

当 `A2A_LOG_PAYLOADS=true` 时，若请求中检测到 `opencode.sessions.*` 的 DataPart，本服务不会将请求/响应 body 写入日志，以避免泄露聊天历史内容。
