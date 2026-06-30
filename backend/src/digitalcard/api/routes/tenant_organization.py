from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.core.errors import AppError
from digitalcard.db.session import get_db
from digitalcard.models.account import User, UserRole
from digitalcard.models.organization import (
    Company,
    Department,
    RolePermission,
    TenantAudit,
    TenantRole,
)
from digitalcard.schemas.organization import (
    CompanyResponse,
    CompanyUpdateRequest,
    DepartmentCreateRequest,
    DepartmentMoveRequest,
    DepartmentResponse,
    DepartmentStatusRequest,
    DepartmentTreeNode,
    DepartmentUpdateRequest,
    PermissionDefinitionResponse,
    RolePermissionsUpdateRequest,
    TenantAuditResponse,
    TenantRoleResponse,
)
from digitalcard.services.permissions import PERMISSION_DEFINITIONS, Permission
from digitalcard.services.tenancy import record_tenant_audit

router = APIRouter(prefix="/tenant", tags=["tenant organization"])


def tenant_department(db: Session, company_id: str, department_id: str) -> Department:
    department = db.scalar(
        select(Department).where(
            Department.id == department_id,
            Department.company_id == company_id,
        )
    )
    if department is None:
        raise AppError("department_not_found", "Department was not found", 404)
    return department


def department_tree(departments: list[Department]) -> list[DepartmentTreeNode]:
    nodes = {
        department.id: DepartmentTreeNode.model_validate(department) for department in departments
    }
    roots: list[DepartmentTreeNode] = []
    for department in departments:
        node = nodes[department.id]
        if department.parent_id and department.parent_id in nodes:
            nodes[department.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


@router.get("/company", response_model=CompanyResponse, summary="Get company profile")
def get_company(
    user: Annotated[User, Depends(require_permission(Permission.COMPANY_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> Company:
    company = db.get(Company, user.company_id)
    if company is None:
        raise AppError("company_not_found", "Company was not found", 404)
    return company


@router.put("/company", response_model=CompanyResponse, summary="Update company profile")
def update_company(
    payload: CompanyUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.COMPANY_UPDATE))],
    db: Annotated[Session, Depends(get_db)],
) -> Company:
    company = db.get(Company, user.company_id)
    if company is None:
        raise AppError("company_not_found", "Company was not found", 404)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("name") is None and "name" in changes:
        raise AppError("invalid_company_name", "Company name cannot be empty", 422)
    before = {key: getattr(company, key) for key in changes}
    for key, value in changes.items():
        setattr(company, key, value)
    if changes:
        record_tenant_audit(
            db,
            company.id,
            user.id,
            "company.profile_updated",
            "company",
            company.id,
            {"before": before, "after": changes},
        )
        db.commit()
        db.refresh(company)
    return company


@router.get("/departments", response_model=list[DepartmentTreeNode], summary="Get department tree")
def list_departments(
    user: Annotated[User, Depends(require_permission(Permission.DEPARTMENT_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[DepartmentTreeNode]:
    departments = list(
        db.scalars(
            select(Department)
            .where(Department.company_id == user.company_id)
            .order_by(Department.sort_order, Department.created_at)
        )
    )
    return department_tree(departments)


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create department",
)
def create_department(
    payload: DepartmentCreateRequest,
    user: Annotated[User, Depends(require_permission(Permission.DEPARTMENT_CREATE))],
    db: Annotated[Session, Depends(get_db)],
) -> Department:
    company_id = user.company_id
    if db.scalar(
        select(Department.id).where(
            Department.company_id == company_id,
            Department.code == payload.code,
        )
    ):
        raise AppError("department_code_exists", "Department code already exists", 409)
    if payload.parent_id:
        parent = tenant_department(db, company_id, payload.parent_id)
        if not parent.is_active:
            raise AppError("parent_department_inactive", "Parent department is inactive", 409)
    department = Department(company_id=company_id, **payload.model_dump())
    db.add(department)
    db.flush()
    record_tenant_audit(
        db,
        company_id,
        user.id,
        "department.created",
        "department",
        department.id,
        {"code": department.code, "name": department.name, "parent_id": department.parent_id},
    )
    db.commit()
    db.refresh(department)
    return department


@router.patch(
    "/departments/{department_id}", response_model=DepartmentResponse, summary="Update department"
)
def update_department(
    department_id: str,
    payload: DepartmentUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.DEPARTMENT_UPDATE))],
    db: Annotated[Session, Depends(get_db)],
) -> Department:
    department = tenant_department(db, user.company_id, department_id)
    changes = payload.model_dump(exclude_unset=True)
    if (
        "code" in changes
        and changes["code"] != department.code
        and db.scalar(
            select(Department.id).where(
                Department.company_id == user.company_id,
                Department.code == changes["code"],
                Department.id != department.id,
            )
        )
    ):
        raise AppError("department_code_exists", "Department code already exists", 409)
    before = {key: getattr(department, key) for key in changes}
    for key, value in changes.items():
        setattr(department, key, value)
    if changes:
        record_tenant_audit(
            db,
            user.company_id,
            user.id,
            "department.updated",
            "department",
            department.id,
            {"before": before, "after": changes},
        )
        db.commit()
        db.refresh(department)
    return department


@router.post(
    "/departments/{department_id}/move",
    response_model=DepartmentResponse,
    summary="Move department",
)
def move_department(
    department_id: str,
    payload: DepartmentMoveRequest,
    user: Annotated[User, Depends(require_permission(Permission.DEPARTMENT_MOVE))],
    db: Annotated[Session, Depends(get_db)],
) -> Department:
    department = tenant_department(db, user.company_id, department_id)
    if payload.parent_id == department.id:
        raise AppError("department_cycle", "A department cannot contain itself", 409)
    cursor = (
        tenant_department(db, user.company_id, payload.parent_id) if payload.parent_id else None
    )
    while cursor is not None:
        if cursor.id == department.id:
            raise AppError("department_cycle", "Department hierarchy cannot contain a cycle", 409)
        cursor = (
            tenant_department(db, user.company_id, cursor.parent_id) if cursor.parent_id else None
        )
    before = {"parent_id": department.parent_id, "sort_order": department.sort_order}
    department.parent_id = payload.parent_id
    department.sort_order = payload.sort_order
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "department.moved",
        "department",
        department.id,
        {"before": before, "after": payload.model_dump()},
    )
    db.commit()
    db.refresh(department)
    return department


@router.post(
    "/departments/{department_id}/status",
    response_model=DepartmentResponse,
    summary="Set department status",
)
def set_department_status(
    department_id: str,
    payload: DepartmentStatusRequest,
    user: Annotated[User, Depends(require_permission(Permission.DEPARTMENT_DISABLE))],
    db: Annotated[Session, Depends(get_db)],
) -> Department:
    department = tenant_department(db, user.company_id, department_id)
    if department.is_active == payload.is_active:
        return department
    if not payload.is_active:
        employee_count = db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.company_id == user.company_id,
                User.department_id == department.id,
                User.is_active.is_(True),
            )
        )
        child_count = db.scalar(
            select(func.count())
            .select_from(Department)
            .where(
                Department.company_id == user.company_id,
                Department.parent_id == department.id,
                Department.is_active.is_(True),
            )
        )
        if employee_count or child_count:
            raise AppError(
                "department_not_empty",
                "Department still contains active employees or child departments",
                409,
                {"employee_count": employee_count or 0, "child_department_count": child_count or 0},
            )
    elif department.parent_id:
        parent = tenant_department(db, user.company_id, department.parent_id)
        if not parent.is_active:
            raise AppError("parent_department_inactive", "Parent department is inactive", 409)
    department.is_active = payload.is_active
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "department.status_changed",
        "department",
        department.id,
        {"is_active": payload.is_active},
    )
    db.commit()
    db.refresh(department)
    return department


