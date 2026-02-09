## 实施方案

### 1. 核心逻辑修改
- **文件路径**：`src/opencode_a2a/opencode_client.py` (或 `config.py`)
- **逻辑设计**：
    - **归一化**：在 `OpencodeClient` 初始化时，对 `opencode_directory` 执行 `os.path.realpath(os.path.expanduser(path))`。
    - **边界校验**：
        - 确定允许的根目录（通常为 A2A 部署的 workspace 或环境变量指定的 `DATA_ROOT`）。
        - 校验归一化后的路径是否以该根目录为前缀。
        - 校验路径中不包含非法字符或尝试越权的模式。
    - **默认值处理**：若请求未提供 `directory` 且环境变量未设置，使用当前运行目录作为默认 workspace。

### 2. 回归测试点
- **路径穿越测试**：构造带有 `../` 的 `OPENCODE_DIRECTORY` 环境变量，验证服务启动失败或路径被强制收拢在边界内。
- **符号链接测试**：在边界内创建一个指向边界外的符号链接，验证访问该链接对应的 `directory` 被拒绝。
