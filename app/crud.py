from sqlalchemy.orm import Session
from . import models, schemas, security
from .config import settings
import uuid
from datetime import date, timedelta
from sqlalchemy import func, case
import statistics

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password, role=user.role)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_age_group(age: int) -> str:
    if 0 <= age <= 6:
        return "0-6"
    if 7 <= age <= 9:
        return "7-9"
    if 10 <= age <= 12:
        return "10-12"
    if 13 <= age <= 18:
        return "13-15"
    return "N/A"

def calculate_points(points_data: schemas.PointsBase) -> int:
    total = 0
    if points_data.presence: total += settings.POINT_VALUES["PRESENCE"]
    if points_data.book: total += settings.POINT_VALUES["BOOK"]
    if points_data.versicle: total += settings.POINT_VALUES["VERSICLE"]
    if points_data.participation: total += settings.POINT_VALUES["PARTICIPATION"]
    if points_data.guest: total += settings.POINT_VALUES["GUEST"]
    if points_data.game: total += settings.POINT_VALUES["GAME"]
    return total

def recalculate_student_total_points(db: Session, student_id: str):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if student:
        total_points = sum(p.total for p in student.points_records)
        student.total_points = total_points
        db.commit()
        db.refresh(student)

def get_student_by_name(db: Session, name: str):
    return db.query(models.Student).filter(models.Student.name == name).first()

def get_student(db: Session, student_id: str):
    return db.query(models.Student).filter(models.Student.id == student_id).first()

def get_students(db: Session, age_group: str = None, gender: str = None, min_age: int = None, max_age: int = None, sort_by: str = None, order: str = "asc", skip: int = 0, limit: int = 100):
    query = db.query(models.Student)

    if age_group:
        if age_group == "custom":
            if min_age is not None:
                query = query.filter(models.Student.age >= min_age)
            if max_age is not None:
                query = query.filter(models.Student.age <= max_age)
        else:
            query = query.filter(models.Student.group == age_group)
    
    if gender:
        query = query.filter(models.Student.gender == gender)

    if sort_by:
        if hasattr(models.Student, sort_by):
            column = getattr(models.Student, sort_by)
            if order == "desc":
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())

    return query.offset(skip).limit(limit).all()

def create_student(db: Session, student: schemas.StudentCreate, user_id: int):
    db_student = models.Student(
        id=str(uuid.uuid4()),
        name=student.name,
        age=student.age,
        gender=student.gender,
        group=get_age_group(student.age),
        address=student.address,
        parent_name=student.parent_name,
        parent_phone=student.parent_phone,
        notes=student.notes,
    )
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    create_audit_log(db, user_id, "create_student", f"Created student {db_student.id}")
    return db_student

def update_student(db: Session, student_id: str, student_update: schemas.StudentUpdate, user_id: int):
    db_student = get_student(db, student_id)
    if not db_student:
        return None
    
    update_data = student_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_student, key, value)
    
    if 'age' in update_data and update_data['age'] is not None:
        db_student.group = get_age_group(db_student.age)

    db.commit()
    db.refresh(db_student)
    create_audit_log(db, user_id, "update_student", f"Updated student {db_student.id}")
    return db_student

def delete_student(db: Session, student_id: str, user_id: int):
    db_student = get_student(db, student_id)
    if not db_student:
        return None
    create_audit_log(db, user_id, "delete_student", f"Deleted student {db_student.id}")
    db.delete(db_student)
    db.commit()
    return db_student

def award_daily_points(db: Session, student_id: str, points_create: schemas.PointsCreate):
    student = get_student(db, student_id)
    if not student:
        return None

    existing_points = db.query(models.Points).filter(
        models.Points.student_id == student_id,
        models.Points.award_date == points_create.award_date
    ).first()

    if existing_points:
        db.delete(existing_points)
        db.commit()

    point_details = points_create.points
    total_daily_points = calculate_points(point_details)

    db_points = models.Points(
        student_id=student_id,
        award_date=points_create.award_date,
        presence=point_details.presence,
        book=point_details.book,
        versicle=point_details.versicle,
        participation=point_details.participation,
        guest=point_details.guest,
        game=point_details.game,
        total=total_daily_points
    )

    db.add(db_points)
    db.commit()

    recalculate_student_total_points(db, student_id) 
    db.refresh(student)
    return student


