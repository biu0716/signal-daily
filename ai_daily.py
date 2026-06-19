#!/usr/bin/env python3
import argparse
import email.utils
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from hashlib import sha256
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_VAULT = Path("/Users/biu/Documents/Obsidian Vault")
CACHE_DIR = Path(".cache")
DEFAULT_TIMEZONE = "Asia/Shanghai"


@dataclass
class Item:
    title: str
    link: str
    source: str
    focus: str
    published: datetime | None
    summary: str


@dataclass
class ReviewedItem:
    item: Item
    score: int
    score_reason: str
    status: str
    why: str
    judgment: str
    keep: str


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def cache_path_for(url: str) -> Path:
    return CACHE_DIR / f"{sha256(url.encode('utf-8')).hexdigest()}.xml"


def fetch_url(url: str, timeout: int = 20) -> bytes:
    cache_path = cache_path_for(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ai-daily-mvp/0.1 (+local Obsidian briefing)"
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            CACHE_DIR.mkdir(exist_ok=True)
            cache_path.write_bytes(raw)
            return raw
    except Exception:
        # Some modern sites close TLS connections in ways urllib handles poorly.
        # curl is present on macOS and makes this MVP much more reliable locally.
        try:
            result = subprocess.run(
                ["curl", "-fsSL", "--max-time", str(timeout), url],
                check=True,
                capture_output=True,
            )
            CACHE_DIR.mkdir(exist_ok=True)
            cache_path.write_bytes(result.stdout)
            return result.stdout
        except Exception:
            if cache_path.exists():
                print(f"warning: using cached feed for {url}", file=sys.stderr)
                return cache_path.read_bytes()
            raise


def child_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def parse_feed(raw: bytes, source_name: str, focus: str) -> list[Item]:
    root = ET.fromstring(raw)
    items: list[Item] = []

    if root.tag.endswith("rss"):
        entries = root.findall("./channel/item")
        for entry in entries:
            title = child_text(entry, ["title"])
            link = child_text(entry, ["link"])
            published = parse_date(child_text(entry, ["pubDate"]))
            summary = strip_html(child_text(entry, ["description", "summary"]))
            if title and link:
                items.append(Item(title, link, source_name, focus, published, summary))
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)
    for entry in entries:
        title = child_text(entry, ["{http://www.w3.org/2005/Atom}title"])
        link_node = entry.find("{http://www.w3.org/2005/Atom}link")
        link = link_node.attrib.get("href", "") if link_node is not None else ""
        published = parse_date(
            child_text(
                entry,
                [
                    "{http://www.w3.org/2005/Atom}published",
                    "{http://www.w3.org/2005/Atom}updated",
                ],
            )
        )
        summary = strip_html(
            child_text(
                entry,
                [
                    "{http://www.w3.org/2005/Atom}summary",
                    "{http://www.w3.org/2005/Atom}content",
                ],
            )
        )
        if title and link:
            items.append(Item(title, link, source_name, focus, published, summary))
    return items


def score_item(item: Item, now: datetime) -> tuple[int, str]:
    score = 0
    reasons = []

    if item.published:
        age_hours = (now - item.published).total_seconds() / 3600
        if age_hours <= 24:
            score += 4
            reasons.append("24 小时内更新")
        elif age_hours <= 72:
            score += 2
            reasons.append("近期更新")
    else:
        score += 1
        reasons.append("发布时间未知")

    title = item.title.lower()
    summary = item.summary.lower()
    keywords = [
        "ai",
        "agent",
        "agents",
        "llm",
        "model",
        "openai",
        "anthropic",
        "deepmind",
        "safety",
        "alignment",
        "coding",
        "research",
        "benchmark",
        "inference",
        "training",
    ]
    hits = [word for word in keywords if word in title or word in summary]
    score += min(len(hits), 4)
    if hits:
        reasons.append("命中主题: " + ", ".join(hits[:4]))

    if item.summary:
        score += 1
        reasons.append("有摘要可读")

    return score, "；".join(reasons) if reasons else "按默认规则入选"


def summarize_locally(item: Item) -> str:
    if item.summary:
        return item.summary[:220] + ("..." if len(item.summary) > 220 else "")
    return "暂无摘要，建议打开原文判断。"


