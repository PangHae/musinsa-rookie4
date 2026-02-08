from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.professor import Professor
from app.schemas.professor import ProfessorResponse

router = APIRouter(prefix="/professors", tags=["professors"])


@router.get("", response_model=list[ProfessorResponse])
async def get_professors(
    department_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Professor).options(joinedload(Professor.department))
    if department_id is not None:
        stmt = stmt.where(Professor.department_id == department_id)
    stmt = stmt.order_by(Professor.id)

    result = await db.execute(stmt)
    professors = result.scalars().unique().all()

    return [
        ProfessorResponse(
            id=p.id,
            name=p.name,
            employee_number=p.employee_number,
            department_id=p.department_id,
            department_name=p.department.name,
        )
        for p in professors
    ]
