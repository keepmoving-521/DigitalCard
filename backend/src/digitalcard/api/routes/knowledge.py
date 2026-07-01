from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.db.session import get_db
from digitalcard.models.account import User
from digitalcard.models.card import CardStatus, DigitalCard
from digitalcard.models.knowledge import (
    AiConfiguration,
    AiInteraction,
    KnowledgeSource,
    KnowledgeStatus,
)
from digitalcard.models.organization import Company, CompanyStatus
from digitalcard.models.product import Material, Product, ProductStatus
from digitalcard.schemas.knowledge import (
    AiAnswer,
    AiCitation,
    AiConfigPayload,
    AiConfigResponse,
    AiFeedbackRequest,
    AiStats,
    DraftRequest,
    DraftResponse,
    KnowledgeCreateRequest,
    KnowledgeResponse,
    PublicAiQuestion,
)
from digitalcard.services.knowledge import checksum, index_source, retrieve
from digitalcard.services.permissions import Permission
from digitalcard.services.tenancy import record_tenant_audit

router = APIRouter(tags=["knowledge and AI"])


def config_for(db: Session, company_id: str) -> AiConfiguration:
    config = db.get(AiConfiguration, company_id)
    if config is None:
        config = AiConfiguration(company_id=company_id)
        db.add(config)
        db.flush()
    return config


def tenant_source(db: Session, company_id: str, source_id: str) -> KnowledgeSource:
    source = db.scalar(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id, KnowledgeSource.company_id == company_id
        )
    )
    if source is None:
        raise AppError("knowledge_not_found", "Knowledge source was not found", 404)
    return source


def upsert_source(
    db: Session,
    company_id: str,
    source_type: str,
    source_id: str | None,
    title: str,
    content: str,
    authorized: bool = True,
) -> KnowledgeSource:
    source = None
    if source_id:
        source = db.scalar(
            select(KnowledgeSource).where(
                KnowledgeSource.company_id == company_id,
                KnowledgeSource.source_type == source_type,
                KnowledgeSource.source_id == source_id,
            )
        )
    if source is None:
        source = KnowledgeSource(
            company_id=company_id,
            source_type=source_type,
            source_id=source_id,
            title=title,
            content=content,
            checksum=checksum(content),
            is_authorized=authorized,
        )
        db.add(source)
    else:
        source.title = title
        source.content = content
        source.is_authorized = authorized
    index_source(source)
    return source


