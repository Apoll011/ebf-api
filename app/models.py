from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import uuid

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="viewer") # admin, teacher, viewer
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    audit_logs = relationship("AuditLog", back_populates="user")

class Student(Base):
    __tablename__ = "students"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    age = Column(Integer)
    gender = Column(String)
    group = Column(String)
    address = Column(String, nullable=True)
    parent_name = Column(String)
    parent_phone = Column(String)
    notes = Column(String, nullable=True)
    total_points = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())
    points_records = relationship("Points", back_populates="student", cascade="all, delete-orphan")

class Points(Base):
    __tablename__ = "points"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("students.id"))
    award_date = Column(Date)
    presence = Column(Boolean, default=False)
    book = Column(Boolean, default=False)
    versicle = Column(Boolean, default=False)
    participation = Column(Boolean, default=False)
    guest = Column(Boolean, default=False)
    game = Column(Boolean, default=False)
    total = Column(Integer)
    student = relationship("Student", back_populates="points_records")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String)
    details = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="audit_logs")
