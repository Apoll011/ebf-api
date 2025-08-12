from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta

from . import crud, models, schemas, dependencies

router = APIRouter()

def get_event_dates():
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=4)
    return start_of_week, end_of_week

@router.get("/event/summary", summary="Get event summary")
def get_event_summary(db: Session = Depends(dependencies.get_db)):
    start_date, end_date = get_event_dates()
    total_students = db.query(models.Student).count()
    
    return {
        "event_name": "Escola Biblica de Ferias 2025",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "current_day": (date.today() - start_date).days + 1,
        "total_days": 5,
        "total_registered": total_students,
        "average_daily_attendance": crud.get_average_daily_attendance(db, start_date, end_date),
        "total_points_awarded": crud.get_total_points_awarded(db),
        "completion_percentage": round(((date.today() - start_date).days + 1) / 5 * 100, 1)
    }

@router.get("/event/progress", summary="Get event progress")
def get_event_progress(db: Session = Depends(dependencies.get_db)):
    start_date, end_date = get_event_dates()
    days_completed = (date.today() - start_date).days + 1
    
    milestones = {}
    for i in range(7):
        day = start_date + timedelta(days=i)
        if day <= date.today():
            status = "completed"
            attendance = crud.get_daily_attendance(db, day)
            points = crud.get_daily_points(db, day)
            milestones[f"day_{i+1}"] = {"status": status, "attendance": attendance, "points": points}
        else:
            status = "upcoming"
            milestones[f"day_{i+1}"] = {"status": status, "projected_attendance": 85} # Placeholder

    return {
        "days_completed": days_completed,
        "days_remaining": 5 - days_completed,
        "overall_progress": round(days_completed / 5 * 100, 1),
        "milestones": milestones
    }

@router.get("/attendance/daily", summary="Get daily attendance")
def get_daily_attendance_stats(day: Optional[int] = None, class_id: Optional[str] = None, db: Session = Depends(dependencies.get_db)):
    start_date, _ = get_event_dates()
    
    if day:
        target_date = start_date + timedelta(days=day-1)
    else:
        target_date = date.today()
        
    return crud.get_daily_attendance_stats(db, target_date, class_id)

@router.get("/today/detailed", summary="Get detailed stats for today")
def get_today_detailed_stats(db: Session = Depends(dependencies.get_db)):
    return crud.get_detailed_today_stats(db)

@router.get("/registrations", summary="Get registration statistics")
def get_registration_stats(db: Session = Depends(dependencies.get_db)):
    return crud.get_registration_statistics(db)

@router.get("/registrations/demographics", summary="Get registration demographics")
def get_registration_demographics(db: Session = Depends(dependencies.get_db)):
    return crud.get_registration_demographics(db)

@router.get("/today/summary", summary="Get summary for today")
def get_today_summary(db: Session = Depends(dependencies.get_db)):
    return crud.get_today_summary(db)

@router.get("/today/students", summary="Get students present today")
def get_students_present_today(db: Session = Depends(dependencies.get_db)):
    return crud.get_students_present_today(db)

@router.get("/engagement", summary="Get event engagement")
def get_event_engagement(day: Optional[str] = 'overall', class_id: Optional[str] = None, gender: Optional[str] = None, db: Session = Depends(dependencies.get_db)):
    return crud.get_event_engagement(db, day, class_id, gender)

@router.get("/performance/rankings", summary="Get student performance rankings")
def get_performance_rankings(class_id: Optional[str] = None, gender: Optional[str] = None, day: Optional[str] = 'overall', limit: int = 10, db: Session = Depends(dependencies.get_db)):
    return crud.get_student_performance_rankings(db, class_id, gender, day, limit)

@router.get("/performance/classes", summary="Get class performance comparison")
def get_class_performance_comparison(db: Session = Depends(dependencies.get_db)):
    return crud.get_class_performance_comparison(db)

@router.get("/points/summary", summary="Get points summary by category")
def get_points_summary_by_category(day: Optional[str] = 'overall', class_id: Optional[str] = None, gender: Optional[str] = None, db: Session = Depends(dependencies.get_db)):
    return crud.get_points_summary_by_category(db, day, class_id, gender)

@router.get("/points/daily", summary="Get daily points trends")
def get_daily_points_trends(include_projections: bool = False, class_id: Optional[str] = None, db: Session = Depends(dependencies.get_db)):
    return crud.get_daily_points_trends(db, include_projections, class_id)

@router.get("/points/distribution", summary="Get event points distribution")
def get_event_points_distribution(db: Session = Depends(dependencies.get_db)):
    return crud.get_event_points_distribution(db)

@router.get("/performance", summary="Get performance analysis")
def get_performance_analysis(db: Session = Depends(dependencies.get_db)):
    return crud.get_performance_analysis(db)

@router.get("/event/predictions", summary="Get event predictions")
def get_event_predictions(db: Session = Depends(dependencies.get_db)):
    return crud.get_event_predictions(db)