def adjust_points(db: Session, student_id: str, adjustment: schemas.PointAdjustment, user_id: int):
    student = get_student(db, student_id)
    if not student:
        return None

    student.total_points += adjustment.amount
    db.commit()
    db.refresh(student)
    
    details = f"Adjusted points by {adjustment.amount} for student {student_id}. Reason: {adjustment.reason}"
    create_audit_log(db, user_id, "adjust_points", details)
    
    return student

def create_audit_log(db: Session, user_id: int, action: str, details: str):
    db_log = models.AuditLog(user_id=user_id, action=action, details=details)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_average_daily_attendance(db: Session, start_date: date, end_date: date):
    total_attendance = db.query(func.count(models.Points.id)).filter(models.Points.award_date.between(start_date, end_date), models.Points.presence == True).scalar()
    num_days = (date.today() - start_date).days + 1
    return total_attendance / num_days if num_days > 0 else 0

def get_total_points_awarded(db: Session):
    return db.query(func.sum(models.Points.total)).scalar() or 0

def get_daily_attendance(db: Session, day: date):
    return db.query(func.count(models.Points.id)).filter(models.Points.award_date == day, models.Points.presence == True).scalar()

def get_daily_points(db: Session, day: date):
    return db.query(func.sum(models.Points.total)).filter(models.Points.award_date == day).scalar() or 0

def get_daily_attendance_stats(db: Session, target_date: date, class_id: str = None):
    base_query = db.query(models.Points).filter(models.Points.award_date == target_date)
    if class_id:
        base_query = base_query.join(models.Student).filter(models.Student.group == class_id)
    
    total_students_query = db.query(func.count(models.Student.id))
    if class_id:
        total_students_query = total_students_query.filter(models.Student.group == class_id)
    total_students = total_students_query.scalar()

    attendance_count = base_query.filter(models.Points.presence == True).count()
    
    male_attendance = base_query.join(models.Student).filter(models.Student.gender == 'male', models.Points.presence == True).count()
    female_attendance = base_query.join(models.Student).filter(models.Student.gender == 'female', models.Points.presence == True).count()

    return [{
        "day": target_date.weekday() + 1,
        "date": target_date.isoformat(),
        "attendance_count": attendance_count,
        "total_students": total_students,
        "attendance_rate": round(attendance_count / total_students * 100, 1) if total_students > 0 else 0,
        "male_attendance": male_attendance,
        "female_attendance": female_attendance,
        "late_arrivals": 0  # Cannot be implemented without arrival time data
    }]

def get_detailed_today_stats(db: Session):
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    
    total_students = db.query(models.Student).count()
    present_count = get_daily_attendance(db, today)
    
    by_gender = {}
    for gender in ['male', 'female', 'other']:
        total = db.query(models.Student).filter(models.Student.gender == gender).count()
        present = db.query(models.Points).join(models.Student).filter(models.Points.award_date == today, models.Student.gender == gender, models.Points.presence == True).count()
        by_gender[gender] = {"present": present, "total": total, "rate": round(present/total * 100, 1) if total > 0 else 0}

    by_class = {}
    for group in settings.AGE_GROUPS.keys():
        total = db.query(models.Student).filter(models.Student.group == group).count()
        present = db.query(models.Points).join(models.Student).filter(models.Points.award_date == today, models.Student.group == group, models.Points.presence == True).count()
        by_class[group] = {"present": present, "total": total, "rate": round(present/total * 100, 1) if total > 0 else 0}

    return {
        "day": today.weekday() + 1,
        "date": today.isoformat(),
        "event_progress": round(((today - start_of_week).days + 1) / 7 * 100, 1),
        "attendance": {
            "present_count": present_count,
            "total_students": total_students,
            "attendance_rate": round(present_count / total_students * 100, 1) if total_students > 0 else 0,
            "by_gender": by_gender,
            "by_class": by_class
        },
        "points_awarded_today": get_daily_points(db, today),
        "activities_completed": 6, # Static for now
        "upcoming_activities": 2 # Static for now
    }