def review_item(item: Item, score: int, score_reason: str, status: str) -> ReviewedItem:
    text = f"{item.title} {item.summary}".lower()
    title = item.title.lower()

    if "benchmark" in text or "frontiercode" in text:
        why = "它不是又发布一个模型，而是在回答一个更实际的问题：AI 写的代码到底能不能用于真实项目。"
        judgment = "重点看它是不是只比答题分数，还是也会检查代码好不好维护、能不能用于真实项目。只有后者，才真正有参考价值。"
        keep = "待复核后大概率沉淀"
    elif "gemma" in text or "multimodal" in text:
        why = "它可能让看图、读文字这类 AI 功能运行得更便宜，也更容易放到自己的产品里。"
        judgment = "先看三个问题：效果有没有变好、运行成本有没有下降、使用限制多不多。说不清这三点，就暂时不用投入太多时间。"
        keep = "待复核"
    elif "robot" in text or "robotics" in text:
        why = "机器人能检验 AI 是否真的会理解环境并完成动作，而不只是会在屏幕里回答问题。"
        judgment = "先判断它讲的是公司合作新闻，还是机器人能力真的有了进步。前者知道即可，后者才值得仔细读。"
        keep = "默认不沉淀"
    elif "agent" in text or "agents" in text:
        why = "Agent 的概念很多，但真正有用的是具体做法：它完成了什么任务，哪里容易失败，能不能重复使用。"
        judgment = "不要只看它说得多宏大。重点找真实案例：解决了什么任务、哪一步仍会失败、能不能放进现有工作流程。"
        keep = "待复核"
    elif "safety" in text or "alignment" in text:
        why = "安全规则会直接决定哪些模型能力能开放、产品能怎么用，也可能影响之后的监管要求。"
        judgment = "先分清它带来了新证据，还是公司在表达立场。对实际产品和监管有影响的证据，更值得关注。"
        keep = "待复核"
    elif "model" in text or "llm" in text:
        why = "新模型只有在效果、速度或价格上带来实际变化，才可能影响我们现在使用的工具。"
        judgment = "别急着被排行榜吸引。先看它能不能让你现在的任务做得更好、更快或更便宜；如果不能，知道发布了就够了。"
        keep = "待复核"
    else:
        why = "它来自长期关注的信息源，但只看标题还无法判断价值，需要快速确认正文有没有新东西。"
        judgment = "目前的信息还不够。打开原文时，只需要找一个明确的新观点、数据或可复用方法；如果没有，就不用继续花时间。"
        keep = "默认不沉淀"

    if status == "补位阅读" and keep == "待复核后大概率沉淀":
        keep = "待复核"

    if score <= 5 and keep != "默认不沉淀":
        keep = "待复核"

    return ReviewedItem(item, score, score_reason, status, why, judgment, keep)


def render_markdown(items: list[ReviewedItem], rules: dict, now: datetime, local_tz: ZoneInfo) -> str:
    date = now.astimezone(local_tz).strftime("%Y-%m-%d")
    lines = [
        f"# AI 日课 - {date}",
        "",
        "## 今日 5 条候选",
        "",
    ]

    if not items:
        lines.extend(
            [
                "今天没有从 RSS / Blog 源里抓到最近内容。",
                "",
                "可以在人工 Review 时补看 X/Twitter、YouTube 或 Newsletter。",
                "",
            ]
        )
    else:
        for index, item in enumerate(items, start=1):
            raw = item.item
            published = (
                raw.published.astimezone(local_tz).strftime("%Y-%m-%d %H:%M")
                if raw.published
                else "未知"
            )
            lines.extend(
                [
                    f"### {index}. {raw.title}",
                    f"- 来源：{raw.source}",
                    f"- 状态：{item.status}",
                    f"- 发布时间：{published}",
                    f"- 链接：{raw.link}",
                    f"- 关注点：{raw.focus}",
                    f"- 一句话摘要：{summarize_locally(raw)}",
                    f"- 为什么值得看：{item.why}",
                    f"- 我的判断：{item.judgment}",
                    f"- 入选理由：{item.score_reason}",
                ]
            )
            if item.keep != "默认不沉淀":
                lines.append(f"- 是否沉淀：{item.keep}")
            lines.append("")

    lines.extend(
        [
            "## 今日沉淀",
            "",
            f"> 规则：每天最多沉淀 {rules.get('max_deep_notes_per_day', 2)} 条。没有自己的判断，就先不要进知识库。",
            "",
            "### 知识卡片 1",
            "- 主题：",
            "- 原始材料：",
            "- 我的观点：",
            "- 可关联笔记：",
            "- 后续问题：",
            "",
            "## 人工 Review",
            "- 删除不值得的：",
            "- 值得深入读的：",
            "- 今天真正学到的东西：",
            "",
        ]
    )
    return "\n".join(lines)


