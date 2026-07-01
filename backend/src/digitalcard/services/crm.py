from sqlalchemy.orm import Session

from digitalcard.models.crm import OpportunityStage

DEFAULT_STAGES = (
    ("initial", "初步接洽", 10, 10, False, False),
    ("proposal", "方案沟通", 20, 40, False, False),
    ("negotiation", "商务谈判", 30, 70, False, False),
    ("won", "成交", 40, 100, True, False),
    ("lost", "丢单", 50, 0, False, True),
)


def seed_opportunity_stages(db: Session, company_id: str) -> None:
    for code, name, sort_order, probability, is_won, is_lost in DEFAULT_STAGES:
        db.add(
            OpportunityStage(
                company_id=company_id,
                code=code,
                name=name,
                sort_order=sort_order,
                probability=probability,
                is_won=is_won,
                is_lost=is_lost,
            )
        )
