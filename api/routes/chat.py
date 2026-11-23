"""
Endpoint de conversação e consulta RAG com suporte a streaming SSE (ADR-0006).
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_community.vectorstores import FAISS

from rag.chain import criar_chain_rag
from rag.ingest import carregar_ou_criar_indice
from rag.ollama_client import obter_llm, obter_url_ollama, verificar_conexao_ollama

from ..schemas import ChatRequest, ChatResponse, SourceItem

router = APIRouter()

# Cache em memória do banco vetorial para evitar recarregamento repetido do disco
_banco_vetores_cache: FAISS | None = None


def obter_banco_vetores() -> FAISS:
    """Retorna o índice vetorial em cache ou carrega com validação do manifesto."""
    global _banco_vetores_cache
    if _banco_vetores_cache is None:
        _banco_vetores_cache = carregar_ou_criar_indice()
    return _banco_vetores_cache


def resetar_cache_vetorial() -> None:
    """Invalida o cache vetorial (útil para testes unitários ou reindexação)."""
    global _banco_vetores_cache
    _banco_vetores_cache = None


def extrair_fontes(docs: list[Any]) -> list[SourceItem]:
    """Extrai fontes com numeração de página amigável para humanos (base 1)."""
    fontes: list[SourceItem] = []
    for doc in docs:
        pagina = doc.metadata.get("page", 0)
        # Se for base 0, converte para base 1 para leitura de leigos
        pagina_humana = pagina + 1 if isinstance(pagina, int) and pagina >= 0 else 1
        fontes.append(
            SourceItem(
                page=pagina_humana,
                text=doc.page_content.strip(),
            )
        )
    return fontes


def gerar_stream_sse(
    pergunta: str,
    k_documentos: int = 3,
) -> Generator[str, None, None]:
    """
    Executa a chain LCEL e transmite tokens e metadados via Server-Sent Events (SSE).
    """
    try:
        url_ollama = obter_url_ollama()
        if not verificar_conexao_ollama(url_ollama):
            msg_erro = "O servidor de inferência local (Ollama) está indisponível no momento."
            yield f"data: {json.dumps({'type': 'error', 'message': msg_erro}, ensure_ascii=False)}\n\n"
            return

        banco = obter_banco_vetores()
        retriever = banco.as_retriever(search_kwargs={"k": k_documentos})
        docs = retriever.invoke(pergunta)

        llm = obter_llm()
        chain = criar_chain_rag(banco, llm, k_documentos=k_documentos)

        # Transmite cada token gerado pelo modelo
        for chunk in chain.stream(pergunta):
            if chunk:
                payload = json.dumps({"type": "token", "content": chunk}, ensure_ascii=False)
                yield f"data: {payload}\n\n"

        # Transmite as fontes utilizadas para auditoria amigável
        fontes = extrair_fontes(docs)
        payload_fontes = json.dumps(
            {
                "type": "sources",
                "sources": [{"page": f.page, "text": f.text} for f in fontes],
            },
            ensure_ascii=False,
        )
        yield f"data: {payload_fontes}\n\n"

        # Evento de conclusão do streaming
        yield 'data: {"type": "done"}\n\n'

    except Exception as exc:
        msg_erro = f"Ocorreu uma falha durante o processamento da consulta: {exc}"
        payload_erro = json.dumps({"type": "error", "message": msg_erro}, ensure_ascii=False)
        yield f"data: {payload_erro}\n\n"


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Consulta ao Assistente de RH (Streaming SSE ou Síncrono)",
)
def consultar_chat(requisicao: ChatRequest):
    """
    Recebe a pergunta do colaborador e responde consultando as políticas internas.
    - Se `stream=true`: Retorna um fluxo contínuo de Server-Sent Events (`text/event-stream`).
    - Se `stream=false`: Retorna a resposta completa consolidada com lista de fontes em JSON.
    """
    if requisicao.stream:
        return StreamingResponse(
            gerar_stream_sse(
                pergunta=requisicao.question,
                k_documentos=requisicao.k_documentos,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Modo síncrono
    try:
        url_ollama = obter_url_ollama()
        if not verificar_conexao_ollama(url_ollama):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="O servidor de inferência local (Ollama) está indisponível no momento.",
            )

        banco = obter_banco_vetores()
        retriever = banco.as_retriever(search_kwargs={"k": requisicao.k_documentos})
        docs = retriever.invoke(requisicao.question)

        llm = obter_llm()
        chain = criar_chain_rag(banco, llm, k_documentos=requisicao.k_documentos)
        resposta = chain.invoke(requisicao.question)

        return ChatResponse(
            answer=resposta,
            sources=extrair_fontes(docs),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha no processamento da consulta: {exc}",
        ) from exc
