# 功能与验证记录

核对日期：2026-10-04。网站入口：https://calculator.assignment1.workers.dev 。

| 检查项目 | 结果与依据 |
|---|---|
| 后端 CI | 234 项通过，覆盖率 98%，包括 PostgreSQL；[检查记录](https://github.com/HX-Jan/calculator-backend/actions/runs/37205630414) |
| 前端 CI | 12 项测试、语法检查和构建通过；[检查记录](https://github.com/HX-Jan/calculator-frontend/actions/runs/37206694865) |
| 本地后端 | 231 项通过；未配置 PostgreSQL，相关 3 项跳过 |
| 配图 | 19 张本地运行截图；3 张设计图已补齐线上 D1 和错误分支，并移除功能图底部旧说明 |
| Cloudflare 配置 | Worker 名称 calculator，D1 绑定为原 calculator 数据库，账号子域名 assignment1 |
| 当前网址访问 | DNS 记录存在；当前网络连接重置，未完成新网址的端到端复验 |

## 功能实现

| 功能 | 代码或文件 |
|---|---|
| 四则、科学函数、优先级及精度 | 后端 `app/parser.py`、`app/scientific.py` |
| 结果由后端计算并返回字符串 | 后端计算路由；前端 `src/api.js`、`src/result-view.js` |
| 历史搜索、分页、指定删除 | 后端 `app/service.py`、`app/main.py`；Cloudflare 使用 `app/cloudflare.py` |
| SQLite/PostgreSQL 与线上 D1 | 后端 `app/database.py`、`migrations/0001_cloudflare.sql` 和 Workers 绑定 |
| 函数包裹、连续计算、100 步撤销重做 | 前端 `src/expression-editor.js`、`src/main.js` |
| 逐步化简与 UTF-16 高亮 | 后端 `app/parser.py`；前端 `src/steps-view.js` |
| 公式校验、参数代入、版本冲突 | 后端 `app/formula_rules.py`、`app/formulas.py`、`app/cloudflare.py`；前端 `src/formula-library.js` |
| 普通/科学、DEG/RAD、主题和手机布局 | 前端 `index.html`、`src/main.js`、`src/style.css` |
| 历史当前页 CSV 导出 | 前端 `src/history-utils.js` |

测试覆盖计算规则、数据库持久化、公式参数与版本冲突，以及前端输入编辑、撤销重做和结果格式化。

此前 Cloudflare 原地址完成过科学运算、公式增删改、冲突、非法输入及重部署后持久化检查。它们不是新地址的复验结果。界面截图仍为 2026-10-02 本地运行画面；390px 截图是浏览器视口，网络失败通过请求阻断模拟。

历史及公式共享，没有账号隔离。未进行大规模并发测试；测试客户端有一条 Starlette/httpx 弃用提示。
