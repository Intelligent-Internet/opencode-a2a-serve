## 实施方案

### 1. 核心逻辑重构
- **文件路径**：`src/opencode_a2a/config.py`
- **逻辑设计**：
    - 将 `Settings` 从 `dataclass` 改为继承 `pydantic.BaseModel` (或 `pydantic_settings.BaseSettings`)。
    - 使用 Pydantic 字段类型约束（如 `HttpUrl`, `int`, `bool`）。
    - 引入 `@field_validator` 校验关键配置：
        - `a2a_jwt_algorithm`: 限制为特定非对称算法（如 RS256, ES256）。
        - `a2a_jwt_audience` / `a2a_jwt_issuer`: 设置为必填。
        - 其他枚举值校验。
    - 在 `from_env` 或 `__init__` 中执行 `model_validate`，实现 Fail-fast。

### 2. 回归测试点
- **无效配置拦截**：编写单测，设置非法环境变量（如 `A2A_JWT_ALGORITHM=MD5`），验证 `Settings` 初始化抛出 `ValidationError`。
- **环境隔离验证**：验证默认值在未设置环境变量时依然正确生效。
