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
