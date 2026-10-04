# Calculator Backend

[简体中文](README.md) | **English**

A Python/FastAPI HTTP API for expression validation, safe evaluation, simplification traces, persistent history and shared formulas. Uses a function whitelist and recursive-descent parser, without `eval`.

[Live site](https://calculator.assignment1.workers.dev) · [Frontend repository](https://github.com/HX-Jan/calculator-frontend) · [Cloudflare deployment (Chinese)](cloudflare/README.md)

## Project information

Owner: [Hong Xiang / HX-Jan](https://github.com/HX-Jan), responsible for requirements, interface decisions and iteration priorities. [Development notes](docs/DEVELOPMENT.en.md)

## Environment and setup

Python 3.13; SQLite is bundled with Python. PostgreSQL uses psycopg. Dependencies are pinned in `requirements.txt`; direct dependencies are listed in `requirements.in`.

Run from the repository directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On macOS/Linux, use `.venv/bin/python` and `cp .env.example .env`.

API documentation: http://127.0.0.1:8000/docs. Health: http://127.0.0.1:8000/api/health.

## Configuration and storage

| Setting | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./calculator.db` | Local SQLite file or PostgreSQL URL |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated exact origins without trailing slash |

The local app creates `calculation_history` and `formulas` on startup. Restarting with the same URL preserves data; moving or deleting SQLite changes the data source. Results use TEXT; older bounded PostgreSQL result columns are upgraded to TEXT. Idempotent SQLite/PostgreSQL migrations add angle_mode with default deg to older history, preserving records. Back up databases before upgrades.

Separate servers can use `postgresql://USER:PASSWORD@HOST/DB?sslmode=require`, converted to the psycopg SQLAlchemy driver. Cloudflare uses D1 independently of local data; local demonstration records are not uploaded. Store secrets only on the hosting platform. `.env` and database files are excluded from Git.

## Calculation and history APIs

Success: `{"success":true,"data":...}`. Handled errors: `{"success":false,"error":{"code":"...","message":"..."}}`.

| Method | Path | Input and response |
|---|---|---|
| POST | `/api/calculate` | expression; optional angle_mode deg (default) or rad; 201 returns id, expression, result, angle_mode, created_at, steps |
| GET | `/api/history` | q, page ≥ 1, page_size 1–100 (default 20); 200 returns items, total, page, page_size |
| DELETE | `/api/history/{id}` | Positive integer ID; 200 returns deleted_id, 404 if missing |
| GET | `/api/health` | 200 when a database query succeeds |

```json
{"expression":"sin(pi/2)","angle_mode":"rad"}
```

Results are decimal strings to preserve JavaScript precision. History does not store steps; recalculation generates fresh steps and a new record. Successful calculations commit before returning. Empty/invalid expressions and division by zero return 400 without saving; failed commits return 503.

Timestamps are UTC; the frontend uses local time. Search matches literal substrings in expression/result. Records are ordered by timestamp descending, then ID descending.

## Rules and precision

```text
expression → term ((+|-) term)*
term       → unary ((*|/) unary)*
unary      → (+|-) unary | power
power      → primary (!|%)* [^ unary]
```

Primary includes numbers, constants, parentheses and whitelisted calls. Spaces, ×/÷ aliases and π are supported. Multiplication must be explicit, as in `2*(3+4)`.

- Powers associate right: `2^3^2=512`, `-2^2=-4`, `2^-3=0.125`. Factorial binds before power.
- Arithmetic, roots, logarithms and powers use 28-significant-digit Decimal with round-half-even. Constants retain guard digits. `1/3` is rounded, not an exact fraction or arbitrary-precision result.
- Trigonometric, inverse trigonometric, hyperbolic and inverse hyperbolic functions use the standard math library at about 15 significant digits. Accuracy decreases near singularities and for large radian inputs. Exact degree quadrants are normalized; small values are not generally rounded to zero.
- Limits: 500 expression characters, 32 nesting levels, 28 significant digits per literal, result/intermediate magnitude at most `1e100`; nonzero results below `1e-1000` are rejected.
- Absolute exponents are limited to 10000, trigonometric inputs to `1e12`. Factorial accepts integers 0–69.
- Real numbers only. Negative square roots, nonpositive logarithms, undefined tangent and invalid real powers return concise errors.

Functions include sqrt, sin/cos/tan, asin/acos/atan, sinh/cosh/tanh and their inverses, ln, log, abs, exp, cbrt, floor/ceil, pi/e, `^`, `!` and `%`. Inverse trigonometry follows DEG/RAD; hyperbolic functions ignore angle units.

Two-argument functions: `root(x,n)`, `logbase(x,b)`, `mod(x,y)`, `perm(n,r)`, `comb(n,r)`. Negative values require integer odd roots; remainder follows the sign of x. Permutations/combinations accept integers `0 ≤ r ≤ n ≤ 1000`, subject to result bounds.

Scientific notation accepts `1.2E-3` and lowercase e. Standalone e requires explicit multiplication. Percent always divides by 100: `200+10% = 200.1`, `200*10% = 20`. Matrices, complex numbers, equation solving and statistics are outside this version.

## Error locations and steps

Errors may include error.position and error.end_position: zero-based UTF-16 offsets into the exact submitted expression, with an exclusive end. Zero-length ranges indicate insertion points. `2+*3` maps to `[2,3)`. Spaces and π/×/÷ keep original offsets. Network/database errors have no source location; older clients may ignore optional fields.

Steps retain operation/result strings and include before, after, label, highlight_start and highlight_end. Highlights refer to the step's before string in UTF-16, suitable for JavaScript slice. Each after matches the next before; the final step matches the result.

Traces follow actual evaluation order and source ranges, handling repeated operands, negative replacements, bracket cleanup, constants and final precision. Trigonometric steps include DEG/RAD. Traces may be rounded, are not symbolic proofs and should not be evaluated as new input; internal constant precision can exceed literal limits. Steps are not stored in history and require no new database columns. Older clients can read the original fields. For separate deployments, update the backend first.

## Shared formula APIs

Builtins are fixed server definitions rather than repeated database seeds: circle area, circumference, the Pythagorean theorem and quadratic evaluation. Custom formulas store names, expressions, parameter labels, angle units and timestamps. SQLAlchemy uses JSON labels; D1 uses JSON-encoded TEXT.

| Method | Path | Request and behavior |
|---|---|---|
| GET | `/api/formulas?q=` | Name search; data.items lists builtins first, custom entries newest first |
| POST | `/api/formulas/validate` | expression; parameters in first-appearance order, syntax only |
| POST | `/api/formulas` | name, expression, parameter_labels, angle_mode; 201 returns full formula |
| PUT | `/api/formulas/{id}` | Same fields plus original updated_at; update custom formula |
| DELETE | `/api/formulas/{id}?updated_at=…` | Delete using original revision; returns deleted_id |
| POST | `/api/formulas/{id}/calculate` | parameters, angle_mode, updated_at; 201 returns standard calculation structure |

Creation example:

```json
{"name":"Reciprocal","expression":"1/x","parameter_labels":{"x":"Input"},"angle_mode":"deg"}
```

Calculation example:

```json
{"parameters":{"x":"1/3"},"angle_mode":"deg","updated_at":"<original returned timestamp>"}
```

Returned fields: id, name, expression, ordered parameters, parameter_labels, angle_mode, builtin, updated_at; custom entries also include created_at. All IDs are strings. Builtin IDs are circle-area, circle-length, hypotenuse, quadratic, with null updated_at. Custom IDs are decimal strings and timestamps are UTC ISO 8601. Preserve the exact updated_at for editing, deleting and calculating custom entries.

Names must be nonblank and at most 40 characters; labels allow 40; expressions allow 500 and depth 32. Up to eight single lowercase parameters excluding e are allowed; pi and function names are reserved. Labels default to letters. Zero-parameter formulas are supported, implicit multiplication is not. Saving checks syntax and numeric literals only: `1/x` and `sqrt(-1)+x` may be saved, with domains checked after substitution.

Parameter values use existing scientific expressions in the same angle unit, without variable references. Missing/extra values fail. Whole variable tokens are replaced by parenthesized expressions, within 500 total characters, using the safe parser. Success saves exactly one expanded-expression history record; errors save none. Deleting formulas does not affect historical reuse.

Parameter errors include error.parameter, with offsets into that parameter expression; overall errors refer to the expanded expression. Conflicts return 409 FORMULA_CONFLICT, missing entries 404, and builtin edits/deletion 403 READ_ONLY. Updates/deletes check timestamps atomically.

## Structure

| File | Responsibility |
|---|---|
| `app/main.py` | Local HTTP validation, CORS, errors and startup |
| `app/parser.py` | Tokenization, recursive descent and traces |
| `app/scientific.py` | Whitelisted functions and domains |
| `app/service.py` | Calculation persistence, history and deletion |
| `app/database.py` | SQLAlchemy models, migrations and sessions |
| `app/formulas.py` | SQLite/PostgreSQL formula routes and revisions |
| `app/formula_rules.py` | Formula syntax, substitution and builtins |
| `app/cloudflare.py` | D1 API adapter |
| `cloudflare/src/entry.py` | Python Workers ASGI entrypoint |
| `migrations/0001_cloudflare.sql` | D1 initialization |
| `app/errors.py` / `tests/` | Error types and regression tests |

History/formulas are shared and editable/deletable by all visitors. There is no account isolation; CORS is not authentication. Do not enter sensitive data.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing -q
.\.venv\Scripts\ruff.exe check app tests
.\.venv\Scripts\ruff.exe format --check app tests
```

Tests use temporary SQLite databases and a PostgreSQL CI service, without clearing user databases. As of 2026-10-04, CI passed 234 tests with 98% coverage. Locally, 231 passed and three PostgreSQL tests were skipped because no database was configured. Frontend passed 12 tests and build. [Verification (Chinese)](docs/VERIFICATION.md)

## Deployment

Production uses Python Workers, Workers Static Assets and D1, sharing parser/formula rules with the local app. Local SQLite and separate-server PostgreSQL remain supported. See [Cloudflare guide (Chinese)](cloudflare/README.md) and [code standards](codestyle.md). GitHub Actions checks code without automatic deployment.

Current site: https://calculator.assignment1.workers.dev. DNS records, deployment and D1 bindings are confirmed. Connections reset on the current network; end-to-end access on the current domain and direct mainland-China access have not been reverified.
