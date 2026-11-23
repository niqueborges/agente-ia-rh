"""
Módulo de ingestão, indexação e persistência vetorial FAISS.
Implementa persistência segura com manifest.json, substituição atômica, travas fcntl e startup recovery (ADR-0004).
"""

from __future__ import annotations

import datetime
import fcntl
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .ollama_client import obter_embeddings

SCHEMA_VERSION = "1.0"
DIRETORIO_DADOS = Path("data")
CAMINHO_INDICE = DIRETORIO_DADOS / "faiss_index"
CAMINHO_BACKUP = DIRETORIO_DADOS / "faiss_index_backup"
CAMINHO_TMP = DIRETORIO_DADOS / "faiss_index_tmp"
CAMINHO_LOCK = DIRETORIO_DADOS / "faiss_index.lock"


class FAISSIntegrityError(RuntimeError):
    """Exceção levantada quando um índice vetorial em disco está corrompido ou incompatível."""


def calcular_hash_arquivo(caminho: Path | str) -> str:
    """Calcula o SHA-256 de um arquivo em blocos."""
    caminho_p = Path(caminho)
    sha256 = hashlib.sha256()
    with open(caminho_p, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def calcular_hash_chunking(
    chunk_size: int,
    chunk_overlap: int,
    separadores: list[str] | None = None,
) -> str:
    """Calcula hash determinístico dos parâmetros canônicos de fatiamento."""
    payload = {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "separators": separadores or ["\n\n", "\n", " ", ""],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def gerar_collection_id(nome_doc: str, doc_hash: str) -> str:
    """Gera identificador estruturado da coleção documental."""
    return f"{Path(nome_doc).stem}:{doc_hash[:8]}"


def sincronizar_diretorio(diretorio: Path) -> None:
    """Executa flush e fsync em todos os arquivos de um diretório e no diretório em si."""
    for root, _, files in os.walk(diretorio):
        for nome_arquivo in files:
            caminho_arquivo = Path(root) / nome_arquivo
            try:
                fd = os.open(caminho_arquivo, os.O_RDWR)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except OSError:
                pass
    try:
        dir_fd = os.open(diretorio, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def mover_para_quarentena(diretorio: Path, motivo: str) -> Path:
    """
    Move um diretório de índice corrompido ou inválido para quarentena técnica com carimbo de tempo único.
    """
    agora = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    nome_quarentena = f"faiss_index_quarantine_{motivo}_{agora}"
    destino = diretorio.parent / nome_quarentena
    shutil.move(str(diretorio), str(destino))
    return destino


def adquirir_lock(caminho_lock: Path, modo: int, timeout: float = 10.0):
    """
    Adquire trava fcntl (LOCK_SH ou LOCK_EX) com timeout controlado.
    Retorna o descritor de arquivo aberto.
    """
    caminho_lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(caminho_lock, os.O_CREAT | os.O_RDWR, 0o644)
    inicio = time.time()
    while True:
        try:
            fcntl.flock(fd, modo | fcntl.LOCK_NB)
            return fd
        except (BlockingIOError, OSError):
            if time.time() - inicio >= timeout:
                os.close(fd)
                raise TimeoutError(
                    f"Tempo limite ({timeout}s) excedido ao aguardar trava em {caminho_lock}"
                )
            time.sleep(0.05)


def liberar_lock(fd: int) -> None:
    """Libera a trava fcntl e fecha o descritor de arquivo."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def validar_indice_funcional(
    caminho_indice: Path,
    embeddings: Embeddings,
    doc_sha256_esperado: str | None = None,
    chunking_hash_esperado: str | None = None,
) -> tuple[bool, str, FAISS | None]:
    """
    Executa os 5 critérios de validação funcional rigorosa sem realizar chamadas de embedding ao Ollama (ADR-0004).

    Critérios:
    1. Validação de manifesto JSON e compatibilidade estrutural.
    2. Carregamento efetivo em memória via FAISS.load_local().
    3. Verificação de dimensão e contagem de vetores (ntotal == total_chunks == len(docstore)).
    4. Consulta vetorial sintética direta com similarity_search_by_vector (sem embedding textual).
    5. Conferência de integridade documental e metadados obrigatórios.
    """
    manifesto_path = caminho_indice / "manifest.json"
    index_faiss_path = caminho_indice / "index.faiss"
    index_pkl_path = caminho_indice / "index.pkl"

    if not (manifesto_path.exists() and index_faiss_path.exists() and index_pkl_path.exists()):
        return False, "Arquivos essenciais do índice ausentes no diretório.", None

    # Critério 1: Manifesto
    try:
        with open(manifesto_path, encoding="utf-8") as f:
            manifesto = json.load(f)
    except Exception as exc:
        return False, f"Falha ao decodificar manifest.json: {exc}", None

    if manifesto.get("schema_version") != SCHEMA_VERSION:
        return False, f"schema_version incompatível: {manifesto.get('schema_version')}", None

    if doc_sha256_esperado and manifesto.get("document_sha256") != doc_sha256_esperado:
        return False, "Hash do documento PDF diverge do manifesto (documento alterado).", None

    if chunking_hash_esperado and manifesto.get("chunking_config_hash") != chunking_hash_esperado:
        return False, "Configuração de chunking diverge da especificação esperada.", None

    dim_esperada = manifesto.get("embedding_dimension")
    total_esperado = manifesto.get("total_chunks")
    if not isinstance(dim_esperada, int) or not isinstance(total_esperado, int):
        return False, "Campos numéricos essenciais ausentes no manifesto.", None

    # Critério 2: Carregamento
    try:
        faiss_index = FAISS.load_local(
            str(caminho_indice),
            embeddings,
            allow_dangerous_deserialization=True,
        )
    except Exception as exc:
        return False, f"Falha ao carregar índice FAISS: {exc}", None

    # Critério 3: Dimensões e contagens
    try:
        ntotal = faiss_index.index.ntotal
        dim_indice = faiss_index.index.d
        docstore_len = len(faiss_index.docstore._dict)
    except AttributeError as exc:
        return False, f"Objeto de índice malformado: {exc}", None

    if dim_indice != dim_esperada:
        return (
            False,
            f"Dimensão do índice ({dim_indice}) diverge do manifesto ({dim_esperada}).",
            None,
        )

    if ntotal != total_esperado or docstore_len != total_esperado:
        return (
            False,
            f"Contagem de fatias divergente: ntotal={ntotal}, docstore={docstore_len}, manifesto={total_esperado}.",
            None,
        )

    # Critério 4: Consulta vetorial sintética direta (zero chamadas de embedding ao Ollama)
    try:
        vetor_teste = [0.0] * dim_esperada
        resultados = faiss_index.similarity_search_by_vector(vetor_teste, k=1)
    except Exception as exc:
        return False, f"Falha ao executar consulta vetorial sintética: {exc}", None

    # Critério 5: Conferência de integridade documental
    if not resultados:
        return False, "A consulta vetorial de sanidade não retornou nenhum documento.", None

    doc_teste = resultados[0]
    if not isinstance(doc_teste.page_content, str) or not doc_teste.page_content.strip():
        return False, "Documento recuperado possui page_content vazio ou inválido.", None

    if not isinstance(doc_teste.metadata, dict) or "source" not in doc_teste.metadata:
        return False, "Metadados obrigatórios ('source') ausentes no documento.", None

    return True, "Índice válido e íntegro.", faiss_index


def carregar_documentos(
    caminho_pdf: str | Path = "data/politica_rh_exemplo.pdf",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[Document]:
    """Carrega o PDF e fatia o conteúdo em blocos textuais."""
    pdf_path = Path(caminho_pdf)
    if not pdf_path.exists():
        if Path("politica_rh.pdf").exists():
            pdf_path = Path("politica_rh.pdf")
        elif (DIRETORIO_DADOS / "politica_rh_exemplo.pdf").exists():
            pdf_path = DIRETORIO_DADOS / "politica_rh_exemplo.pdf"
        else:
            raise FileNotFoundError(f"Documento não encontrado no caminho: {caminho_pdf}")

    loader = PyPDFLoader(str(pdf_path))
    documentos = loader.load()

    separador = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return separador.split_documents(documentos)


def criar_banco_vetores(
    documentos: list[Document],
    embeddings: Embeddings,
) -> FAISS:
    """Indexa documentos em um banco FAISS em memória."""
    return FAISS.from_documents(documentos, embeddings)


def salvar_indice_persistente(
    banco_vetores: FAISS,
    caminho_pdf: Path,
    documentos: list[Document],
    embeddings: Embeddings,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Path:
    """
    Persiste o índice FAISS de forma atômica com manifesto e sincronização em disco (ADR-0004).
    """
    caminho_pdf = Path(caminho_pdf)
    doc_sha256 = calcular_hash_arquivo(caminho_pdf)
    chunking_hash = calcular_hash_chunking(chunk_size, chunk_overlap)
    collection_id = gerar_collection_id(caminho_pdf.name, doc_sha256)
    dim_vetorial = banco_vetores.index.d
    total_chunks = len(documentos)

    lock_fd = adquirir_lock(CAMINHO_LOCK, fcntl.LOCK_EX, timeout=60.0)
    try:
        # 1. Construção no diretório temporário
        if CAMINHO_TMP.exists():
            shutil.rmtree(CAMINHO_TMP)
        CAMINHO_TMP.mkdir(parents=True, exist_ok=True)

        banco_vetores.save_local(str(CAMINHO_TMP))

        # Calcula hashes dos artefatos gravados
        faiss_hash = calcular_hash_arquivo(CAMINHO_TMP / "index.faiss")
        pkl_hash = calcular_hash_arquivo(CAMINHO_TMP / "index.pkl")

        manifesto = {
            "schema_version": SCHEMA_VERSION,
            "collection_id": collection_id,
            "document_source": str(caminho_pdf),
            "document_sha256": doc_sha256,
            "chunking_config_hash": chunking_hash,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "total_chunks": total_chunks,
            "embedding_dimension": dim_vetorial,
            "created_at": datetime.datetime.now().isoformat(),
            "faiss_files": {
                "index.faiss": faiss_hash,
                "index.pkl": pkl_hash,
            },
        }

        with open(CAMINHO_TMP / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifesto, f, indent=2, ensure_ascii=False)

        # 2. Sincronização de durabilidade (fsync)
        sincronizar_diretorio(CAMINHO_TMP)

        # 3. Preservação do índice anterior em backup
        if CAMINHO_INDICE.exists():
            if CAMINHO_BACKUP.exists():
                shutil.rmtree(CAMINHO_BACKUP)
            os.rename(CAMINHO_INDICE, CAMINHO_BACKUP)

        # 4. Ativação provisória
        os.rename(CAMINHO_TMP, CAMINHO_INDICE)

        # 5. Sincronização do diretório pai
        sincronizar_diretorio(DIRETORIO_DADOS)

        # 6. Validação funcional rigorosa
        valido, motivo, _ = validar_indice_funcional(
            CAMINHO_INDICE,
            embeddings,
            doc_sha256_esperado=doc_sha256,
            chunking_hash_esperado=chunking_hash,
        )

        if valido:
            # Descarte seguro do backup
            if CAMINHO_BACKUP.exists():
                shutil.rmtree(CAMINHO_BACKUP)
            return CAMINHO_INDICE
        else:
            # 7. Rollback de exceção
            mover_para_quarentena(CAMINHO_INDICE, "failed_activation")
            if CAMINHO_BACKUP.exists():
                os.rename(CAMINHO_BACKUP, CAMINHO_INDICE)
            raise FAISSIntegrityError(
                f"Índice recém-gerado falhou na validação funcional: {motivo}"
            )

    finally:
        liberar_lock(lock_fd)


def recuperar_na_inicializacao(
    embeddings: Embeddings,
    doc_sha256_esperado: str,
    chunking_hash_esperado: str,
) -> FAISS | None:
    """
    Executa a rotina de Startup Recovery inspecionando data/ (ADR-0004).
    """
    lock_fd = adquirir_lock(CAMINHO_LOCK, fcntl.LOCK_EX, timeout=15.0)
    try:
        # Limpeza de escrita temporária interrompida
        if CAMINHO_TMP.exists():
            try:
                shutil.rmtree(CAMINHO_TMP)
            except OSError:
                pass

        # Inspeciona índice principal
        if CAMINHO_INDICE.exists():
            valido, _motivo, index = validar_indice_funcional(
                CAMINHO_INDICE,
                embeddings,
                doc_sha256_esperado=doc_sha256_esperado,
                chunking_hash_esperado=chunking_hash_esperado,
            )
            if valido and index is not None:
                if CAMINHO_BACKUP.exists():
                    try:
                        shutil.rmtree(CAMINHO_BACKUP)
                    except OSError:
                        pass
                return index
            else:
                mover_para_quarentena(CAMINHO_INDICE, "startup_invalid_main")

        # Inspeciona backup funcional
        if CAMINHO_BACKUP.exists():
            valido_bak, _motivo_bak, index_bak = validar_indice_funcional(
                CAMINHO_BACKUP,
                embeddings,
                doc_sha256_esperado=doc_sha256_esperado,
                chunking_hash_esperado=chunking_hash_esperado,
            )
            if valido_bak and index_bak is not None:
                os.rename(CAMINHO_BACKUP, CAMINHO_INDICE)
                return index_bak
            else:
                mover_para_quarentena(CAMINHO_BACKUP, "startup_invalid_backup")

        return None
    finally:
        liberar_lock(lock_fd)


def carregar_ou_criar_indice(
    caminho_pdf: str | Path = "data/politica_rh_exemplo.pdf",
    embeddings: Embeddings | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    forcar_reindexacao: bool = False,
) -> FAISS:
    """
    Ponto de entrada principal para carregar o índice persistente FAISS com validação e cache local.
    """
    caminho_pdf = Path(caminho_pdf)
    if not caminho_pdf.exists():
        if (DIRETORIO_DADOS / "politica_rh_exemplo.pdf").exists():
            caminho_pdf = DIRETORIO_DADOS / "politica_rh_exemplo.pdf"
        elif Path("politica_rh.pdf").exists():
            caminho_pdf = Path("politica_rh.pdf")
        else:
            raise FileNotFoundError(f"Arquivo PDF não encontrado: {caminho_pdf}")

    if embeddings is None:
        embeddings = obter_embeddings()

    doc_sha256 = calcular_hash_arquivo(caminho_pdf)
    chunking_hash = calcular_hash_chunking(chunk_size, chunk_overlap)

    if not forcar_reindexacao:
        indice = recuperar_na_inicializacao(
            embeddings,
            doc_sha256_esperado=doc_sha256,
            chunking_hash_esperado=chunking_hash,
        )
        if indice is not None:
            return indice

    # Reindexação completa necessária
    blocos = carregar_documentos(
        caminho_pdf=caminho_pdf, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    novo_indice = criar_banco_vetores(blocos, embeddings)
    salvar_indice_persistente(
        banco_vetores=novo_indice,
        caminho_pdf=caminho_pdf,
        documentos=blocos,
        embeddings=embeddings,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return novo_indice


def carregar_e_indexar_pdf(
    caminho_pdf: str = "data/politica_rh_exemplo.pdf",
    embeddings: Embeddings | None = None,
) -> FAISS:
    """Função de compatibilidade retroativa com a V1."""
    return carregar_ou_criar_indice(caminho_pdf=caminho_pdf, embeddings=embeddings)
