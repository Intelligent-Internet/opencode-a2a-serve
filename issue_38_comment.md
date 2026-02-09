## 实施方案

### 1. 配置扩展
- **文件路径**：`src/opencode_a2a/config.py`
- **逻辑设计**：
    - 新增 `a2a_jwks_url` 配置项。
    - 确保 `pydantic` 校验支持 URL 格式。

### 2. JWKS 客户端实现
- **建议路径**：`src/opencode_a2a/auth_utils.py` (新增)
- **逻辑设计**：
    - 实现 `JWKSClient` 类，负责从 `a2a_jwks_url` 获取 JSON 响应。
    - 增加本地内存缓存（TTL），避免频繁网络请求。
    - 提供 `get_public_key(kid: str)` 方法，根据 JWT Header 中的 `kid` 返回 PEM/DER 格式公钥。

### 3. 鉴权流程集成
- **文件路径**：`src/opencode_a2a/app.py`
- **逻辑设计**：
    - 在 JWT 验签逻辑中，首先检查 Header 是否包含 `kid`。
    - 若包含且配置了 `a2a_jwks_url`，则通过 `JWKSClient` 获取对应公钥。
    - 兜底逻辑：若无 `kid` 或 JWKS 查找失败，尝试使用本地静态公钥。

### 4. 回归测试点
- **动态验签测试**：模拟 JWKS 端点返回 Mock 公钥，并使用对应私钥签发 JWT，验证 A2A 服务能成功验签。
- **Key Rotation 测试**：更新 Mock JWKS 内容，验证缓存过期后系统能自动识别新密钥。
