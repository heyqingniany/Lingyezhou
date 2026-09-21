from __future__ import annotations

from typing import Any
from pathlib import Path

from lingyezhou.models.transcript import Transcript


def _bullets(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return "- 无"
    return "\n".join(f"- {value}" for value in values)


def render_report(data: dict, transcript: Transcript) -> str:
    questions = data.get("questions") if isinstance(data.get("questions"), list) else []
    lines = [
        "# 聆页舟 面试复盘",
        "",
        "## 面试概览",
        "",
        str(data.get("summary") or "未提供概览。"),
        "",
        f"- 录音：{transcript.source_file}",
        f"- 时长：{Transcript.format_time(transcript.duration_ms)}",
        f"- 识别出的技术问题：{len(questions)} 个",
    ]
    for index, question in enumerate(questions, 1):
        if not isinstance(question, dict):
            continue
        lines.extend([
            "", "---", "", f"## Q{index} {question.get('question', '未命名问题')}",
            "", "### 面试官", "", str(question.get("interviewer_context") or question.get("question") or "无"),
            "", "### 我的回答", "", str(question.get("candidate_answer") or "未识别到回答。"),
            "", "### 回答分析", "", str(question.get("analysis") or "无"),
            "", "### 遗漏知识点", "", _bullets(question.get("missing_points")),
            "", "### 更完整的参考回答", "", str(question.get("better_answer") or "无"),
        ])
    lines.extend([
        "", "---", "", "## 本次暴露出的知识盲区", "", _bullets(data.get("knowledge_gaps")),
        "", "## 建议重点复习内容", "", _bullets(data.get("review_suggestions")), "",
    ])
    return "\n".join(lines)


def render_general_report(data: dict, transcript: Transcript) -> str:
    title = str(data.get("title") or Path(transcript.source_file).stem or "录音整理")
    action_items = data.get("action_items") if isinstance(data.get("action_items"), list) else []
    lines = [
        f"# {title}", "",
        "> 由 聆页舟 根据录音转写生成，请结合原始录音核对关键信息。", "",
        "## 内容摘要", "", str(data.get("summary") or "未提供摘要。"), "",
        f"- 来源：{transcript.source_file}",
        f"- 时长：{Transcript.format_time(transcript.duration_ms)}", "",
        "## 主要话题", "", _bullets(data.get("topics")), "",
        "## 重点内容", "", _bullets(data.get("highlights")), "",
        "## 决策与结论", "", _bullets(data.get("decisions")), "",
        "## 待办事项", "",
    ]
    if action_items:
        for item in action_items:
            if isinstance(item, dict):
                task = str(item.get("task") or "未命名事项")
                owner = str(item.get("owner") or "未指定")
                deadline = str(item.get("deadline") or "未指定")
                lines.append(f"- [ ] {task}（负责人：{owner}；截止：{deadline}）")
            else:
                lines.append(f"- [ ] {item}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 补充备注", "", _bullets(data.get("notes")), ""])
    return "\n".join(lines)


def render_history_report(data: dict) -> str:
    lines = ["# 多次记录复盘", "", str(data.get("overview") or "未提供总体概览。"), ""]
    sections = (
        ("有证据支持的进步", "improvements"),
        ("需要关注的退步", "regressions"),
        ("反复出现的模式", "recurring_patterns"),
    )
    for title, key in sections:
        lines.extend([f"## {title}", ""])
        values = data.get(key) if isinstance(data.get(key), list) else []
        if not values:
            lines.extend(["- 暂无足够证据", ""])
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            label = value.get("dimension") or value.get("pattern") or "未命名维度"
            finding = value.get("finding") or ""
            lines.append(f"### {label}")
            if finding:
                lines.extend(["", str(finding)])
            evidence = value.get("evidence") if isinstance(value.get("evidence"), list) else []
            lines.extend(["", *[f"- 证据：{item}" for item in evidence], ""])
    lines.extend(["## 下一步行动", "", _bullets(data.get("next_actions")), "", "## 分析限制", "", _bullets(data.get("limitations")), ""])
    return "\n".join(lines)


def render_qa_answer(question: str, data: dict) -> str:
    lines = [f"## 你：{question}", "", str(data.get("answer") or "未生成有效回答。"), ""]
    evidence = data.get("evidence") if isinstance(data.get("evidence"), list) else []
    if evidence:
        lines.extend(["### 录音依据", ""])
        for item in evidence:
            if not isinstance(item, dict):
                continue
            time = str(item.get("time") or "时间未知")
            quote = str(item.get("quote") or "")
            meaning = str(item.get("meaning") or "")
            lines.append(f"- **[{time}]** {quote}" + (f" — {meaning}" if meaning else ""))
        lines.append("")
    uncertainties = data.get("uncertainties")
    if isinstance(uncertainties, list) and uncertainties:
        lines.extend(["### 仍需核实", "", _bullets(uncertainties), ""])
    actions = data.get("suggested_actions")
    if isinstance(actions, list) and actions:
        lines.extend(["### 建议下一步", "", _bullets(actions), ""])
    notice = str(data.get("professional_notice") or "").strip()
    if notice:
        lines.extend([f"> {notice}", ""])
    return "\n".join(lines)


def render_qa_conversation(messages: list[dict]) -> str:
    if not messages:
        return ""
    return "\n\n---\n\n".join(
        str(item.get("markdown") or render_qa_answer(str(item.get("question") or ""), item.get("answer") or {}))
        for item in messages if isinstance(item, dict)
    )
