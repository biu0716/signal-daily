#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


DEFAULT_VAULT = Path("/Users/biu/Documents/Obsidian Vault")
DEFAULT_MODEL = "claude-sonnet-4-20250514"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_prompt(daily_note: str) -> str:
    return f"""请你作为我的 AI 行业转型教练和产品项目顾问，基于我今天的 Obsidian 记录，帮我做一次复盘。

我的背景：
- 我正在找工作，目标是转到 AI 行业。
- 我正在设计一个「乙方模拟器」交互小游戏，想把它作为作品集的一部分。
- 我希望你同时关注：求职叙事、作品集推进、产品判断、AI 行业匹配度。

请用中文输出，结构固定为：

## 今日判断
- 最值得肯定的进展：
- 最大风险：
- 明天最小但关键的一步：

## 乙方模拟器建议
- 产品方向：
- 交互/玩法：
- 作品集表达：

## 求职建议
- 可以强化的能力标签：
- 可以投递的岗位方向：
- 面试官可能追问的 3 个问题：

## 小红书/零散想法处理
- 值得沉淀的素材：
- 暂时不要花时间的素材：

## 给明天的 3 个任务
- [ ] 
- [ ] 
- [ ] 

下面是今天的记录：

---

{daily_note}
"""


def call_claude(api_key: str, prompt: str, model: str) -> str:
    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 1600,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Claude API failed: HTTP {exc.code}: {detail}") from exc

    blocks = data.get("content", [])
    texts = [block.get("text", "") for block in blocks if block.get("type") == "text"]
    return "\n".join(texts).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync today's AI career note to Claude.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Obsidian vault path")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Date in YYYY-MM-DD")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Claude model")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt without calling Claude")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    vault = Path(args.vault).expanduser()
    daily_path = vault / "AI-Career" / "00-Daily" / f"{args.date} AI 转行日记.md"
    output_path = vault / "AI-Career" / "90-Claude-Sync" / f"{args.date} Claude 复盘.md"
    package_path = vault / "AI-Career" / "90-Claude-Sync" / f"{args.date} Claude 同步包.md"

    if not daily_path.exists():
        raise SystemExit(f"error: daily note not found: {daily_path}")

    prompt = build_prompt(read_text(daily_path))
    if args.dry_run:
        print(prompt)
        return 0

    if not api_key:
        write_text(package_path, f"# Claude 同步包 - {args.date}\n\n```text\n{prompt}\n```\n")
        raise SystemExit("error: ANTHROPIC_API_KEY is required")

    try:
        response = call_claude(api_key, prompt, args.model)
    except Exception:
        write_text(package_path, f"# Claude 同步包 - {args.date}\n\n```text\n{prompt}\n```\n")
        raise
    write_text(output_path, f"# Claude 复盘 - {args.date}\n\n{response}\n")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
