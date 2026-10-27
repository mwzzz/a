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
