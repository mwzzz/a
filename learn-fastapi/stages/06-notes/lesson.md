# 第 6 课：迷你记事本

这一课把第 5 课的 `Note` 放进一个字典里。程序开着的时候，笔记还在；程序一关，笔记就没了。专门用来长期保存数据的是数据库，这一轮先不用它。

这一课的文件只做记事本，打招呼的地址留在前面几课。

## 先看结果

还没添加任何笔记时，`GET /notes` 的响应是：

```json
[]
```

方括号里面是空的，表示一条笔记都没有。

用 `POST /notes` 发送 `{"title": "买牛奶"}` 之后，响应是：

```json
{"id": 1, "title": "买牛奶"}
```

`id` 是程序自己编的编号，从 1 开始。再添加一条「写作业」，编号就是 2。

`GET /notes` 会把已经添加的笔记放进一个列表：

```json
[
  {"id": 1, "title": "买牛奶"},
  {"id": 2, "title": "写作业"}
]
```

`GET /notes/1` 只看编号 1。`DELETE /notes/1` 删掉编号 1。编号不存在时，例如 `GET /notes/9`，响应是：

```json
{"detail": "没有这份笔记"}
```

`/docs` 里这次响应会标成 **404**。

## 这一课的新词

- **404**：没有这份资源。这里就是：这个编号下面没有笔记。
- **HTTPException**：在函数里主动结束这次请求，并带上 404 和一句说明。
- **字典**：这一课用编号当钥匙，把笔记存进去。`notes[1]` 就是编号 1 的那条笔记。
- **列表**：方括号包起来的一串数据。查看全部时，返回的就是列表。

## 代码

代码都在 [main.py](main.py)。

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="第6课 迷你记事本")


class Note(BaseModel):
    title: str


notes: dict[int, Note] = {}
next_id = 1


def find_note(note_id: int) -> Note:
    if note_id not in notes:
        raise HTTPException(status_code=404, detail="没有这份笔记")
    return notes[note_id]


@app.post("/notes")
def create_note(note: Note):
    global next_id
    note_id = next_id
    next_id = next_id + 1
    notes[note_id] = note
    return {"id": note_id, "title": note.title}


@app.get("/notes")
def list_notes():
    result = []
    for note_id, note in notes.items():
        result.append({"id": note_id, "title": note.title})
    return result


@app.get("/notes/{note_id}")
def get_note(note_id: int):
    note = find_note(note_id)
    return {"id": note_id, "title": note.title}


@app.delete("/notes/{note_id}")
def delete_note(note_id: int):
    note = find_note(note_id)
    del notes[note_id]
    return {"id": note_id, "title": note.title}
```

- `notes = {}`：空字典，用来放笔记。`next_id = 1`：下一个要发出的编号。
- `find_note`：按编号去字典里找。找不到就用 `HTTPException` 结束这次请求。`-> Note` 表示找到后交回一条笔记。
- `global next_id`：函数里面要修改函数外面的 `next_id`，所以先写这一行。每添加一条，编号就加 1。删掉一条笔记时，编号不会重新发给别人，避免两个笔记用同一个编号。
- `POST /notes`：保存笔记，返回编号和标题。
- `GET /notes`：用一个普通循环，把字典里的每一条放进列表。
- `GET /notes/{note_id}`：看一条。`{note_id}` 是第 2 课学过的路径参数，这里的编号是整数。
- `DELETE /notes/{note_id}`：先找到，再从字典里删掉，然后把删掉的那条返回给你看。

## 自己运行

停掉上一课的程序，在 `learn-fastapi` 目录运行：

```powershell
uvicorn main:app --reload --app-dir stages\06-notes
```

1. 打开 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)，确认标题是「第6课 迷你记事本」。
2. 点开 `GET /notes`，执行，看到 `[]`。
3. 点开 `POST /notes`，请求体写 `{"title": "买牛奶"}`，执行，看到 `"id": 1`。
4. 再添加一次，标题换成 `写作业`，看到 `"id": 2`。
5. 再执行 `GET /notes`，列表里有两条。
6. 点开 `GET /notes/{note_id}`，`note_id` 填 `1`，看到「买牛奶」。
7. `note_id` 改成 `9`，看到 `{"detail": "没有这份笔记"}`，状态是 404。
8. 点开 `DELETE /notes/{note_id}`，`note_id` 填 `1`，执行。
9. 再查看 `GET /notes/1`，仍然是 404。`GET /notes` 里只剩「写作业」。

停掉程序再启动一次，然后执行 `GET /notes`。列表又是 `[]`，因为字典里的数据跟着程序一起消失了。

## 练习

先按课文把服务跑起来，连续添加「买牛奶」和「写作业」。删除编号 1，再查看全部。列表里应只剩：

```json
[{"id": 2, "title": "写作业"}]
```

然后再访问 `/notes/1`，响应是：

```json
{"detail": "没有这份笔记"}
```

做完可以想一句：标题写成空字符串 `{"title": ""}` 时，这一课仍会保存。`title: str` 只要求它是一段文字，空字符串也是一段文字。

## 怎样算学会

- 能自己完成添加、查看全部、按编号查看、删除。
- 知道编号不存在时会得到 404，以及 `detail` 里的那句说明。
- 能说出这些笔记只活在这次运行里，程序关掉就没了。
