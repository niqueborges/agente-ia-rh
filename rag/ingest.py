"""
Módulo de ingestão e indexação de documentos.
Responsável por extrair texto de PDFs, realizar chunking e criar o banco vetorial FAISS.
"""

import os
from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings


def carregar_documentos(
    caminho_pdf: str = "data/politica_rh_exemplo.pdf",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Document]:
    """
    Carrega o arquivo PDF e divide o conteúdo em blocos (chunks).
    
    Args:
        caminho_pdf: Caminho do arquivo PDF.
        chunk_size: Quantidade máxima de caracteres por bloco.
        chunk_overlap: Sobreposição de caracteres entre blocos consecutivos.
        
    Returns:
        Lista de documentos segmentados.
    """
    if not os.path.exists(caminho_pdf):
        # Fallback para o caso de estar na raiz
        if os.path.exists("politica_rh.pdf"):
            caminho_pdf = "politica_rh.pdf"
        elif os.path.exists("data/politica_rh_exemplo.pdf"):
            caminho_pdf = "data/politica_rh_exemplo.pdf"
        else:
            raise FileNotFoundError(f"Documento não encontrado no caminho: {caminho_pdf}")

    loader = PyPDFLoader(caminho_pdf)
    documentos = loader.load()

    separador = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return separador.split_documents(documentos)


def criar_banco_vetores(
    documentos: List[Document],
    embeddings: Embeddings,
) -> FAISS:
    """
    Indexa os documentos segmentados em um banco vetorial FAISS em memória.
    
    Args:
        documentos: Lista de documentos segmentados.
        embeddings: Provedor de embeddings (ex: OllamaEmbeddings).
        
    Returns:
        Instância do FAISS pronta para recuperação.
    """
    return FAISS.from_documents(documentos, embeddings)


def carregar_e_indexar_pdf(
    caminho_pdf: str = "data/politica_rh_exemplo.pdf",
    embeddings: Embeddings | None = None,
) -> FAISS:
    """Função de conveniência que executa a ingestão e a indexação completa."""
    if embeddings is None:
        from .ollama_client import obter_embeddings
        embeddings = obter_embeddings()

    blocos = carregar_documentos(caminho_pdf=caminho_pdf)
    return criar_banco_vetores(blocos, embeddings)
