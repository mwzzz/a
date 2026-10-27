# 第 3 课：问号后面的条件

这一课只学查询参数：把值写在问号后面，函数也能收到。

## 先看结果

打开 `/docs`，点开 `GET /hello`。在 `name` 一栏填 `小明`，点 **Execute**。Response body 是：

```json
{"message": "你好，小明"}
```

对应的网址是 [http://127.0.0.1:8000/hello?name=小明](http://127.0.0.1:8000/hello?name=小明)。

第 2 课的写法是 `/hello/小明`，名字在路径里。这一课的写法是 `/hello?name=小明`，名字在问号后面。两种网址都会把「小明」交给函数，返回的 JSON 都是上面这一句。

再试一个整数。点开 `GET /double`，`number` 填 `3`，返回：

```json
{"result": 6}
```

把 `number` 改成 `abc` 再执行。这次请求会失败，Response body 里有一段 `detail`，意思是 `number` 没能变成整数。程序本身还在运行，改回 `3` 就可以再成功。

## 这一课的新词

- **查询参数**：写在问号后面的条件，形状是 `名字=值`。`name=小明` 里，名字是 `name`，值是 `小明`。
- **int**：整数。`number: int` 表示这里要一个整数，例如 `3`。
- **校验**：FastAPI 按你写的类型检查对方传来的值。对不上时，这次请求会得到一份错误 JSON。

## 代码

代码都在 [main.py](main.py)。

```python
from fastapi import FastAPI

app = FastAPI(title="第3课 问号后面的条件")


@app.get("/")
def read_root():
    return {"message": "你好"}


@app.get("/hello/{name}")
def say_hello_by_path(name: str):
    return {"message": f"你好，{name}"}


@app.get("/hello")
def say_hello_by_query(name: str):
    return {"message": f"你好，{name}"}


@app.get("/double")
def double(number: int):
    return {"result": number * 2}
```

- `@app.get("/hello")` 下面的 `name: str` 没有写进路径。FastAPI 就到问号后面找 `name`。
- `/hello/{name}` 仍然留着，方便和上一课对照。它和 `/hello` 是两个不同的地址。
- `number: int` 要求问号后面的 `number` 是整数。`number * 2` 是把这个整数乘以 2。

## 自己运行

停掉上一课的程序，在 `learn-fastapi` 目录运行：

```powershell
uvicorn main:app --reload --app-dir stages\03-query
```

1. 打开 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)，确认标题是「第3课 问号后面的条件」。
2. 点开 `GET /hello`，**Try it out**，`name` 填 `小明`，**Execute**。看到 `{"message": "你好，小明"}`。
3. 点开 `GET /hello/{name}`，`name` 也填 `小明`。返回的 JSON 和第 2 步一样。
4. 点开 `GET /double`，`number` 填 `3`，看到 `{"result": 6}`。
5. `number` 改成 `abc`，再执行一次。看 Response body 里的 `detail`。

## 练习

复制 `main.py` 为 `practice.py`。给 `say_hello_by_query` 再加一个查询参数 `city: str`，让返回变成：

```json
{"message": "你好，小明", "city": "上海"}
```

试这个网址：`/hello?name=小明&city=上海`。问号后面有两个条件时，中间用 `&` 连起来。

```powershell
uvicorn practice:app --reload --app-dir stages\03-query
```

## 怎样算学会

- 能读出 `/hello?name=小明`：问号后面的 `name` 会进入函数。
- 能分清 `/hello/小明` 和 `/hello?name=小明` 是两种传值位置。
- 见过一次类型不对的错误，并且知道程序还可以继续接受下一次请求。
