from enum import StrEnum
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.models.account import User, UserRole
from digitalcard.models.organization import RolePermission, TenantRole


class Permission(StrEnum):
    PLATFORM_COMPANIES_MANAGE = "platform.companies.manage"
    PLATFORM_USERS_MANAGE = "platform.users.manage"
    COMPANY_READ = "company.read"
    COMPANY_UPDATE = "company.update"
    DEPARTMENT_READ = "department.read"
    DEPARTMENT_CREATE = "department.create"
    DEPARTMENT_UPDATE = "department.update"
    DEPARTMENT_MOVE = "department.move"
    DEPARTMENT_DISABLE = "department.disable"
    ROLE_READ = "role.read"
    ROLE_UPDATE = "role.update"
    AUDIT_READ = "audit.read"
    CONTENT_MANAGE = "content.manage"
    CUSTOMER_ALL_MANAGE = "customer.all_manage"
    EMPLOYEE_READ = "employee.read"
    EMPLOYEE_CREATE = "employee.create"
    EMPLOYEE_UPDATE = "employee.update"
    EMPLOYEE_STATUS = "employee.status"
    EMPLOYEE_IMPORT = "employee.import"
    EMPLOYEE_INVITE = "employee.invite"
    EMPLOYEE_SELF_UPDATE = "employee.self_update"
    CARD_READ = "card.read"
    CARD_EDIT_SELF = "card.edit_self"
    CARD_PUBLISH_SELF = "card.publish_self"
    CARD_MANAGE = "card.manage"
    CARD_TEMPLATE_MANAGE = "card.template.manage"
    PRODUCT_READ = "product.read"
    PRODUCT_MANAGE = "product.manage"
    MATERIAL_READ = "material.read"
    MATERIAL_MANAGE = "material.manage"
    LEAD_READ = "lead.read"
    LEAD_MANAGE = "lead.manage"
    LEAD_CLAIM = "lead.claim"
    NOTIFICATION_READ = "notification.read"
    CUSTOMER_READ = "customer.read"
    CUSTOMER_MANAGE = "customer.manage"
    CUSTOMER_SELF_MANAGE = "customer.self_manage"
    OPPORTUNITY_MANAGE = "opportunity.manage"
    OPPORTUNITY_STAGE_MANAGE = "opportunity.stage.manage"
    ANALYTICS_READ = "analytics.read"
    ANALYTICS_ALL = "analytics.all"
    ANALYTICS_EXPORT = "analytics.export"


PERMISSION_DEFINITIONS: dict[str, tuple[str, str]] = {
    Permission.COMPANY_READ.value: ("查看企业资料", "企业"),
    Permission.COMPANY_UPDATE.value: ("维护企业资料", "企业"),
    Permission.DEPARTMENT_READ.value: ("查看部门", "组织"),
    Permission.DEPARTMENT_CREATE.value: ("创建部门", "组织"),
    Permission.DEPARTMENT_UPDATE.value: ("编辑部门", "组织"),
    Permission.DEPARTMENT_MOVE.value: ("移动和排序部门", "组织"),
    Permission.DEPARTMENT_DISABLE.value: ("停用或启用部门", "组织"),
    Permission.ROLE_READ.value: ("查看角色权限", "权限"),
    Permission.ROLE_UPDATE.value: ("配置角色权限", "权限"),
    Permission.AUDIT_READ.value: ("查看变更审计", "审计"),
    Permission.CONTENT_MANAGE.value: ("管理企业内容", "业务"),
    Permission.CUSTOMER_MANAGE.value: ("管理客户与跟进", "业务"),
    Permission.EMPLOYEE_READ.value: ("查看员工档案", "员工"),
    Permission.EMPLOYEE_CREATE.value: ("创建员工", "员工"),
    Permission.EMPLOYEE_UPDATE.value: ("编辑员工", "员工"),
    Permission.EMPLOYEE_STATUS.value: ("停用或恢复员工", "员工"),
    Permission.EMPLOYEE_IMPORT.value: ("批量导入员工", "员工"),
    Permission.EMPLOYEE_INVITE.value: ("邀请员工开通账户", "员工"),
    Permission.EMPLOYEE_SELF_UPDATE.value: ("维护个人资料", "员工"),
    Permission.CARD_READ.value: ("查看名片", "名片"),
    Permission.CARD_EDIT_SELF.value: ("编辑本人名片", "名片"),
    Permission.CARD_PUBLISH_SELF.value: ("发布本人名片", "名片"),
    Permission.CARD_MANAGE.value: ("管理企业员工名片", "名片"),
    Permission.CARD_TEMPLATE_MANAGE.value: ("管理企业名片模板", "名片"),
    Permission.PRODUCT_READ.value: ("查看企业产品", "产品"),
    Permission.PRODUCT_MANAGE.value: ("管理企业产品", "产品"),
    Permission.MATERIAL_READ.value: ("查看企业素材", "素材"),
    Permission.MATERIAL_MANAGE.value: ("管理企业素材", "素材"),
    Permission.LEAD_READ.value: ("查看销售线索", "线索"),
    Permission.LEAD_MANAGE.value: ("分配和管理销售线索", "线索"),
    Permission.LEAD_CLAIM.value: ("领取和处理本人线索", "线索"),
    Permission.NOTIFICATION_READ.value: ("查看站内通知", "通知"),
    Permission.CUSTOMER_READ.value: ("查看客户档案", "客户"),
    Permission.CUSTOMER_ALL_MANAGE.value: ("管理和转移企业全部客户", "客户"),
    Permission.CUSTOMER_SELF_MANAGE.value: ("维护本人负责的客户", "客户"),
    Permission.OPPORTUNITY_MANAGE.value: ("管理客户商机", "商机"),
    Permission.OPPORTUNITY_STAGE_MANAGE.value: ("配置商机阶段", "商机"),
    Permission.ANALYTICS_READ.value: ("查看经营分析", "分析"),
    Permission.ANALYTICS_ALL.value: ("查看企业全部经营数据", "分析"),
    Permission.ANALYTICS_EXPORT.value: ("导出经营报表", "分析"),
}

