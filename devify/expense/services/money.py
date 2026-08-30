"""Render amounts the way a reimbursement form expects them."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

DIGITS = "零壹贰叁肆伍陆柒捌玖"
# Units within a four-digit group, and the group markers above them.
SECTION_UNITS = ("", "拾", "佰", "仟")
GROUP_UNITS = ("", "万", "亿", "万亿")

MAX_AMOUNT = Decimal("9999999999999.99")


def _render_section(value: int) -> str:
    """Render one four-digit group, collapsing runs of zeros to one 零."""
    text = ""
    zero_pending = False

    for position in range(3, -1, -1):
        digit = (value // (10**position)) % 10
        if digit == 0:
            if text:
                zero_pending = True
            continue
        if zero_pending:
            text += DIGITS[0]
            zero_pending = False
        text += DIGITS[digit] + SECTION_UNITS[position]

    return text


def to_chinese_amount(amount) -> str:
    """
    Convert an amount to the formal Chinese capitalized form.

    Returns an empty string for anything that cannot be written this way,
    rather than guessing, since this text goes onto a financial form.
    """
    if amount is None:
        return ""

    try:
        value = Decimal(str(amount))
    except (ArithmeticError, ValueError):
        return ""

    if value < 0 or value > MAX_AMOUNT:
        return ""

    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    yuan = int(value)
    cents = int((value - yuan) * 100)
    jiao, fen = divmod(cents, 10)

    if yuan == 0 and cents == 0:
        return "零元整"

    integer_text = ""
    if yuan:
        groups = []
        remaining = yuan
        while remaining:
            groups.append(remaining % 10000)
            remaining //= 10000

        for index in range(len(groups) - 1, -1, -1):
            section = groups[index]
            if section == 0:
                # A wholly empty group still needs one 零 to keep the
                # magnitudes readable, but never two in a row.
                if integer_text and not integer_text.endswith(DIGITS[0]):
                    integer_text += DIGITS[0]
                continue

            rendered = _render_section(section)
            # A group under a thousand needs a leading 零 to show the gap,
            # e.g. 100,005 is 壹拾万零伍.
            if integer_text and section < 1000:
                if not integer_text.endswith(DIGITS[0]):
                    integer_text += DIGITS[0]
            integer_text += rendered + GROUP_UNITS[index]

        # Empty lower groups can leave a dangling 零 with nothing after it.
        integer_text = integer_text.rstrip(DIGITS[0])
        integer_text += "元"
    else:
        integer_text = DIGITS[0] + "元"

    if jiao == 0 and fen == 0:
        return integer_text + "整"

    decimal_text = DIGITS[jiao] + "角" if jiao else DIGITS[0]
    decimal_text += DIGITS[fen] + "分" if fen else "整"

    return integer_text + decimal_text
