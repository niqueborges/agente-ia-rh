"""
Módulo de orquestração RAG com LangChain Expression Language (LCEL).
Combina o recuperador FAISS, o prompt instrucional e o modelo LLM em uma chain executável.
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_community.vectorstores import FAISS

PROMPT_SISTEMA_RH = """Você é um assistente de RH prestativo e profissional que responde dúvidas sobre as políticas internas da empresa.
Use APENAS as informações presentes no contexto abaixo para responder.
Se a informação não estiver expressamente descrita no contexto, diga claramente que não encontrou essa informação nas políticas internas da empresa.
Responda em português do Brasil de forma clara, estruturada e objetiva.

Contexto:
{context}

Pergunta do colaborador:
{question}

Resposta:"""


def criar_chain_rag(
    banco_vetores: FAISS,
    llm: BaseChatModel,
    k_documentos: int = 3,
):
    """
    Constrói a chain RAG com LCEL.
    
    Args:
        banco_vetores: Índice FAISS com os documentos vetorizados.
        llm: Instância do modelo de linguagem (ex: ChatOllama).
        k_documentos: Quantidade de trechos mais relevantes a recuperar (padrão: 3).
        
    Returns:
        Chain LCEL compilada pronta para invoke() ou stream().
    """
    prompt_template = ChatPromptTemplate.from_template(PROMPT_SISTEMA_RH)
    buscador_contexto = banco_vetores.as_retriever(search_kwargs={"k": k_documentos})

    chain = (
        {"context": buscador_contexto, "question": RunnablePassthrough()}
        | prompt_template
        | llm
        | StrOutputParser()
    )

    return chain
