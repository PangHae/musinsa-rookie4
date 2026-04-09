from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.professor import Professor
from app.schemas.professor import PaginatedProfessorResponse, ProfessorResponse

router = APIRouter(prefix="/professors", tags=["professors"])


@router.get("", response_model=PaginatedProfessorResponse)
async def get_professors(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    department_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    count_stmt = select(func.count(Professor.id))
    if department_id is not None:
        count_stmt = count_stmt.where(Professor.department_id == department_id)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = select(Professor).options(joinedload(Professor.department))
    if department_id is not None:
        stmt = stmt.where(Professor.department_id == department_id)
    stmt = stmt.order_by(Professor.id).offset((page - 1) * size).limit(size)

    result = await db.execute(stmt)
    professors = result.scalars().unique().all()

    return PaginatedProfessorResponse(
        total=total,
        page=page,
        size=size,
        items=[
            ProfessorResponse(
                id=p.id,
                name=p.name,
                employee_number=p.employee_number,
                department_id=p.department_id,
                department_name=p.department.name,
            )
            for p in professors
        ],
    )
