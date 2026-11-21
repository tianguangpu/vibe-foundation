"""登录鉴权测试：对真实跑起来的服务测注册/登录/JWT/未登录 401。

只用标准库。用法：
    python test_auth.py
退出码 0 = 全部通过；非 0 = 有失败（并打印哪一步失败）。
测试用临时数据库，跑完自动删掉，不碰 items.db。
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8002
BASE = f"http://127.0.0.1:{PORT}"

passed = 0
failed = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}  {extra}")


def req(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    if token is not None:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def wait_ready(proc, timeout=20):
    for _ in range(int(timeout * 10)):
        if proc.poll() is not None:
            return False
        try:
            status, _ = req("GET", "/health")
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def start_server(db_path):
    env = dict(os.environ)
    env["FASTAPI_STARTER_DB"] = db_path
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", str(PORT)],
        cwd=HERE, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc


def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_auth():
    # 公开接口不用登录
    status, _ = req("GET", "/hello")
    check("GET /hello 不用登录", status == 200, f"got {status}")
    status, _ = req("GET", "/health")
    check("GET /health 不用登录", status == 200, f"got {status}")

    # 注册
    status, body = req("POST", "/register", {"username": "anthony", "password": "secret123"})
    check("POST /register 成功 201", status == 201 and body["username"] == "anthony" and "id" in body,
          f"got {status} {body}")

    status, _ = req("POST", "/register", {"username": "anthony", "password": "otherpass"})
    check("POST /register 重复用户名 400", status == 400, f"got {status}")

    status, _ = req("POST", "/register", {"username": "bob", "password": "123"})
    check("POST /register 密码太短 422", status == 422, f"got {status}")

    status, _ = req("POST", "/register", {"username": "ab", "password": "secret123"})
    check("POST /register 用户名太短 422", status == 422, f"got {status}")

    # 登录
    status, body = req("POST", "/login", {"username": "anthony", "password": "secret123"})
    check("POST /login 成功 200 有 token", status == 200 and body.get("access_token") and body.get("token_type") == "bearer",
          f"got {status} {body}")
    token = body.get("access_token", "")

    status, _ = req("POST", "/login", {"username": "anthony", "password": "wrongpass"})
    check("POST /login 密码错 401", status == 401, f"got {status}")

    status, _ = req("POST", "/login", {"username": "nobody", "password": "secret123"})
    check("POST /login 用户不存在 401", status == 401, f"got {status}")

    # 没带 token 一律 401
    status, _ = req("GET", "/items")
    check("GET /items 没 token 401", status == 401, f"got {status}")
    status, _ = req("POST", "/items", {"name": "book", "price": 12.5})
    check("POST /items 没 token 401", status == 401, f"got {status}")
    status, _ = req("PUT", "/items/0", {"name": "x", "price": 1})
    check("PUT /items 没 token 401", status == 401, f"got {status}")
    status, _ = req("DELETE", "/items/0")
    check("DELETE /items 没 token 401", status == 401, f"got {status}")
    status, _ = req("GET", "/me")
    check("GET /me 没 token 401", status == 401, f"got {status}")

    # 乱 token 401
    status, _ = req("GET", "/items", token="garbage.token.here")
    check("GET /items 乱 token 401", status == 401, f"got {status}")

    # 带 token 正常用
    status, body = req("GET", "/me", token=token)
    check("GET /me 带 token 返回自己", status == 200 and body["username"] == "anthony",
          f"got {status} {body}")

    status, body = req("POST", "/items", {"name": "book", "price": 12.5}, token=token)
    check("POST /items 带 token 201", status == 201 and body == {"name": "book", "price": 12.5},
          f"got {status} {body}")

    status, body = req("GET", "/items", token=token)
    check("GET /items 带 token 有 1 条", status == 200 and len(body["items"]) == 1,
          f"got {status} {body}")

    status, body = req("PUT", "/items/0", {"name": "book", "price": 15.0}, token=token)
    check("PUT /items 带 token 改价 15", status == 200 and body["price"] == 15.0,
          f"got {status} {body}")

    status, body = req("DELETE", "/items/0", token=token)
    check("DELETE /items 带 token 删掉", status == 200 and body["name"] == "book",
          f"got {status} {body}")

    return token


def main():
    tmp = tempfile.mkdtemp(prefix="fastapi-auth-test-")
    db_path = os.path.join(tmp, "test.db")

    proc = start_server(db_path)
    try:
        if not wait_ready(proc):
            print("FAIL  服务没起来")
            return 1
        print("--- 第一轮：注册登录 + 鉴权 ---")
        token = run_auth()
    finally:
        stop_server(proc)

    # 重启服务：用户还在（能登录），旧 token 还能用（JWT 无状态，密钥没变）
    proc = start_server(db_path)
    try:
        if not wait_ready(proc):
            print("FAIL  重启后服务没起来")
            return 1
        print("--- 第二轮：重启后 ---")
        status, body = req("POST", "/login", {"username": "anthony", "password": "secret123"})
        check("重启后用户还在，能登录", status == 200 and body.get("access_token"),
              f"got {status} {body}")
        status, body = req("GET", "/me", token=token)
        check("重启后旧 token 还能用", status == 200 and body["username"] == "anthony",
              f"got {status} {body}")
        status, body = req("GET", "/items", token=token)
        check("重启后数据还在（0 条，上一轮删光了）", status == 200 and body["items"] == [],
              f"got {status} {body}")
    finally:
        stop_server(proc)

    print(f"\n{passed} 通过，{failed} 失败")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
