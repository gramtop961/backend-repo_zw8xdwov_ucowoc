import os
from datetime import datetime, timedelta, date, time as dtime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import create_document, get_documents, db
from schemas import Task, Routine, Pantryitem, Meal, Bill, Subscription, Shoppinglistitem, Checkin, User

app = FastAPI(title="Daily Life Optimizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Daily Life Optimizer Backend is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but error: {str(e)[:60]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:60]}"
    return response


# Utility to get collection name from model class
MODEL_TO_COLLECTION = {
    Task: "task",
    Routine: "routine",
    Pantryitem: "pantryitem",
    Meal: "meal",
    Bill: "bill",
    Subscription: "subscription",
    Shoppinglistitem: "shoppinglistitem",
    Checkin: "checkin",
    User: "user",
}


# Generic create/list endpoints for core resources
class CreateResponse(BaseModel):
    id: str


def create_and_list_endpoints(model_cls, base_path: str):
    collection = MODEL_TO_COLLECTION[model_cls]

    @app.post(f"/api/{base_path}", response_model=CreateResponse)
    def create_item(item: model_cls):  # type: ignore
        try:
            new_id = create_document(collection, item)
            return {"id": new_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get(f"/api/{base_path}")
    def list_items(limit: Optional[int] = None):
        try:
            docs = get_documents(collection, {}, limit)
            # Convert ObjectId to string if present
            for d in docs:
                if "_id" in d:
                    d["id"] = str(d.pop("_id"))
            return docs
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# Register endpoints
create_and_list_endpoints(Task, "tasks")
create_and_list_endpoints(Routine, "routines")
create_and_list_endpoints(Pantryitem, "pantry")
create_and_list_endpoints(Meal, "meals")
create_and_list_endpoints(Bill, "bills")
create_and_list_endpoints(Subscription, "subscriptions")
create_and_list_endpoints(Shoppinglistitem, "shopping-list")
create_and_list_endpoints(Checkin, "checkins")
create_and_list_endpoints(User, "users")


@app.get("/schema")
def get_schema():
    # Simple schema description for viewer/tools
    return {
        "collections": [
            {"name": "task"},
            {"name": "routine"},
            {"name": "pantryitem"},
            {"name": "meal"},
            {"name": "bill"},
            {"name": "subscription"},
            {"name": "shoppinglistitem"},
            {"name": "checkin"},
            {"name": "user"},
        ]
    }


# Smart suggestions: meals from pantry (simple heuristic)
@app.get("/api/suggest-meals")
def suggest_meals():
    try:
        pantry = get_documents("pantryitem")
        have = {p.get("name", "").lower() for p in pantry}
        suggestions: List[Dict[str, Any]] = []

        def has(items: List[str]):
            return all(i in have for i in items)

        # Simple rules
        if has(["eggs", "bread"]):
            suggestions.append({
                "title": "Egg toast",
                "ingredients": ["eggs", "bread", "butter"],
                "steps": ["Toast bread", "Scramble eggs", "Combine and season"],
                "tags": ["quick", "breakfast"]
            })
        if has(["pasta", "tomato sauce"]) or has(["pasta", "tomatoes"]):
            suggestions.append({
                "title": "Simple pasta",
                "ingredients": ["pasta", "tomato sauce", "olive oil"],
                "steps": ["Boil pasta", "Heat sauce", "Combine"],
                "tags": ["dinner", "15-min"]
            })
        if has(["rice", "beans"]):
            suggestions.append({
                "title": "Rice & beans bowl",
                "ingredients": ["rice", "beans", "spices"],
                "steps": ["Cook rice", "Warm beans", "Season and serve"],
                "tags": ["budget", "vegan"]
            })
        if has(["tortilla", "cheese"]):
            suggestions.append({
                "title": "Cheesy quesadilla",
                "ingredients": ["tortilla", "cheese"],
                "steps": ["Heat tortilla", "Melt cheese inside"],
                "tags": ["snack", "kid-friendly"]
            })

        # Fall back minimal suggestions
        if not suggestions and have:
            suggestions.append({
                "title": "Pantry mix bowl",
                "ingredients": list(have)[:5],
                "steps": ["Combine ingredients you have and season to taste"],
                "tags": ["creative"]
            })

        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Daily schedule generator
class ScheduleRequest(BaseModel):
    start_time: Optional[str] = "09:00"  # HH:MM
    end_time: Optional[str] = "18:00"
    break_every_minutes: int = 90
    break_minutes: int = 10


@app.get("/api/schedule")
def get_schedule_default():
    return generate_schedule(ScheduleRequest())


@app.post("/api/schedule")
def generate_schedule(req: ScheduleRequest):  # type: ignore
    try:
        # Parse times
        today = date.today()
        def parse_hhmm(s: str) -> datetime:
            hh, mm = [int(x) for x in s.split(":")]
            return datetime.combine(today, dtime(hour=hh, minute=mm))

        start = parse_hhmm(req.start_time or "09:00")
        end = parse_hhmm(req.end_time or "18:00")
        cursor = start
        blocks: List[Dict[str, Any]] = []
        minutes_since_break = 0

        # Pull tasks and routines
        tasks = get_documents("task")
        routines = get_documents("routine")

        # Simple prioritization by priority then estimated time
        def task_sort_key(t):
            return (t.get("priority", 3), t.get("estimated_minutes", 30) or 30)
        tasks_sorted = sorted(tasks, key=task_sort_key)

        # Turn routines into soft reminders blocks (15min)
        routine_blocks = []
        for r in routines:
            label = r.get("name", "Routine")
            preferred = (r.get("preferred_time") or "").lower()
            if preferred == "morning":
                rt = datetime.combine(today, dtime(9, 0))
            elif preferred == "afternoon":
                rt = datetime.combine(today, dtime(13, 0))
            elif preferred == "evening":
                rt = datetime.combine(today, dtime(18, 0))
            else:
                rt = datetime.combine(today, dtime(10, 0))
            routine_blocks.append({
                "title": f"Routine: {label}",
                "start": rt.isoformat(),
                "end": (rt + timedelta(minutes=15)).isoformat(),
                "type": "routine"
            })

        i = 0
        while cursor < end and i < len(tasks_sorted):
            t = tasks_sorted[i]
            est = int(t.get("estimated_minutes", 30) or 30)
            block_end = cursor + timedelta(minutes=est)
            if block_end > end:
                break
            blocks.append({
                "title": t.get("title", "Task"),
                "start": cursor.isoformat(),
                "end": block_end.isoformat(),
                "type": "task",
                "priority": t.get("priority", 3)
            })
            cursor = block_end
            minutes_since_break += est
            if minutes_since_break >= req.break_every_minutes:
                b_end = cursor + timedelta(minutes=req.break_minutes)
                if b_end <= end:
                    blocks.append({
                        "title": "Break",
                        "start": cursor.isoformat(),
                        "end": b_end.isoformat(),
                        "type": "break"
                    })
                    cursor = b_end
                minutes_since_break = 0
            i += 1

        # Add routine reminder blocks (non-overlapping check omitted for simplicity)
        blocks.extend(routine_blocks)
        blocks_sorted = sorted(blocks, key=lambda x: x["start"])
        return {"date": today.isoformat(), "blocks": blocks_sorted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
