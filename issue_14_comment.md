## 实施方案

### 1. systemd 配置调整
- **建议操作**：修改 `scripts/deploy.sh` 或生成的 `.service` 模板。
- **配置项建议**：
    ```ini
    [Service]
    # 路径拦截
    InaccessiblePaths=/data/projects
    # 精确放通当前项目的可写路径（%i 为 instance 名称）
    ReadWritePaths=/data/projects/%i
    # 运行环境收紧（根据风险评估选择）
    # RootDirectory=/opt/opencode-a2a/%i
    # BindReadOnlyPaths=/usr /bin /lib /lib64 /etc
    ```

### 2. 核心逻辑验证
- **设计说明**：
    - 验证 `gh` CLI 及其调用的 `ssh` 等工具在更严苛的隔离环境下是否仍能正常运行（可能需要额外 BindPaths）。
    - 验证 OpenCode 后端调用是否受影响。

### 3. 回归测试点
- **权限边界测试**：在 A2A 进程中尝试 `ls /data/projects/other-project`，验证返回 Permission Denied。
- **正常功能测试**：执行 A2A 基础对话流程，确保 `directory` 访问（如有绑定）依然正常。
