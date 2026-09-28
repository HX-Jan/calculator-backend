# Clarity Calculator Backend

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
      {"operation": "1 + 2", "result": "3"},
      {"operation": "3 * 3", "result": "9"}
    ]
  }
}
```

This is an illustrative response, not a claim about the current database. Results are decimal **strings** to preserve precision in JavaScript. History does not persist the step list; recalculating a reused expression produces fresh steps and a new record.

## Calculation rules

Grammar: `expression → term ((+|-) term)*`; `term → unary ((*|/) unary)*`; `unary → (+|-) unary | power`; `power → primary (!)* [^ unary]`; primary includes numbers, constants, parenthesized expressions and function calls.

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
app/database.py   SQLAlchemy model, engine and sessions
app/errors.py     Client-safe calculation errors
tests/           Parser, persistence and API regression tests
```

No account authentication is implemented. All visitors share the demonstration history and may delete records. CORS is not an authentication mechanism. Do not store sensitive input. This is a coursework demo, not a multi-tenant production service.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing -q
.\.venv\Scripts\ruff.exe check app tests
.\.venv\Scripts\ruff.exe format --check app tests
```

Tests use temporary SQLite databases. GitHub Actions also runs the persistence contract against a PostgreSQL service. No user database is cleared by tests.

## Manual deployment

Render: Python 3.13, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health path `/api/health`. Set `DATABASE_URL` to Neon PostgreSQL and `ALLOWED_ORIGINS` to your frontend HTTPS origin. Do not use SQLite on Render's free ephemeral filesystem. The free service can sleep; allow for cold starts. No public deployment is included in this repository upload.

See [Render FastAPI guide](https://render.com/docs/deploy-fastapi), [free service limitations](https://render.com/docs/free), and [code standards](codestyle.md).


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
