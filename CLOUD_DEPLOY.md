# GitHub Actions 云端运行

这个项目可以完全免费地跑在 GitHub Actions 上。电脑关机也不影响每天生成日报。

## 零配置运行

不配置任何 secret，也能运行。

1. Fork 仓库。
2. 打开 `Actions` 页面。
3. 启用 workflow。
4. 选择 `今日信号 Signal Daily`。
5. 点击 `Run workflow`。
6. `mode` 选择 `all`。
7. `audio` 保持 `never`。

运行完成后，GitHub 会自动提交生成文件：

```text
AI-Daily/YYYY-MM-DD AI 日课.md
AI-Daily/Podcast/YYYY-MM-DD AI 日课播客稿.md
```

## 自动运行时间

默认北京时间：

- 08:37 生成 AI 日课。
- 09:07 生成播客稿。

GitHub Actions 的定时任务可能有几分钟延迟。

## 可选：飞书文字推送

如果你想每天收到飞书文字推送，进入：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

新增：

```text
Name: FEISHU_WEBHOOK_URL
Secret: 你的飞书群机器人 webhook
```

配置后，workflow 会自动推送。没有这个 secret 时，只生成 Markdown。

## 可选：Fish Audio 音频

如果你想生成双人 MP3，新增：

```text
Name: FISH_API_KEY
Secret: 你的 Fish Audio API Key
```

手动运行 workflow 时：

- `audio: never`：不生成音频，适合测试。
- `audio: auto`：有 `FISH_API_KEY` 时生成音频。
- `audio: always`：强制尝试生成音频。

定时任务默认使用 `audio: auto`。配置了 `FISH_API_KEY` 时会生成音频；没有 API Key 或额度不足时，只生成文字稿。

## 可选：飞书群内可播放音频

只配置 `FEISHU_WEBHOOK_URL` 时，飞书能收到文字消息和音频文件链接。

如果希望群里直接出现可播放音频，需要配置飞书应用机器人，并添加这些 secrets：

```text
FEISHU_APP_ID
FEISHU_APP_SECRET
```

可选：

```text
FEISHU_CHAT_NAME
FEISHU_CHAT_ID
```

应用机器人需要权限：

- `im:chat:readonly`
- `im:message:send_as_bot`
- `im:resource`

并且机器人需要加入目标群聊。

## 常见问题

### 没有飞书会失败吗？

不会。没有 `FEISHU_WEBHOOK_URL` 时，只生成 Markdown。

### 没有 Fish Audio 会失败吗？

不会。没有 `FISH_API_KEY` 或额度不足时，只生成文字稿。

### 生成文件会提交到哪里？

workflow 会提交到当前仓库的 `AI-Daily/` 目录。

### 想改时间怎么办？

编辑 `.github/workflows/ai-daily.yml` 里的 cron。

GitHub Actions 使用 UTC 时间。当前配置：

```yaml
- cron: "37 0 * * *"  # 北京时间 08:37
- cron: "7 1 * * *"   # 北京时间 09:07
```
