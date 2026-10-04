# Cloudflare 部署

线上地址：https://hx-jan-calculator.hongxiang-jan777.workers.dev

Python Workers 运行 FastAPI 和原有安全计算引擎；Workers Static Assets 托管前端；D1 保存历史和共享公式。前后端同域，无须跨域配置、服务器或独立 PostgreSQL。原来的 SQLite/PostgreSQL 部署仍可使用 `app.main:app`。

## 本机更新

要求 Node.js 22.12+、Python 3.13 和 uv。两个仓库作为相邻目录时，构建直接使用本机前端；独立克隆后端时自动从公开 GitHub 前端仓库克隆。

```powershell
cd calculator_backend/cloudflare
node prepare.mjs
uv run pywrangler deploy
```

先运行 `uv run pywrangler login` 完成 Cloudflare 授权。构建会把必要 Python 模块复制到 `src/app/`，这些生成文件不提交到 Git。前端生产环境默认调用同域 `/api/`；开发环境继续使用本机 8000 端口。

Windows 如 uv 同步选择不到现有 Python，可使用后端虚拟环境中的 pywrangler；须确保 uv、Node 和 Python 在 PATH 中：

```powershell
../.venv/Scripts/python.exe -m pywrangler deploy
```

## 新账号部署

```powershell
uv run pywrangler d1 create calculator
```

把输出的 database_id 写入 `wrangler.jsonc` 的 D1 绑定。仓库现有 ID 属于作者账号，其他账号必须替换。ID 不是访问凭据，登录 Token 不得提交到 Git。

```powershell
uv run pywrangler d1 migrations apply calculator --remote
node prepare.mjs
uv run pywrangler deploy
```

迁移只初始化 D1 表，不自动导入本机 SQLite 数据。内置公式固定由服务端提供，不重复写库。更新前可通过 Cloudflare 控制台或 Wrangler 导出 D1 备份。

## 本地验证

```powershell
node prepare.mjs
uv run pywrangler d1 migrations apply calculator --local
uv run pywrangler dev --port 8787
```

打开 http://127.0.0.1:8787/ 。本地 D1 与线上 D1 分离。检查 `/api/health`、科学计算、历史分页、公式参数计算和修改冲突。

compatibility_date 固定在 2026-09-07，以使用已验证的 Python 3.13 Workers 运行时。升级日期前应重新运行真实 Workers 测试。`pylock.toml` 锁定 WASM 依赖，`uv.lock` 锁定工具依赖。

## 免费额度与维护

当前项目使用免费套餐，没有购买域名、服务器或开启付费套餐。免费资源有请求、CPU、D1 存储与读写额度限制，持续监控控制台用量；超额行为以 Cloudflare 当时的套餐规则为准。默认域名在不同网络的访问情况应分别验证。

共享历史和公式仍采用原有无账号设计，所有访问者均可读写和删除；适合课程演示，勿录入个人隐私数据。本次首次部署使用命令行；尚未配置 GitHub 推送后自动部署。

官方资料：
- https://developers.cloudflare.com/workers/languages/python/packages/fastapi/
- https://developers.cloudflare.com/d1/worker-api/prepared-statements/
- https://developers.cloudflare.com/workers/platform/limits/
