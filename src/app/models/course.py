from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_department_id", "department_id"),
        Index("ix_courses_professor_id", "professor_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=False
    )
    professor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("professors.id"), nullable=False
    )

    department = relationship("Department", back_populates="courses")
    professor = relationship("Professor", back_populates="courses")
    schedules = relationship("CourseSchedule", back_populates="course")
    enrollments = relationship("Enrollment", back_populates="course")
