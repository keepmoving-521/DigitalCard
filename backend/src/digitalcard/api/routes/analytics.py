import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.api.routes.leads import current_employee
from digitalcard.core.errors import AppError
from digitalcard.db.session import get_db
from digitalcard.models.account import User
from digitalcard.models.analytics import BusinessEvent
from digitalcard.models.card import DigitalCard
from digitalcard.models.employee import Employee
from digitalcard.models.organization import Department
from digitalcard.models.product import Product
from digitalcard.schemas.analytics import (
    AnalyticsDashboardResponse,
    AnalyticsMetric,
    EventSample,
    FunnelItem,
    MetricDefinition,
    RankingItem,
    TrendPoint,
)
from digitalcard.services.permissions import Permission, permissions_for_user

router = APIRouter(prefix="/tenant/analytics", tags=["analytics"])

DEFINITIONS = [
    MetricDefinition(
        code="views",
        name="有效访问量",
        formula="有效 view 事件数",
        deduplication="同一访客、名片、渠道在 30 分钟窗口内只计一次",
    ),
    MetricDefinition(
        code="unique_visitors",
        name="独立访客",
        formula="有效访问事件 visitor_hash 去重数",
        deduplication="所选时间范围内去重",
    ),
    MetricDefinition(
        code="leads",
        name="有效留资",
        formula="去重后新建 lead_submitted 事件数",
        deduplication="同名片相同联系方式 24 小时内重复提交不新增事件",
    ),
    MetricDefinition(
        code="conversions",
        name="客户转化",
        formula="lead_converted 事件数",
        deduplication="每条线索最多转换一次",
    ),
]


def date_range(
    date_from: date | None, date_to: date | None
) -> tuple[date, date, datetime, datetime]:
    end = date_to or date.today()
    start = date_from or end - timedelta(days=29)
    if start > end:
        raise AppError("analytics_date_range_invalid", "Start date must not exceed end date", 422)
    if (end - start).days > 366:
        raise AppError("analytics_date_range_too_large", "Date range cannot exceed 366 days", 422)
    return (
        start,
        end,
        datetime.combine(start, time.min),
        datetime.combine(end + timedelta(days=1), time.min),
    )


def analytics_scope(db: Session, user: User) -> tuple[bool, str | None]:
    permissions = permissions_for_user(db, user)
    if Permission.ANALYTICS_ALL.value in permissions:
        return True, None
    employee = current_employee(db, user)
    return False, employee.id if employee else ""


def event_conditions(
    db: Session,
    user: User,
    start_at: datetime,
    end_at: datetime,
    department_id: str | None,
    employee_id: str | None,
    card_id: str | None,
    product_id: str | None,
    channel: str | None,
    include_bots: bool,
    include_internal: bool,
):  # type: ignore[no-untyped-def]
    all_scope, own_employee_id = analytics_scope(db, user)
    conditions = [
        BusinessEvent.company_id == user.company_id,
        BusinessEvent.occurred_at >= start_at,
        BusinessEvent.occurred_at < end_at,
    ]
    if all_scope:
        if department_id:
            conditions.append(BusinessEvent.department_id == department_id)
        if employee_id:
            conditions.append(BusinessEvent.employee_id == employee_id)
    else:
        conditions.append(BusinessEvent.employee_id == own_employee_id)
    if card_id:
        conditions.append(BusinessEvent.card_id == card_id)
    if product_id:
        conditions.append(BusinessEvent.product_id == product_id)
    if channel:
        conditions.append(BusinessEvent.channel == channel)
    if not include_bots:
        conditions.append(BusinessEvent.is_bot.is_(False))
    if not include_internal:
        conditions.append(BusinessEvent.is_internal.is_(False))
    return conditions


