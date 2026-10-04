"""Formula grammar and request rules shared by SQLAlchemy and Cloudflare D1."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.errors import CalculatorError
from app.parser import MAX_DEPTH, Parser, calculate
from app.scientific import ARITY

FUNCTIONS = {**ARITY, **dict.fromkeys(("sqrt", "sin", "cos", "tan", "ln", "log"), 1)}
BUILTINS = [
    ("circle-area", "圆面积", "pi*r^2", {"r": "半径"}),
    ("circle-length", "圆周长", "2*pi*r", {"r": "半径"}),
    ("hypotenuse", "勾股定理", "sqrt(a^2+b^2)", {"a": "直角边 a", "b": "直角边 b"}),
    (
        "quadratic",
        "二次函数求值",
        "a*x^2+b*x+c",
        {"a": "系数 a", "x": "自变量 x", "b": "系数 b", "c": "常数 c"},
    ),
]


class FormulaSyntax(Parser):
    """Walk the calculator grammar without executing domain-dependent operations."""

    def validate(self):
        self.parameters = []
        self.expr(0)
        if self.peek() is not None:
            self.fail("这里需要运算符。")
        return self.parameters

    def expr(self, depth):
        self.term_syntax(depth)
        while self.peek() in ("+", "-"):
            self.take()
            self.term_syntax(depth)

    def term_syntax(self, depth):
        self.unary_syntax(depth)
        while self.peek() in ("*", "/"):
            self.take()
            self.unary_syntax(depth)

    def unary_syntax(self, depth):
        if depth > MAX_DEPTH:
            raise CalculatorError("TOO_DEEP", "公式嵌套不能超过 32 层。")
        if self.peek() in ("+", "-"):
            self.take()
            self.unary_syntax(depth + 1)
            return
        token = self.take()
        if token == "(":
            self.expr(depth + 1)
            self.expect(")", "这里缺少右括号。")
        elif token in FUNCTIONS:
            self.expect("(", "函数名后需要左括号。")
            for i in range(FUNCTIONS[token]):
                if i:
                    self.expect(",", "参数之间需要逗号。")
                self.expr(depth + 1)
            self.expect(")", "请检查函数参数数量及右括号。")
        elif token in ("pi", "e"):
            pass
        elif re.fullmatch("[a-df-z]", token):
            if token not in self.parameters:
                self.parameters.append(token)
            if len(self.parameters) > 8:
                raise CalculatorError("TOO_MANY_PARAMETERS", "公式最多包含 8 个参数。")
        elif re.fullmatch(
            r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", token
        ):
            # Reuse literal limits, without evaluating the formula itself.
            calculate(token)
        else:
            self.fail("参数须为单个小写字母；e、pi 和函数名保留。")
        while self.peek() in ("!", "%"):
            self.take()
        if self.peek() == "^":
            self.take()
            self.unary_syntax(depth + 1)


def inspect_formula(expression):
    return FormulaSyntax(expression).validate()


def builtin_items():
    return [
        dict(
            id=key,
            name=name,
            expression=expression,
            parameter_labels=labels,
            parameters=list(labels),
            angle_mode="deg",
            builtin=True,
            updated_at=None,
        )
        for key, name, expression, labels in BUILTINS
    ]


class SyntaxRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: StrictStr = Field(max_length=500)


class FormulaRequest(SyntaxRequest):
    name: StrictStr = Field(min_length=1, max_length=40)
    parameter_labels: dict[str, StrictStr] = Field(default_factory=dict, max_length=8)
    angle_mode: Literal["deg", "rad"] = "deg"
    updated_at: StrictStr | None = None


class FormulaCalculation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parameters: dict[str, StrictStr] = Field(max_length=8)
    angle_mode: Literal["deg", "rad"] = "deg"
    updated_at: StrictStr | None = None


def check_revision(item, expected):
    if item["builtin"]:
        return
    if expected != item["updated_at"]:
        raise CalculatorError("FORMULA_CONFLICT", "公式已被修改，请重新打开。", 409)


def values_for(body):
    parameters = inspect_formula(body.expression)
    if not body.name.strip():
        raise CalculatorError("INVALID_NAME", "请输入公式名称。")
    if set(body.parameter_labels) - set(parameters):
        raise CalculatorError(
            "INVALID_LABELS", "参数名称与公式不一致，请重新识别参数。"
        )
    labels = {
        key: body.parameter_labels.get(key, key).strip() or key for key in parameters
    }
    if any(len(label) > 40 for label in labels.values()):
        raise CalculatorError("INVALID_LABELS", "参数名称最多 40 个字符。")
    return dict(
        name=body.name.strip(),
        expression=body.expression.strip(),
        parameter_labels=labels,
        angle_mode=body.angle_mode,
    )