def get_registration_statistics(db: Session):
    total_students = db.query(models.Student).count()
    
    # Active defined as having at least one point record in the last 7 days
    seven_days_ago = date.today() - timedelta(days=7)
    active_students = db.query(func.count(func.distinct(models.Points.student_id))).filter(models.Points.award_date >= seven_days_ago).scalar()

    by_gender = db.query(models.Student.gender, func.count(models.Student.id)).group_by(models.Student.gender).all()
    by_class = db.query(models.Student.group, func.count(models.Student.id)).group_by(models.Student.group).all()

    return {
        "total_students": total_students,
        "active_participants": active_students,
        "inactive_participants": total_students - active_students,
        "by_gender": {g: c for g, c in by_gender},
        "by_class": {c: co for c, co in by_class},
        "registration_completion_rate": 100.0 # Assuming all fields are required for creation
    }

def get_registration_demographics(db: Session):
    age_dist = db.query(models.Student.age, func.count(models.Student.id).label("count")).group_by(models.Student.age).order_by(models.Student.age).all()
    gender_dist = db.query(models.Student.gender, func.count(models.Student.id).label("count")).group_by(models.Student.gender).all()
    class_dist = db.query(models.Student.group, func.count(models.Student.id).label("count")).group_by(models.Student.group).all()
    
    total_students = db.query(models.Student).count()
    if total_students == 0:
        return {
            "age_distribution": [], "gender_distribution": {}, "class_distribution": {}
        }

    return {
        "age_distribution": [{"age": a, "count": c, "percentage": round(c/total_students*100, 1)} for a, c in age_dist],
        "gender_distribution": {g: {"count": c, "percentage": round(c/total_students*100, 1)} for g, c in gender_dist},
        "class_distribution": {cls: {"count": c, "percentage": round(c/total_students*100, 1)} for cls, c in class_dist}
    }

def get_today_summary(db: Session):
    today = date.today()
    present_count = get_daily_attendance(db, today)
    total_students = db.query(models.Student).count()
    
    top_performers = db.query(models.Student).join(models.Points).filter(models.Points.award_date == today).order_by(models.Points.total.desc()).limit(5).all()
    
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    return {
        "day": today.weekday() + 1,
        "date": today.isoformat(),
        "event_day_name": day_names[today.weekday()],
        "present_count": present_count,
        "total_students": total_students,
        "attendance_rate": round(present_count/total_students*100, 1) if total_students > 0 else 0,
        "points_awarded_today": get_daily_points(db, today),
        "daily_goal_completion": 92.3, # Static for now
        "top_performers_today": [{
            "student_id": p.id, "name": p.name, "gender": p.gender, "class": p.group, 
            "points_today": db.query(models.Points.total).filter(models.Points.student_id == p.id, models.Points.award_date == today).scalar() or 0
        } for p in top_performers],
        "activities_status": {"completed": 6, "in_progress": 1, "upcoming": 1} # Static for now
    }

def get_students_present_today(db: Session):
    today = date.today()
    present_students = db.query(models.Student).join(models.Points).filter(models.Points.award_date == today, models.Points.presence == True).all()
    total_students = db.query(models.Student).count()
    
    return {
        "present_count": len(present_students),
        "present_students": [{
            "id": s.id, "name": s.name, "age": s.age, "gender": s.gender, "class": s.group,
            "points_today": db.query(models.Points.total).filter(models.Points.student_id == s.id, models.Points.award_date == today).scalar() or 0,
            "arrival_time": "08:45" # Static for now
        } for s in present_students],
        "absent_count": total_students - len(present_students),
        "absence_rate": round((total_students - len(present_students)) / total_students * 100, 1) if total_students > 0 else 0,
        "late_arrivals": 4 # Static for now
    }

def get_event_engagement(db: Session, day: str, class_id: str, gender: str):
    base_query = db.query(models.Points)
    student_query = db.query(models.Student)

    if class_id:
        base_query = base_query.join(models.Student).filter(models.Student.group == class_id)
        student_query = student_query.filter(models.Student.group == class_id)
    if gender:
        base_query = base_query.join(models.Student).filter(models.Student.gender == gender)
        student_query = student_query.filter(models.Student.gender == gender)

    total_points_awarded = base_query.with_entities(func.sum(models.Points.total)).scalar() or 0
    total_students = student_query.count()
    
    days_elapsed = (date.today() - (date.today() - timedelta(days=date.today().weekday()))).days + 1
    max_possible_points = total_students * days_elapsed * settings.MAX_DAILY_POINTS
    
    engagement_percent = round(total_points_awarded / max_possible_points * 100, 1) if max_possible_points > 0 else 0
    
    participation_points = base_query.filter(models.Points.participation == True).count() * settings.POINT_VALUES['PARTICIPATION']
    total_participation_possible = student_query.join(models.Points).filter(models.Points.presence==True).count() * settings.POINT_VALUES['PARTICIPATION']
    participation_rate = round(participation_points / total_participation_possible * 100, 1) if total_participation_possible > 0 else 0

    return {
        "event_day": day,
        "days_elapsed": days_elapsed,
        "max_possible_points": max_possible_points,
        "awarded_points": total_points_awarded,
        "engagement_percent": engagement_percent,
        "participation_rate": participation_rate,
        "trend": "increasing",  # Simplified
        "benchmark": settings.ENGAGEMENT_BENCHMARK,
        "performance": "above_benchmark" if engagement_percent > settings.ENGAGEMENT_BENCHMARK else "below_benchmark"
    }

