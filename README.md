# 计算器后端

**简体中文** | [English](README.en.md)

基于 Python/FastAPI 的计算器 HTTP API，负责表达式校验、安全求值、逐步化简、历史持久化和共享公式库。使用函数白名单与递归下降解析器，不使用 `eval`。

[在线体验](https://calculator.assignment1.workers.dev) · [前端仓库](https://github.com/HX-Jan/calculator-frontend) · [Cloudflare 部署](cloudflare/README.md)

技术栈：Python 3.13、FastAPI、Pydantic、SQLAlchemy；本地 SQLite/独立服务器 PostgreSQL，Cloudflare 版本使用 Python Workers 与 D1。

## 项目信息

负责人：[洪翔 / HX-Jan](https://github.com/HX-Jan)，负责需求规划、界面方案和功能迭代方向。[开发说明](docs/DEVELOPMENT.md)

## 环境与运行

Python 3.13；SQLite 随 Python 提供，PostgreSQL 通过 psycopg 支持。依赖锁定在 `requirements.txt`，直接依赖列于 `requirements.in`。

在仓库目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

macOS/Linux 将 Python 路径改为 `.venv/bin/python`，使用 `cp .env.example .env`。

接口文档：http://127.0.0.1:8000/docs 。健康检查：http://127.0.0.1:8000/api/health 。

## 配置与存储

| 配置 | 默认值 | 用途 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./calculator.db` | 本地 SQLite 文件或 PostgreSQL 连接地址 |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 逗号分隔的精确来源，不带末尾斜杠 |

本地服务启动创建 `calculation_history` 和 `formulas` 表。同一数据库地址重启保留数据；移动或删除 SQLite 文件会改变数据源。历史结果使用 TEXT，旧 PostgreSQL 限长结果列自动升级为 TEXT。旧历史表通过幂等 SQLite/PostgreSQL 迁移补充默认 `deg` 的 `angle_mode`，保留原记录；升级前应备份数据库。

独立服务器可使用 `postgresql://USER:PASSWORD@HOST/DB?sslmode=require`，自动转换为 psycopg SQLAlchemy 驱动。Cloudflare 线上版本使用 D1，与本地数据库分离；不会上传本地演示记录。密钥仅存放在部署平台，`.env` 和数据库文件不提交。

## 计算与历史接口

成功返回 `{"success":true,"data":...}`；已处理的错误返回 `{"success":false,"error":{"code":"...","message":"..."}}`。

| 方法 | 路径 | 输入及响应 |
|---|---|---|
| POST | `/api/calculate` | expression；可选 angle_mode 为 deg（默认）或 rad；201 返回 id、expression、result、angle_mode、created_at、steps |
| GET | `/api/history` | q、page ≥ 1、page_size 1–100（默认 20）；200 返回 items、total、page、page_size |
| DELETE | `/api/history/{id}` | 正整数 ID；200 返回 deleted_id，不存在返回 404 |
| GET | `/api/health` | 数据库查询成功返回 200 |

```json
{"expression":"sin(pi/2)","angle_mode":"rad"}
```

结果始终是十进制字符串，避免 JavaScript 精度损失。历史不保存步骤，复用算式重新计算生成新步骤与记录。成功结果先提交数据库再返回；空输入、非法算式和除零返回 400，不写历史，数据库提交失败返回 503。

时间戳为 UTC，前端转为当地时间。搜索对算式和结果做字面子串匹配；先按时间倒序，再按 ID 倒序。

## 运算规则与精度

```text
expression → term ((+|-) term)*
term       → unary ((*|/) unary)*
unary      → (+|-) unary | power
power      → primary (!|%)* [^ unary]
```

primary 包括数字、常量、括号表达式和白名单函数调用。支持空格、×/÷ 别名及 π；不支持隐式乘法，应写 `2*(3+4)`。

- 乘方右结合：`2^3^2=512`；`-2^2=-4`；`2^-3=0.125`。阶乘优先于乘方。
- 四则、根、对数和乘方使用 28 位有效数字 Decimal，采用银行家舍入；常量保留额外保护位。`1/3` 为舍入值，不是精确分数或任意精度计算。
- 三角、反三角、双曲及反双曲函数使用标准数学库，约 15 位有效数字。在奇点附近或巨大弧度输入时精度下降。角度制精确象限做归一化，不普遍把小数值舍为零。
- 表达式最多 500 字符、嵌套 32 层、单个数值 28 位有效数字；结果及中间值绝对值不超过 `1e100`，非零结果小于 `1e-1000` 拒绝。
- 指数绝对值最多 10000，三角函数输入绝对值最多 `1e12`。阶乘只接受 0–69 整数。
- 只支持实数。负数开方、非正对数、未定义正切及非法实数乘方返回简短错误。

支持 sqrt、sin/cos/tan、asin/acos/atan、sinh/cosh/tanh 及其反函数、ln、log、abs、exp、cbrt、floor/ceil、pi/e、`^`、`!` 和 `%`。反三角输出遵循 DEG/RAD；双曲函数不使用角度单位。

双参数函数：`root(x,n)`、`logbase(x,b)`、`mod(x,y)`、`perm(n,r)`、`comb(n,r)`。负数只接受整数奇次根，余数符号跟随 x；排列组合接受 `0 ≤ r ≤ n ≤ 1000` 的整数，仍受结果范围限制。

支持 `1.2E-3` 或小写 e 的科学计数法，常量 e 独立使用，乘号不能省略。百分号固定除以 100：`200+10% = 200.1`，`200*10% = 20`。矩阵、复数、方程求解及统计不在本版本范围内。

## 错误定位与计算步骤

计算错误可附带 `error.position`、`error.end_position`，针对提交原文的 UTF-16 下标，零起点、左闭右开；零长度范围表示插入位置。例如 `2+*3` 对应 `[2,3)`。空格和 π/×/÷ 的源码位置保持准确。网络及数据库错误没有源码位置，旧客户端可忽略可选字段。

steps 保留字符串 `operation`、`result`，另含 `before`、`after`、`label` 和整数 `highlight_start`、`highlight_end`。高亮针对该步 before 的 UTF-16 范围，可直接用于 JavaScript slice；每步 after 等于下一步 before，最后一步与结果一致。

轨迹记录实际求值顺序与源码范围，支持重复子表达式、负数替换、括号整理、常量读取与最终精度处理。三角相关步骤标记 DEG/RAD。轨迹可能舍入，不是符号证明，也不应作为新输入重新计算，内部常量精度可能高于输入限制。历史不存步骤，无需为步骤增加数据库字段；旧前端仍可读取原字段。更新独立前后端时先发布后端。

## 共享公式接口

内置公式固定由服务端提供，不重复写入数据库：圆面积、圆周长、勾股定理、二次函数求值。自定义公式表保存名称、表达式、参数标签、角度单位和时间戳；SQLAlchemy 使用 JSON 标签列，D1 使用 JSON 编码的 TEXT。

| 方法 | 路径 | 请求及行为 |
|---|---|---|
| GET | `/api/formulas?q=` | 名称搜索；data.items 中内置优先，自定义按新到旧 |
| POST | `/api/formulas/validate` | expression；返回按首次出现顺序排列的 parameters，只校验语法 |
| POST | `/api/formulas` | name、expression、parameter_labels、angle_mode；201 返回完整公式 |
| PUT | `/api/formulas/{id}` | 相同字段及原 updated_at；更新自定义公式 |
| DELETE | `/api/formulas/{id}?updated_at=…` | 使用原版本删除，返回 deleted_id |
| POST | `/api/formulas/{id}/calculate` | parameters、angle_mode、updated_at；201 返回标准计算结构 |

创建示例：

```json
{"name":"倒数","expression":"1/x","parameter_labels":{"x":"输入值"},"angle_mode":"deg"}
```

代入示例：

```json
{"parameters":{"x":"1/3"},"angle_mode":"deg","updated_at":"<原响应时间戳>"}
```

公式返回 id、name、expression、按顺序的 parameters、parameter_labels、angle_mode、builtin、updated_at；自定义项另含 created_at。ID 均为字符串；内置 ID 为 circle-area、circle-length、hypotenuse、quadratic，updated_at 为 null。自定义 ID 为十进制字符串，时间为 UTC ISO 8601，修改、删除和计算保留原始 updated_at。

名称非空且最多 40 字，参数标签最多 40 字，公式最多 500 字符与 32 层。参数最多 8 个单个小写字母，排除 e；pi 和函数名保留，标签默认字母。支持无参数公式，不支持隐式乘法。保存只校验语法与数字字面量，因此 `1/x` 和 `sqrt(-1)+x` 可保存；定义域在代入后检查。

参数支持现有科学表达式，使用同一角度单位，不能引用变量；缺失或多余参数报错。后端按完整变量标记替换，每项加括号，总长度最多 500 字符，沿用安全解析器。成功只写一条展开算式历史，失败不写；删除公式不影响历史复用。

参数错误含 error.parameter，其位置针对参数表达式；整体错误位置针对展开算式。版本冲突返回 409 FORMULA_CONFLICT，缺失返回 404，修改/删除内置项返回 403 READ_ONLY。更新与删除原子检查时间戳。

## 目录结构

| 文件 | 职责 |
|---|---|
| `app/main.py` | 本地 HTTP 校验、CORS、异常处理与启动 |
| `app/parser.py` | 分词、递归下降求值与步骤轨迹 |
| `app/scientific.py` | 科学函数白名单和定义域 |
| `app/service.py` | 计算保存、历史查询与删除 |
| `app/database.py` | SQLAlchemy 模型、迁移与会话 |
| `app/formulas.py` | SQLite/PostgreSQL 公式路由和版本检查 |
| `app/formula_rules.py` | 公式语法、参数代入和内置项 |
| `app/cloudflare.py` | D1 API 适配 |
| `cloudflare/src/entry.py` | Python Workers ASGI 入口 |
| `migrations/0001_cloudflare.sql` | D1 初始化 |
| `app/errors.py` / `tests/` | 错误类型与回归测试 |

历史和公式均共享，所有访问者可读写和删除，没有账号隔离；CORS 不是身份认证，不应录入敏感数据。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing -q
.\.venv\Scripts\ruff.exe check app tests
.\.venv\Scripts\ruff.exe format --check app tests
```

测试使用临时 SQLite，CI 另有 PostgreSQL 服务，不清空用户数据库。截至 2026-10-04，CI 234 项通过、覆盖率 98%；本地 231 项通过、3 项 PostgreSQL 测试因未配置数据库跳过。前端 12 项及构建通过。[验证记录](docs/VERIFICATION.md)

## 部署

线上采用 Python Workers、Workers Static Assets 和 D1，与本机共用解析器和公式规则。本机仍支持 SQLite，独立服务器支持 PostgreSQL。部署命令见 [Cloudflare 指南](cloudflare/README.md)，代码规范见 [codestyle.md（英文）](codestyle.md)。GitHub Actions 只检查，不自动部署。

当前网址：https://calculator.assignment1.workers.dev 。域名记录、部署及 D1 绑定已确认，但当前网络连接重置，新域名端到端访问及国内直连尚未复验。
