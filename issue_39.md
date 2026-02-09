## 实施清单 (Implementation Checklist)
- [ ] 引入 `pydantic-settings` 到 `pyproject.toml` 的依赖中。
- [ ] 在 `src/opencode_a2a/config.py` 中重构 `Settings` 类，继承自 `pydantic_settings.BaseSettings`。
- [ ] 使用 `Field(..., env="...")` 映射环境变量。
- [ ] 增加 `Validator` 校验：
    - `a2a_jwt_algorithm`: 限制为非对称算法（如 RS256, ES256）。
    - `a2a_jwt_audience` / `a2a_jwt_issuer`: 必填项校验。
- [ ] 修改 `src/opencode_a2a/app.py` 中的 `create_app`，移除对 `a2a_bearer_token` 的显式运行时校验（由 Settings 统一处理）。
- [ ] 增加单元测试：模拟缺失/无效环境变量导致 `Settings` 初始化失败。

## 核心逻辑 / 修改说明
```python
from pydantic import Field, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    a2a_bearer_token: str = Field(..., min_length=1)
    # ... 其他字段 ...

    @validator("a2a_jwt_algorithm")
    def validate_algo(cls, v):
        if v not in {"RS256", "ES256", "PS256"}:
            raise ValueError("Only asymmetric algorithms are supported")
        return v
```

## 回归测试点
- 服务启动时缺失 `A2A_BEARER_TOKEN` 应立即崩溃并报错。
- 有效配置下服务应能正常初始化并读取 `agent-card`。
