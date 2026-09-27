# Python code standards

Sources: [PEP 8](https://peps.python.org/pep-0008/), [PEP 257](https://peps.python.org/pep-0257/), and [Ruff formatter](https://docs.astral.sh/ruff/formatter/). This project adopts these conventions with an explicit 88-character line-length adaptation.

- Four spaces for indentation; UTF-8; final newline. Use Ruff for formatting and imports.
- `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
- Keep HTTP handling, calculation logic, business operations and database models separate.
- Public calculation interfaces use type annotations and concise docstrings. Comments explain intent and constraints.
- No `eval`, `exec`, arbitrary code compilation or shell execution of expressions.
- Only validated arithmetic tokens reach the evaluator. Bound input length, nesting and numeric magnitude.
- Use Decimal for arithmetic, strings for serialized decimal values and timezone-aware timestamps.
- SQLAlchemy binds query values. Never concatenate user input into SQL.
- Commit before reporting successful writes. Roll back failures. Do not expose credentials or raw database errors to clients or logs.
- Parameterize edge-case tests; test observable behavior, persistence and failure modes.
- Before commit: `ruff check app tests`, `ruff format --check app tests`, and `python -m pytest -q`.
- Never commit `.env`, credentials, databases, `.venv`, caches or private user information.
