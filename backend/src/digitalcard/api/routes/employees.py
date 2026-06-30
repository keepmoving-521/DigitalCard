import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.core.config import Settings, get_settings
from digitalcard.core.errors import AppError
from digitalcard.db.session import get_db
from digitalcard.models.account import User, UserRole
from digitalcard.models.employee import Employee, EmployeeStatus
from digitalcard.models.organization import Company, Department
from digitalcard.schemas.employee import (
    EmployeeCreateRequest,
    EmployeeImportResponse,
    EmployeeImportRowResult,
    EmployeeInviteRequest,
    EmployeeInviteResponse,
    EmployeePageResponse,
    EmployeeResponse,
    EmployeeSelfUpdateRequest,
    EmployeeStatusRequest,
    EmployeeUpdateRequest,
)
from digitalcard.services.invitations import issue_employee_invitation
from digitalcard.services.permissions import Permission
from digitalcard.services.tenancy import record_tenant_audit
from digitalcard.services.tokens import revoke_all_sessions

router = APIRouter(prefix="/tenant/employees", tags=["employees"])


def tenant_employee(db: Session, company_id: str, employee_id: str) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.company_id == company_id)
    )
    if employee is None:
        raise AppError("employee_not_found", "Employee was not found", 404)
    return employee


def validate_unique_fields(
    db: Session, company_id: str, values: dict[str, object], employee_id: str | None = None
) -> None:
    definitions = (
        ("employee_no", "employee_no_exists", "Employee number already exists"),
        ("phone", "employee_phone_exists", "Phone number already exists"),
        ("email", "employee_email_exists", "Email address already exists"),
    )
    for field, code, message in definitions:
        value = values.get(field)
        if value is None:
            continue
        query = select(Employee.id).where(
            Employee.company_id == company_id, getattr(Employee, field) == value
        )
        if employee_id:
            query = query.where(Employee.id != employee_id)
        if db.scalar(query):
            raise AppError(code, message, 409)


def validate_relations(
    db: Session,
    company_id: str,
    values: dict[str, object],
    employee_id: str | None = None,
) -> None:
    department_id = values.get("department_id")
    if department_id:
        department = db.scalar(
            select(Department).where(
                Department.id == department_id, Department.company_id == company_id
            )
        )
        if department is None:
            raise AppError("department_not_found", "Department was not found", 404)
        if not department.is_active:
            raise AppError("department_inactive", "Department is inactive", 409)
    manager_id = values.get("manager_id")
    if manager_id:
        if manager_id == employee_id:
            raise AppError("manager_cycle", "An employee cannot manage themselves", 409)
        manager = tenant_employee(db, company_id, str(manager_id))
        seen = {employee_id}
        while manager.manager_id:
            if manager.manager_id in seen:
                raise AppError("manager_cycle", "Reporting hierarchy cannot contain a cycle", 409)
            seen.add(manager.id)
            manager = tenant_employee(db, company_id, manager.manager_id)
    user_id = values.get("user_id")
    if user_id:
        account = db.get(User, str(user_id))
        if (
            account is None
            or account.company_id != company_id
            or account.role == UserRole.PLATFORM_ADMIN.value
        ):
            raise AppError("account_not_found", "Tenant account was not found", 404)
        linked = db.scalar(select(Employee.id).where(Employee.user_id == user_id))
        if linked and linked != employee_id:
            raise AppError("account_already_linked", "Account is linked to another employee", 409)


def create_employee_record(
    db: Session, company_id: str, payload: EmployeeCreateRequest
) -> Employee:
    values = payload.model_dump()
    validate_unique_fields(db, company_id, values)
    validate_relations(db, company_id, values)
    employee = Employee(company_id=company_id, **values)
    db.add(employee)
    db.flush()
    if employee.user_id:
        account = db.get(User, employee.user_id)
        account.department_id = employee.department_id
    return employee


