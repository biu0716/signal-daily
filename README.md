# 今日信号 Signal Daily

把每天的 AI 信息流，筛成一份中文简报和双人对谈播客稿。

默认不需要 API Key，不需要飞书，不需要 TTS。Fork 后点一次 GitHub Actions，就能在仓库里生成 Markdown 文件。

## 它会做什么

- 从 `sources.json` 里的 RSS / Blog 信息源抓取最近内容。
- 每天筛选最多 5 条候选信息。
- 生成 `AI-Daily/YYYY-MM-DD AI 日课.md`。
- 生成 `AI-Daily/Podcast/YYYY-MM-DD AI 日课播客稿.md`。
- 可选：推送文字到飞书。
- 可选：用 Fish Audio 生成双人 MP3，并通过飞书应用机器人发送可播放音频。

## 最快开始：零配置本地运行

```bash
git clone <your-repo-url>
cd ai-daily
python3 ai_daily.py --dry-run
```

确认预览正常后，生成 Markdown 文件：

```bash
python3 ai_daily.py
```

默认输出到：

```text
AI-Daily/YYYY-MM-DD AI 日课.md
```

生成当天播客稿：

```bash
python3 podcast_daily.py --audio never
```

默认输出到：

```text
AI-Daily/Podcast/YYYY-MM-DD AI 日课播客稿.md
```

## 最快开始：零配置 GitHub Actions

1. Fork 这个仓库。
2. 打开你的仓库 `Actions` 页面。
3. 启用 workflow。
4. 选择 `今日信号 Signal Daily`。
5. 点击 `Run workflow`。
6. `mode` 选择 `all`。
7. `audio` 保持 `never`。

运行完成后，仓库会自动出现：

```text
AI-Daily/YYYY-MM-DD AI 日课.md
AI-Daily/Podcast/YYYY-MM-DD AI 日课播客稿.md
```

定时任务默认按北京时间运行：

- 08:37 生成 AI 日课。
- 09:07 生成播客稿。

GitHub Actions 的定时任务可能会有几分钟延迟。

## 进阶：推送到飞书

只想收到文字推送，需要配置一个 GitHub Secret：

```text
FEISHU_WEBHOOK_URL
```

配置后，workflow 会自动把日报和播客稿摘要推送到飞书。没有这个 secret 时，项目只生成 Markdown，不会报错。

## 进阶：生成音频

生成 Fish Audio 双人 MP3，需要配置：

```text
FISH_API_KEY
```

手动运行 workflow 时，把 `audio` 从 `never` 改成 `auto` 或 `always`。

默认双人声音：

- Host A: `bc9e47fd83a04010ad6617ed54b92ee3`
- Host B: `5c353fdb312f4888836a9a5680099ef0`

可以用环境变量替换：

```text
FISH_HOST_A_VOICE_ID
FISH_HOST_B_VOICE_ID
```

Fish Audio 额度不足时，流程会降级为只生成文字稿，不会让整条 workflow 失败。

## 进阶：飞书可播放音频

如果希望群里直接出现可播放音频，还需要飞书应用机器人：

```text
FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_CHAT_NAME    # 可选，默认 AI日课群
FEISHU_CHAT_ID      # 可选，配置后可跳过群名查找
```

飞书应用机器人需要权限：

- `im:chat:readonly`
- `im:message:send_as_bot`
- `im:resource`

并且机器人需要加入目标群聊。

## 自定义信息源

编辑 `sources.json`：

```json
{
  "name": "Swyx",
  "focus": "AI engineer, developer ecosystem",
  "feeds": ["https://www.latent.space/feed"]
}
```

第一版优先支持 RSS / Atom。X、Newsletter、没有公开 RSS 的主页，建议先作为人工补充来源。

## 常用命令

本地预览日报：

```bash
python3 ai_daily.py --dry-run
```

生成日报：

```bash
python3 ai_daily.py
```

生成播客稿，不生成音频：

```bash
python3 podcast_daily.py --audio never
```

生成音频：

```bash
FISH_API_KEY="你的 Fish Audio API Key" python3 podcast_daily.py --audio always
```

推送文字到飞书：

```bash
FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/..." \
python3 ai_daily.py --send-feishu
```

## 项目文件

- `sources.json`：信息源和日报规则。
- `ai_daily.py`：抓取、筛选、生成日报。
- `podcast_daily.py`：把日报改写成中文双人播客稿，可选生成音频。
- `.github/workflows/ai-daily.yml`：GitHub Actions 定时任务。
- `CLOUD_DEPLOY.md`：GitHub Actions 部署说明。

## 说明

这是一个偏个人使用的开源小工具，不是完整新闻平台。它的目标不是覆盖所有 AI 新闻，而是每天帮你留出几条值得看的线索。