ROLE_DEFINITIONS: dict[UserRole, tuple[str, str]] = {
    UserRole.COMPANY_ADMIN: ("企业管理员", "管理企业资料、组织、角色和审计"),
    UserRole.CONTENT_ADMIN: ("内容管理员", "维护企业展示内容"),
    UserRole.SALES: ("销售", "查看组织并管理客户"),
    UserRole.EMPLOYEE: ("普通员工", "查看企业和组织基础信息"),
}

DEFAULT_ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.COMPANY_ADMIN: set(PERMISSION_DEFINITIONS),
    UserRole.CONTENT_ADMIN: {
        Permission.COMPANY_READ.value,
        Permission.DEPARTMENT_READ.value,
        Permission.CONTENT_MANAGE.value,
        Permission.EMPLOYEE_READ.value,
        Permission.EMPLOYEE_SELF_UPDATE.value,
        Permission.CARD_READ.value,
        Permission.CARD_EDIT_SELF.value,
        Permission.CARD_PUBLISH_SELF.value,
        Permission.CARD_MANAGE.value,
        Permission.CARD_TEMPLATE_MANAGE.value,
        Permission.PRODUCT_READ.value,
        Permission.PRODUCT_MANAGE.value,
        Permission.MATERIAL_READ.value,
        Permission.MATERIAL_MANAGE.value,
        Permission.LEAD_READ.value,
        Permission.NOTIFICATION_READ.value,
        Permission.CUSTOMER_READ.value,
        Permission.ANALYTICS_READ.value,
        Permission.ANALYTICS_ALL.value,
        Permission.ANALYTICS_EXPORT.value,
    },
    UserRole.SALES: {
        Permission.COMPANY_READ.value,
        Permission.DEPARTMENT_READ.value,
        Permission.CUSTOMER_MANAGE.value,
        Permission.EMPLOYEE_READ.value,
        Permission.EMPLOYEE_SELF_UPDATE.value,
        Permission.CARD_READ.value,
        Permission.CARD_EDIT_SELF.value,
        Permission.CARD_PUBLISH_SELF.value,
        Permission.PRODUCT_READ.value,
        Permission.MATERIAL_READ.value,
        Permission.LEAD_READ.value,
        Permission.LEAD_CLAIM.value,
        Permission.NOTIFICATION_READ.value,
        Permission.CUSTOMER_READ.value,
        Permission.CUSTOMER_SELF_MANAGE.value,
        Permission.OPPORTUNITY_MANAGE.value,
        Permission.ANALYTICS_READ.value,
    },
    UserRole.EMPLOYEE: {
        Permission.COMPANY_READ.value,
        Permission.DEPARTMENT_READ.value,
        Permission.EMPLOYEE_READ.value,
        Permission.EMPLOYEE_SELF_UPDATE.value,
        Permission.CARD_READ.value,
        Permission.CARD_EDIT_SELF.value,
        Permission.CARD_PUBLISH_SELF.value,
        Permission.PRODUCT_READ.value,
        Permission.NOTIFICATION_READ.value,
        Permission.ANALYTICS_READ.value,
    },
}

PLATFORM_PERMISSIONS = {
    Permission.PLATFORM_COMPANIES_MANAGE.value,
    Permission.PLATFORM_USERS_MANAGE.value,
}


def seed_tenant_roles(db: Session, company_id: str) -> None:
    for role_code, (name, description) in ROLE_DEFINITIONS.items():
        role = TenantRole(
            id=str(uuid4()),
            company_id=company_id,
            code=role_code.value,
            name=name,
            description=description,
            is_system=True,
        )
        db.add(role)
        db.flush()
        for permission_code in DEFAULT_ROLE_PERMISSIONS[role_code]:
            db.add(RolePermission(role_id=role.id, permission_code=permission_code))


def permissions_for_user(db: Session, user: User) -> set[str]:
    if user.role == UserRole.PLATFORM_ADMIN.value:
        return PLATFORM_PERMISSIONS.copy()
    if user.company_id is None:
        return set()
    role = db.scalar(
        select(TenantRole).where(
            TenantRole.company_id == user.company_id,
            TenantRole.code == user.role,
        )
    )
    if role is None:
        return set()
    return set(
        db.scalars(select(RolePermission.permission_code).where(RolePermission.role_id == role.id))
    )