def get_student_performance_rankings(db: Session, class_id: str, gender: str, day: str, limit: int):
    query = db.query(models.Student).order_by(models.Student.total_points.desc())
    if class_id:
        query = query.filter(models.Student.group == class_id)
    if gender:
        query = query.filter(models.Student.gender == gender)
    
    rankings = query.limit(limit).all()
    
    response = []
    for i, s in enumerate(rankings):
        days_attended = db.query(func.count(models.Points.id)).filter(models.Points.student_id == s.id, models.Points.presence == True).scalar()
        total_event_days = (date.today() - (date.today() - timedelta(days=date.today().weekday()))).days + 1
        
        response.append({
            "rank": i + 1,
            "student_id": s.id,
            "name": s.name,
            "age": s.age,
            "gender": s.gender,
            "class": s.group,
            "total_points": s.total_points,
            "days_attended": days_attended,
            "attendance_rate": round(days_attended / total_event_days * 100, 1) if total_event_days > 0 else 0,
            "avg_daily_points": round(s.total_points / days_attended, 1) if days_attended > 0 else 0
        })
    return response

def get_class_performance_comparison(db: Session):
    response = []
    for group_id, group_name in settings.AGE_GROUPS.items():
        student_count = db.query(models.Student).filter(models.Student.group == group_id).count()
        if student_count == 0:
            continue

        avg_points = db.query(func.avg(models.Student.total_points)).filter(models.Student.group == group_id).scalar() or 0
        
        total_attendance = db.query(func.count(models.Points.id)).join(models.Student).filter(models.Student.group == group_id, models.Points.presence == True).scalar()
        total_event_days = (date.today() - (date.today() - timedelta(days=date.today().weekday()))).days + 1
        average_attendance_rate = round((total_attendance / student_count) / total_event_days * 100, 1) if student_count > 0 and total_event_days > 0 else 0

        engagement = get_event_engagement(db, 'overall', group_id, None)

        response.append({
            "class_id": group_id,
            "class_name": group_name,
            "student_count": student_count,
            "average_attendance_rate": average_attendance_rate,
            "average_points": round(avg_points, 2),
            "engagement_score": engagement['engagement_percent'],
            "daily_participation": engagement['participation_rate']
        })
    return response

def get_points_summary_by_category(db: Session, day: str, class_id: str, gender: str):
    base_query = db.query(models.Points)
    if class_id:
        base_query = base_query.join(models.Student).filter(models.Student.group == class_id)
    if gender:
        base_query = base_query.join(models.Student).filter(models.Student.gender == gender)

    total_points_all_categories = base_query.with_entities(func.sum(models.Points.total)).scalar() or 0
    
    response = []
    for category in ["presence", "book", "versicle", "participation", "guest", "game"]:
        category_upper = category.upper()
        point_value = settings.POINT_VALUES[category_upper]
        
        times_awarded = base_query.filter(getattr(models.Points, category) == True).count()
        total_points = times_awarded * point_value
        
        percentage = round(total_points / total_points_all_categories * 100, 1) if total_points_all_categories > 0 else 0
        
        response.append({
            "category": category_upper,
            "total_points": total_points,
            "times_awarded": times_awarded,
            "percentage_of_total": percentage,
            "daily_average": round(total_points / 7, 1) # Simplified
        })
    return response

