from chat_analysis.topic_services import (
    QUESTION_PROMPT,
    format_question_answer,
)


def test_question_prompt_requires_a_readable_answer():
    assert "same language as the question" in QUESTION_PROMPT
    assert "using Markdown" in QUESTION_PROMPT
    assert '"## "' in QUESTION_PROMPT
    assert '"- "' in QUESTION_PROMPT
    assert "Do not use tables or code fences." in QUESTION_PROMPT
    assert "Do not repeat the citations as another list." in QUESTION_PROMPT
    assert "Do not use circled numbers" in QUESTION_PROMPT
    assert "related material exists" in QUESTION_PROMPT
    assert "Do not describe it." in QUESTION_PROMPT


def test_format_question_answer_splits_circled_numbers():
    answer = (
        "记录里没有逐条计数，因此无法给出确定件数。"
        "若按被记录成事件的事项来算，是 3 件："
        "①提醒会员明天到期，并要求对方续开；"
        "②说明老板那套工具是自身配置问题；"
        "③提出要借山姆会员卡，确认后作罢。"
    )
    formatted = format_question_answer(answer)
    assert formatted.startswith("记录里没有逐条计数")
    assert "\n\n1. 提醒会员明天到期" in formatted
    assert "\n2. 说明老板那套工具是自身配置问题；" in formatted
    assert formatted.endswith("3. 提出要借山姆会员卡，确认后作罢。")
    assert format_question_answer("先更新 0.12 再看 0.1.11。") == (
        "先更新 0.12 再看 0.1.11。"
    )


def test_format_question_answer_turns_chinese_sections_into_markdown():
    formatted = format_question_answer(
        "客户端问题可以分成几块：\n"
        "一、登录与授权 - 浏览器授权点不开 - 忘记密码跳转 404\n"
        "二、性能与加载 - 打开授权页大约 10-15 秒"
    )
    assert formatted.startswith("客户端问题可以分成几块：\n\n## 登录与授权")
    assert "\n\n- 浏览器授权点不开\n- 忘记密码跳转 404" in formatted
    assert "\n\n## 性能与加载\n\n- 打开授权页大约 10-15 秒" in formatted
