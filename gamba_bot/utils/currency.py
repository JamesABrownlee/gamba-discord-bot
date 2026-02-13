from decimal import Decimal, ROUND_HALF_UP


def parse_credits_to_cents(amount: float) -> int:
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cents = int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))
    if cents <= 0:
        raise ValueError("Stake must be greater than zero.")
    return cents


def format_cents(cents: int) -> str:
    return f"{(Decimal(cents) / Decimal(100)):.2f}"