@router.get("", response_model=EmployeePageResponse, summary="List employees")
def list_employees(
    user: Annotated[User, Depends(require_permission(Permission.EMPLOYEE_READ))],
    db: Annotated[Session, Depends(get_db)],
    keyword: str | None = None,
    employee_status: Annotated[EmployeeStatus | None, Query(alias="status")] = None,
    department_id: str | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EmployeePageResponse:
    conditions = [Employee.company_id == user.company_id]
    if keyword:
        pattern = f"%{keyword.strip()}%"
        conditions.append(
            or_(
                Employee.employee_no.ilike(pattern),
                Employee.name.ilike(pattern),
                Employee.phone.ilike(pattern),
                Employee.email.ilike(pattern),
            )
        )
    if employee_status:
        conditions.append(Employee.status == employee_status.value)
    if department_id:
        conditions.append(Employee.department_id == department_id)
    total = db.scalar(select(func.count()).select_from(Employee).where(*conditions)) or 0
    items = list(
        db.scalars(
            select(Employee)
            .where(*conditions)
            .order_by(Employee.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return EmployeePageResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/me", response_model=EmployeeResponse, summary="Get my employee profile")
def get_my_employee(
    user: Annotated[User, Depends(require_permission(Permission.EMPLOYEE_SELF_UPDATE))],
    db: Annotated[Session, Depends(get_db)],
) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.company_id == user.company_id, Employee.user_id == user.id)
    )
    if employee is None:
        raise AppError("employee_profile_not_found", "Employee profile was not found", 404)
    return employee


@router.patch("/me", response_model=EmployeeResponse, summary="Update my employee profile")
def update_my_employee(
    payload: EmployeeSelfUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.EMPLOYEE_SELF_UPDATE))],
    db: Annotated[Session, Depends(get_db)],
) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.company_id == user.company_id, Employee.user_id == user.id)
    )
    if employee is None:
        raise AppError("employee_profile_not_found", "Employee profile was not found", 404)
    changes = payload.model_dump(exclude_unset=True)
    company = db.get(Company, user.company_id)
    denied = set(changes) - set(company.employee_self_editable_fields or [])
    if denied:
        raise AppError(
            "self_edit_not_allowed",
            "One or more fields cannot be edited by employees",
            403,
            {"fields": sorted(denied)},
        )
    validate_unique_fields(db, user.company_id, changes, employee.id)
    before = {key: getattr(employee, key) for key in changes}
    for key, value in changes.items():
        setattr(employee, key, value)
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "employee.self_updated",
        "employee",
        employee.id,
        {"before": before, "after": changes},
    )
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/{employee_id}", response_model=EmployeeResponse, summary="Get employee")
def get_employee(
    employee_id: str,
    user: Annotated[User, Depends(require_permission(Permission.EMPLOYEE_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> Employee:
    return tenant_employee(db, user.company_id, employee_id)


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create employee",
)
def create_employee(
    payload: EmployeeCreateRequest,
    user: Annotated[User, Depends(require_permission(Permission.EMPLOYEE_CREATE))],
    db: Annotated[Session, Depends(get_db)],
) -> Employee:
    employee = create_employee_record(db, user.company_id, payload)
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "employee.created",
        "employee",
        employee.id,
        {"employee_no": employee.employee_no, "name": employee.name},
    )
    db.commit()
    db.refresh(employee)
    return employee


@router.patch("/{employee_id}", response_model=EmployeeResponse, summary="Update employee")
def update_employee(
    employee_id: str,
    payload: EmployeeUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.EMPLOYEE_UPDATE))],
    db: Annotated[Session, Depends(get_db)],
) -> Employee:
    employee = tenant_employee(db, user.company_id, employee_id)
    changes = payload.model_dump(exclude_unset=True)
    validate_unique_fields(db, user.company_id, changes, employee.id)
    relation_values = {
        "department_id": changes.get("department_id", employee.department_id),
        "manager_id": changes.get("manager_id", employee.manager_id),
        "user_id": changes.get("user_id", employee.user_id),
    }
    validate_relations(db, user.company_id, relation_values, employee.id)
    before = {key: getattr(employee, key) for key in changes}
    for key, value in changes.items():
        setattr(employee, key, value)
    if "user_id" in changes or "department_id" in changes:
        account = db.get(User, employee.user_id) if employee.user_id else None
        if account:
            account.department_id = employee.department_id
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "employee.updated",
        "employee",
        employee.id,
        {"before": before, "after": changes},
    )
    db.commit()
    db.refresh(employee)
    return employee