@router.get(
    "/permissions",
    response_model=list[PermissionDefinitionResponse],
    summary="List permissions",
)
def list_permissions(
    _: Annotated[User, Depends(require_permission(Permission.ROLE_READ))],
) -> list[PermissionDefinitionResponse]:
    return [
        PermissionDefinitionResponse(code=code, name=name, category=category)
        for code, (name, category) in PERMISSION_DEFINITIONS.items()
    ]


@router.get("/roles", response_model=list[TenantRoleResponse], summary="List tenant roles")
def list_roles(
    user: Annotated[User, Depends(require_permission(Permission.ROLE_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[TenantRoleResponse]:
    roles = list(
        db.scalars(
            select(TenantRole)
            .where(TenantRole.company_id == user.company_id)
            .order_by(TenantRole.created_at)
        )
    )
    result: list[TenantRoleResponse] = []
    for role in roles:
        permissions = list(
            db.scalars(
                select(RolePermission.permission_code)
                .where(RolePermission.role_id == role.id)
                .order_by(RolePermission.permission_code)
            )
        )
        result.append(
            TenantRoleResponse(
                id=role.id,
                code=UserRole(role.code),
                name=role.name,
                description=role.description,
                is_system=role.is_system,
                permissions=permissions,
            )
        )
    return result


@router.put(
    "/roles/{role_code}/permissions",
    response_model=TenantRoleResponse,
    summary="Update role permissions",
)
def update_role_permissions(
    role_code: UserRole,
    payload: RolePermissionsUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.ROLE_UPDATE))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantRoleResponse:
    if role_code in {UserRole.PLATFORM_ADMIN, UserRole.COMPANY_ADMIN}:
        raise AppError("protected_role", "This role's permissions are protected", 409)
    requested = set(payload.permissions)
    invalid = requested - set(PERMISSION_DEFINITIONS)
    if invalid:
        raise AppError(
            "invalid_permissions",
            "One or more permissions are invalid",
            422,
            {"codes": sorted(invalid)},
        )
    role = db.scalar(
        select(TenantRole).where(
            TenantRole.company_id == user.company_id,
            TenantRole.code == role_code.value,
        )
    )
    if role is None:
        raise AppError("role_not_found", "Role was not found", 404)
    previous = set(
        db.scalars(select(RolePermission.permission_code).where(RolePermission.role_id == role.id))
    )
    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    for permission_code in requested:
        db.add(RolePermission(role_id=role.id, permission_code=permission_code))
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "role.permissions_updated",
        "role",
        role.id,
        {"before": sorted(previous), "after": sorted(requested)},
    )
    db.commit()
    return TenantRoleResponse(
        id=role.id,
        code=UserRole(role.code),
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=sorted(requested),
    )


@router.get("/audits", response_model=list[TenantAuditResponse], summary="List tenant audits")
def list_tenant_audits(
    user: Annotated[User, Depends(require_permission(Permission.AUDIT_READ))],
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[TenantAudit]:
    return list(
        db.scalars(
            select(TenantAudit)
            .where(TenantAudit.company_id == user.company_id)
            .order_by(TenantAudit.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
