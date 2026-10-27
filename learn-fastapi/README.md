# FastAPI 入门六课

这是一套给初学者的教程。学完六课后，你能用 FastAPI 写一个很小的记事本接口：别人按网址访问它，程序返回 JSON。

这一轮只学「怎样写一个能访问的接口」。数据库、登录、测试、缓存和 Docker 先不学。

每一课大约 30 到 60 分钟。一课只加一个新概念。

## 三个词

先把这三个词记住，后面的课都在用它们。

- **接口**：一个网址。别人访问它，你的程序返回数据。
- **请求**：浏览器或文档页面对程序的一次访问。
- **JSON**：用大括号包起来的数据。例如 `{"title": "买牛奶"}`。`title` 是名字，`买牛奶` 是内容。

## 准备环境

用 PowerShell，进入本目录 `learn-fastapi`。这个目录里能看到 `requirements.txt`。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

如果激活虚拟环境时出现红色的执行策略提示，可以不激活，改用虚拟环境里的 Python：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

后面的启动命令也一样，把 `uvicorn` 换成：

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --app-dir stages\01-hello
```

## 六课路线

1. [第 1 课 打招呼](stages/01-hello/lesson.md)：启动程序，访问首页，拿到一句「你好」。
2. [第 2 课 网址里的名字](stages/02-path/lesson.md)：`/hello/小明` 怎样把「小明」交给函数。
3. [第 3 课 问号后面的条件](stages/03-query/lesson.md)：`/hello?name=小明` 怎样把值交给函数。
4. [第 4 课 提交一段 JSON](stages/04-post/lesson.md)：用 POST 把 `{"title": "买牛奶"}` 发给程序。
5. [第 5 课 规定 JSON 的形状](stages/05-model/lesson.md)：少了字段，或类型不对时，程序怎样拒绝。
6. [第 6 课 迷你记事本](stages/06-notes/lesson.md)：添加、查看全部、按编号查看、删除。

## 每一课怎么学

1. 打开该课的 `lesson.md`。
2. 先看「先看结果」和「这一课的新词」。
3. 读完代码，再按「自己运行」做一遍。
4. 做练习。请把该课的 `main.py` 复制成 `practice.py`，只改 `practice.py`。
5. 用「怎样算学会」检查自己。

练习的启动命令和课文几乎一样，只是把 `main:app` 换成 `practice:app`。例如第 1 课：

```powershell
uvicorn practice:app --reload --app-dir stages\01-hello
```

一次只开一个服务，它们都使用 8000 端口。换下一课之前，在运行窗口按 `Ctrl+C` 停掉当前服务。

终端里出现 `Uvicorn running on http://127.0.0.1:8000` 就表示程序已经跑起来了。然后用浏览器打开 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。这个页面是 FastAPI 自动生成的，可以在里面点按钮发请求。

## 学完这一轮

你应该能看懂一个最简单的 FastAPI 文件：它有哪些网址、每个网址用 GET 还是 POST、函数怎样拿到对方传来的值，以及怎样返回 JSON。数据目前只放在内存里，程序一关就没了。
