"""
Pacote RAG para Assistente de RH.
Exporta os componentes principais de ingestão, cliente Ollama e construção de chains.
"""

from .ollama_client import (
    MODELO_CHAT_PADRAO,
    MODELO_EMBEDDINGS_PADRAO,
    OllamaConfigurationError,
    listar_modelos_chat,
    obter_embeddings,
    obter_llm,
    obter_url_ollama,
    verificar_conexao_ollama,
    verificar_modelo_disponivel,
)
from .ingest import carregar_documentos, criar_banco_vetores
from .chain import criar_chain_rag

__all__ = [
    "MODELO_CHAT_PADRAO",
    "MODELO_EMBEDDINGS_PADRAO",
    "OllamaConfigurationError",
    "carregar_documentos",
    "criar_banco_vetores",
    "criar_chain_rag",
    "listar_modelos_chat",
    "obter_embeddings",
    "obter_llm",
    "obter_url_ollama",
    "verificar_conexao_ollama",
    "verificar_modelo_disponivel",
]