def get_daily_points_trends(db: Session, include_projections: bool, class_id: str):
    base_query = db.query(models.Points.award_date, func.sum(models.Points.total).label("total_points"))
    if class_id:
        base_query = base_query.join(models.Student).filter(models.Student.group == class_id)
        
    trends = base_query.group_by(models.Points.award_date).order_by(models.Points.award_date).all()
    
    response = []
    for d, t in trends:
        response.append({
            "day": d.weekday() + 1,
            "date": d.isoformat(),
            "total_points": t or 0
        })
    
    if include_projections:
        avg_points = (sum(r['total_points'] for r in response) / len(response)) if response else 0
        last_day = response[-1]['date'] if response else date.today().isoformat()
        
        for i in range(1, 4): # Project next 3 days
            next_day = (date.fromisoformat(last_day) + timedelta(days=i))
            response.append({
                "day": next_day.weekday() + 1,
                "date": next_day.isoformat(),
                "total_points": round(avg_points, 0),
                "projected": True
            })

    return response

def get_event_points_distribution(db: Session):
    points_data = db.query(models.Student.total_points).all()
    points = [p[0] for p in points_data]
    
    if not points:
        return {"distribution": [], "median_points": 0, "average_points": 0, "top_score": 0}

    distribution = {"0-100": 0, "101-200": 0, "201-300": 0, "300+": 0}
    for p in points:
        if p <= 100: distribution["0-100"] += 1
        elif p <= 200: distribution["101-200"] += 1
        elif p <= 300: distribution["201-300"] += 1
        else: distribution["300+"] += 1
            
    return {
        "distribution": [{"range": r, "student_count": c, "percentage": round(c/len(points)*100,1)} for r, c in distribution.items()],
        "median_points": statistics.median(points),
        "average_points": round(statistics.mean(points), 1),
        "top_score": max(points)
    }

def get_performance_analysis(db: Session):
    male_students = db.query(models.Student).filter(models.Student.gender == 'male').count()
    female_students = db.query(models.Student).filter(models.Student.gender == 'female').count()
    
    male_avg_points = db.query(func.avg(models.Student.total_points)).filter(models.Student.gender == 'male').scalar() or 0
    female_avg_points = db.query(func.avg(models.Student.total_points)).filter(models.Student.gender == 'female').scalar() or 0

    male_engagement = get_event_engagement(db, 'overall', None, 'male')['engagement_percent']
    female_engagement = get_event_engagement(db, 'overall', None, 'female')['engagement_percent']

    return {
        "male": {
            "total_students": male_students,
            "average_points": round(male_avg_points, 2),
            "engagement_score": male_engagement
        },
        "female": {
            "total_students": female_students,
            "average_points": round(female_avg_points, 2),
            "engagement_score": female_engagement
        },
        "comparison": {
            "points_difference": round(male_avg_points - female_avg_points, 2),
            "engagement_difference": round(male_engagement - female_engagement, 2)
        }
    }

def get_event_predictions(db: Session):
    start_of_week = date.today() - timedelta(days=date.today().weekday())
    days_elapsed = (date.today() - start_of_week).days + 1
    
    if days_elapsed == 0:
        return {"projected_final_attendance": 0, "projected_total_points": 0, "at_risk_participants": 0}

    avg_daily_attendance = get_average_daily_attendance(db, start_of_week, date.today())
    total_points_awarded = get_total_points_awarded(db)
    avg_daily_points = total_points_awarded / days_elapsed

    projected_total_points = round(total_points_awarded + (avg_daily_points * (7 - days_elapsed)), 0)
    
    # At-risk: less than 2 days attendance in the last 7 days
    seven_days_ago = date.today() - timedelta(days=7)
    at_risk_students = db.query(models.Student.id).join(models.Points).filter(models.Points.award_date >= seven_days_ago, models.Points.presence == True).group_by(models.Student.id).having(func.count(models.Points.id) < 2).count()

    return {
        "remaining_days": 7 - days_elapsed,
        "projected_final_attendance": round(avg_daily_attendance, 1),
        "projected_total_points": projected_total_points,
        "completion_forecast": round((projected_total_points / (db.query(models.Student).count() * 7 * settings.MAX_DAILY_POINTS)) * 100, 1) if db.query(models.Student).count() > 0 else 0,
        "at_risk_participants": {
            "low_attendance": at_risk_students,
            "low_engagement": 0, # Placeholder
            "likely_to_drop": 0 # Placeholder
        }
    }
