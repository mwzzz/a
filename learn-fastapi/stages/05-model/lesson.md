# 第 5 课：规定 JSON 的形状

这一课只学一件事：用一个模型规定请求体必须有 `title`，而且它得是一段文字。

## 先看结果

打开 `/docs`，点开 `POST /notes`。请求体写成：

```json
{"title": "买牛奶"}
```

执行后，Response body 是：

```json
{"title": "买牛奶"}
```

再试两种会失败的写法。

少了 `title`，只发送 `{}`。响应里会有 `detail`，其中能看到 `Field required`，表示这个字段是必须的。

`title` 写成数字：`{"title": 123}`。响应的 `detail` 里会说明这里需要一段文字。程序仍然在运行。

如果多写一个字段，例如 `{"title": "买牛奶", "extra": 1}`，响应里只保留 `title`。模型里没有写出的字段不会退回去。

## 这一课的新词

- **模型**：一份形状说明。这里用类 `Note` 说明 JSON 里要有哪些字段。
- **BaseModel**：Pydantic 提供的基类。自己的模型写在它后面，FastAPI 就会按这个类检查请求体。
- **字段**：JSON 里的一项。`title` 就是一个字段。
- **422**：这次请求的数据形状不对，程序没有按正常结果处理它。`/docs` 里失败的响应会标出这个状态。

Pydantic 在安装 FastAPI 时已经一起装好了，这一课不用再安装新的包。

## 代码

代码都在 [main.py](main.py)。

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="第5课 规定 JSON 的形状")


class Note(BaseModel):
    title: str


@app.get("/")
def read_root():
    return {"message": "你好"}


@app.post("/notes")
def create_note(note: Note):
    return note
```

- `class Note(BaseModel)`：定义一份名为 `Note` 的形状。
- `title: str`：请求体里必须有 `title`，值是一段文字。
- `note: Note`：FastAPI 按 `Note` 检查请求体。通过检查后，`note.title` 就是「买牛奶」这种文字。
- `return note`：按这个模型把 JSON 交回去。

第 4 课用的是 `dict`，来什么就回什么。这一课换成 `Note` 之后，形状由类来规定。

## 自己运行

停掉上一课的程序，在 `learn-fastapi` 目录运行：

```powershell
uvicorn main:app --reload --app-dir stages\05-model
```

1. 打开 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)，确认标题是「第5课 规定 JSON 的形状」。
2. 点开 `POST /notes`，**Try it out**。
3. 请求体用 `{"title": "买牛奶"}`，执行，看到同样的 JSON。
4. 请求体改成 `{}`，执行，在 `detail` 里看到缺字段。
5. 请求体改成 `{"title": 123}`，执行，在 `detail` 里看到类型不对。
6. 请求体改成 `{"title": "买牛奶", "extra": 1}`，执行，响应里只有 `title`。

## 练习

复制 `main.py` 为 `practice.py`。给 `Note` 加上第二个字段 `content: str`。

这样可以成功：

```json
{"title": "买牛奶", "content": "去楼下超市"}
```

这样会失败，因为少了 `content`：

```json
{"title": "买牛奶"}
```

```powershell
uvicorn practice:app --reload --app-dir stages\05-model
```

## 怎样算学会

- 能指出 `class Note` 里的 `title: str` 就是在规定 JSON 的形状。
- 亲手看过一次少字段的错误，和一次类型不对的错误。
- 知道通过检查后，可以用 `note.title` 拿到这段文字。
