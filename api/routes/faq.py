"""
Endpoint de perguntas frequentes (FAQ) para apoiar funcionários leigos (ADR-0006).
"""

from __future__ import annotations

from fastapi import APIRouter

from ..schemas import FaqItem, FaqResponse

router = APIRouter()

FAQS_PREDEFINIDAS: list[FaqItem] = [
    FaqItem(
        category="Férias",
        question="Como funciona o período aquisitivo e a solicitação de férias?",
        icon="🌴",
    ),
    FaqItem(
        category="Saúde e Atestados",
        question="Qual é o prazo para entrega de atestado médico e quais os requisitos?",
        icon="🏥",
    ),
    FaqItem(
        category="Trabalho Remoto",
        question="Quais são as regras para o trabalho remoto ou híbrido?",
        icon="🏠",
    ),
    FaqItem(
        category="Benefícios",
        question="Quais são as regras do vale-refeição e do plano de saúde?",
        icon="💳",
    ),
    FaqItem(
        category="Jornada e Ponto",
        question="Como funciona o registro de ponto e a compensação de banco de horas?",
        icon="⏰",
    ),
    FaqItem(
        category="Reembolso",
        question="Como funciona o reembolso de despesas de viagem e cursos?",
        icon="📑",
    ),
]


@router.get("/faq", response_model=FaqResponse, summary="Lista de perguntas frequentes de RH")
def obter_faq() -> FaqResponse:
    """
    Retorna dúvidas frequentes estruturadas em categorias cotidianas de RH
    para renderização de chips visuais na interface do colaborador.
    """
    return FaqResponse(faqs=FAQS_PREDEFINIDAS)
