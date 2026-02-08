from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Professor(Base):
    __tablename__ = "professors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    employee_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=False
    )

    department = relationship("Department", back_populates="professors")
    courses = relationship("Course", back_populates="professor")
