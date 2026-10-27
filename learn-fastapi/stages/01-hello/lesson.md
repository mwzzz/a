# 第 1 课：打招呼

这一课只做一件事：把程序跑起来，用浏览器访问首页，看到一句「你好」。

## 先看结果

启动后打开 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。页面最上面的标题是「第1课 打招呼」。

找到 `GET /`，点开，再点 **Try it out**，再点 **Execute**。下面的 Response body 是：

```json
{"message": "你好"}
```

也可以直接打开 [http://127.0.0.1:8000/](http://127.0.0.1:8000/)，浏览器里同样是这句 JSON。

## 这一课的新词

- **GET**：来读取。打开网页、查看数据，用的就是 GET。
- **/**：网站首页那个地址。完整网址是 `http://127.0.0.1:8000/`。
- **127.0.0.1**：你自己的这台电脑。程序现在只在你自己的电脑上跑。
- **8000**：端口，像门牌上的分机号。同一个电脑上可以有很多程序，8000 用来找到我们这个程序。
- **uvicorn**：负责把这个 FastAPI 程序跑起来，让别人能用网址访问它。
- **@app.get("/")**：给下面的函数挂上首页地址。有人用 GET 访问 `/`，这个函数就运行。

## 代码

代码都在 [main.py](main.py)。

```python
from fastapi import FastAPI

app = FastAPI(title="第1课 打招呼")


@app.get("/")
def read_root():
    return {"message": "你好"}
```

- `from fastapi import FastAPI`：拿出 FastAPI。
- `app = FastAPI(...)`：创建你的程序。`title` 会显示在 `/docs` 页面最上面。
- `@app.get("/")`：谁用 GET 访问首页，就运行下面这个函数。
- `return {"message": "你好"}`：把这份 JSON 交回去。

## 自己运行

先按 [README](../../README.md) 准备好虚拟环境，并进入 `learn-fastapi` 目录。

```powershell
uvicorn main:app --reload --app-dir stages\01-hello
```

终端里出现 `Uvicorn running on http://127.0.0.1:8000` 后：

1. 打开 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。
2. 点开 `GET /`。
3. 点 **Try it out**。
4. 点 **Execute**。
5. 在 Response body 里看到 `{"message": "你好"}`。

看完后，在这个终端按 `Ctrl+C` 停掉程序。

## 练习

把 `main.py` 复制成 `practice.py`，只改 `practice.py`。把返回的「你好」换成「你好，我是你的名字」。

```powershell
uvicorn practice:app --reload --app-dir stages\01-hello
```

再按上面的步骤点一次 Execute。Response body 应类似：

```json
{"message": "你好，我是小明"}
```

## 怎样算学会

- 能独立把这一课的程序跑起来。
- 能在 `/docs` 里点出 `{"message": "你好"}`。
- 知道 `GET /` 的意思是：用读取的方式访问首页。
