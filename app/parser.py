"""A bounded recursive-descent arithmetic parser; never executes Python code."""

import math
import re
from decimal import Decimal, DecimalException, localcontext
from functools import wraps

from app.errors import CalculatorError
from app.scientific import ARITY, extended

TOKEN = re.compile(
    r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?|[a-z]+|[(),%^!+*/-]"
)
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
    if value.adjusted() < -1000:
        raise CalculatorError("NUMERIC_ERROR", "结果过小，超出显示范围。")
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def located(method):
    @wraps(method)
    def evaluate(self, *args):
        start = self.position
        try:
            return method(self, *args)
        except CalculatorError as error:
            self.locate(error, start, self.position)
            raise

    return evaluate


class Parser:
    """expression → term → unary → primary implements mathematical precedence."""

    def __init__(self, expression: str, angle_mode: str = "deg"):
        self.angle_mode = angle_mode
        if len(expression) > MAX_LENGTH:
            raise CalculatorError("EXPRESSION_TOO_LONG", "表达式不能超过 500 个字符。")
        self.source = expression
        normalized = []
        self.offsets = []
        offset = 0
        for char in expression:
            replacement = {"×": "*", "÷": "/", "π": "pi"}.get(char, char)
            width = len(char.encode("utf-16-le")) // 2
            normalized.append(replacement)
            self.offsets.extend([(offset, offset + width)] * len(replacement))
            offset += width
        self.source_length = offset
        self.expression = "".join(normalized)
        self.spans = []
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
                    "INVALID_CHARACTER",
                    "这个字符不受支持。",
                    position=self.offsets[offset][0],
                    end_position=self.offsets[offset][1],
                )
            self.tokens.append(match.group())
            self.spans.append(
                (self.offsets[match.start()][0], self.offsets[match.end() - 1][1])
            )
            offset = match.end()
        if not self.tokens:
            raise CalculatorError(
                "EMPTY_EXPRESSION",
                "请输入需要计算的表达式。",
                position=0,
                end_position=0,
            )

    def locate(self, error, start, end):
        if error.position is None:
            error.position = (
                self.spans[start][0] if start < len(self.spans) else self.source_length
            )
            error.end_position = (
                self.spans[end - 1][1] if end > start else error.position
            )

    def fail(self, message):
        error = CalculatorError("INVALID_EXPRESSION", message)
        self.locate(error, self.position, min(self.position + 1, len(self.spans)))
        raise error

    def expect(self, expected, message):
        if self.peek() != expected:
            self.fail(message)
        self.take()

    def peek(self) -> str | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self) -> str:
        token = self.peek()
        if token is None:
            self.fail("这里需要数字或表达式。")
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
            start = self.position
            right = self.unary(depth)
            try:
                value = self.apply(value, operator, right)
            except CalculatorError as error:
                self.locate(error, start, self.position)
                raise
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
        return self.power(depth)

    def power(self, depth: int) -> Decimal:
        value = self.primary(depth)
        while self.peek() in ("!", "%"):
            operator = self.take()
            if operator == "%":
                value = self.record(f"{format_decimal(value)}%", value / 100)
                continue
            if value != value.to_integral_value() or not 0 <= value <= 69:
                raise CalculatorError("DOMAIN_ERROR", "阶乘仅支持 0–69 的整数。")
            value = self.record(
                f"{format_decimal(value)}!", Decimal(math.factorial(int(value)))
            )
        if self.peek() == "^":
            self.take()
            right = self.unary(depth + 1)
            if (value == 0 and right <= 0) or (
                value < 0 and right != right.to_integral_value()
            ):
                raise CalculatorError("DOMAIN_ERROR", "乘方在实数范围内无定义。")
            if abs(right) > 10000:
                raise CalculatorError("NUMERIC_ERROR", "指数绝对值不能超过 10000。")
            value = self.record(
                f"{format_decimal(value)} ^ {format_decimal(right)}", value**right
            )
        return value

    def record(self, operation: str, value: Decimal) -> Decimal:
        self.steps.append({"operation": operation, "result": format_decimal(value)})
        return value

    @located
    def primary(self, depth: int) -> Decimal:
        name = self.peek()
        if name in ("pi", "e"):
            self.take()
            with localcontext() as constants_context:
                constants_context.prec = 40
                return (
                    Decimal("3.141592653589793238462643383279502884197")
                    if name == "pi"
                    else Decimal(1).exp()
                )
        if name in ARITY:
            self.take()
            self.expect("(", "函数名后需要左括号。")
            argument_start = self.position
            args = [self.expression_value(depth + 1)]
            argument_spans = [(argument_start, self.position)]
            for _ in range(ARITY[name] - 1):
                self.expect(",", "参数之间需要逗号。")
                argument_start = self.position
                args.append(self.expression_value(depth + 1))
                argument_spans.append((argument_start, self.position))
            self.expect(")", "需要右括号，请检查函数参数数量。")
            unit = (
                f" [{self.angle_mode.upper()}]"
                if name in ("asin", "acos", "atan")
                else ""
            )
            operation = (
                name + "(" + ", ".join(format_decimal(v) for v in args) + ")" + unit
            )
            try:
                return self.record(operation, extended(name, args, self.angle_mode))
            except CalculatorError as error:
                if error.argument is not None:
                    self.locate(error, *argument_spans[error.argument])
                raise
        if name in ("sqrt", "sin", "cos", "tan", "ln", "log"):
            self.take()
            self.expect("(", "函数名后需要左括号。")
            value = self.expression_value(depth + 1)
            self.expect(")", "这里缺少右括号。")
            if name == "sqrt":
                if value < 0:
                    raise CalculatorError("DOMAIN_ERROR", "负数不能开平方。")
                result = value.sqrt()
            elif name in ("ln", "log"):
                if value <= 0:
                    raise CalculatorError("DOMAIN_ERROR", "对数的参数必须大于零。")
                result = value.ln() if name == "ln" else value.log10()
            else:
                if abs(value) > Decimal("1e12"):
                    raise CalculatorError(
                        "NUMERIC_ERROR", "三角函数参数绝对值不能超过 10¹²。"
                    )
                reduced = value % 360 if self.angle_mode == "deg" else value
                angle = (
                    math.radians(float(reduced))
                    if self.angle_mode == "deg"
                    else float(value)
                )
                if name == "tan" and abs(math.cos(angle)) < 1e-15:
                    raise CalculatorError("DOMAIN_ERROR", "此角度的正切无定义。")
                number = {"sin": math.sin, "cos": math.cos, "tan": math.tan}[name](
                    angle
                )
                if self.angle_mode == "deg" and reduced % 90 == 0:
                    number = round(number)
                result = Decimal(format(number, ".15g"))
            unit = (
                f" [{self.angle_mode.upper()}]" if name in ("sin", "cos", "tan") else ""
            )
            return self.record(f"{name}({format_decimal(value)}){unit}", result)
        if self.peek() == "(":
            self.take()
            value = self.expression_value(depth + 1)
            self.expect(")", "这里缺少右括号。")
            return value
        token_start = self.position
        token = self.take()
        if not re.fullmatch(
            r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", token
        ):
            raise CalculatorError(
                "INVALID_EXPRESSION",
                "此处需要数字或左括号。",
                position=self.spans[token_start][0],
                end_position=self.spans[token_start][1],
            )
        if (
            len(re.split("[eE]", token)[0].replace(".", "").lstrip("0").rstrip("0"))
            > 28
        ):
            raise CalculatorError("NUMBER_TOO_LONG", "单个数字最多支持 28 位有效数字。")
        value = Decimal(token)
        format_decimal(value)
        return value

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


def calculate(
    expression: str, angle_mode: str = "deg"
) -> tuple[str, str, list[dict[str, str]]]:
    parser = Parser(expression, angle_mode)
    try:
        with localcontext() as context:
            context.prec = 28
            value = parser.expression_value()
            if parser.peek() is not None:
                parser.fail("这里需要运算符，请检查括号和小数点。")
            return parser.expression.strip(), format_decimal(+value), parser.steps
    except CalculatorError as exc:
        parser.locate(exc, max(0, parser.position - 1), parser.position)
        raise
    except DecimalException as exc:
        raise CalculatorError(
            "NUMERIC_ERROR",
            "数值无法计算，请缩小输入范围。",
            position=0,
            end_position=parser.source_length,
        ) from exc
