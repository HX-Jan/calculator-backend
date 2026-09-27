"""Whitelisted extended real-valued scientific functions."""

import math
from decimal import Decimal, localcontext

from app.errors import CalculatorError

ARITY = {
    name: 1
    for name in (
        "asin",
        "acos",
        "atan",
        "sinh",
        "cosh",
        "tanh",
        "asinh",
        "acosh",
        "atanh",
        "abs",
        "exp",
        "cbrt",
        "floor",
        "ceil",
    )
}
ARITY.update({name: 2 for name in ("root", "logbase", "mod", "perm", "comb")})


def extended(name, args, angle_mode):
    x = args[0]
    try:
        if name == "abs":
            return abs(x)
        if name == "floor":
            return Decimal(math.floor(x))
        if name == "ceil":
            return Decimal(math.ceil(x))
        if name == "exp":
            if abs(x) > 2300:
                raise ValueError()
            return x.exp()
        if name in ("root", "cbrt"):
            n = args[1] if name == "root" else Decimal(3)
            if n == 0 or abs(n) > 10000 or (x == 0 and n < 0):
                raise ValueError()
            if x < 0 and (n != n.to_integral_value() or n % 2 == 0):
                raise ValueError()
            return (abs(x) ** (1 / n)) * (-1 if x < 0 else 1)
        if name == "logbase":
            base = args[1]
            if x <= 0 or base <= 0 or base == 1:
                raise ValueError()
            with localcontext() as context:
                context.prec = 40
                result = x.ln() / base.ln()
            return +result
        if name == "mod":
            if args[1] == 0:
                raise ValueError()
            return x % args[1]
        if name in ("perm", "comb"):
            r = args[1]
            if x != int(x) or r != int(r) or not 0 <= r <= x <= 1000:
                raise ValueError()
            return Decimal((math.perm if name == "perm" else math.comb)(int(x), int(r)))
        if name in ("sinh", "cosh") and abs(x) > 230:
            raise ValueError()
        number = getattr(math, name)(float(x))
        if name in ("asin", "acos", "atan") and angle_mode == "deg":
            number = math.degrees(number)
        return Decimal(format(number, ".15g"))
    except (ValueError, OverflowError):
        raise CalculatorError(
            "DOMAIN_ERROR", "参数超出该函数的实数定义域或范围。"
        ) from None
