from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.core.errors import AppError
from digitalcard.models.account import User
from digitalcard.models.employee import Employee, EmployeeStatus
from digitalcard.services.quotas import enforce_quota
from digitalcard.services.tenancy import record_tenant_audit


def get_or_create_employee_for_user(db: Session, user: User) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.company_id == user.company_id, Employee.user_id == user.id)
    )
    if employee is not None:
        return employee

    employee = db.scalar(
        select(Employee).where(
            Employee.company_id == user.company_id,
            Employee.email == user.email,
        )
    )
    if employee is not None:
        if employee.user_id is not None and employee.user_id != user.id:
            raise AppError(
                "employee_account_conflict",
                "An employee with this email is linked to another account",
                409,
            )
        employee.user_id = user.id
        record_tenant_audit(
            db,
            user.company_id,
            user.id,
            "employee.account_auto_linked",
            "employee",
            employee.id,
            {"user_id": user.id},
        )
        db.flush()
        return employee

    base_number = f"AUTO-{user.id.replace('-', '')[:8].upper()}"
    employee_number = base_number
    suffix = 1
    while db.scalar(
        select(Employee.id).where(
            Employee.company_id == user.company_id,
            Employee.employee_no == employee_number,
        )
    ):
        suffix += 1
        employee_number = f"{base_number}-{suffix}"
    enforce_quota(db, user.company_id, "employees")
    employee = Employee(
        company_id=user.company_id,
        employee_no=employee_number,
        name=user.display_name,
        email=user.email,
        department_id=user.department_id,
        user_id=user.id,
        status=EmployeeStatus.ACTIVE.value,
    )
    db.add(employee)
    db.flush()
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "employee.auto_created_for_account",
        "employee",
        employee.id,
        {"employee_no": employee.employee_no, "user_id": user.id},
    )
    return employee
