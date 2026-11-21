"""最小测试：对真实跑起来的服务测增删改查 + 重启后数据还在。

只用标准库。用法：
    python test_persistence.py
退出码 0 = 全部通过；非 0 = 有失败（并打印哪一步失败）。
测试用临时数据库，跑完自动删掉，不碰 items.db。
v0.3.0 起 /items 需要登录：测试先注册一个用户、登录拿 token 再测。
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
PORT = 8001
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


def login():
    """注册一个测试用户并登录，返回 token。"""
    status, _ = req("POST", "/register", {"username": "tester", "password": "secret123"})
    if status not in (201, 400):
        raise RuntimeError(f"register failed: {status}")
    status, body = req("POST", "/login", {"username": "tester", "password": "secret123"})
    if status != 200:
        raise RuntimeError(f"login failed: {status}")
    return body["access_token"]


def run_crud(token):
    status, body = req("GET", "/hello?name=Anthony")
    check("GET /hello", status == 200 and body == {"message": "Hello, Anthony"}, f"got {status} {body}")

    status, body = req("GET", "/health")
    check("GET /health", status == 200 and body == {"status": "ok"}, f"got {status} {body}")

    status, body = req("POST", "/items", {"name": "book", "price": 12.5}, token=token)
    check("POST /items book", status == 201 and body == {"name": "book", "price": 12.5}, f"got {status} {body}")

    status, body = req("POST", "/items", {"name": "pen", "price": 3.0}, token=token)
    check("POST /items pen", status == 201, f"got {status} {body}")

    status, body = req("GET", "/items", token=token)
    check("GET /items 有 2 条", status == 200 and len(body["items"]) == 2, f"got {status} {body}")

    status, body = req("GET", "/items/0", token=token)
    check("GET /items/0 是 book", status == 200 and body["name"] == "book", f"got {status} {body}")

    status, _ = req("POST", "/items", {"name": "bad", "price": -1}, token=token)
    check("POST 负价返回 422", status == 422, f"got {status}")

    status, _ = req("POST", "/items", {"price": 1}, token=token)
    check("POST 缺 name 返回 422", status == 422, f"got {status}")

    status, body = req("PUT", "/items/0", {"name": "book", "price": 15.0}, token=token)
    check("PUT /items/0 改价 15", status == 200 and body["price"] == 15.0, f"got {status} {body}")

    status, body = req("DELETE", "/items/1", token=token)
    check("DELETE /items/1 删 pen", status == 200 and body["name"] == "pen", f"got {status} {body}")

    status, body = req("GET", "/items", token=token)
    check("删后只剩 1 条", status == 200 and len(body["items"]) == 1, f"got {status} {body}")

    status, _ = req("GET", "/items/5", token=token)
    check("GET /items/5 返回 404", status == 404, f"got {status}")

    status, _ = req("PUT", "/items/5", {"name": "x", "price": 1}, token=token)
    check("PUT 不存在返回 404", status == 404, f"got {status}")

    status, _ = req("DELETE", "/items/5", token=token)
    check("DELETE 不存在返回 404", status == 404, f"got {status}")


def main():
    tmp = tempfile.mkdtemp(prefix="fastapi-test-")
    db_path = os.path.join(tmp, "test.db")

    proc = start_server(db_path)
    try:
        if not wait_ready(proc):
            print("FAIL  服务没起来")
            return 1
        print("--- 第一轮：增删改查 ---")
        token = login()
        run_crud(token)
    finally:
        stop_server(proc)

    # 重启服务，同一个数据库文件，验证数据还在
    proc = start_server(db_path)
    try:
        if not wait_ready(proc):
            print("FAIL  重启后服务没起来")
            return 1
        print("--- 第二轮：重启后 ---")
        token = login()
        status, body = req("GET", "/items", token=token)
        check("重启后数据还在（1 条 book 15.0）",
              status == 200 and body["items"] == [{"name": "book", "price": 15.0}],
              f"got {status} {body}")
    finally:
        stop_server(proc)

    print(f"\n{passed} 通过，{failed} 失败")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
