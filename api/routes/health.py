"""
Endpoint de diagnóstico e monitoramento de integridade do assistente (ADR-0006).
"""

from __future__ import annotations

import json

from fastapi import APIRouter

from rag.ingest import CAMINHO_INDICE
from rag.ollama_client import (
    MODELO_CHAT_PADRAO,
    MODELO_EMBEDDINGS_PADRAO,
    obter_url_ollama,
    verificar_conexao_ollama,
)

from ..schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Diagnóstico de saúde do assistente")
def verificar_saude() -> HealthResponse:
    """
    Retorna o status detalhado da infraestrutura local:
    - Conectividade com o daemon do Ollama
    - Disponibilidade do índice vetorial FAISS e manifesto
    - Nome do modelo configurado
    """
    url_ollama = obter_url_ollama()
    ollama_ok = verificar_conexao_ollama(url_ollama)

    faiss_info = {
        "index_exists": CAMINHO_INDICE.exists(),
        "manifest_valid": False,
        "total_chunks": 0,
        "embedding_dimension": None,
        "embedding_model": MODELO_EMBEDDINGS_PADRAO,
    }

    caminho_manifesto = CAMINHO_INDICE / "manifest.json"
    if caminho_manifesto.exists():
        try:
            with open(caminho_manifesto, encoding="utf-8") as f:
                dados_manifesto = json.load(f)
                faiss_info["manifest_valid"] = True
                faiss_info["total_chunks"] = dados_manifesto.get("total_chunks", 0)
                faiss_info["embedding_dimension"] = dados_manifesto.get("embedding_dimension")
                if "embedding_model" in dados_manifesto:
                    faiss_info["embedding_model"] = dados_manifesto["embedding_model"]
        except Exception:
            faiss_info["manifest_valid"] = False

    status_geral = "ok" if (ollama_ok and faiss_info["index_exists"]) else "degraded"

    return HealthResponse(
        status=status_geral,
        ollama={
            "connected": ollama_ok,
            "url": url_ollama,
        },
        faiss=faiss_info,
        model=MODELO_CHAT_PADRAO,
    )
