# 第 4 课：提交一段 JSON

这一课只学 POST：对方送来一段 JSON，函数把它读出来，再原样返回。

## 先看结果

打开 `/docs`，点开 `POST /notes`。把请求体改成：

```json
{"title": "买牛奶"}
```

点 **Execute**。Response body 还是：

```json
{"title": "买牛奶"}
```

这段 JSON 放在请求体里。请求体是这次请求另外附上的数据，跟在网址后面一起发出去。

## 这一课的新词

- **POST**：送来一段新数据。查看用 GET，提交用 POST。
- **请求体**：请求里附带的那段数据。这一课的请求体是 `{"title": "买牛奶"}`。
- **dict**：字典，也就是一对对的名字和值。这里的 `title` 是名字，`买牛奶` 是值。

## 代码

代码都在 [main.py](main.py)。前几个地址是前面课里的。这一课新加的是最下面的 `POST /notes`。

```python
from fastapi import FastAPI

app = FastAPI(title="第4课 提交一段 JSON")


@app.get("/")
def read_root():
    return {"message": "你好"}


@app.get("/hello/{name}")
def say_hello_by_path(name: str):
    return {"message": f"你好，{name}"}


@app.get("/hello")
def say_hello_by_query(name: str):
    return {"message": f"你好，{name}"}


@app.post("/notes")
def create_note(note: dict):
    return note
```

- `@app.post("/notes")`：有人用 POST 访问 `/notes`，就运行 `create_note`。
- `note: dict`：请求体里的 JSON 会变成字典，放进 `note`。
- `return note`：把这个字典原样交回去。所以你发什么，响应里就是什么。

这一课先不检查 JSON 里一定要有 `title`。少字段、多字段都可以原样返回。下一课再来规定形状。

## 自己运行

停掉上一课的程序，在 `learn-fastapi` 目录运行：

```powershell
uvicorn main:app --reload --app-dir stages\04-post
```

1. 打开 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)，确认标题是「第4课 提交一段 JSON」。
2. 点开 `POST /notes`。
3. 点 **Try it out**。
4. 在 Request body 里写成 `{"title": "买牛奶"}`。
5. 点 **Execute**，Response body 也是 `{"title": "买牛奶"}`。
6. 把请求体改成 `{"title": "写作业"}`，再执行一次，响应跟着变成「写作业」。

## 练习

复制 `main.py` 为 `practice.py`。让 `POST /notes` 的返回值多一个 `ok`。对方发来 `{"title": "买牛奶"}` 时，响应是：

```json
{"title": "买牛奶", "ok": true}
```

`true` 在 JSON 里表示「是」。可以先从 `note` 里取出 `title`，再自己组装一份新的字典返回。

```powershell
uvicorn practice:app --reload --app-dir stages\04-post
```

## 怎样算学会

- 能在 `/docs` 里用 POST 送出一段 JSON，并在响应里看到它。
- 能说出请求体是这次请求附带的数据。
- 知道这一课的函数还没有规定 JSON 必须长什么样。
