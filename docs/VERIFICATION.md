# 功能与验证记录

核对日期：2026-10-05。网站入口：https://calculator.assignment1.workers.dev 。

| 检查项目 | 当前结果与依据 |
|---|---|
| 后端 CI | 234 项通过，覆盖率 98%，包括 PostgreSQL；[检查记录](https://github.com/HX-Jan/calculator-backend/actions) |
| 前端 CI | 20 项测试、语法检查和构建通过；[检查记录](https://github.com/HX-Jan/calculator-frontend/actions) |
| 本地后端既有记录 | 231 项通过；未配置 PostgreSQL，相关 3 项跳过 |
| 博客配图 | 两版各 22 张：19 张新版运行截图共用，3 张设计图按语言区分；6.17 半径输入为 9 |
| 项目预览 | README 预览图对应新版科学模式，历史已采用数学排版 |
| Cloudflare 配置 | Worker 名称 calculator，D1 绑定及同源 API 保持不变 |

## 功能实现

| 功能 | 代码或文件 |
|---|---|
| 四则、科学函数、优先级及精度 | 后端 `app/parser.py`、`app/scientific.py` |
| 后端返回字符串结果 | 后端计算路由；前端 `src/api.js`、`src/result-view.js` |
| 历史搜索、分页、指定删除 | 后端 `app/service.py`、`app/main.py`；线上 `app/cloudflare.py` |
| SQLite/PostgreSQL 与线上 D1 | 后端 `app/database.py`、`migrations/0001_cloudflare.sql` 和 Workers 绑定 |
| 函数包裹、连续计算、100 步撤销重做 | 前端 `src/expression-editor.js`、`src/main.js` |
| 逐步化简与 UTF-16 高亮 | 后端 `app/parser.py`；前端 `src/steps-view.js` |
| 公式校验、参数代入、编辑冲突 | 后端 `app/formula_rules.py`、`app/formulas.py`、`app/cloudflare.py`；前端 `src/formula-library.js` |
| 普通/科学、DEG/RAD、主题和手机布局 | 前端 `index.html`、`src/main.js`、`src/style.css` |
| 乘除符号、π 及历史复用 | 前端 `src/expression-editor.js`、`src/history-utils.js`、`src/main.js` |
| 根号、上标、多次方根和分式展示 | 前端 `src/formula-notation.js`、`src/formula-view.js`；本地打包 KaTeX |
| 历史当前页 CSV 导出 | 前端 `src/history-utils.js` |

## 计算与展示规则

数学排版用于公式列表、编辑预览、参数窗口、历史和删除确认。编辑与计算保留原表达式语法；展示时省略乘号不代表支持隐式乘法。输入框中的乘除显示为 ×、÷，历史复用还将 pi 显示为 π。复制和 CSV 使用原始表达式；结果继续按字符串保存、显示和复用。

既有浏览器检查覆盖连续计算、重复等号、撤销、错误选区、角度切换、历史搜索与复用、确认删除、公式参数代入、复制及科学计数。数学排版回归包括 sqrt(9)+2^3=11、(-2)^2=4、-2^2=-4、2^3^2=512、root(32,5)=2 及 1/3；保留负数括号与乘方结合顺序。

390px 深色视口中，长历史公式在自身区域横向滚动，页面宽度仍为 390px。运行图片来自本地 Edge 浏览器；手机图是视口截图。网络失败图通过阻断请求模拟。19 张运行图均已在最新符号及历史排版版本下重新拍摄。

## 数据与检查范围

历史结果使用 TEXT；旧 PostgreSQL 限长列的幂等升级保留已有数据，相关 CI 覆盖长结果保存及旧表迁移。历史与自定义公式共享，没有账号隔离。

本轮整理核对远端提交、最新自动检查、文档及配图，不新增公网可访问性检测或负载测试。测试客户端的一条 Starlette/httpx 弃用提示不影响既有检查通过。
