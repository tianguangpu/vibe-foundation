"""FastAPI 起手项目：路由 + 请求体校验（Pydantic）+ SQLite 持久化 + JWT 登录鉴权。

跑起来：uvicorn main:app --reload
接口文档：http://127.0.0.1:8000/docs

存储：标准库 sqlite3，数据文件 items.db 就在当前目录；
重启后数据还在。改数据库位置可设环境变量 FASTAPI_STARTER_DB。

鉴权：JWT（PyJWT，HS256）。
- 注册：POST /register {"username", "password"}
- 登录：POST /login {"username", "password"} -> {"access_token", "token_type": "bearer"}
- 之后调接口要在请求头带上：Authorization: Bearer <access_token>
- /items 全部接口和 /me 都需要登录；/hello、/health 不用。
- 密钥用环境变量 FASTAPI_STARTER_SECRET；不设就用内置的开发默认值，
  只适合本地学习，上线前必须换掉。
- token 有效期默认 60 分钟，改环境变量 FASTAPI_STARTER_TOKEN_MINUTES。
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

app = FastAPI(title="fastapi-starter", version="0.3.0")

DB_PATH = Path(os.environ.get("FASTAPI_STARTER_DB", Path(__file__).parent / "items.db"))
# 开发默认值：只适合本地学习。上线前必须设 FASTAPI_STARTER_SECRET。
SECRET_KEY = os.environ.get("FASTAPI_STARTER_SECRET", "dev-only-change-me")
TOKEN_MINUTES = int(os.environ.get("FASTAPI_STARTER_TOKEN_MINUTES", "60"))

bearer_scheme = HTTPBearer(auto_error=False)


class Item(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    price: float = Field(ge=0)


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=6, max_length=100)


class UserLogin(BaseModel):
    username: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=100)


class UserOut(BaseModel):
    id: int
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _connect() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS items ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "name TEXT NOT NULL,"
            "price REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "username TEXT NOT NULL UNIQUE,"
            "password_hash TEXT NOT NULL)"
        )


def _hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256，存成 salt_hex$hash_hex。只用标准库。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(digest.hex(), hash_hex)


def _create_token(user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "uid": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserOut:
    """鉴权依赖：没带 token、token 坏了、过期了都返回 401。"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")
    return UserOut(id=payload["uid"], username=payload["sub"])


def _all_items():
    with _connect() as conn:
        rows = conn.execute("SELECT name, price FROM items ORDER BY id").fetchall()
    return [Item(name=r["name"], price=r["price"]) for r in rows]


def _item_at(index: int):
    """按插入顺序取第 index 个（和原来内存列表的下标行为一致）。"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, price FROM items ORDER BY id LIMIT 1 OFFSET ?", (index,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="item not found")
    return row


_init_db()


@app.get("/hello")
def hello(name: str = "Anthony"):
    return {"message": f"Hello, {name}"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register", status_code=201)
def register(user: UserRegister):
    with _connect() as conn:
        exists = conn.execute(
            "SELECT id FROM users WHERE username = ?", (user.username,)
        ).fetchone()
        if exists is not None:
            raise HTTPException(status_code=400, detail="username already taken")
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (user.username, _hash_password(user.password)),
        )
        user_id = cur.lastrowid
    return UserOut(id=user_id, username=user.username)


@app.post("/login")
def login(user: UserLogin):
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (user.username,),
        ).fetchone()
    # 用户名不存在和密码错误返回一样的 401，不泄露哪个错了
    if row is None or not _verify_password(user.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="incorrect username or password")
    return Token(access_token=_create_token(row["id"], row["username"]))


@app.get("/me")
def me(current_user: UserOut = Depends(_get_current_user)):
    return current_user


@app.get("/items")
def list_items(current_user: UserOut = Depends(_get_current_user)):
    return {"items": _all_items()}


@app.post("/items", status_code=201)
def create_item(item: Item, current_user: UserOut = Depends(_get_current_user)):
    with _connect() as conn:
        conn.execute("INSERT INTO items (name, price) VALUES (?, ?)", (item.name, item.price))
    return item


@app.get("/items/{index}")
def get_item(index: int, current_user: UserOut = Depends(_get_current_user)):
    row = _item_at(index)
    return Item(name=row["name"], price=row["price"])


@app.put("/items/{index}")
def update_item(index: int, item: Item, current_user: UserOut = Depends(_get_current_user)):
    row = _item_at(index)
    with _connect() as conn:
        conn.execute(
            "UPDATE items SET name = ?, price = ? WHERE id = ?",
            (item.name, item.price, row["id"]),
        )
    return item


@app.delete("/items/{index}")
def delete_item(index: int, current_user: UserOut = Depends(_get_current_user)):
    row = _item_at(index)
    with _connect() as conn:
        conn.execute("DELETE FROM items WHERE id = ?", (row["id"],))
    return Item(name=row["name"], price=row["price"])
