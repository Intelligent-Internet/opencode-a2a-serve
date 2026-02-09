## 实施清单 (Implementation Checklist)
- [ ] 修改 `scripts/deploy/install_units.sh` 中的 systemd 模板。
- [ ] 在 `[Service]` 段增加以下配置：
    - `InaccessiblePaths=${DATA_ROOT}` (拦截对其他项目的访问)
    - `ReadWritePaths=${DATA_ROOT}/%i` (重新开放本项目的读写权限)
- [ ] 验证 `ReadOnlyPaths` 是否包含所有必要的系统路径（如 `/usr/bin/gh`, `/opt/uv-python` 等）。
- [ ] 更新文档，说明此隔离级别对本地路径引用的影响。

## 核心逻辑 / 修改说明
```ini
# scripts/deploy/install_units.sh 模板修改

[Service]
...
ProtectSystem=strict
# 禁止访问整个数据根目录，防止跨项目泄露
InaccessiblePaths=${DATA_ROOT}
# 仅允许访问当前实例目录
ReadWritePaths=${DATA_ROOT}/%i
...
```

## 回归测试点
- 部署新实例后，通过 A2A 请求尝试读取 `/data/opencode-a2a/other-project/config/a2a.env`，应被内核拒绝。
- 实例自身读写 `/data/opencode-a2a/%i/workspace` 应保持正常。
