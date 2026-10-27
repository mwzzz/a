from fastapi import FastAPI

app = FastAPI(title="第1课 打招呼")


@app.get("/")
def read_root():
    return {"message": "你好"}
