#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_daily import send_feishu


DEFAULT_TIMEZONE = "Asia/Shanghai"
FISH_AUDIO_TTS_URL = "https://api.fish.audio/v1/tts"
HOST_A_VOICE_ID = "bc9e47fd83a04010ad6617ed54b92ee3"
HOST_B_VOICE_ID = "5c353fdb312f4888836a9a5680099ef0"


@dataclass
class DailyItem:
    title: str
    source: str = ""
    status: str = ""
    link: str = ""
    focus: str = ""
    summary: str = ""
    why: str = ""
    judgment: str = ""
    keep: str = ""


def today_string(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d")


def find_daily_file(input_dir: Path, date: str) -> Path:
    exact = input_dir / f"{date} AI 日课.md"
    if exact.exists():
        return exact
    matches = sorted(input_dir.glob(f"{date}*AI 日课*.md"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"没有找到当天 AI 日课文件: {exact}")


def strip_markdown(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = value.replace("**", "").replace("`", "")
    return value.strip()


def parse_items(markdown: str) -> list[DailyItem]:
    blocks = re.split(r"\n###\s+\d+\.\s+", markdown)
    items: list[DailyItem] = []
    for block in blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        item = DailyItem(title=strip_markdown(lines[0]))
        for line in lines[1:]:
            if not line.startswith("- "):
                continue
            key, _, value = line[2:].partition("：")
            value = strip_markdown(value)
            if key == "来源":
                item.source = value
            elif key == "状态":
                item.status = value
            elif key == "链接":
                item.link = value
            elif key == "关注点":
                item.focus = value
            elif key == "一句话摘要":
                item.summary = value
            elif key == "为什么值得看":
                item.why = value
            elif key == "我的判断":
                item.judgment = value
            elif key == "是否沉淀":
                item.keep = value
        items.append(item)
    return items


def short(value: str, limit: int = 90) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[:limit].rstrip() + "..."


def render_podcast(date: str, items: list[DailyItem], source_path: Path) -> str:
    if not items:
        return "\n".join(
            [
                f"# {date} AI 日课播客稿",
                "",
                "今天的 AI 日课没有抓到候选内容。",
                "",
                "可以把今天当成轻量复盘日：不用追热点，只回看最近一周有没有一个方向值得继续深挖。",
                "",
                f"原始日报：{source_path}",
                "",
            ]
        )

    lead_item = items[0]
    lines = [
        f"# {date} AI 日课播客稿",
        "",
        "## 开场",
        "",
        f"早上好。今天最值得听的主线是：{lead_item.title}。它不一定是最大的新闻，但最适合作为今天理解 AI 进展的入口。",
        "",
        "## 正文",
        "",
    ]

    transitions = [
        "先看第一条。",
        "第二条，我们换到另一个角度。",
        "第三条更适合放进工作流里理解。",
        "第四条，重点不是标题本身，而是它背后的趋势。",
        "最后一条，可以作为今天的补位阅读。",
    ]

    for index, item in enumerate(items, start=1):
        transition = transitions[index - 1] if index <= len(transitions) else f"第 {index} 条。"
        lines.extend(
            [
                f"{transition}",
                "",
                f"这条来自 {item.source or '原始信息源'}，标题是《{item.title}》。",
            ]
        )
        if item.summary:
            lines.append(f"简单说，{short(item.summary, 140)}")
        if item.why:
            lines.append(f"它值得看，是因为{short(item.why, 150)}")
        if item.judgment:
            lines.append(f"我的判断是：{short(item.judgment, 170)}")
        if item.keep:
            lines.append(f"沉淀建议：{item.keep}。")
        if item.link:
            lines.append(f"原文链接：{item.link}")
        lines.append("")

    lines.extend(
        [
            "## 给今天的行动建议",
            "",
            "今天不用追求把每条都读完。更适合做的一件事是：选一条最能连接你当前方向的内容，写下它对「汽车 PR Agent」的启发。比如它能不能帮助做竞品监测、卖点提炼、发布会内容生成，或者事实风险检查。",
            "",
            "如果只能留下一个问题，就是：这条 AI 进展能不能变成一个真实 PR 工作流里的小功能？能，就继续拆；不能，就只当信息流经过。",
            "",
            "## 来源",
            "",
            f"- 原始日报：{source_path}",
            "",
        ]
    )
    return "\n".join(lines)


def render_dialogue(date: str, items: list[DailyItem]) -> list[dict[str, str]]:
    if not items:
        return [
            {
                "speaker": "A",
                "text": "欢迎来到轻舟 AI 日课。今天没有抓到新的候选内容，我们把它当成一个轻量复盘日。",
            },
            {
                "speaker": "B",
                "text": "不用硬追热点。今天更适合回看最近一周，挑一个真正能连接汽车 PR Agent 或 AI 产品转型的方向继续深挖。",
            },
        ]

    dialogue: list[dict[str, str]] = [
        {
            "speaker": "A",
            "text": f"欢迎来到轻舟 AI 日课。今天是 {date}。我们不做新闻播报，换成两个声音来拆今天最值得听的 AI 线索。",
        },
        {
            "speaker": "B",
            "text": f"今天的主线可以从这条开始：{items[0].title}。它不一定是最大的新闻，但适合作为今天理解 AI 进展的入口。",
        },
    ]

    for index, item in enumerate(items[:5], start=1):
        dialogue.append(
            {
                "speaker": "A",
                "text": f"第 {index} 条，来自 {item.source or '原始信息源'}：《{item.title}》。这条为什么值得听？",
            }
        )
        parts = []
        if item.summary:
            parts.append(f"简单说，{short(item.summary, 120)}")
        if item.why:
            parts.append(short(item.why, 120))
        if item.judgment:
            parts.append(f"我的判断是：{short(item.judgment, 140)}")
        if item.keep:
            parts.append(f"沉淀建议是：{item.keep}。")
        dialogue.append(
            {
                "speaker": "B",
                "text": "".join(parts) if parts else "这条目前信息还比较少，先低成本浏览，不急着沉淀。",
            }
        )

    dialogue.extend(
        [
            {
                "speaker": "A",
                "text": "如果今天只做一个动作，你会建议做什么？",
            },
            {
                "speaker": "B",
                "text": "选一条最能连接你当前方向的内容，写下它对汽车 PR Agent 的启发。比如它能不能帮助做竞品监测、卖点提炼、发布会内容生成，或者事实风险检查。",
            },
            {
                "speaker": "A",
                "text": "好，今天的轻舟 AI 日课就到这里。不要急着翻山，先把下一步划出去。",
            },
        ]
    )
    return dialogue


def fish_tts(text: str, voice_id: str, api_key: str) -> bytes:
    payload = json.dumps(
        {
            "text": text,
            "reference_id": voice_id,
            "format": "mp3",
            "mp3_bitrate": 128,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        FISH_AUDIO_TTS_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Fish Audio TTS failed: HTTP {exc.code}: {detail}") from exc


def stitch_mp3(chunks: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("ffmpeg"):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as file:
            concat_path = Path(file.name)
            for chunk in chunks:
                escaped = str(chunk).replace("'", "'\\''")
                file.write(f"file '{escaped}'\n")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-c", "copy", str(output_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        finally:
            concat_path.unlink(missing_ok=True)

    with output_path.open("wb") as output:
        for chunk in chunks:
            output.write(chunk.read_bytes())


def generate_audio(dialogue: list[dict[str, str]], output_path: Path, api_key: str) -> Path:
    voice_map = {
        "A": os.environ.get("FISH_HOST_A_VOICE_ID", HOST_A_VOICE_ID),
        "B": os.environ.get("FISH_HOST_B_VOICE_ID", HOST_B_VOICE_ID),
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        chunks: list[Path] = []
        for index, segment in enumerate(dialogue, start=1):
            speaker = segment.get("speaker", "A")
            text = segment.get("text", "").strip()
            if not text:
                continue
            audio = fish_tts(text, voice_map.get(speaker, voice_map["A"]), api_key)
            chunk_path = Path(tmp_dir) / f"chunk_{index:04d}.mp3"
            chunk_path.write_bytes(audio)
            chunks.append(chunk_path)
        if not chunks:
            raise RuntimeError("Fish Audio did not generate any audio chunks.")
        stitch_mp3(chunks, output_path)
    return output_path


def github_file_url(path: Path) -> str:
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        return ""
    encoded = urllib.parse.quote(path.as_posix())
    return f"https://github.com/{repository}/blob/main/{encoded}"


def render_feishu_text(date: str, output_path: Path, items: list[DailyItem], audio_path: Path | None = None) -> str:
    top_items = items[:3]
    lines = [
        f"AI 日课播客版 - {date}",
        "",
        "今天的 3 个听点：",
    ]
    if top_items:
        for index, item in enumerate(top_items, start=1):
            lines.append(f"{index}. {item.title}")
    else:
        lines.append("今天没有抓到候选内容，适合做轻量复盘。")
    lines.extend(
        [
            "",
            f"播客稿：{output_path}",
        ]
    )
    if audio_path:
        audio_url = github_file_url(audio_path)
        lines.append(f"音频文件：{audio_url or audio_path}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a listenable podcast script from AI daily Markdown.")
    parser.add_argument("--input-dir", default="AI-Daily", help="Directory containing daily Markdown files")
    parser.add_argument("--output-dir", default="AI-Daily/Podcast", help="Directory for podcast Markdown files")
    parser.add_argument("--date", help="Date in YYYY-MM-DD; defaults to today in Asia/Shanghai")
    parser.add_argument("--timezone", default=os.environ.get("AI_DAILY_TIMEZONE", DEFAULT_TIMEZONE))
    parser.add_argument("--send-feishu", action="store_true", help="Send a Feishu message after generating the script")
    parser.add_argument("--feishu-webhook", default=os.environ.get("FEISHU_WEBHOOK_URL"), help="Feishu bot webhook URL, or set FEISHU_WEBHOOK_URL")
    parser.add_argument("--audio", choices=["auto", "always", "never"], default="auto", help="Generate MP3 with Fish Audio")
    parser.add_argument("--audio-dir", default="AI-Daily/Podcast/Audio", help="Directory for generated MP3 files")
    args = parser.parse_args()

    date = args.date or today_string(args.timezone)
    input_dir = Path(args.input_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    source_path = find_daily_file(input_dir, date)
    markdown = source_path.read_text(encoding="utf-8")
    items = parse_items(markdown)
    podcast = render_podcast(date, items, source_path)
    dialogue = render_dialogue(date, items)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date} AI 日课播客稿.md"
    output_path.write_text(podcast, encoding="utf-8")
    dialogue_path = output_dir / f"{date} AI 日课双人对谈.json"
    dialogue_path.write_text(json.dumps(dialogue, ensure_ascii=False, indent=2), encoding="utf-8")

    audio_path: Path | None = None
    fish_api_key = os.environ.get("FISH_API_KEY")
    should_generate_audio = args.audio == "always" or (args.audio == "auto" and bool(fish_api_key))
    if should_generate_audio:
        if not fish_api_key:
            raise SystemExit("error: --audio always requires FISH_API_KEY")
        audio_dir = Path(args.audio_dir).expanduser()
        audio_path = audio_dir / f"{date} AI 日课双人播客.mp3"
        generate_audio(dialogue, audio_path, fish_api_key)

    if args.send_feishu:
        if not args.feishu_webhook:
            raise SystemExit("error: --send-feishu requires --feishu-webhook or FEISHU_WEBHOOK_URL")
        send_feishu(args.feishu_webhook, render_feishu_text(date, output_path, items, audio_path))

    print(audio_path or output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
