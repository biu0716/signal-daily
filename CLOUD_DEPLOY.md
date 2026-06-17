# 免费云端部署：GitHub Actions

这个项目可以放到 GitHub Actions 上每天自动跑。电脑关机也不影响飞书推送。

## 会自动做什么

- 每天 08:37（北京时间）生成 `AI-Daily/YYYY-MM-DD AI 日课.md`，并推送飞书。
- 每天 09:07（北京时间）生成 `AI-Daily/Podcast/YYYY-MM-DD AI 日课播客稿.md`，并推送飞书。
- 如果配置了 Fish Audio API Key，还会生成 `AI-Daily/Podcast/Audio/YYYY-MM-DD AI 日课双人播客.mp3`，并在飞书里推送音频链接。
- 生成的 Markdown 会自动提交回 GitHub 仓库。

## 需要你手动做一次

1. 在 GitHub 新建一个私有仓库，比如 `ai-daily-mvp`。
2. 把这个目录里的文件上传到仓库：
   - `ai_daily.py`
   - `podcast_daily.py`
   - `sources.json`
   - `README.md`
   - `CLOUD_DEPLOY.md`
   - `.github/workflows/ai-daily.yml`
3. 进入仓库的 `Settings` -> `Secrets and variables` -> `Actions`。
4. 新增一个 Repository secret：
   - Name: `FEISHU_WEBHOOK_URL`
   - Secret: 你的飞书机器人 webhook 地址
5. 新增另一个 Repository secret：
   - Name: `FISH_API_KEY`
   - Secret: 你的 Fish Audio API Key
6. 打开 `.github/workflows/ai-daily.yml`，在 `env:` 里加一行：

```yaml
      FISH_API_KEY: ${{ secrets.FISH_API_KEY }}
```

最终 `env:` 应该类似这样：

```yaml
    env:
      AI_DAILY_TIMEZONE: Asia/Shanghai
      FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
      FISH_API_KEY: ${{ secrets.FISH_API_KEY }}
```

7. 进入仓库的 `Actions` 页面，启用 workflow。
8. 可选：手动点一次 `AI Daily` -> `Run workflow`，选择 `all`，确认飞书能收到消息。

## 注意

- GitHub Actions 的定时任务按 UTC 写，所以配置里 `37 0 * * *` 对应北京时间 08:37，`7 1 * * *` 对应北京时间 09:07。
- GitHub 官方免费额度对这个任务足够用。私有仓库在 GitHub Free 下每月有免费分钟数；这个脚本每天只跑几分钟。
- 当前 mp3 由 Fish Audio 生成，使用已经选好的两个中文双人声音。Fish Audio 额度不足时，音频生成会失败，需要补充 API credit 或等额度恢复。
- 不要把飞书 webhook 直接写进公开代码里，放到 GitHub Secrets 最稳。
