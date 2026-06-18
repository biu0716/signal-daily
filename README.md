# AI Daily MVP

一个极简版「AI 日课」生成器：从固定 RSS / Blog 源优先抓取最近 24 小时内容，筛选最多 5 条，生成 Obsidian Markdown 日报。不足 5 条时，会用最近 7 天的高质量内容补位，并标注为“补位阅读”。

## 文件

- `sources.json`：10 个核心信息源和日报规则。
- `ai_daily.py`：抓取、筛选、生成 Markdown。
- `podcast_daily.py`：把当天 AI 日课改写成适合听的中文播客稿。
- `.github/workflows/ai-daily.yml`：GitHub Actions 免费云端定时任务。
- `CLOUD_DEPLOY.md`：把项目搬到 GitHub Actions 的部署说明。

## 运行

在这个目录下执行：

```bash
python3 ai_daily.py --dry-run
```

确认内容正常后，写入你的 Obsidian Vault：

```bash
python3 ai_daily.py --output-dir "/Users/biu/Documents/Obsidian Vault/AI-Daily"
```

同时推送到飞书群机器人：

```bash
FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/..." \
python3 ai_daily.py --output-dir "/Users/biu/Documents/Obsidian Vault/AI-Daily" --send-feishu
```

也可以显式传入：

```bash
python3 ai_daily.py \
  --output-dir "/Users/biu/Documents/Obsidian Vault/AI-Daily" \
  --send-feishu \
  --feishu-webhook "https://open.feishu.cn/open-apis/bot/v2/hook/..."
```

生成当天播客稿：

```bash
python3 podcast_daily.py \
  --input-dir "/Users/biu/Documents/Obsidian Vault/AI-Daily" \
  --output-dir "/Users/biu/Documents/Obsidian Vault/AI-Daily/Podcast"
```

生成 Fish Audio 双人 mp3：

```bash
FISH_API_KEY="你的 Fish Audio API Key" \
python3 podcast_daily.py \
  --input-dir "/Users/biu/Documents/Obsidian Vault/AI-Daily" \
  --output-dir "/Users/biu/Documents/Obsidian Vault/AI-Daily/Podcast" \
  --audio always
```

默认双人声音沿用已选好的 Fish Audio voices：

- Host A: `bc9e47fd83a04010ad6617ed54b92ee3`
- Host B: `5c353fdb312f4888836a9a5680099ef0`

如果同时配置以下环境变量，脚本会把音频转换为 OPUS，并通过飞书应用机器人发送到群聊中，群成员可以直接在线播放：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_CHAT_NAME`（可选，默认 `AI日课群`）

应用机器人需要拥有 `im:chat:readonly`、`im:message:send_as_bot` 和 `im:resource` 权限，并已加入目标群聊。

同时推送播客稿摘要到飞书：

```bash
FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/..." \
python3 podcast_daily.py \
  --input-dir "/Users/biu/Documents/Obsidian Vault/AI-Daily" \
  --output-dir "/Users/biu/Documents/Obsidian Vault/AI-Daily/Podcast" \
  --send-feishu
```

## 免费云端运行

如果你经常关机，可以把这个项目放到 GitHub Actions 上跑。见 `CLOUD_DEPLOY.md`。

## 第一版原则

- 固定 10 个高质量信息源。
- 每天只保留最多 5 条候选，不足时用近 7 天内容补位。
- 每天最多沉淀 1-2 条知识卡片。
- 每条进入知识库的笔记必须有你的判断。

## 注意

第一版优先使用 RSS / Blog，因为它们稳定、可自动化。X/Twitter、没有公开 RSS 的人物主页、Newsletter 可以作为人工 Review 的补充源，后续再接入更稳的抓取方式。

## Claude 同步

Claude 同步脚本会读取当天的 `AI-Career/00-Daily/YYYY-MM-DD AI 转行日记.md`，调用 Claude 生成复盘，然后写入 `AI-Career/90-Claude-Sync/`。

```bash
ANTHROPIC_API_KEY="你的 Anthropic API Key" \
python3 claude_sync.py --date 2026-06-09
```
