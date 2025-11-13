import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Todo

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: Optional[int] = 2

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[int] = None

@app.get("/")
def read_root():
    return {"message": "Todo API is running"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# Helper to convert Mongo doc to plain dict with id

def serialize_todo(doc: dict) -> dict:
    if not doc:
        return {}
    return {
        "id": str(doc.get("_id")),
        "title": doc.get("title"),
        "description": doc.get("description"),
        "completed": bool(doc.get("completed", False)),
        "priority": doc.get("priority", 2),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }

COLLECTION = "todo"

@app.post("/api/todos")
async def create_todo(payload: TodoCreate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    todo = Todo(**payload.model_dump())
    inserted_id = create_document(COLLECTION, todo)
    doc = db[COLLECTION].find_one({"_id": ObjectId(inserted_id)})
    return serialize_todo(doc)

@app.get("/api/todos")
async def list_todos():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    docs = get_documents(COLLECTION, {}, None)
    return [serialize_todo(d) for d in docs]

@app.patch("/api/todos/{todo_id}")
async def update_todo(todo_id: str, payload: TodoUpdate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        oid = ObjectId(todo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
    update_data = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_data["updated_at"] = __import__("datetime").datetime.utcnow()
    result = db[COLLECTION].update_one({"_id": oid}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Todo not found")
    doc = db[COLLECTION].find_one({"_id": oid})
    return serialize_todo(doc)

@app.delete("/api/todos/{todo_id}")
async def delete_todo(todo_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        oid = ObjectId(todo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
    result = db[COLLECTION].delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
