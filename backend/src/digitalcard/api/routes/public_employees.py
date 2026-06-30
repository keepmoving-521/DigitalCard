from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.core.errors import AppError
from digitalcard.db.session import get_db
from digitalcard.models.employee import Employee, EmployeeStatus
from digitalcard.models.organization import Company, CompanyStatus, InactiveEmployeeVisibility
from digitalcard.schemas.employee import PublicEmployeeResponse

router = APIRouter(prefix="/public/employees", tags=["public employees"])


@router.get("/{employee_id}", response_model=PublicEmployeeResponse, summary="Get public employee")
def get_public_employee(
    employee_id: str, db: Annotated[Session, Depends(get_db)]
) -> PublicEmployeeResponse:
    employee = db.scalar(select(Employee).where(Employee.id == employee_id))
    if employee is None:
        raise AppError("employee_not_found", "Employee was not found", 404)
    company = db.get(Company, employee.company_id)
    hidden = (
        company is None
        or company.status != CompanyStatus.ACTIVE.value
        or (
            employee.status == EmployeeStatus.INACTIVE.value
            and company.inactive_employee_visibility == InactiveEmployeeVisibility.HIDDEN.value
        )
    )
    if hidden:
        raise AppError("employee_not_found", "Employee was not found", 404)
    return PublicEmployeeResponse(
        id=employee.id,
        name=employee.name,
        avatar_url=employee.avatar_url,
        bio=employee.bio,
        position=employee.position,
        employment_status=EmployeeStatus(employee.status),
    )
