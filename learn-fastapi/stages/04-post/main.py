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
