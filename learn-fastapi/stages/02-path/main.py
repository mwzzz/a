from fastapi import FastAPI

app = FastAPI(title="第2课 网址里的名字")


@app.get("/")
def read_root():
    return {"message": "你好"}


@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"你好，{name}"}
