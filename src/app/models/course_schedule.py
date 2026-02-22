from sqlalchemy import ForeignKey, Index, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CourseSchedule(Base):
    __tablename__ = "course_schedules"
    __table_args__ = (
        Index("ix_course_schedules_course_id", "course_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id"), nullable=False
    )
    day_of_week: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "09:00"
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "10:15"

    course = relationship("Course", back_populates="schedules")
