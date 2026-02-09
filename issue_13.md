## 实施清单 (Implementation Checklist)
- [ ] 在 `src/opencode_a2a/` 下新增工具函数 `validate_directory_path(path, workspace_root)`。
- [ ] 使用 `os.path.realpath` 处理传入路径，确保消除 `..` 和 符号链接。
- [ ] 校验逻辑：`path.startswith(workspace_root)` 且路径分隔符匹配，防止 `workspace_root_extra` 绕过。
- [ ] 在 `OpencodeAgentExecutor` 初始化或 `execute` 阶段调用校验。
- [ ] 补充文档说明 `A2A_ALLOW_DIRECTORY_OVERRIDE` 开关（可选）。

## 核心逻辑 / 修改说明
```python
def validate_path(requested_dir: str, allowed_root: str):
    real_requested = os.path.realpath(requested_dir)
    real_allowed = os.path.realpath(allowed_root)
    # Ensure it's inside allowed_root
    if not real_requested.startswith(real_allowed):
        raise ValueError("Directory access out of bounds")
```

## 回归测试点
- 传入 `directory="/etc"` 或 `directory="../"` 应返回错误或被拦截。
- 合法的 workspace 子目录应能正常工作。
