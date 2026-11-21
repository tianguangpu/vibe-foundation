# vibe-foundation

西邮人工智能 2025 级，大二上。目标：直接就业，AI 应用开发为主、后端兜底。
这个仓库是学习地基：Git、终端、读代码、测试，每一步都有可跑的交付物。

## 现在有什么

- `fastapi-starter/` — FastAPI 起手项目：`GET /hello`、`/health`、`/items`（SQLite 持久化）+ 注册/登录/JWT 鉴权，Pydantic 校验（`price` 传负数返回 422），接口文档在 `/docs`。测试 38 项全过（持久化 15 + 鉴权 23）。这是寒假阶段 2 的起手架子，先跑通、改着玩。

## 跑起来

```powershell
cd fastapi-starter
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

打开 http://127.0.0.1:8000/docs 直接调接口。

## 下一步（按计划顺序）

1. ~~把内存 `items` 换成 SQLite~~（已完成，v0.2.0）
2. ~~加登录鉴权~~（已完成，v0.3.0）
3. 部署：Docker + 云服务器（进行中，Render）

## 规则

- AI 生成的代码逐行看一遍再接受，不懂的代码不提交。
- 每个功能做完必须跑通测试，测试不过不继续做下一个。
- 每周至少一次不用 AI，自己手写一个小功能。
