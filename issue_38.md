## 实施清单 (Implementation Checklist)
- [ ] 增加 `python-jose[cryptography]` 和 `httpx` 到依赖（如尚未包含）。
- [ ] 实现 `JWKSClient`：支持从 `A2A_JWKS_URL` 异步获取公钥集。
- [ ] 实现公钥缓存：建议使用内存缓存，TTL 默认为 1 小时。
- [ ] 修改 JWT 验签逻辑：根据 Token Header 中的 `kid` 从 JWKS 缓存中匹配公钥。
- [ ] 兼容模式：若 `A2A_JWKS_URL` 未配置，回退到现有的静态 `A2A_JWT_PUBLIC_KEY`。

## 核心逻辑 / 修改说明
```python
# 伪代码：
class JWKSClient:
    async def get_key(self, kid: str):
        if kid in self.cache and not self.is_expired():
            return self.cache[kid]
        # Fetch from URL, parse JSON, update cache
        ...
```

## 回归测试点
- 配置 `A2A_JWKS_URL` 指向 Mock 服务，验证 Token 携带正确 `kid` 时验签通过。
- 验证 JWKS 刷新机制：Mock 服务更新 Key 后，A2A 能在缓存过期后自动获取新 Key。

## 状态说明
此任务依赖于 #27 (JWT 基础鉴权接入)，目前标记为 **Blocked**。
