from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import structlog

from . import crud, models, schemas, dependencies
from .database import SessionLocal, engine
from .dependencies import get_db
from . import auth, statistics
from .logging_config import setup_logging

setup_logging()

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EBF Management API",
    description="A simple API to manage students, points, and statistics.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        path=request.url.path,
        method=request.method,
        client_host=request.client.host,
    )
    response = await call_next(request)
    structlog.get_logger().info("request processed")
    return response

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(statistics.router, prefix="/stats", tags=["statistics"])

@app.get("/health")
def health_check():
    return {"status": "ok"}

# --- API Endpoints ---

# User Management
@app.post("/users", response_model=schemas.User, status_code=201)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

# Student Management
@app.post("/students", response_model=schemas.StudentResponse, status_code=201)
def create_student(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user), student: StudentBase):
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    student = schemas.StudentCreate(**sanitized_body)
    return crud.create_student(db=db, student=student, user_id=current_user.id)

@app.get("/students", response_model=List[schemas.StudentResponse])
def list_students(
    age_group: str = None,
    gender: str = None,
    min_age: int = None,
    max_age: int = None,
    sort_by: str = None,
    order: str = "asc",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    return crud.get_students(
        db,
        age_group=age_group,
        gender=gender,
        min_age=min_age,
        max_age=max_age,
        sort_by=sort_by,
        order=order,
        skip=skip,
        limit=limit
    )

@app.get("/students/{student_id}", response_model=schemas.StudentDetailResponse)
def get_student(student_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    db_student = crud.get_student(db, student_id=student_id)
    if db_student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return db_student

@app.put("/students/{student_id}", response_model=schemas.StudentResponse)
def update_student(student_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user), sanitized_body: dict = Depends(dependencies.sanitize_body)):
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    student_update = schemas.StudentUpdate(**sanitized_body)
    db_student = crud.update_student(db, student_id=student_id, student_update=student_update, user_id=current_user.id)
    if db_student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return db_student

@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    db_student = crud.delete_student(db, student_id=student_id, user_id=current_user.id)
    if db_student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return

# Points Management
@app.post("/students/{student_id}/points", response_model=schemas.StudentResponse)
def award_daily_points(student_id: str, points_create: schemas.PointsCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    student = crud.award_daily_points(db, student_id=student_id, points_create=points_create)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if isinstance(student, str):
        raise HTTPException(status_code=400, detail=student)
    return student

@app.patch("/students/{student_id}/points/adjust", response_model=schemas.StudentResponse)
def adjust_student_points(student_id: str, adjustment: schemas.PointAdjustment, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    student = crud.adjust_points(db, student_id=student_id, adjustment=adjustment, user_id=current_user.id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

# Class & Teacher Management
@app.get("/classes", response_model=List[schemas.ClassResponse])
def list_classes(db: Session = Depends(get_db)):
    # This data is static for now, but could be moved to a separate table
    classes = [
        {"id": "0-6", "name": "Nursery", "description": "Early childhood development and basic learning", "min_age": 0, "max_age": 6},
        {"id": "7-9", "name": "Beginners", "description": "Foundation skills and structured learning", "min_age": 7, "max_age": 9},
        {"id": "10-12", "name": "Intermediate", "description": "Advanced concepts and critical thinking", "min_age": 10, "max_age": 12},
        {"id": "13-15", "name": "Advanced", "description": "Complex topics and leadership development", "min_age": 13, "max_age": 15},
    ]
    
    response = []
    for c in classes:
        student_count = db.query(models.Student).filter(models.Student.group == c["id"]).count()
        response.append({**c, "student_count": student_count})
    return response

@app.get("/classes/{class_id}/teachers", response_model=List[schemas.TeacherResponse])
def get_class_teachers(class_id: str):
    # Placeholder data
    teachers = {
        "7-9": [
            {"id": "teacher-001", "name": "Sarah Johnson", "phone": "+1234567890", "email": "sarah.johnson@school.edu", "specialization": "Elementary Education", "years_experience": 8}
        ]
    }
    return teachers.get(class_id, [])

# Constants & Configuration
@app.get("/constants/points", response_model=dict)
def get_point_values():
    return {
        "PRESENCE": {"value": 50, "description": "Daily attendance bonus", "category": "attendance"},
        "BOOK": {"value": 20, "description": "Bringing required materials", "category": "preparation"},
        "VERSICLE": {"value": 30, "description": "Reciting verses or passages", "category": "academic"},
        "PARTICIPATION": {"value": 40, "description": "Active class participation", "category": "engagement"},
        "GUEST": {"value": 10, "description": "Bringing visitors", "category": "outreach"},
        "GAME": {"value": 15, "description": "Winning games or competitions", "category": "achievement"},
    }

@app.get("/constants/config", response_model=dict)
def get_system_config():
    return {
        "age_groups": {
            "0-6": "Nursery",
            "7-9": "Beginners",
            "10-12": "Intermediate",
            "13-15": "Advanced"
        },
        "attendance_threshold": 70.0,
        "engagement_benchmark": 80.0,
        "max_daily_points": 165,
        "system_version": "1.0.0"
    }
