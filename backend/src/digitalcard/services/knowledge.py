import hashlib
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.core.time import utc_now
from digitalcard.models.knowledge import KnowledgeSource, KnowledgeStatus


def checksum(content: str) -> str:
    return hashlib.sha256(content.strip().encode()).hexdigest()


def index_source(source: KnowledgeSource) -> None:
    content = source.content.strip()
    if not source.is_authorized:
        source.status = KnowledgeStatus.DISABLED.value
        source.error_message = None
        return
    if len(content) < 2:
        source.status = KnowledgeStatus.FAILED.value
        source.error_message = "No readable content was extracted"
        return
    source.checksum = checksum(content)
    source.status = KnowledgeStatus.INDEXED.value
    source.error_message = None
    source.indexed_at = utc_now()


def tokens(text: str) -> set[str]:
    lowered = text.lower()
    words = set(re.findall(r"[a-z0-9]{2,}", lowered))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", lowered))
    words.update(chinese[index : index + 2] for index in range(max(len(chinese) - 1, 0)))
    return {item for item in words if item}


def retrieve(db: Session, company_id: str, question: str, limit: int = 3) -> list[KnowledgeSource]:
    question_tokens = tokens(question)
    sources = db.scalars(
        select(KnowledgeSource).where(
            KnowledgeSource.company_id == company_id,
            KnowledgeSource.status == KnowledgeStatus.INDEXED.value,
            KnowledgeSource.is_authorized.is_(True),
        )
    )
    scored = []
    for source in sources:
        overlap = len(question_tokens & tokens(f"{source.title} {source.content}"))
        if overlap:
            scored.append((overlap, source.updated_at, source))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:limit]]
