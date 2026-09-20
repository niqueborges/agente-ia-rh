"""
Pacote RAG para Assistente de RH.
Exporta os componentes principais de ingestão, cliente Ollama e construção de chains.
"""

from .ollama_client import obter_url_ollama, obter_embeddings, obter_llm
from .ingest import carregar_documentos, criar_banco_vetores
from .chain import criar_chain_rag

__all__ = [
    "obter_url_ollama",
    "obter_embeddings",
    "obter_llm",
    "carregar_documentos",
    "criar_banco_vetores",
    "criar_chain_rag",
]