def render_feishu_text(items: list[ReviewedItem], output_path: Path | None, now: datetime, local_tz: ZoneInfo) -> str:
    date = now.astimezone(local_tz).strftime("%Y-%m-%d")
    lines = [f"AI 日课 - {date}", ""]
    if output_path:
        lines.extend([f"Obsidian: {output_path}", ""])

    if not items:
        lines.append("今天没有抓到候选内容。")
        return "\n".join(lines)

    for index, reviewed in enumerate(items, start=1):
        item = reviewed.item
        lines.extend(
            [
                f"{index}. {item.title}",
                f"来源: {item.source} / {reviewed.status}",
                f"链接: {item.link}",
                f"判断: {reviewed.judgment}",
            ]
        )
        if reviewed.keep != "默认不沉淀":
            lines.append(f"沉淀建议: {reviewed.keep}")
        lines.append("")
    return "\n".join(lines).strip()


def send_feishu(webhook_url: str, text: str) -> None:
    payload = json.dumps(
        {
            "msg_type": "text",
            "content": {
                "text": text,
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Feishu webhook failed: HTTP {exc.code}: {detail}") from exc


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def collect_items(config: dict, now: datetime) -> list[tuple[int, Item, str]]:
    cutoff = now - timedelta(hours=config["daily_rules"].get("lookback_hours", 24))
    fallback_days = config["daily_rules"].get("fallback_lookback_days", 7)
    fallback_cutoff = now - timedelta(days=fallback_days)
    collected: list[tuple[int, Item, str]] = []
    fallback: list[tuple[int, Item, str]] = []
    seen_links: set[str] = set()

    for source in config["sources"]:
        for feed in source.get("feeds", []):
            try:
                raw = fetch_url(feed)
                items = parse_feed(raw, source["name"], source["focus"])
            except Exception as exc:
                print(f"warning: failed to fetch {feed}: {exc}", file=sys.stderr)
                continue

            for item in items:
                if item.link in seen_links:
                    continue
                if not item.published:
                    continue
                if item.published < fallback_cutoff:
                    continue
                seen_links.add(item.link)
                score, reason = score_item(item, now)
                if item.published >= cutoff:
                    collected.append((score, item, reason))
                else:
                    fallback.append((score, item, f"补位阅读；{reason}"))

    collected.sort(key=lambda row: (row[0], row[1].published or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    fallback.sort(key=lambda row: (row[0], row[1].published or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    max_items = config["daily_rules"].get("max_items", 5)
    if len(collected) >= max_items:
        return [(score, item, f"今日更新；{reason}") for score, item, reason in collected]
    needed = max_items - len(collected)
    today = [(score, item, f"今日更新；{reason}") for score, item, reason in collected]
    return today + fallback[:needed]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an Obsidian AI daily briefing.")
    parser.add_argument("--config", default="sources.json", help="Path to sources.json")
    parser.add_argument("--output-dir", default=str(DEFAULT_VAULT / "AI-Daily"), help="Directory for generated Markdown")
    parser.add_argument("--dry-run", action="store_true", help="Print Markdown instead of writing it")
    parser.add_argument("--send-feishu", action="store_true", help="Send a Feishu message after generating the briefing")
    parser.add_argument("--feishu-webhook", default=os.environ.get("FEISHU_WEBHOOK_URL"), help="Feishu bot webhook URL, or set FEISHU_WEBHOOK_URL")
    parser.add_argument("--timezone", default=os.environ.get("AI_DAILY_TIMEZONE", DEFAULT_TIMEZONE), help="Timezone for output dates, default: Asia/Shanghai")
    args = parser.parse_args()

    config_path = Path(args.config)
    output_dir = Path(args.output_dir).expanduser()
    now = datetime.now(timezone.utc)
    local_tz = ZoneInfo(args.timezone)
    config = load_config(config_path)
    ranked = collect_items(config, now)
    max_items = config["daily_rules"].get("max_items", 5)
    items = [
        review_item(
            item,
            score,
            reason,
            "补位阅读" if reason.startswith("补位阅读") else "今日更新",
        )
        for score, item, reason in ranked[:max_items]
    ]
    markdown = render_markdown(items, config["daily_rules"], now, local_tz)

    if args.dry_run:
        print(markdown)
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{now.astimezone(local_tz).strftime('%Y-%m-%d')} AI 日课.md"
    output_path.write_text(markdown, encoding="utf-8")

    if args.send_feishu:
        if not args.feishu_webhook:
            raise SystemExit("error: --send-feishu requires --feishu-webhook or FEISHU_WEBHOOK_URL")
        send_feishu(args.feishu_webhook, render_feishu_text(items, output_path, now, local_tz))

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
