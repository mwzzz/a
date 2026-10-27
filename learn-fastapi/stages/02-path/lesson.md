# 第 2 课：网址里的名字

这一课只学路径参数：把一个词写在网址路径里，函数就能收到它。

## 先看结果

启动后打开 `/docs`，点开 `GET /hello/{name}`。在 `name` 一栏填 `小明`，点 **Execute**。Response body 是：

```json
{"message": "你好，小明"}
```

也可以直接打开 [http://127.0.0.1:8000/hello/小明](http://127.0.0.1:8000/hello/小明)。把网址最后的「小明」换成「小红」，返回的句子也会换成小红。

## 这一课的新词

- **路径**：网址里斜杠分开的那一段。`/hello/小明` 里有两段：`hello` 和 `小明`。
- **路径参数**：路径里会变化的那一段。代码里写成 `{name}`，访问时换成真正的名字。
- **str**：字符串，也就是一段文字。`name: str` 表示函数收到的 `name` 是一段文字。

## 代码

代码都在 [main.py](main.py)。首页仍和第 1 课一样。这一课新加的是 `/hello/{name}`。

```python
from fastapi import FastAPI

app = FastAPI(title="第2课 网址里的名字")


@app.get("/")
def read_root():
    return {"message": "你好"}


@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"你好，{name}"}
```

- `@app.get("/hello/{name}")`：网址形如 `/hello/小明`。花括号里的 `name` 是会变的部分。
- `def say_hello(name: str)`：FastAPI 把网址里的那一段文字放进 `name`。
- `f"你好，{name}"`：字符串前面的 `f` 会把 `{name}` 换成真正的名字。访问 `/hello/小明` 时，`name` 就是 `"小明"`。

## 自己运行

先停掉上一课的程序（`Ctrl+C`），再在 `learn-fastapi` 目录运行：

```powershell
uvicorn main:app --reload --app-dir stages\02-path
```

1. 打开 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)，确认标题是「第2课 网址里的名字」。
2. 点开 `GET /hello/{name}`。
3. 点 **Try it out**。
4. 在 `name` 里输入 `小明`。
5. 点 **Execute**，看到 `{"message": "你好，小明"}`。
6. 把 `name` 改成 `小红`，再点一次 **Execute**。

## 练习

复制 `main.py` 为 `practice.py`。在里面再加一个地址 `/bye/{name}`。访问 `/bye/小明` 时返回：

```json
{"message": "再见，小明"}
```

用下面的命令运行练习：

```powershell
uvicorn practice:app --reload --app-dir stages\02-path
```

在 `/docs` 里应能看到 `GET /bye/{name}`。填入 `小明` 后，Response body 是上面的 JSON。

## 怎样算学会

- 能说出 `/hello/小明` 里的「小明」会进入函数的 `name`。
- 能在 `/docs` 里自己填一个名字，并看到句子跟着变。
- 知道 `{name}` 写在路径里，表示这一段由访问者决定。
