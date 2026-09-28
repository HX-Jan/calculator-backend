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

    def reject(message, argument=0):
        raise CalculatorError("DOMAIN_ERROR", message, argument=argument)

    if name in ("asin", "acos") and not -1 <= x <= 1:
        reject("反正弦和反余弦的参数应在 −1 到 1 之间。")
    if name == "acosh" and x < 1:
        reject("反双曲余弦的参数必须大于或等于 1。")
    if name == "atanh" and not -1 < x < 1:
        reject("反双曲正切的参数必须大于 −1 且小于 1。")
    if name in ("perm", "comb"):
        r = args[1]
        if x != x.to_integral_value() or not 0 <= x <= 1000:
            reject("总数 n 必须是 0 到 1000 的整数。")
        if r != r.to_integral_value() or r < 0:
            reject("选取数 r 必须是非负整数。", 1)
        if r > x:
            reject("选取数 r 不能大于总数 n。", 1)
    if name == "logbase":
        if x <= 0:
            reject("对数的真数必须大于零。")
        if args[1] <= 0 or args[1] == 1:
            reject("对数的底数必须大于零且不能等于 1。", 1)
    if name == "mod" and args[1] == 0:
        reject("取余的除数不能为零。", 1)
    if name == "root":
        n = args[1]
        if n == 0 or abs(n) > 10000:
            reject("根次数不能为零，且绝对值不能超过 10000。", 1)
        if x == 0 and n < 0:
            reject("零不能取负次方根。", 1)
        if x < 0 and (n != n.to_integral_value() or n % 2 == 0):
            reject("负数只支持整数奇次方根。", 1)
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
