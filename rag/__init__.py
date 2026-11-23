"""
Pacote RAG para Assistente de RH.
Exporta os componentes principais de ingestão, cliente Ollama e construção de chains.
"""

from .chain import criar_chain_rag, formatar_documentos
from .ingest import (
    FAISSIntegrityError,
    carregar_documentos,
    carregar_e_indexar_pdf,
    carregar_ou_criar_indice,
    criar_banco_vetores,
    recuperar_na_inicializacao,
    salvar_indice_persistente,
    validar_indice_funcional,
)
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

__all__ = [
    "MODELO_CHAT_PADRAO",
    "MODELO_EMBEDDINGS_PADRAO",
    "FAISSIntegrityError",
    "OllamaConfigurationError",
    "carregar_documentos",
    "carregar_e_indexar_pdf",
    "carregar_ou_criar_indice",
    "criar_banco_vetores",
    "criar_chain_rag",
    "formatar_documentos",
    "listar_modelos_chat",
    "obter_embeddings",
    "obter_llm",
    "obter_url_ollama",
    "recuperar_na_inicializacao",
    "salvar_indice_persistente",
    "validar_indice_funcional",
    "verificar_conexao_ollama",
    "verificar_modelo_disponivel",
]
