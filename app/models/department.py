from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)

    professors = relationship("Professor", back_populates="department")
    courses = relationship("Course", back_populates="department")
    students = relationship("Student", back_populates="department")
