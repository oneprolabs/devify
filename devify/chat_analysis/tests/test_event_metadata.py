from chat_analysis.event_metadata import participant_metadata


def test_shortened_nicknames_are_removed_without_losing_the_matter():
    assert participant_metadata(
        "闲人晚上开通Plus会员", "闲人",
        ["几时归去做个闲人", "闲人", "Plus会员"],
        "闲人晚上开通Plus会员。", ["几时归去做个闲人"],
    ) == ("晚上开通Plus会员", "", ["Plus会员"])
    assert participant_metadata(
        "干啥向老板确认浏览器直接操作", "干啥",
        ["干啥", "浏览器"],
        "干啥将向老板确认。", ["干啥？出去玩啊！"],
    ) == ("向老板确认浏览器直接操作", "", ["浏览器"])


def test_entity_made_from_multiple_nicknames_is_discarded():
    names_only = "干啥-出去玩啊-几时归去做个闲人"
    assert participant_metadata(
        "浏览器操作确认", names_only, ["浏览器", names_only],
        "干啥向老板确认浏览器操作。",
        ["干啥？出去玩啊！", "几时归去做个闲人"],
    ) == ("浏览器操作确认", "", ["浏览器"])


def test_title_keeps_words_that_only_happen_to_contain_a_nickname():
    assert participant_metadata(
        "脉冲项目与Malice测试", "脉冲项目", ["Malice", "甲方"],
        "检查项目。", ["脉冲", "Alice", "甲"],
    ) == ("脉冲项目与Malice测试", "脉冲项目", ["Malice", "甲方"])


def test_nickname_only_title_falls_back_to_the_matter_in_the_summary():
    assert participant_metadata(
        "Alice (PM)", "Alice", ["Alice", "Customer quote"],
        "Alice will submit the customer quote. Bob will review it.",
        ["Alice (PM)", "Bob"],
    ) == ("Submit the customer quote", "", ["Customer quote"])
