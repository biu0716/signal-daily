#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
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
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


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
            elif key in {"是否沉淀", "后续处理"}:
                item.keep = value
        items.append(item)
    return items


def short(value: str, limit: int = 90) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[:limit].rstrip() + "..."


def clean_spoken_text(value: str) -> str:
    value = strip_markdown(value)
    value = re.sub(
        r"^(?:简单说|一句话摘要|我的判断(?:是)?|我的初判(?:是)?|初步判断|判断)[：:，,\s]*",
        "",
        value,
    )
    value = re.sub(r"我的初判(?:是)?[：:]\s*", "", value)
    value = value.replace("先低成本浏览", "先快速看一遍")
    value = value.replace("值得沉淀", "值得长期保存")
    value = value.replace("进入知识卡片", "长期保存")
    value = value.replace("Review 候选", "候选内容")
    value = value.replace("可验证的能力变化", "能够实际验证的提升")
    value = value.replace("工作流", "日常工作")
    return value.strip()


def contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def translate_to_chinese(value: str) -> str:
    value = clean_spoken_text(value)
    if not value or contains_chinese(value):
        return value
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "auto",
            "tl": "zh-CN",
            "dt": "t",
            "q": value,
        }
    )
    request = urllib.request.Request(
        f"https://translate.googleapis.com/translate_a/single?{query}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
        translated = "".join(part[0] for part in result[0] if part and part[0])
        return translated.strip() or value
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def chinese_title(item: DailyItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    if "anjney midha" in text or "outputmaxxing" in text:
        return "投资人 Anjney Midha：如何押中多家 AI 公司"
    if "midjourney medical" in text or ("scan" in text and "organs" in text):
        return "Midjourney 进入医疗领域：让器官扫描像称体重一样简单"
    if "glm-5.2" in text:
        return "GLM-5.2 发布，主打前端编程能力"
    if "securing the future of ai agents" in text:
        return "怎样让 AI Agent 更安全"
    if "self-driving lab" in text or "radical ai" in text:
        return "AI 自动实验室：真正的优势可能不在模型"
    return translate_to_chinese(item.title) or ""


def explain_news(item: DailyItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    if "anjney midha" in text or "outputmaxxing" in text:
        return (
            "这是一篇对投资人 Anjney Midha 的近一小时访谈。真正值得听的是他对算力利用率的判断。"
            "他认为 AI 行业现在太关注买多少 GPU，却忽略了 GPU 到底有没有被充分利用。"
            "一些大型训练集群的实际算力利用率可能很低，而做得好的团队可以达到六成到七成。"
            "他创办的 AMP 想把不同数据中心的算力连接成一张“算力电网”，根据任务的重要程度动态分配资源，减少昂贵算力闲置。"
            "访谈还谈到数据中心耗电、当地社区反对，以及 Anthropic 为什么很早就把编程能力列为核心方向。"
        )
    if "midjourney medical" in text or ("scan" in text and "organs" in text):
        return (
            "Midjourney 展示了一台全身超声扫描原型机。它不用 X 光辐射，也不用 MRI 的强磁场，"
            "设备会从身体周围多个方向采集超声数据，再重建身体内部图像。"
            "目前设备仍是第一代原型，只扫描过大约十几个人，一次扫描可能需要二十分钟。"
            "团队希望以后把时间压缩到一分钟左右，并在旧金山开一家带扫描设备的健康中心。"
            "但它还没有完成医疗验证，也不能把宣传中的精度和未来用途当成已经实现的能力。"
        )
    if "glm-5.2" in text:
        return (
            "智谱发布了开放权重模型 GLM-5.2，重点提升编程、长任务和 Agent 能力。"
            "它支持一百万 token 的上下文，API 价格与上一代相同，并采用 MIT 许可证。"
            "在部分第三方榜单里，它的前端代码能力进入第一梯队，甚至超过一些 Claude Opus 版本；"
            "但普通文本能力并没有同步达到顶尖，而且真实项目中的长时间稳定性仍需要更多测试。"
            "技术上，它用 IndexShare 降低超长上下文的计算成本，也改进了多 token 预测来提高输出速度。"
        )
    if "securing the future of ai agents" in text or "control roadmap" in text:
        return (
            "DeepMind 发布了一套 AI Agent 安全路线图。它的出发点是：即使模型平时表现正常，"
            "也要把能够访问内部系统的 Agent 当作可能出错的内部人员来管理。"
            "具体做法包括限制权限、在沙箱中运行、抵御提示词注入，并让另一个可信系统持续检查 Agent 的计划和操作。"
            "低风险错误可以事后复盘，高风险操作则必须在执行前实时拦截。"
            "DeepMind 已用这套思路分析约一百万次编程 Agent 任务，发现很多危险行为并非恶意，而是 Agent 误解需求或过度积极。"
        )
    if "self-driving lab" in text or "radical ai" in text:
        return (
            "Radical AI 建了一套“自动驾驶实验室”：AI 先提出材料配方，机器人负责合成和测试，"
            "实验结果再反馈给 AI，形成不断迭代的闭环。"
            "他们在六个月内制造并测试了约一千二百种合金，比传统项目快接近十倍；"
            "另一轮实验测试了三百种新材料，其中十种表现出新的领先性能。"
            "创始人 Joseph Krause 的核心观点是，材料领域没有模型一次就能给出正确答案，"
            "真正的护城河是实验设备、真实数据，以及把失败结果继续用于下一轮实验的能力。"
        )
    translated = translate_to_chinese(item.summary)
    translated = translated.rstrip("。.!！ ")
    return translated or "目前公开摘要信息很少，只能先确认主题，不能据此下结论。"


def explain_relevance(item: DailyItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    if any(word in text for word in ["investor", "anthropic", "mistral", "black forest labs", "fund"]):
        return (
            "这条对你有用的地方在于一个产品判断：资源多不等于产出高，"
            "真正拉开差距的是能否把算力、数据、团队和任务调度成一个高效系统。"
            "放到 PR Agent 上也一样，接入更强模型只是第一步，资料是否结构化、流程是否顺畅、结果是否能校验，才决定产品是否真的好用。"
        )
    if any(word in text for word in ["medical", "organ", "health", "diagnosis"]):
        return (
            "它展示了一个很典型的 AI 产品思路：把模型、硬件、数据、空间体验和长期服务组合成完整产品。"
            "对做垂直 Agent 的启发是，专业能力必须嵌入真实场景；同时医疗宣传风险很高，原型、目标和已验证能力必须严格区分。"
        )
    if any(word in text for word in ["coding", "frontend", "code", "glm"]):
        return (
            "如果你继续做 Herlife 或 PR Agent，可以把它当成一个候选开发模型，重点测试三个真实任务："
            "能不能一次改对页面、能不能理解较长项目上下文、连续工作时会不会越改越乱。"
            "只有这些测试稳定，榜单成绩才有意义；开放权重和较低价格则可能降低以后部署产品的成本。"
        )
    if any(word in text for word in ["security", "securing", "control roadmap", "safeguard", "monitoring"]):
        return (
            "这和 PR Agent 非常直接。未来它可能读取未发布车型资料、客户文件和传播计划，还可能自动生成或发送内容。"
            "因此产品至少要有最小权限、敏感信息识别、发送前人工确认、操作日志和异常阻断。"
            "不能只要求模型“听话”，还要假设它会误解指令，并在系统层准备刹车。"
        )
    if any(word in text for word in ["self-driving lab", "materials", "radical ai", "experiment"]):
        return (
            "这是最值得迁移到垂直 Agent 的一条经验：护城河往往来自持续获得行业反馈的闭环。"
            "汽车 PR Agent 也应该让每次任务产生反馈，例如哪些卖点被客户删掉、哪些事实经常出错、哪种品牌语气被接受，"
            "再把这些结果反哺资料库和规则。长期积累下来的真实修改记录，会比单纯换一个更强模型更难复制。"
        )
    if "agent" in text:
        return "对你来说，重点放在三件事：它能否完成真实任务，哪里会失败，是否能安全接入现有工作流程。"
        
    return "判断它的价值，看有没有新的事实、方法或案例。只有人物故事或宣传观点的话，知道发生了什么就够了。"


def dialogue_exchanges(item: DailyItem) -> list[tuple[str, str]]:
    text = f"{item.title} {item.summary}".lower()
    if "anjney midha" in text or "outputmaxxing" in text:
        return [
            (
                "先别讲他的履历。这篇访谈里，最值得记住的观点是什么？",
                "他认为 AI 行业太关注买了多少 GPU，却很少追问这些 GPU 有没有真正干活。资源规模很显眼，但资源利用率更能决定一家公司的实际产出。",
            ),
            (
                "GPU 买来不就是用的吗？为什么还会大量闲置？",
                "因为不同任务的优先级、机器位置和运行时间都不一样，调度不好就会互相等待。有些大型训练集群的实际利用率可能很低，而做得好的团队可以把利用率提高到六成到七成。",
            ),
            (
                "那他创办的 AMP 到底想解决什么？",
                "AMP 想把分散在不同数据中心的算力连接成一张“算力电网”。系统根据任务的重要程度动态分配 GPU，让紧急训练先跑，也减少昂贵设备空转。",
            ),
            (
                "这和做 PR Agent 有什么关系？我们又没有数据中心。",
                "逻辑是一样的：接入强模型不代表产品就好用。资料是否结构化、任务怎样分配、结果能否校验，才决定产出质量。PR Agent 的优势应该来自完整流程，而不只是模型名字。",
            ),
        ]
    if "midjourney medical" in text or ("scan" in text and "organs" in text):
        return [
            (
                "Midjourney 以前主要做图，为什么现在开始做医疗扫描？",
                "它展示了一台全身超声扫描原型机，希望把器官检查做成更日常的服务。设备从身体周围多个方向采集超声数据，再重建身体内部图像。",
            ),
            (
                "它和医院里的 MRI、CT 有什么不同？",
                "它不用 X 光辐射，也不用 MRI 的强磁场，理论上更容易做成高频检查。但这不代表它已经能替代医院设备，两者解决的问题和验证标准并不相同。",
            ),
            (
                "现在已经能用了吗？",
                "还很早。第一代原型只扫描过大约十几个人，一次可能需要二十分钟。团队希望以后压缩到一分钟左右，但精度、适用范围和医疗认证都还需要验证。",
            ),
            (
                "这件事对做垂直 Agent 有什么启发？",
                "专业产品不能只交付一个模型，还要把硬件、数据、服务流程和用户体验组合起来。同时要严格区分“已经验证的能力”和“未来目标”，尤其是在医疗、汽车这类高风险传播中。",
            ),
        ]
    if "glm-5.2" in text:
        return [
            (
                "GLM-5.2 又是一个新模型。它这次主要强在哪里？",
                "它重点提升编程、长任务和 Agent 能力，支持一百万 token 的上下文，采用 MIT 许可证，而且 API 价格与上一代相同。",
            ),
            (
                "网上说它前端编程排名很高，这能说明它真的好用吗？",
                "只能说明它值得测试，不能直接下结论。部分第三方榜单里它进入第一梯队，但普通文本能力没有同步达到顶尖，长时间改项目时是否稳定也还需要验证。",
            ),
            (
                "它提到的 IndexShare 是什么？",
                "可以把它理解成一种降低超长文本计算成本的方法。模型读很长的代码仓库时，不必让每一层都重复做同样昂贵的索引工作，因此有机会跑得更快、更省资源。",
            ),
            (
                "那我们该怎么判断要不要用它？",
                "拿 Herlife 或 PR Agent 做真实测试：让它修改页面、理解多个文件、连续完成几轮任务。看它是否一次改对、会不会越改越乱，再比较速度和价格，别只看排行榜。",
            ),
        ]
    if "securing the future of ai agents" in text or "control roadmap" in text:
        return [
            (
                "DeepMind 为什么现在专门谈 Agent 安全？",
                "因为 Agent 不只是回答问题，它可能读取文件、调用工具甚至执行操作。一旦误解指令，影响就会从“答错一句话”升级成真的改错或泄露数据。",
            ),
            (
                "它提出的解决办法是什么？",
                "第一层是传统控制，比如最小权限、沙箱和提示词注入防护。第二层是让另一个可信系统持续检查 Agent 的计划和操作，相当于给它配一个监督员。",
            ),
            (
                "是不是只要发现异常，再事后复盘就行？",
                "要看风险。低风险行为可以事后分析，高风险操作必须在执行前拦截。DeepMind 分析大量编程 Agent 任务后发现，危险行为很多不是恶意，而是 Agent 误解需求后过度积极。",
            ),
            (
                "放到汽车 PR Agent，最少要做哪些防护？",
                "至少要限制它能读什么资料，识别未发布车型和客户敏感信息，所有外发内容必须人工确认，还要保留操作日志。系统设计时就要假设它会误解指令，而不是只相信模型会听话。",
            ),
        ]
    if "self-driving lab" in text or "radical ai" in text:
        return [
            (
                "“自动驾驶实验室”听起来像汽车，其实它到底是什么？",
                "这里说的是实验室自动化。AI 提出材料配方，机器人完成合成和测试，结果再反馈给 AI，接着设计下一轮实验。",
            ),
            (
                "这种自动循环真的比人工研究快很多吗？",
                "他们称六个月内制造并测试了约一千二百种合金，速度接近传统项目的十倍。另一轮测试了三百种新材料，其中十种表现出新的领先性能。",
            ),
            (
                "既然用了 AI，为什么创始人更强调实验室闭环？",
                "因为材料实验没有模型能一次给出正确答案。真正难复制的是实验设备、持续产生的真实数据，以及把失败结果继续用于下一轮实验的闭环。",
            ),
            (
                "这对 PR Agent 有什么最直接的启发？",
                "每次任务都应该留下反馈：哪些卖点被客户删除、哪些事实经常出错、什么语气更符合品牌。把这些修改记录反哺资料库和规则，长期形成的反馈闭环会比单纯换强模型更难复制。",
            ),
        ]

    news = (explain_news(item) or "这条信息目前公开摘要较少，只能先确认主题，不能据此下结论").rstrip("。")
    relevance = (explain_relevance(item) or "这条信息值得关注，但需要更多上下文判断它和当前项目的关系").rstrip("。")
    return [
        ("先用一句话说，这条新闻到底发生了什么？", f"{news}。"),
        ("这里面最值得注意的是什么？", "看它有没有带来新的事实、方法或真实案例。只有标题新鲜，价值不够。"),
        ("有没有什么需要保留判断的地方？", "如果公开信息只有宣传口径或很短的摘要，就不能把未来目标当成已经实现的能力。"),
        ("最后，它和我们现在做的事有什么关系？", f"{relevance}。"),
    ]


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
    lead_title = chinese_title(lead_item) or "今天的第一条 AI 线索"
    lines = [
        f"# {date} AI 日课播客稿",
        "",
        "## 开场",
        "",
        f"早上好。今天先从《{lead_title}》讲起。我们不堆术语，只说清楚发生了什么，以及它和你有什么关系。",
        "",
        "## 正文",
        "",
    ]

    transitions = [
        "第一条。",
        "第二条，我们换到另一个角度。",
        "第三条更适合放进工作流里理解。",
        "第四条，我们看它背后的趋势。",
        "最后一条，可以作为今天的补位阅读。",
    ]

    for index, item in enumerate(items, start=1):
        transition = transitions[index - 1] if index <= len(transitions) else f"第 {index} 条。"
        title = chinese_title(item) or f"第 {index} 条内容"
        summary = explain_news(item)
        lines.extend(
            [
                f"{transition}",
                "",
                f"这条来自 {item.source or '原始信息源'}，讲的是《{title}》。",
            ]
        )
        if summary:
            lines.append(f"发生了什么：{short(summary, 180)}")
        lines.append(f"和你有什么关系：{explain_relevance(item)}")
        if item.link:
            lines.append(f"原文链接：{item.link}")
        lines.append("")

    lines.extend(
        [
        "## 今日行动",
            "",
        "今天选一条最能连接当前方向的内容，写下它对「汽车 PR Agent」的启发。可以从竞品监测、卖点提炼、发布会内容生成、事实风险检查里任选一个角度。",
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

    lead_title = chinese_title(items[0]) or "今天的第一条 AI 线索"
    dialogue: list[dict[str, str]] = [
        {
            "speaker": "A",
            "text": f"欢迎来到轻舟 AI 日课。今天是 {date}。我们不做新闻播报，换成两个声音来拆今天最值得听的 AI 线索。",
        },
        {
            "speaker": "B",
            "text": f"今天先从《{lead_title}》讲起。我们不堆术语，只说清楚发生了什么，以及它和你有什么关系。",
        },
    ]

    setup_replies = [
        "好，先抓住它最关键的部分。",
        "可以，这条需要把宣传和事实分开看。",
        "好，我们不看榜单口号，直接看实际能力。",
        "这条和 Agent 产品很相关，我们一步步拆。",
        "这条很有意思，关键不只是用了 AI。",
    ]
    for index, item in enumerate(items[:5], start=1):
        title = chinese_title(item) or f"第 {index} 条内容"
        dialogue.append(
            {
                "speaker": "A",
                "text": f"第 {index} 条，来自 {item.source or '原始信息源'}，我们聊聊《{title}》。",
            }
        )
        dialogue.append({"speaker": "B", "text": setup_replies[index - 1]})
        for question, answer in dialogue_exchanges(item):
            dialogue.append({"speaker": "A", "text": question})
            dialogue.append({"speaker": "B", "text": answer})

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


def feishu_json_request(url: str, payload: dict | None = None, token: str = "", method: str = "POST") -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Feishu API failed: HTTP {exc.code}: {detail}") from exc
    if result.get("code", 0) != 0:
        raise RuntimeError(f"Feishu API failed: {result}")
    return result


def feishu_tenant_token(app_id: str, app_secret: str) -> str:
    result = feishu_json_request(
        f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    token = result.get("tenant_access_token")
    if not token:
        raise RuntimeError("Feishu did not return tenant_access_token.")
    return token


def find_feishu_chat(token: str, chat_name: str) -> str:
    page_token = ""
    available_names: list[str] = []
    while True:
        query = {"page_size": "100"}
        if page_token:
            query["page_token"] = page_token
        url = f"{FEISHU_API_BASE}/im/v1/chats?{urllib.parse.urlencode(query)}"
        result = feishu_json_request(url, token=token, method="GET")
        data = result.get("data", {})
        for chat in data.get("items", []):
            name = chat.get("name", "")
            available_names.append(name)
            if name == chat_name:
                return chat["chat_id"]
        if not data.get("has_more"):
            break
        page_token = data.get("page_token", "")
    names = "、".join(name for name in available_names if name) or "无"
    raise RuntimeError(f"机器人没有找到群聊「{chat_name}」。当前可见群聊：{names}")


def convert_to_opus(audio_path: Path) -> Path:
    if not shutil.which("ffmpeg"):
        if os.environ.get("GITHUB_ACTIONS") == "true" and shutil.which("sudo"):
            subprocess.run(
                ["sudo", "apt-get", "update", "-qq"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                ["sudo", "apt-get", "install", "-y", "-qq", "ffmpeg"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        if not shutil.which("ffmpeg"):
            raise RuntimeError("Sending playable Feishu audio requires ffmpeg.")
    opus_path = audio_path.with_suffix(".opus")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-vn",
            "-c:a",
            "libopus",
            "-b:a",
            "48k",
            "-application",
            "audio",
            str(opus_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return opus_path


def encode_multipart(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----CodexBoundary{os.urandom(12).hex()}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), boundary


def upload_feishu_audio(token: str, opus_path: Path) -> str:
    body, boundary = encode_multipart({"file_type": "opus", "file_name": opus_path.name}, "file", opus_path)
    request = urllib.request.Request(
        f"{FEISHU_API_BASE}/im/v1/files",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Feishu audio upload failed: HTTP {exc.code}: {detail}") from exc
    if result.get("code", 0) != 0:
        raise RuntimeError(f"Feishu audio upload failed: {result}")
    return result["data"]["file_key"]


def send_feishu_audio(token: str, chat_id: str, file_key: str) -> None:
    url = f"{FEISHU_API_BASE}/im/v1/messages?receive_id_type=chat_id"
    feishu_json_request(
        url,
        {
            "receive_id": chat_id,
            "msg_type": "audio",
            "content": json.dumps({"file_key": file_key}, ensure_ascii=False),
        },
        token=token,
    )


def send_feishu_text_message(token: str, chat_id: str, text: str) -> None:
    url = f"{FEISHU_API_BASE}/im/v1/messages?receive_id_type=chat_id"
    feishu_json_request(
        url,
        {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
        token=token,
    )


def render_dialogue_transcript(date: str, dialogue: list[dict[str, str]]) -> str:
    lines = [f"🎧 {date} AI 日课双人播客｜对谈文字", ""]
    for segment in dialogue:
        speaker = "主播 A" if segment.get("speaker") == "A" else "主播 B"
        text = segment.get("text", "").strip()
        if text:
            lines.append(f"{speaker}：{text}")
            lines.append("")
    lines.append("👇 点击下一条音频即可边听边看。")
    return "\n".join(lines)


def split_feishu_text(text: str, limit: int = 3500) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = paragraph
    if current:
        chunks.append(current)
    return chunks


def send_playable_feishu_audio(
    audio_path: Path,
    app_id: str,
    app_secret: str,
    chat_name: str,
    date: str,
    dialogue: list[dict[str, str]],
    chat_id: str = "",
) -> None:
    token = feishu_tenant_token(app_id, app_secret)
    chat_id = chat_id or find_feishu_chat(token, chat_name)
    for text_chunk in split_feishu_text(render_dialogue_transcript(date, dialogue)):
        send_feishu_text_message(token, chat_id, text_chunk)
    opus_path = convert_to_opus(audio_path)
    file_key = upload_feishu_audio(token, opus_path)
    send_feishu_audio(token, chat_id, file_key)


def github_file_url(path: Path) -> str:
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        return ""
    encoded = urllib.parse.quote(path.as_posix())
    return f"https://github.com/{repository}/blob/main/{encoded}"


def concise_audio_error(error: str) -> str:
    if "insufficient" in error.lower() or "余量不足" in error or "quota" in error.lower():
        return "Fish Audio 额度不足，暂未生成音频。"
    return f"音频暂未生成：{short(error, 120)}"


def render_feishu_text(
    date: str,
    output_path: Path,
    items: list[DailyItem],
    audio_path: Path | None = None,
    audio_error: str = "",
) -> str:
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
    elif audio_error:
        lines.append(concise_audio_error(audio_error))
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
    audio_error = ""
    fish_api_key = os.environ.get("FISH_API_KEY")
    should_generate_audio = args.audio == "always" or (args.audio == "auto" and bool(fish_api_key))
    if should_generate_audio:
        if not fish_api_key:
            audio_error = "--audio always requires FISH_API_KEY"
        else:
            audio_dir = Path(args.audio_dir).expanduser()
            candidate_audio_path = audio_dir / f"{date} AI 日课双人播客.mp3"
            try:
                audio_path = generate_audio(dialogue, candidate_audio_path, fish_api_key)
            except Exception as exc:
                audio_error = str(exc)
                audio_path = None
                candidate_audio_path.unlink(missing_ok=True)
    if audio_error:
        print(f"warning: {concise_audio_error(audio_error)}", file=sys.stderr)

    if args.send_feishu:
        if not args.feishu_webhook:
            raise SystemExit("error: --send-feishu requires --feishu-webhook or FEISHU_WEBHOOK_URL")
        send_feishu(args.feishu_webhook, render_feishu_text(date, output_path, items, audio_path, audio_error))
        app_id = os.environ.get("FEISHU_APP_ID")
        app_secret = os.environ.get("FEISHU_APP_SECRET")
        chat_name = os.environ.get("FEISHU_CHAT_NAME", "AI日课群")
        chat_id = os.environ.get("FEISHU_CHAT_ID", "")
        if audio_path and app_id and app_secret:
            send_playable_feishu_audio(
                audio_path,
                app_id,
                app_secret,
                chat_name,
                date,
                dialogue,
                chat_id,
            )

    print(audio_path or output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
