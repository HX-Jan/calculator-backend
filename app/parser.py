"""A bounded recursive-descent arithmetic parser; never executes Python code."""

import re
from decimal import Decimal, DecimalException, localcontext

from app.errors import CalculatorError

TOKEN = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)|[()+*/-]")
MAX_LENGTH = 500
MAX_DEPTH = 32


def format_decimal(value: Decimal) -> str:
    """Keep JSON/JavaScript from rounding a precise decimal result."""
    if not value.is_finite() or abs(value) > Decimal("1e100"):
        raise CalculatorError(
            "RESULT_OUT_OF_RANGE", "结果超出允许范围（绝对值 ≤ 10¹⁰⁰）。"
        )
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class Parser:
    """expression → term → unary → primary implements mathematical precedence."""

    def __init__(self, expression: str):
        if len(expression) > MAX_LENGTH:
            raise CalculatorError("EXPRESSION_TOO_LONG", "表达式不能超过 500 个字符。")
        self.expression = expression.strip().replace("×", "*").replace("÷", "/")
        self.tokens: list[str] = []
        self.position = 0
        self.steps: list[dict[str, str]] = []
        offset = 0
        while offset < len(self.expression):
            if self.expression[offset].isspace():
                offset += 1
                continue
            match = TOKEN.match(self.expression, offset)
            if not match:
                raise CalculatorError(
                    "INVALID_CHARACTER", f"第 {offset + 1} 个字符不受支持。"
                )
            self.tokens.append(match.group())
            offset = match.end()
        if not self.tokens:
            raise CalculatorError("EMPTY_EXPRESSION", "请输入需要计算的表达式。")

    def peek(self) -> str | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self) -> str:
        token = self.peek()
        if token is None:
            raise CalculatorError(
                "INVALID_EXPRESSION", "表达式不完整，请检查数字与运算符。"
            )
        self.position += 1
        return token

    def expression_value(self, depth: int = 0) -> Decimal:
        value = self.term(depth)
        while self.peek() in ("+", "-"):
            operator = self.take()
            value = self.apply(value, operator, self.term(depth))
        return value

    def term(self, depth: int) -> Decimal:
        value = self.unary(depth)
        while self.peek() in ("*", "/"):
            operator = self.take()
            value = self.apply(value, operator, self.unary(depth))
        return value

    def unary(self, depth: int) -> Decimal:
        if depth > MAX_DEPTH:
            raise CalculatorError("TOO_DEEP", "括号或连续正负号嵌套不能超过 32 层。")
        if self.peek() in ("+", "-"):
            operator = self.take()
            value = self.unary(depth + 1)
            result = value if operator == "+" else -value
            self.steps.append(
                {
                    "operation": f"{operator}({format_decimal(value)})",
                    "result": format_decimal(result),
                }
            )
            return result
        if self.peek() == "(":
            self.take()
            value = self.expression_value(depth + 1)
            if self.take() != ")":
                raise CalculatorError("INVALID_EXPRESSION", "括号不匹配。")
            return value
        token = self.take()
        if token in ("*", "/", ")"):
            raise CalculatorError("INVALID_EXPRESSION", "此处需要数字或左括号。")
        if len(token.replace(".", "").lstrip("0")) > 28:
            raise CalculatorError("NUMBER_TOO_LONG", "单个数字最多支持 28 位有效数字。")
        return Decimal(token)

    def apply(self, left: Decimal, operator: str, right: Decimal) -> Decimal:
        if operator == "+":
            result = left + right
        elif operator == "-":
            result = left - right
        elif operator == "*":
            result = left * right
        else:
            if right == 0:
                raise CalculatorError("DIVISION_BY_ZERO", "除数不能为零。")
            result = left / right
        self.steps.append(
            {
                "operation": (
                    f"{format_decimal(left)} {operator} {format_decimal(right)}"
                ),
                "result": format_decimal(result),
            }
        )
        return result


def calculate(expression: str) -> tuple[str, str, list[dict[str, str]]]:
    parser = Parser(expression)
    try:
        with localcontext() as context:
            context.prec = 28
            value = parser.expression_value()
            if parser.peek() is not None:
                raise CalculatorError(
                    "INVALID_EXPRESSION", "数字之间需要运算符，请检查括号和小数点。"
                )
            return parser.expression, format_decimal(value), parser.steps
    except DecimalException as exc:
        raise CalculatorError(
            "NUMERIC_ERROR", "数值无法计算，请缩小输入范围。"
        ) from exc
