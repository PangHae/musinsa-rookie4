from app.models.base import Base
from app.models.department import Department
from app.models.professor import Professor
from app.models.course import Course
from app.models.course_schedule import CourseSchedule
from app.models.student import Student
from app.models.enrollment import Enrollment

__all__ = [
    "Base",
    "Department",
    "Professor",
    "Course",
    "CourseSchedule",
    "Student",
    "Enrollment",
]
