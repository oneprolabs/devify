"""No network calls or database access: verify the exact model input shape."""

import json
from datetime import datetime
from types import SimpleNamespace

from chat_analysis.summaries.input import summary_content
from chat_analysis.summaries.tasks import PROMPT


def record(messages):
    return SimpleNamespace(
        title="总结测试",
        range_label="今天",
        language="中文",
        input_messages=messages,
    )


def test_compact_input_keeps_all_text_speakers_times_and_conversations():
    messages = [
        {
            "username": "first",
            "display": "同名群",
            "sender": "甲",
            "time": 1795165000,
            "text": "保留原文\n  空格与表情😀",
        },
        {
            "username": "second",
            "display": "同名群",
            "sender": "乙",
            "time": 1795165001,
            "text": "另一会话",
        },
        {
            "username": "first",
            "display": "同名群",
            "sender": "甲",
            "time": 1795165002,
            "text": "后续消息",
        },
    ]
    before = json.dumps(messages, ensure_ascii=False)
    payload = json.loads(summary_content(record(messages)))
    assert (
        len(payload["chats"]) == 2
    )  # Identical display names do not merge accounts.
    expected = {
        1795165000: messages[0],
        1795165001: messages[1],
        1795165002: messages[2],
    }
    actual = {}
    for chat in payload["chats"]:
        for stamp, speaker, text in chat["messages"]:
            assert datetime.fromisoformat(stamp).utcoffset() is not None
            timestamp = int(datetime.fromisoformat(stamp).timestamp())
            assert text == expected[timestamp]["text"]
            assert (
                payload["speakers"][speaker] == expected[timestamp]["sender"]
            )
            actual[timestamp] = text
    assert len(actual) == 3
    assert json.dumps(messages, ensure_ascii=False) == before


def test_midsize_mixed_language_chat_is_not_rejected_for_transport_metadata():
    messages = [
        {
            "username": "wxid_long_identity_12345678901234567890@chatroom",
            "display": "这是一个会重复出现的完整会话名称",
            "sender": f"参与者{i % 14}",
            "time": 1795165000 + i,
            "text": (
                "今日工作进展已确认，follow up with the project owner tomorrow. "
                "请保留负责人和待处理事项。"
            ),
        }
        for i in range(68)
    ]
    content = summary_content(record(messages))
    # Exercise the strict byte-based fallback; no change to token/model limits.
    assert 64 + len(PROMPT.encode()) + len(content.encode()) < 12000
    original = json.dumps({"messages": messages}, ensure_ascii=False)
    assert len(original.encode()) > 12000
    assert sum(len(c["messages"]) for c in json.loads(content)["chats"]) == 68


def test_large_text_is_not_truncated_to_make_the_budget_pass():
    text = "原文必须完整保留。" * 5000
    content = summary_content(
        record(
            [
                {
                    "username": "one",
                    "display": "群聊",
                    "sender": "甲",
                    "time": 1795165000,
                    "text": text,
                }
            ]
        )
    )
    assert json.loads(content)["chats"][0]["messages"][0][2] == text
    assert 64 + len(PROMPT.encode()) + len(content.encode()) > 12000
