# FastAPI 起手项目

最小可跑的后端：路由（GET/POST/PUT/DELETE）+ Pydantic 校验 + SQLite 持久化 + JWT 登录鉴权。

存储：标准库 `sqlite3`，数据文件 `items.db` 就在当前目录，服务重启后数据还在（改位置可设环境变量 `FASTAPI_STARTER_DB`）。用户也存在同一个库的 `users` 表里。

鉴权：JWT（PyJWT，HS256）。密码用标准库 PBKDF2-HMAC-SHA256 加盐哈希，不存明文。密钥用环境变量 `FASTAPI_STARTER_SECRET`，不设就用内置开发默认值，只适合本地学习，**上线前必须换掉**。token 默认有效 60 分钟，改环境变量 `FASTAPI_STARTER_TOKEN_MINUTES`。

## 跑起来

```bash
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

打开 http://127.0.0.1:8000/docs 直接调接口。

Windows PowerShell 第一次跑 `Activate.ps1` 报错（执行策略）时，先跑一次：
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /hello | 问候，`?name=` 可改名字，不用登录 |
| GET | /health | 健康检查，返回 `{"status": "ok"}`，不用登录 |
| POST | /register | 注册，用户名 3–30 字符，密码最少 6 位；重复用户名返回 400 |
| POST | /login | 登录，返回 `{"access_token", "token_type": "bearer"}`；错了返回 401 |
| GET | /me | 看当前登录的是谁，需要登录 |
| GET | /items | 列出全部，需要登录 |
| POST | /items | 新增，201；price 为负返回 422；需要登录 |
| GET | /items/{index} | 按顺序取第几个，不存在返回 404；需要登录 |
| PUT | /items/{index} | 改第几个，不存在返回 404；需要登录 |
| DELETE | /items/{index} | 删第几个，返回被删的那条；需要登录 |

没登录调需要登录的接口返回 401；token 过期返回 401；乱 token 返回 401。

## 测试

```bash
python test_persistence.py   # 增删改查 + 重启后数据还在，15 项
python test_auth.py          # 注册/登录/JWT/未登录 401，23 项
```

两个测试都起真实服务进程，用临时数据库，跑完自动删掉，不碰 `items.db`。

## 试一下

```bash
curl http://127.0.0.1:8000/hello?name=Anthony
# 注册
curl -X POST http://127.0.0.1:8000/items -H "Content-Type: application/json" -d '{"name": "book", "price": 12.5}'
# 上面会返回 401，因为没登录。先注册再登录：
curl -X POST http://127.0.0.1:8000/register -H "Content-Type: application/json" -d '{"username": "anthony", "password": "secret123"}'
curl -X POST http://127.0.0.1:8000/login -H "Content-Type: application/json" -d '{"username": "anthony", "password": "secret123"}'
# 把返回的 access_token 换到下面，带上就能用了：
curl http://127.0.0.1:8000/items -H "Authorization: Bearer <access_token>"
curl -X POST http://127.0.0.1:8000/items -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" -d '{"name": "book", "price": 12.5}'
```

传错参数（比如 price 传负数或缺 name）会直接返回 422，不用自己写 if 校验。

## 下一步（按计划顺序）

1. ~~连数据库：把内存 `items` 换成 SQLite~~（已完成，v0.2.0）
2. ~~登录鉴权~~（已完成，v0.3.0：注册/登录/JWT，38 项测试全过）
3. 部署：Docker + 云服务器

这是寒假阶段 2 的 FastAPI 部分的起手架子，现在先跑通、改着玩就行。
