# Agent 自助拉起/释放 SOP（中文草案）

> 状态：Draft（仅用于需求评审，后续再产出英文正式版）
>
> 关联议题：#145

## 1. 目标

本 SOP 用于指导“消费方 agent”在当前 `systemd` 主路径下，自助完成：

1. 拉起一个新的 `opencode-a2a-serve` 实例。
2. 验证实例是否可用。
3. 在不再需要时安全卸载并释放资源。

## 2. 适用范围与边界

1. 仅覆盖当前脚本主路径：`scripts/init_system.sh`、`scripts/deploy.sh`、`scripts/uninstall.sh`。
2. 不覆盖 Docker/Kubernetes 方案。
3. 不替代产品协议文档；协议行为请参考 `docs/guide.md`。

## 3. 输入契约（给调用方 agent）

### 3.1 必填输入

1. 环境变量 `GH_TOKEN`（仅环境变量，不允许通过 CLI 传入）。
2. 环境变量 `A2A_BEARER_TOKEN`（仅环境变量，不允许通过 CLI 传入）。
3. CLI 参数 `project=<name>`。

### 3.2 常用可选输入

1. `a2a_port=<port>`（默认 `8000`）。
2. `a2a_host=<host>`（默认 `127.0.0.1`）。
3. `a2a_public_url=<url>`（默认 `http://<A2A_HOST>:<A2A_PORT>`）。
4. `data_root=<path>`（默认 `/data/opencode-a2a`）。
5. `opencode_provider_id=<id>`、`opencode_model_id=<id>`。
6. `repo_url=<url>`、`repo_branch=<branch>`（首次部署可自动 clone 工作区）。

### 3.3 提供方密钥（按需）

以下密钥仅支持环境变量注入（不可走 CLI）：

- `GOOGLE_GENERATIVE_AI_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `AZURE_OPENAI_API_KEY`
- `OPENROUTER_API_KEY`

## 4. 标准执行流程

### 步骤 0：前置检查（建议）

```bash
command -v systemctl
command -v sudo
```

首次机器初始化时，先执行：

```bash
./scripts/init_system.sh
```

### 步骤 1：部署实例

最小示例：

```bash
GH_TOKEN='<gh-token>' A2A_BEARER_TOKEN='<a2a-token>' \
./scripts/deploy.sh project=alpha a2a_port=8010 a2a_host=127.0.0.1
```

公网 URL 示例：

```bash
GH_TOKEN='<gh-token>' A2A_BEARER_TOKEN='<a2a-token>' \
./scripts/deploy.sh project=alpha a2a_port=8010 a2a_public_url=https://a2a.example.com
```

### 步骤 2：可用性校验

1. systemd 状态：

```bash
sudo systemctl status opencode@alpha.service --no-pager
sudo systemctl status opencode-a2a@alpha.service --no-pager
```

2. 健康检查：

```bash
curl -fsS http://127.0.0.1:8010/health
```

预期返回包含 `{\"status\":\"ok\"}`。

3. Agent Card 检查（可选）：

```bash
curl -fsS http://127.0.0.1:8010/.well-known/agent-card.json
```

### 步骤 3：升级/重启（可选）

当共享代码更新后，可执行：

```bash
GH_TOKEN='<gh-token>' A2A_BEARER_TOKEN='<a2a-token>' \
./scripts/deploy.sh project=alpha update_a2a=true force_restart=true
```

### 步骤 4：卸载并释放资源

先预览：

```bash
./scripts/uninstall.sh project=alpha
```

确认后执行：

```bash
./scripts/uninstall.sh project=alpha confirm=UNINSTALL
```

说明：脚本不会删除共享模板 unit（`opencode@.service`、`opencode-a2a@.service`）。

## 5. 成功判定与返回语义（供 agent 使用）

### 5.1 部署成功判定

满足以下条件即视为成功：

1. `deploy.sh` 退出码为 `0`。
2. `opencode@<project>.service` 与 `opencode-a2a@<project>.service` 为 active/running。
3. `GET /health` 返回 200 且响应包含 `status=ok`。

### 5.2 卸载返回语义

1. 预览模式：不执行破坏动作，输出 `Preview completed.`。
2. 应用模式成功：退出码 `0`。
3. 应用模式“带非致命问题完成”：退出码 `2`（需记录 WARN 并人工复核）。

## 6. 常见失败与处理建议

1. 缺少必填 secrets：补齐 `GH_TOKEN`、`A2A_BEARER_TOKEN` 后重试。
2. `sudo` 不可用或需交互密码：切换到可交互终端，或配置最小范围 NOPASSWD。
3. project 名不合法（卸载 apply 更严格）：改为小写字母/数字/`_`/`-` 组合。
4. provider/model 与密钥不匹配：补齐对应 provider key 后重试。
5. 服务启动失败：先看 `journalctl`，再按失败点回滚或重试部署。

## 7. 安全基线（当前版本）

1. 严禁通过 CLI 明文传 token/key。
2. `a2a_enable_session_shell=true` 为高风险开关，仅限可信内部场景。
3. 脚本生成的 `config/*.env` 包含敏感信息，禁止外泄与日志打印。
4. 对外暴露实例时，必须配合网络访问控制与 token 管理策略。

## 8. 给“消费方 agent”的最小执行模板

1. 检查前置条件（systemd/sudo/脚本路径）。
2. 组装环境变量与 `project` 参数。
3. 执行 `deploy.sh`。
4. 执行状态与健康检查，输出结构化结果（成功/失败/原因）。
5. 任务结束后按策略执行 `uninstall.sh`（先 preview，后 apply）。

---

如果本草案评审通过，下一步再输出英文正式版，并考虑将“输入契约 + 成功判定 + 错误语义”抽成可机读规范（便于 agent 稳定消费）。