def safe_rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def dimension_name_map(
    db: Session, company_id: str, dimension: str, ids: set[str]
) -> dict[str, str]:
    if not ids:
        return {}
    if dimension == "employee":
        rows = db.execute(select(Employee.id, Employee.name).where(Employee.id.in_(ids))).tuples()
        return {item_id: name for item_id, name in rows}
    if dimension == "department":
        rows = db.execute(
            select(Department.id, Department.name).where(Department.id.in_(ids))
        ).tuples()
        return {item_id: name for item_id, name in rows}
    if dimension == "card":
        rows = db.execute(
            select(DigitalCard.id, Employee.name)
            .join(Employee, Employee.id == DigitalCard.employee_id)
            .where(DigitalCard.id.in_(ids), DigitalCard.company_id == company_id)
        )
        return {key: f"{name}的名片" for key, name in rows}
    if dimension == "product":
        rows = db.execute(select(Product.id, Product.name).where(Product.id.in_(ids))).tuples()
        return {item_id: name for item_id, name in rows}
    return {item: item for item in ids}


@router.get("/dashboard", response_model=AnalyticsDashboardResponse)
def analytics_dashboard(
    user: Annotated[User, Depends(require_permission(Permission.ANALYTICS_READ))],
    db: Annotated[Session, Depends(get_db)],
    date_from: date | None = None,
    date_to: date | None = None,
    department_id: str | None = None,
    employee_id: str | None = None,
    card_id: str | None = None,
    product_id: str | None = None,
    channel: str | None = None,
    ranking_dimension: Literal["department", "employee", "card", "product", "channel"] = "employee",
    include_bots: bool = False,
    include_internal: bool = False,
) -> AnalyticsDashboardResponse:
    start, end, start_at, end_at = date_range(date_from, date_to)
    conditions = event_conditions(
        db,
        user,
        start_at,
        end_at,
        department_id,
        employee_id,
        card_id,
        product_id,
        channel,
        include_bots,
        include_internal,
    )
    rows = db.execute(
        select(
            BusinessEvent.event_category,
            func.count(BusinessEvent.id),
            func.count(func.distinct(BusinessEvent.visitor_hash)),
        )
        .where(*conditions)
        .group_by(BusinessEvent.event_category)
    ).all()
    counts = {category: count for category, count, _ in rows}
    unique_visitors = next((unique for category, _, unique in rows if category == "view"), 0)
    views = counts.get("view", 0)
    shares = counts.get("share", 0)
    clicks = counts.get("click", 0)
    leads = counts.get("lead", 0)
    conversions = counts.get("conversion", 0)

    trend_rows = db.execute(
        select(
            func.date(BusinessEvent.occurred_at),
            BusinessEvent.event_category,
            func.count(BusinessEvent.id),
        )
        .where(*conditions)
        .group_by(func.date(BusinessEvent.occurred_at), BusinessEvent.event_category)
    ).all()
    trend_data: defaultdict[str, dict[str, int]] = defaultdict(dict)
    for day, category, count in trend_rows:
        trend_data[str(day)][category] = count
    trend = []
    current = start
    while current <= end:
        values = trend_data[current.isoformat()]
        trend.append(
            TrendPoint(
                date=current,
                views=values.get("view", 0),
                shares=values.get("share", 0),
                clicks=values.get("click", 0),
                leads=values.get("lead", 0),
                conversions=values.get("conversion", 0),
            )
        )
        current += timedelta(days=1)

    dimension_column = {
        "department": BusinessEvent.department_id,
        "employee": BusinessEvent.employee_id,
        "card": BusinessEvent.card_id,
        "product": BusinessEvent.product_id,
        "channel": BusinessEvent.channel,
    }[ranking_dimension]
    ranking_rows = db.execute(
        select(
            dimension_column,
            func.sum(case((BusinessEvent.event_category == "view", 1), else_=0)),
            func.sum(case((BusinessEvent.event_category == "lead", 1), else_=0)),
            func.sum(case((BusinessEvent.event_category == "conversion", 1), else_=0)),
        )
        .where(*conditions, dimension_column.is_not(None))
        .group_by(dimension_column)
        .order_by(func.count(BusinessEvent.id).desc())
        .limit(20)
    ).all()
    ids = {str(row[0]) for row in ranking_rows}
    names = dimension_name_map(db, user.company_id or "", ranking_dimension, ids)
    ranking = [
        RankingItem(
            dimension_id=str(item),
            dimension_name=names.get(str(item), str(item)),
            views=int(item_views or 0),
            leads=int(item_leads or 0),
            conversions=int(item_conversions or 0),
        )
        for item, item_views, item_leads, item_conversions in ranking_rows
    ]
    funnel_values = [
        ("views", "名片访问", views),
        ("leads", "有效留资", leads),
        ("conversions", "转为客户", conversions),
    ]
    funnel = [
        FunnelItem(
            code=code,
            name=name,
            value=value,
            previous_rate=None if index == 0 else safe_rate(value, funnel_values[index - 1][2]),
        )
        for index, (code, name, value) in enumerate(funnel_values)
    ]
    sample_events = list(
        db.scalars(
            select(BusinessEvent)
            .where(*conditions)
            .order_by(BusinessEvent.occurred_at.desc())
            .limit(30)
        )
    )
    unfiltered_conditions = event_conditions(
        db,
        user,
        start_at,
        end_at,
        department_id,
        employee_id,
        card_id,
        product_id,
        channel,
        True,
        True,
    )
    filtered_bots = (
        db.scalar(
            select(func.count())
            .select_from(BusinessEvent)
            .where(*unfiltered_conditions, BusinessEvent.is_bot.is_(True))
        )
        or 0
    )
    filtered_internal = (
        db.scalar(
            select(func.count())
            .select_from(BusinessEvent)
            .where(*unfiltered_conditions, BusinessEvent.is_internal.is_(True))
        )
        or 0
    )
    last_updated = db.scalar(select(func.max(BusinessEvent.occurred_at)).where(*conditions))
    all_scope, _ = analytics_scope(db, user)
    return AnalyticsDashboardResponse(
        date_from=start,
        date_to=end,
        scope="company" if all_scope else "employee",
        metrics=AnalyticsMetric(
            views=views,
            unique_visitors=unique_visitors,
            shares=shares,
            clicks=clicks,
            leads=leads,
            conversions=conversions,
            view_to_lead_rate=safe_rate(leads, views),
            lead_to_customer_rate=safe_rate(conversions, leads),
        ),
        trend=trend,
        ranking_dimension=ranking_dimension,
        ranking=ranking,
        funnel=funnel,
        samples=[EventSample.model_validate(item, from_attributes=True) for item in sample_events],
        definitions=DEFINITIONS,
        last_updated_at=last_updated,
        filtered_bot_events=filtered_bots,
        filtered_internal_events=filtered_internal,
    )


@router.get("/export")
def export_analytics(
    user: Annotated[User, Depends(require_permission(Permission.ANALYTICS_EXPORT))],
    db: Annotated[Session, Depends(get_db)],
    date_from: date | None = None,
    date_to: date | None = None,
) -> Response:
    start, end, start_at, end_at = date_range(date_from, date_to)
    conditions = event_conditions(
        db, user, start_at, end_at, None, None, None, None, None, False, False
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "事件时间",
            "事件类型",
            "事件分类",
            "渠道",
            "员工ID",
            "名片ID",
            "产品ID",
            "线索ID",
            "客户ID",
        ]
    )
    for event in db.scalars(
        select(BusinessEvent).where(*conditions).order_by(BusinessEvent.occurred_at).limit(100000)
    ):
        writer.writerow(
            [
                event.occurred_at.isoformat(),
                event.event_type,
                event.event_category,
                event.channel,
                event.employee_id or "",
                event.card_id or "",
                event.product_id or "",
                event.lead_id or "",
                event.customer_id or "",
            ]
        )
    filename = f"digitalcard-analytics-{start.isoformat()}-{end.isoformat()}.csv"
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