@router.post(
    "/{employee_id}/status", response_model=EmployeeResponse, summary="Set employee status"
)
def set_employee_status(
    employee_id: str,
    payload: EmployeeStatusRequest,
    user: Annotated[User, Depends(require_permission(Permission.EMPLOYEE_STATUS))],
    db: Annotated[Session, Depends(get_db)],
) -> Employee:
    employee = tenant_employee(db, user.company_id, employee_id)
    if employee.status == payload.status.value:
        return employee
    account = db.get(User, employee.user_id) if employee.user_id else None
    if payload.status == EmployeeStatus.INACTIVE:
        if account and account.is_active:
            account.is_active = False
            account.token_version += 1
            employee.account_disabled_by_employee = True
            revoke_all_sessions(db, account.id)
    elif account and employee.account_disabled_by_employee:
        account.is_active = True
        employee.account_disabled_by_employee = False
    employee.status = payload.status.value
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "employee.status_changed",
        "employee",
        employee.id,
        {"status": employee.status},
    )
    db.commit()
    db.refresh(employee)
    return employee


@router.post(
    "/{employee_id}/invite", response_model=EmployeeInviteResponse, summary="Invite employee"
)
def invite_employee(
    employee_id: str,
    payload: EmployeeInviteRequest,
    user: Annotated[User, Depends(require_permission(Permission.EMPLOYEE_INVITE))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmployeeInviteResponse:
    employee = tenant_employee(db, user.company_id, employee_id)
    invitation, invite_url = issue_employee_invitation(db, employee, payload.role, settings)
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "employee.invited",
        "employee",
        employee.id,
        {"invitation_id": invitation.id, "role": payload.role.value},
    )
    db.commit()
    return EmployeeInviteResponse(
        invitation_id=invitation.id, invite_url=invite_url, expires_at=invitation.expires_at
    )


@router.post("/import", response_model=EmployeeImportResponse, summary="Import employees from CSV")
async def import_employees(
    request: Request,
    user: Annotated[User, Depends(require_permission(Permission.EMPLOYEE_IMPORT))],
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeImportResponse:
    try:
        content = (await request.body()).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError("invalid_csv_encoding", "CSV must use UTF-8 encoding", 422) from exc
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or not {"employee_no", "name"}.issubset(reader.fieldnames):
        raise AppError("invalid_csv_headers", "CSV requires employee_no and name columns", 422)
    rows = list(reader)
    if len(rows) > 500:
        raise AppError("csv_row_limit", "CSV cannot contain more than 500 rows", 422)
    results: list[EmployeeImportRowResult] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            department_id = None
            if row.get("department_code", "").strip():
                department_id = db.scalar(
                    select(Department.id).where(
                        Department.company_id == user.company_id,
                        Department.code == row["department_code"].strip().upper(),
                    )
                )
                if not department_id:
                    raise AppError("department_not_found", "Department code was not found", 404)
            manager_id = None
            if row.get("manager_employee_no", "").strip():
                manager_id = db.scalar(
                    select(Employee.id).where(
                        Employee.company_id == user.company_id,
                        Employee.employee_no == row["manager_employee_no"].strip().upper(),
                    )
                )
                if not manager_id:
                    raise AppError(
                        "manager_not_found", "Manager employee number was not found", 404
                    )
            payload = EmployeeCreateRequest(
                employee_no=row.get("employee_no", ""),
                name=row.get("name", ""),
                phone=row.get("phone") or None,
                email=row.get("email") or None,
                position=row.get("position") or None,
                bio=row.get("bio") or None,
                avatar_url=row.get("avatar_url") or None,
                department_id=department_id,
                manager_id=manager_id,
            )
            employee = create_employee_record(db, user.company_id, payload)
            record_tenant_audit(
                db,
                user.company_id,
                user.id,
                "employee.imported",
                "employee",
                employee.id,
                {"row": row_number, "employee_no": employee.employee_no},
            )
            db.commit()
            results.append(
                EmployeeImportRowResult(row=row_number, status="success", employee_id=employee.id)
            )
        except (AppError, ValidationError) as exc:
            db.rollback()
            if isinstance(exc, AppError):
                code, message = exc.code, exc.message
            else:
                code, message = "validation_error", exc.errors()[0]["msg"]
            results.append(
                EmployeeImportRowResult(row=row_number, status="failed", code=code, message=message)
            )
    succeeded = sum(result.status == "success" for result in results)
    return EmployeeImportResponse(
        total=len(results), succeeded=succeeded, failed=len(results) - succeeded, results=results
    )
