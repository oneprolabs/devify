"""Unit tests for the formal Chinese amount form."""

import pytest

from expense.services.money import to_chinese_amount


pytestmark = pytest.mark.unit


class TestToChineseAmount:
    @pytest.mark.parametrize(
        "amount,expected",
        [
            ("0", "零元整"),
            ("1", "壹元整"),
            ("10", "壹拾元整"),
            ("100", "壹佰元整"),
            ("1000", "壹仟元整"),
            ("10000", "壹万元整"),
            ("100000000", "壹亿元整"),
        ],
    )
    def test_round_magnitudes_have_no_dangling_zero(self, amount, expected):
        assert to_chinese_amount(amount) == expected

    @pytest.mark.parametrize(
        "amount,expected",
        [
            ("128.50", "壹佰贰拾捌元伍角整"),
            ("1286.50", "壹仟贰佰捌拾陆元伍角整"),
            ("0.01", "零元零壹分"),
            ("0.10", "零元壹角整"),
            ("999.09", "玖佰玖拾玖元零玖分"),
        ],
    )
    def test_jiao_and_fen(self, amount, expected):
        assert to_chinese_amount(amount) == expected

    @pytest.mark.parametrize(
        "amount,expected",
        [
            ("10005", "壹万零伍元整"),
            ("100005", "壹拾万零伍元整"),
        ],
    )
    def test_internal_gaps_get_exactly_one_zero(self, amount, expected):
        assert to_chinese_amount(amount) == expected

    def test_rounding_is_half_up_at_the_cent(self):
        assert to_chinese_amount("1.005") == "壹元零壹分"

    def test_a_negative_amount_is_refused(self):
        # This text goes on a financial form; a guess is worse than blank.
        assert to_chinese_amount("-5") == ""

    def test_an_absurd_amount_is_refused(self):
        assert to_chinese_amount("1" * 20) == ""

    def test_none_is_blank(self):
        assert to_chinese_amount(None) == ""

    def test_garbage_is_blank(self):
        assert to_chinese_amount("abc") == ""
