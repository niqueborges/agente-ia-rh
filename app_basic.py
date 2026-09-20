"""
Assistente RAG de Políticas Internas (RH) — Prova de Conceito Inicial
======================================================================

ARQUIVO HISTÓRICO — Prova de Conceito (PoC)
--------------------------------------------
Este script representa a versão inicial do projeto, desenvolvida como PoC
a partir do tutorial de referência:
  https://www.youtube.com/watch?v=XqG3RN6VzDw

Ele foi preservado intencionalmente para ilustrar o ponto de partida do
projeto e contrastar com a arquitetura modular atual (app.py + pacote rag/).

Limitações desta versão (que motivaram a refatoração):
  1. Script monolítico: toda a lógica (ingestão, vetorização, chain e UI)
     em um único arquivo, sem separação de responsabilidades.
  2. Sem cache: carregar_pdf(), separar_em_blocos() e criar_banco_vetores()
     são executadas a cada interação do Streamlit, gerando chamadas
     desnecessárias à API de embeddings da OpenAI.
  3. Dependência de API paga: requer OPENAI_API_KEY com créditos ativos.
     O projeto evoluiu para Ollama (modelos locais) para eliminar essa
     dependência e manter o processamento no ambiente local.
  4. Sem streaming: chain.invoke() bloqueia até a resposta completa.
     A versão atual usa chain.stream() + st.write_stream().
  5. Sem configuração dinâmica: modelo e temperatura fixos no código.
     A versão atual permite seleção via sidebar da interface.

Pilha tecnológica desta PoC:
  - Streamlit (interface)
  - LangChain com LCEL (orquestração)
  - FAISS (banco vetorial)
  - OpenAI: text-embedding-3-small (embeddings) + gpt-4o-mini (LLM)

Para a versão atual e modularizada, consulte: app.py + rag/
"""

import streamlit as st
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# =============================================================================
# Lógica de Ingestão — executada a cada rerun do Streamlit (sem cache)
# LIMITAÇÃO: gera chamadas repetidas à API de embeddings da OpenAI.
# Na versão atual, isso é resolvido com @st.cache_resource em carregar_recursos().
# =============================================================================

def carregar_pdf():
    """Carrega e extrai o texto do PDF de políticas."""
    pdf_loader = PyPDFLoader("data/politica_rh_exemplo.pdf")
    texto = pdf_loader.load()
    return texto


texto_pdf = carregar_pdf()


def separar_em_blocos(texto_pdf):
    """Divide o texto em blocos com sobreposição para melhorar a recuperação."""
    separador = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    lista_blocos = separador.split_documents(texto_pdf)
    return lista_blocos


lista_blocos = separar_em_blocos(texto_pdf)


def criar_banco_vetores(lista_blocos):
    """Gera embeddings via OpenAI e indexa os blocos no FAISS.

    LIMITAÇÃO: requer OPENAI_API_KEY com créditos disponíveis.
    Na versão atual, substituído por OllamaEmbeddings (nomic-embed-text)
    para execução local sem dependência de API paga.
    """
    ferramenta_embedding = OpenAIEmbeddings(model="text-embedding-3-small")
    banco_vetores = FAISS.from_documents(lista_blocos, ferramenta_embedding)
    return banco_vetores


banco_vetores = criar_banco_vetores(lista_blocos)


# =============================================================================
# Lógica da Chain RAG
# =============================================================================

def criar_chain_agente(banco_vetores):
    """Monta a chain RAG com LCEL: retriever → prompt → LLM → parser.

    LIMITAÇÃO: usa ChatOpenAI (gpt-4o-mini) — API paga e externa.
    Na versão atual, substituído por ChatOllama para execução local.
    """
    prompt_template = ChatPromptTemplate.from_template(
        """Você é um assistente de RH que responde perguntas sobre políticas internas da empresa.
    Use APENAS as informações do contexto abaixo para responder.
    Se não encontrar a resposta, diga claramente que não sabe responder.
    Responda em português do Brasil, de forma clara e objetiva.

    Contexto: {context}

    A pergunta: {question}

    Resposta:"""
    )

    buscador_contexto = banco_vetores.as_retriever()
    llm = ChatOpenAI(model="gpt-4o-mini")

    chain = (
        {"context": buscador_contexto, "question": RunnablePassthrough()}
        | prompt_template
        | llm
        | StrOutputParser()
    )

    return chain


# =============================================================================
# Interface Streamlit — PoC mínima
# LIMITAÇÃO: sem sidebar de configurações, sem streaming, sem status de host.
# =============================================================================

st.title("Assistente RAG — Políticas Internas (PoC)")

chain = criar_chain_agente(banco_vetores)

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

prompt = st.chat_input("Pergunte sobre as políticas da empresa...")
if prompt:
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Buscando..."):
            # LIMITAÇÃO: chain.invoke() bloqueia até a resposta completa.
            # Na versão atual, chain.stream() + st.write_stream() exibem
            # a resposta token a token (streaming progressivo).
            answer = chain.invoke(prompt)
            st.write(answer)

    st.session_state["messages"].append({"role": "assistant", "content": answer})
