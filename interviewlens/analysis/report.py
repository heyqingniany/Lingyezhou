from __future__ import annotations

from typing import Any
from pathlib import Path

from interviewlens.models.transcript import Transcript


def _bullets(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return "- 无"
    return "\n".join(f"- {value}" for value in values)


def render_report(data: dict, transcript: Transcript) -> str:
    questions = data.get("questions") if isinstance(data.get("questions"), list) else []
    lines = [
        "# InterviewLens 面试复盘",
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
        "> 由 InterviewLens 根据录音转写生成，请结合原始录音核对关键信息。", "",
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