@router.get("/tenant/ai/config", response_model=AiConfigResponse)
def get_ai_config(
    user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    config = config_for(db, user.company_id)
    db.commit()
    db.refresh(config)
    return config


@router.put("/tenant/ai/config", response_model=AiConfigResponse)
def update_ai_config(
    payload: AiConfigPayload,
    user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    config = config_for(db, user.company_id)
    for key, value in payload.model_dump().items():
        setattr(config, key, value)
    record_tenant_audit(
        db, user.company_id, user.id, "ai.config_updated", "ai_config", user.company_id
    )
    db.commit()
    db.refresh(config)
    return config


@router.get("/tenant/knowledge/sources", response_model=list[KnowledgeResponse])
def list_sources(
    user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    return list(
        db.scalars(
            select(KnowledgeSource)
            .where(KnowledgeSource.company_id == user.company_id)
            .order_by(KnowledgeSource.updated_at.desc())
        )
    )


@router.post("/tenant/knowledge/sources", response_model=KnowledgeResponse, status_code=201)
def create_source(
    payload: KnowledgeCreateRequest,
    user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    source = upsert_source(
        db,
        user.company_id,
        payload.source_type,
        None,
        payload.title,
        payload.content,
        payload.is_authorized,
    )
    db.flush()
    record_tenant_audit(db, user.company_id, user.id, "knowledge.created", "knowledge", source.id)
    db.commit()
    db.refresh(source)
    return source


@router.post("/tenant/knowledge/sync", response_model=list[KnowledgeResponse])
def sync_business_knowledge(
    user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    company = db.get(Company, user.company_id)
    content = "\n".join(
        value
        for value in [company.name, company.description, company.address, company.contact_phone]
        if value
    )
    updated = [
        upsert_source(db, company.id, "company", company.id, company.name, content or company.name)
    ]
    products = list(db.scalars(select(Product).where(Product.company_id == company.id)))
    active_ids = set()
    for product in products:
        existing = db.scalar(
            select(KnowledgeSource).where(
                KnowledgeSource.company_id == company.id,
                KnowledgeSource.source_type == "product",
                KnowledgeSource.source_id == product.id,
            )
        )
        if product.status != ProductStatus.PUBLISHED.value:
            if existing:
                existing.status = KnowledgeStatus.DISABLED.value
                existing.is_authorized = False
            continue
        active_ids.add(product.id)
        product_content = "\n".join(
            value
            for value in [
                product.name,
                product.summary,
                product.description,
                "; ".join(f"{key}: {value}" for key, value in product.specifications.items()),
            ]
            if value
        )
        updated.append(
            upsert_source(db, company.id, "product", product.id, product.name, product_content)
        )
    stale = db.scalars(
        select(KnowledgeSource).where(
            KnowledgeSource.company_id == company.id,
            KnowledgeSource.source_type == "product",
            KnowledgeSource.source_id.not_in(active_ids) if active_ids else True,
        )
    )
    for source in stale:
        source.status = KnowledgeStatus.DISABLED.value
        source.is_authorized = False
    record_tenant_audit(db, company.id, user.id, "knowledge.synchronized", "company", company.id)
    db.commit()
    return updated


@router.post(
    "/tenant/knowledge/materials/{material_id}",
    response_model=KnowledgeResponse,
    status_code=201,
)
def index_authorized_document(
    material_id: str,
    payload: KnowledgeCreateRequest,
    user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    material = db.scalar(
        select(Material).where(Material.id == material_id, Material.company_id == user.company_id)
    )
    if material is None or material.kind != "pdf":
        raise AppError("document_not_found", "Authorized PDF material was not found", 404)
    source = upsert_source(
        db,
        user.company_id,
        "document",
        material.id,
        payload.title or material.name,
        payload.content,
        payload.is_authorized,
    )
    db.commit()
    db.refresh(source)
    return source


@router.post("/tenant/knowledge/sources/{source_id}/disable", response_model=KnowledgeResponse)
def disable_source(
    source_id: str,
    user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    source = tenant_source(db, user.company_id, source_id)
    source.is_authorized = False
    source.status = KnowledgeStatus.DISABLED.value
    source.indexed_at = None
    record_tenant_audit(db, user.company_id, user.id, "knowledge.disabled", "knowledge", source.id)
    db.commit()
    db.refresh(source)
    return source


@router.post("/tenant/knowledge/sources/{source_id}/retry", response_model=KnowledgeResponse)
def retry_source(
    source_id: str,
    user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    source = tenant_source(db, user.company_id, source_id)
    index_source(source)
    db.commit()
    db.refresh(source)
    return source


def public_ai_company(db: Session, company_code: str) -> tuple[Company, AiConfiguration]:
    company = db.scalar(
        select(Company).where(
            Company.code == company_code, Company.status == CompanyStatus.ACTIVE.value
        )
    )
    if company is None:
        raise AppError("ai_company_not_found", "AI assistant was not found", 404)
    config = db.get(AiConfiguration, company.id)
    if config is None or not config.enabled or not config.public_qa_enabled:
        raise AppError("ai_not_enabled", "AI assistant is not enabled", 404)
    today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    used = (
        db.scalar(
            select(func.count())
            .select_from(AiInteraction)
            .where(
                AiInteraction.company_id == company.id,
                AiInteraction.mode == "public_qa",
                AiInteraction.created_at >= today,
            )
        )
        or 0
    )
    if used >= config.daily_limit:
        raise AppError("ai_daily_limit", "AI daily usage limit has been reached", 429)
    return company, config


@router.post("/public/ai/{company_code}/ask", response_model=AiAnswer)
def ask_public_ai(
    company_code: str,
    payload: PublicAiQuestion,
    db: Annotated[Session, Depends(get_db)],
):
    company, _ = public_ai_company(db, company_code)
    sources = retrieve(db, company.id, payload.question)
    uncertain = not sources
    if uncertain:
        answer = "抱歉，我没有找到足够可靠的企业资料来回答这个问题。建议联系企业人员确认。"
    else:
        answer = "根据企业已授权资料：" + "；".join(
            source.content[:300].replace("\n", " ") for source in sources
        )
    interaction = AiInteraction(
        company_id=company.id,
        mode="public_qa",
        prompt=payload.question,
        response=answer,
        source_ids=[source.id for source in sources],
        success=True,
        uncertain=uncertain,
        input_tokens=len(payload.question),
        output_tokens=len(answer),
    )
    db.add(interaction)
    db.flush()
    card = db.scalar(
        select(DigitalCard).where(
            DigitalCard.company_id == company.id,
            DigitalCard.status == CardStatus.PUBLISHED.value,
        )
    )
    citations = [
        AiCitation(
            source_id=source.id,
            source_type=source.source_type,
            title=source.title,
            excerpt=source.content[:160],
        )
        for source in sources
    ]
    db.commit()
    return AiAnswer(
        interaction_id=interaction.id,
        answer=answer,
        uncertain=uncertain,
        citations=citations,
        handoff_url=f"/card/{card.id}?source=ai" if card else None,
    )


@router.post("/public/ai/interactions/{interaction_id}/feedback")
def submit_ai_feedback(
    interaction_id: str,
    payload: AiFeedbackRequest,
    db: Annotated[Session, Depends(get_db)],
):
    interaction = db.get(AiInteraction, interaction_id)
    if interaction is None or interaction.mode != "public_qa":
        raise AppError("ai_interaction_not_found", "AI interaction was not found", 404)
    interaction.feedback = payload.rating
    interaction.feedback_comment = payload.comment
    db.commit()
    return {"recorded": True}


@router.post("/tenant/ai/drafts", response_model=DraftResponse)
def generate_draft(
    payload: DraftRequest,
    user: Annotated[User, Depends(require_permission(Permission.AI_GENERATE))],
    db: Annotated[Session, Depends(get_db)],
):
    config = config_for(db, user.company_id)
    if not config.enabled or not config.sales_assistant_enabled:
        raise AppError("sales_ai_not_enabled", "Sales AI assistant is not enabled", 409)
    company = db.get(Company, user.company_id)
    if payload.draft_type == "company_intro":
        content = (
            f"【AI 建议草稿】{company.name}：{company.description or '请补充企业优势与服务内容。'}"
        )
    elif payload.draft_type == "product_copy":
        product = db.scalar(
            select(Product).where(
                Product.id == payload.product_id, Product.company_id == user.company_id
            )
        )
        if product is None:
            raise AppError("product_not_found", "Product was not found", 404)
        description = product.summary or product.description or "请补充产品价值。"
        content = f"【AI 建议草稿】{product.name}。{description}"
    else:
        context = payload.context or "预算、时间与决策重点"
        content = (
            f"【AI 建议草稿】感谢您的沟通。建议结合客户需求继续确认：{context}。"
            "不承诺价格或合同条款。"
        )
    interaction = AiInteraction(
        company_id=user.company_id,
        user_id=user.id,
        mode=payload.draft_type,
        prompt=payload.context or payload.draft_type,
        response=content,
        source_ids=[],
        input_tokens=len(payload.context or ""),
        output_tokens=len(content),
    )
    db.add(interaction)
    db.commit()
    return DraftResponse(interaction_id=interaction.id, content=content)


@router.get("/tenant/ai/stats", response_model=AiStats)
def ai_stats(
    user: Annotated[User, Depends(require_permission(Permission.AI_AUDIT))],
    db: Annotated[Session, Depends(get_db)],
):
    items = list(
        db.scalars(select(AiInteraction).where(AiInteraction.company_id == user.company_id))
    )
    calls = len(items)
    successes = sum(item.success for item in items)
    failures = calls - successes
    return AiStats(
        calls=calls,
        successes=successes,
        failures=failures,
        uncertain=sum(item.uncertain for item in items),
        positive_feedback=sum(item.feedback == 1 for item in items),
        negative_feedback=sum(item.feedback == -1 for item in items),
        failure_rate=round(failures / calls, 4) if calls else 0,
    )
