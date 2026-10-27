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
