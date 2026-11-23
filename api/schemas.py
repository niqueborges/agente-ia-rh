"""
Modelos de dados Pydantic para validação e serialização da API REST/SSE (ADR-0006).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class SourceItem(BaseModel):
    """Representa um trecho recuperado como fonte com metadados amigáveis."""

    page: int = Field(..., description="Número da página do documento de referência (base 1)")
    text: str = Field(..., description="Trecho de texto extraído da política interna")


class ChatRequest(BaseModel):
    """Payload de entrada para consulta ao assistente de RH."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Pergunta do colaborador em linguagem natural",
    )
    stream: bool = Field(
        default=True,
        description="Se verdadeiro, transmite a resposta via Server-Sent Events (SSE)",
    )
    k_documentos: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Quantidade de trechos documentais a recuperar para compor o contexto",
    )

    @field_validator("question")
    @classmethod
    def validar_pergunta_nao_vazia(cls, v: str) -> str:
        limpo = v.strip()
        if not limpo:
            raise ValueError("A pergunta não pode ser vazia ou conter apenas espaços.")
        return limpo


class ChatResponse(BaseModel):
    """Resposta síncrona estruturada do assistente de RH."""

    answer: str = Field(..., description="Resposta formulada com base nas políticas internas")
    sources: list[SourceItem] = Field(
        default_factory=list,
        description="Fontes e páginas do manual utilizadas na resposta",
    )


class HealthResponse(BaseModel):
    """Diagnóstico de saúde operacional do assistente e suas integrações."""

    status: str = Field(..., description="Status geral da aplicação: 'ok' ou 'degraded'")
    ollama: dict[str, Any] = Field(..., description="Estado de conectividade e URL do Ollama")
    faiss: dict[str, Any] = Field(..., description="Estado do índice vetorial FAISS e manifesto")
    model: str = Field(..., description="Modelo de chat ativo configurado para inferência")


class FaqItem(BaseModel):
    """Item de pergunta frequente pré-formatada para sugestões na UI."""

    category: str = Field(..., description="Categoria temática (ex.: Férias, Saúde, Jornada)")
    question: str = Field(..., description="Texto da dúvida frequente")
    icon: str = Field(
        default="💼", description="Ícone representativo para exibição em chips visuais"
    )


class FaqResponse(BaseModel):
    """Lista de perguntas frequentes para guiar usuários não técnicos."""

    faqs: list[FaqItem] = Field(..., description="Lista de dúvidas sugeridas")
