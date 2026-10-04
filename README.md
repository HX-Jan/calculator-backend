# Calculator Backend

在线体验：[Cloudflare 计算器](https://calculator.hongxiang-jan777.workers.dev)。本次上线使用 Python Workers + 静态前端 + D1，参见 [Cloudflare 部署说明](cloudflare/README.md)。计算解析器和公式规则与本机版本共用，SQLite/PostgreSQL 运行方式继续保留。

Python HTTP API for a front-end/back-end separated calculator. The backend validates and evaluates every expression, commits successful results to a database, and serves searchable, paginated history.

配套前端：[calculator-frontend](https://github.com/HX-Jan/calculator-frontend)。本项目由 AI 辅助实现与测试，使用者应理解代码并按课程要求声明辅助范围。

## Environment and installation

- Python 3.13; SQLite is built into Python. PostgreSQL is supported through psycopg.
- Dependencies are pinned in `requirements.txt`; `requirements.in` lists direct dependencies.
- Windows PowerShell (run from this repository):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

macOS/Linux: replace `.venv\Scripts\python.exe` with `.venv/bin/python` and use `cp .env.example .env`.

API documentation: http://127.0.0.1:8000/docs. Health: http://127.0.0.1:8000/api/health.

## Configuration and database initialization

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./calculator.db` | SQLite file relative to the server working directory, or PostgreSQL URL |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated exact frontend origins without trailing slash |

The application creates the `calculation_history` table on startup. Restarting with the same database URL preserves records. Deleting or moving the SQLite file changes the data source. `.env` and database files are excluded from Git.

Production: use a PostgreSQL connection string with TLS, such as `postgresql://USER:PASSWORD@HOST/DB?sslmode=require`. The application converts this to the psycopg SQLAlchemy driver. Set secrets only in the hosting platform, never in Git. Local and hosted databases are independent; local demonstration rows are not uploaded.

## API contract

All successful responses: `{"success":true,"data":...}`. All handled validation/calculation/database errors: `{"success":false,"error":{"code":"...","message":"..."}}`.

| Method | Path | Input | Response |
|---|---|---|---|
| POST | `/api/calculate` | `{"expression":"(1+2)*3"}` | 201: id, expression, result, angle_mode, created_at, steps |
| GET | `/api/history` | `q`, `page` ≥ 1, `page_size` 1–100 (default 20) | 200: items, total, page, page_size |
| DELETE | `/api/history/{id}` | Positive integer id | 200: deleted_id; 404 if absent |
| GET | `/api/health` | None | 200 if a database query succeeds |

```json
{
  "success": true,
  "data": {
    "id": 1,
    "expression": "(1+2)*3",
    "result": "9",
    "angle_mode": "deg",
    "created_at": "2026-09-27T01:00:00+00:00",
    "steps": [
      {
        "operation": "1 + 2",
        "result": "3",
        "label": "加法",
        "before": "(1+2)*3",
        "after": "(3)*3",
        "highlight_start": 1,
        "highlight_end": 4
      },
      {
        "operation": "(3)",
        "result": "3",
        "label": "括号",
        "before": "(3)*3",
        "after": "3*3",
        "highlight_start": 0,
        "highlight_end": 3
      },
      {
        "operation": "3 * 3",
        "result": "9",
        "label": "乘法",
        "before": "3*3",
        "after": "9",
        "highlight_start": 0,
        "highlight_end": 3
      }
    ]
  }
}
```

This is an illustrative response, not a claim about the current database. Results are decimal **strings** to preserve precision in JavaScript. History does not persist the step list; recalculating a reused expression produces fresh steps and a new record.

## Calculation rules

Grammar: `expression → term ((+|-) term)*`; `term → unary ((*|/) unary)*`; `unary → (+|-) unary | power`; `power → primary (!|%)* [^ unary]`; primary includes numbers, constants, parenthesized expressions and function calls.

- Supports decimals, parentheses, unary signs, spaces, `×`/`÷` aliases. Multiplication must be explicit: `2*(3+4)`.
- Supports sqrt, sin, cos, tan, ln, log, pi/π, e, power `^` and factorial `!`. Only whitelisted functions are accepted; no arbitrary code execution.
- Decimal precision: 28 significant digits, round-half-even. `1/3` is rounded, not an exact rational number. This is not arbitrary-precision arithmetic.
- Maximum expression length 500, nesting 32, individual number 28 significant digits, result/intermediate magnitude ≤ `1e100`.
- Empty/invalid expressions and zero division return 400 and do not create history. Failed database commits return 503, not a successful calculation response.
- UTC timestamps; frontend displays the visitor's local time. Search matches literal substrings in expression or result. Ordering: timestamp descending, then id descending.

## Structure and design

```text
app/main.py       HTTP validation, CORS, exception handlers and startup
app/parser.py     Tokenizer and recursive-descent Decimal evaluator
app/service.py    Calculate/save, query and delete use cases
app/scientific.py Whitelisted scientific functions and domain checks
app/formulas.py   Shared formulas, syntax validation and parameter substitution
app/database.py   SQLAlchemy model, engine and sessions
app/errors.py     Client-safe calculation errors
tests/           Parser, persistence and API regression tests
```

No account authentication is implemented. All visitors share demonstration history and custom formulas, including editing and deletion. CORS is not an authentication mechanism. Do not store sensitive input. This is a coursework demo, not a multi-tenant production service.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing -q
.\.venv\Scripts\ruff.exe check app tests
.\.venv\Scripts\ruff.exe format --check app tests
```

Tests use temporary SQLite databases. GitHub Actions also runs the persistence contract against a PostgreSQL service. No user database is cleared by tests.

## Manual deployment

当前公网版本使用 Cloudflare Python Workers、Static Assets 和 D1，部署步骤见 [cloudflare/README.md](cloudflare/README.md)。本机使用 SQLite，独立服务器可使用 PostgreSQL；线上 D1 与本机数据库分离。GitHub Actions 负责验证，发布更新仍需执行部署命令。

See [Cloudflare deployment](cloudflare/README.md) and [code standards](codestyle.md).


## Scientific mode and compatibility

`POST /api/calculate` accepts `{"expression":"sin(pi/2)","angle_mode":"rad"}`. The optional angle_mode is `deg` (default) or `rad`; invalid values return 400. Calculation responses and history entries include this unit. No UI mode field is needed: both keyboards use the same evaluator.

Power is right associative: `2^3^2=512`, `-2^2=-4`, `2^-3=0.125`. Factorial binds before power. Multiplication must remain explicit. Only real numbers are supported. Factorial accepts integers 0–69; negative square roots, nonpositive logarithms, undefined tangent and invalid real powers return errors without saving history. The absolute exponent is limited to 10000, trigonometric arguments to 10^12, and nonzero results below 10^-1000 are rejected to bound display length. The existing upper result bound remains 10^100.

Decimal arithmetic, roots, logarithms and powers use 28-digit precision. Constants carry extra guard digits. Trigonometry uses Python's standard math library and is rounded to 15 significant digits; it is approximate, with reduced accuracy near singularities and for large radian inputs. Exact degree quadrants are normalized; tiny results are not generally rounded to zero. Steps include DEG/RAD for trigonometry.

Startup performs an additive, repeatable SQLite/PostgreSQL upgrade, adding angle_mode with default `deg` to old history. Back up the database before a deployment upgrade. Existing IDs, expressions, results and timestamps are retained. Deploy the backend before the updated frontend so the optional request field is accepted.


## 扩展科学功能

科学键盘使用 2nd 切换两页。新增 asin/acos/atan、sinh/cosh/tanh 及其反函数、abs、exp、cbrt、floor/ceil。反三角函数输出遵循 DEG/RAD；双曲函数及其反函数不使用角度单位。

双参数函数使用逗号分隔：`root(x,n)`（n 次方根）、`logbase(x,b)`（底 b）、`mod(x,y)`（余数符号跟随 x）、`perm(n,r)`、`comb(n,r)`。排列组合仅接受 `0 ≤ r ≤ n ≤ 1000` 的整数，结果仍受范围限制。负数仅支持整数奇次根。

EXP 输入 E，例如 `1.2E-3`；也接受小写 e。常量 e 单独使用，乘法需明确输入。百分号固定表示除以 100，`200+10%` 为 `200.1`，`200*10%` 为 `20`。

Ans 插入上次成功结果；MS 存储当前结果，MR 读取，MC 清除。Ans 和存储仅在当前页面会话保留，AC 不清除存储。所有数值运算仍通过后端。函数键优先包裹选区；双参数函数打开输入窗口，确认后生成完整表达式，按等号计算。

三角、反三角、双曲及反双曲函数为约 15 位有效数字的浮点近似；根和对数也可能产生舍入。仅支持实数。本次不含矩阵、复数、方程和统计模块。


## 连续计算与编辑体验

计算完成后，数字、小数点和常量开始新表达式；运算符接着当前结果计算。点击输入框或用方向键移动光标后，可继续编辑原表达式。未修改表达式时重复等号不重复保存历史。

函数键包裹选区或光标前完整操作数；没有操作数时自动配对括号。平方、立方、倒数、正负号在结果状态下直接提交后端运算。任意根、任意底对数、排列组合和取余通过双参数窗口输入，确认后按等号。取消不改变算式。

结果可复制原始十进制字符串，也可切换科学计数显示；显示切换不使用浮点数，不改变计算值。Ans、存储和连续计算始终复用原始值，长数以等值科学计数输入。网络或计算错误保留输入；所有实际计算仍调用后端。科学键盘适配 1366×768 桌面，手机端保留较大触控目标。

## Error location contract

Calculation errors may include `position` and `end_position` in the existing `error` object. They are zero-based UTF-16 offsets into the exact submitted expression, with an exclusive end. A zero-length range marks an insertion point, including missing input at the end. The fields are optional: older clients can ignore them, and transport/database errors do not have source locations.

Example: `2+*3` returns an error range `[2,3)`. Leading whitespace and aliases such as π/×/÷ retain their original source locations even when normalized for evaluation. Invalid scientific arguments include specific domain messages; where possible the range covers the offending argument. Failed calculations never create history. The frontend's undo/redo changes the expression only and does not delete saved records.


## 逐步化简接口

计算响应的 `steps` 保留 `operation`、`result` 字符串，新增 `before`、`after`、`label` 字符串及 `highlight_start`、`highlight_end` 整数。范围针对该步 `before` 的 UTF-16 下标，左闭右开，可直接用于 JavaScript `slice`。每一步的 `after` 等于下一步的 `before`，最后一步等于响应的 `result`。

轨迹按解析器实际求值顺序产生，以原始源码范围定位，避免重复子表达式误替换。负数中间值保留必要括号；括号整理、常量读取和最终精度整理会在需要时单独显示。数字全程以字符串传输，展示轨迹不应作为新输入重新计算（内部常量精度可能高于输入限制）。所有步骤可能含舍入值，不是符号证明。

无需数据库迁移；历史不保存步骤。旧客户端仍可读取原字段，新前端对只有旧字段的响应提供列表回退。发布时先更新后端，再更新前端。

## Shared formula API

Formulas are shared by all visitors, without accounts. Builtins are server constants, not database seeds. The new `formulas` table stores name, expression, JSON parameter labels, angle mode, and timestamps. `create_all` adds this table on startup in SQLite/PostgreSQL; existing history data and columns are unchanged by the formula feature.

| Method | Path | Request / behavior |
|---|---|---|
| GET | `/api/formulas?q=` | Search names, return `data.items`; builtins first, custom entries newest first |
| POST | `/api/formulas/validate` | `{ "expression": "1/x" }` → `data.parameters: ["x"]`; syntax only, no formula evaluation |
| POST | `/api/formulas` | Create from name, expression, parameter_labels and angle_mode; returns 201 and full formula |
| PUT | `/api/formulas/{id}` | Same fields plus original updated_at; replace custom formula |
| DELETE | `/api/formulas/{id}?updated_at=…` | Confirmed deletion using original revision; returns deleted_id |
| POST | `/api/formulas/{id}/calculate` | parameters, angle_mode, updated_at; returns 201 and the existing calculation response structure |

Example creation:

```json
{"name":"倒数","expression":"1/x","parameter_labels":{"x":"输入值"},"angle_mode":"deg"}
```

Returned formula: string `id`, `name`, `expression`, ordered `parameters`, `parameter_labels`, `angle_mode`, `builtin`, `updated_at`; custom records also include `created_at`. Builtins have stable string IDs `circle-area`, `circle-length`, `hypotenuse`, `quadratic`, and null updated_at. Custom IDs are decimal strings. Dates are UTC ISO 8601. Preserve updated_at exactly for edits, deletion and calculation of custom formulas.

Example calculation body:

```json
{"parameters":{"x":"1/3"},"angle_mode":"deg","updated_at":"<original returned timestamp>"}
```

Name must be nonblank and at most 40 characters. Expressions retain the 500-character and 32-depth bounds. Parameters are single lowercase letters except e, at most 8 in first-appearance order; pi/e and all existing function names remain reserved. Parameter labels are optional, default to their letters, and have a 40-character bound. No implicit multiplication. Zero-parameter formulas are allowed. Validation accepts `1/x` and domain-dependent formulas such as `sqrt(-1)+x`, but rejects invalid syntax and invalid numeric literals without saving history.

All parameter values use the existing numeric expression parser in the selected angle mode and cannot reference variables. Missing/extra parameters fail. Only whole tokens are substituted, each wrapped in parentheses, preserving signs and precedence. The expanded expression must fit 500 characters. Calculation saves exactly one history record; invalid parameters, domain errors or revision conflicts save none. History stores the expanded expression and angle mode, independent of the formula thereafter.

Errors use the normal envelope. Parameter errors additionally contain `error.parameter` (letter); their position offsets refer to that parameter expression. Other evaluation errors refer to the expanded expression. Revision mismatch returns HTTP 409 `FORMULA_CONFLICT`; missing formula returns 404; modifying/deleting a builtin returns 403 `READ_ONLY`. PUT/DELETE use conditional timestamp checks atomically. All builtin and custom calculations stay on the backend; no eval or frontend numerical evaluation is introduced.


## Current verification / 当前交付状态

功能基线核对于 2026-10-02：后端 CI 220 项通过（含 PostgreSQL），前端 12 项测试、语法及构建通过。[验证摘要](docs/VERIFICATION.md)。支持科学运算、逐步化简与共享公式库。公开 GitHub 仓库不代表已部署公网；公网入口尚待实际部署验收。
