"""
Testes unitários para o módulo rag.ingest e persistência FAISS (ADR-0004).
"""

import json

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.ingest import (
    SCHEMA_VERSION,
    calcular_hash_arquivo,
    calcular_hash_chunking,
    gerar_collection_id,
    recuperar_na_inicializacao,
    salvar_indice_persistente,
    validar_indice_funcional,
)


class MockEmbeddings(Embeddings):
    """Embeddings determinísticos para testes sem chamadas de rede."""

    def __init__(self, dimension: int = 4):
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(i % self.dimension)] * self.dimension for i, _ in enumerate(texts)]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * self.dimension


class TestHashesEIdentificadores:
    """Testes para cálculo de hashes e identificadores de manifesto."""

    def test_calcular_hash_arquivo(self, tmp_path):
        arquivo = tmp_path / "teste.txt"
        arquivo.write_text("conteúdo de teste para hash", encoding="utf-8")
        h1 = calcular_hash_arquivo(arquivo)
        h2 = calcular_hash_arquivo(arquivo)
        assert len(h1) == 64
        assert h1 == h2

    def test_calcular_hash_chunking_determinismo(self):
        h1 = calcular_hash_chunking(1000, 200)
        h2 = calcular_hash_chunking(1000, 200)
        h3 = calcular_hash_chunking(800, 100)
        assert h1 == h2
        assert h1 != h3

    def test_gerar_collection_id(self):
        cid = gerar_collection_id("manual_colaborador.pdf", "a1b2c3d4e5f6")
        assert cid == "manual_colaborador:a1b2c3d4"


class TestValidacaoFuncionalIndice:
    """Testes dos 5 critérios de validação funcional sem chamadas de embedding."""

    def test_falha_se_arquivos_ausentes(self, tmp_path):
        valido, motivo, idx = validar_indice_funcional(tmp_path, MockEmbeddings())
        assert valido is False
        assert "Arquivos essenciais do índice ausentes" in motivo
        assert idx is None

    def test_falha_se_manifesto_corrompido(self, tmp_path):
        (tmp_path / "index.faiss").write_bytes(b"dados")
        (tmp_path / "index.pkl").write_bytes(b"dados")
        (tmp_path / "manifest.json").write_text("{json_invalido", encoding="utf-8")

        valido, motivo, idx = validar_indice_funcional(tmp_path, MockEmbeddings())
        assert valido is False
        assert "Falha ao decodificar manifest.json" in motivo

    def test_falha_se_hash_documento_diverge(self, tmp_path):
        docs = [
            Document(page_content="Texto de teste", metadata={"source": "manual.pdf", "page": 1})
        ]
        embeddings = MockEmbeddings(dimension=4)
        faiss_store = FAISS.from_documents(docs, embeddings)
        faiss_store.save_local(str(tmp_path))

        manifesto = {
            "schema_version": SCHEMA_VERSION,
            "document_sha256": "hash_antigo",
            "chunking_config_hash": "chunk_hash",
            "embedding_dimension": 4,
            "total_chunks": 1,
        }
        with open(tmp_path / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifesto, f)

        valido, motivo, idx = validar_indice_funcional(
            tmp_path,
            embeddings,
            doc_sha256_esperado="hash_novo_diferente",
        )
        assert valido is False
        assert "Hash do documento PDF diverge" in motivo

    def test_sucesso_em_indice_integro(self, tmp_path):
        docs = [
            Document(
                page_content="Política de férias da empresa",
                metadata={"source": "manual.pdf", "page": 1},
            )
        ]
        embeddings = MockEmbeddings(dimension=4)
        faiss_store = FAISS.from_documents(docs, embeddings)
        faiss_store.save_local(str(tmp_path))

        doc_hash = "abc123hash"
        chunk_hash = calcular_hash_chunking(1000, 200)
        manifesto = {
            "schema_version": SCHEMA_VERSION,
            "document_sha256": doc_hash,
            "chunking_config_hash": chunk_hash,
            "embedding_dimension": 4,
            "total_chunks": 1,
        }
        with open(tmp_path / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifesto, f)

        valido, motivo, idx = validar_indice_funcional(
            tmp_path,
            embeddings,
            doc_sha256_esperado=doc_hash,
            chunking_hash_esperado=chunk_hash,
        )
        assert valido is True
        assert "Índice válido e íntegro" in motivo
        assert idx is not None


class TestPersistenciaEStartupRecovery:
    """Testes de ciclo de vida atômico e recuperação na inicialização."""

    def test_salvar_indice_persistente_cria_manifesto_e_arquivos(self, tmp_path, monkeypatch):
        dir_dados = tmp_path / "data"
        dir_dados.mkdir()
        pdf_fake = dir_dados / "politica_rh_exemplo.pdf"
        pdf_fake.write_bytes(b"%PDF-1.4 fake pdf content")

        monkeypatch.setattr("rag.ingest.DIRETORIO_DADOS", dir_dados)
        monkeypatch.setattr("rag.ingest.CAMINHO_INDICE", dir_dados / "faiss_index")
        monkeypatch.setattr("rag.ingest.CAMINHO_BACKUP", dir_dados / "faiss_index_backup")
        monkeypatch.setattr("rag.ingest.CAMINHO_TMP", dir_dados / "faiss_index_tmp")
        monkeypatch.setattr("rag.ingest.CAMINHO_LOCK", dir_dados / "faiss_index.lock")

        docs = [
            Document(page_content="Manual interno", metadata={"source": str(pdf_fake), "page": 1})
        ]
        embeddings = MockEmbeddings(dimension=4)
        banco = FAISS.from_documents(docs, embeddings)

        caminho_salvo = salvar_indice_persistente(
            banco_vetores=banco,
            caminho_pdf=pdf_fake,
            documentos=docs,
            embeddings=embeddings,
        )

        assert caminho_salvo.exists()
        assert (caminho_salvo / "manifest.json").exists()
        assert (caminho_salvo / "index.faiss").exists()
        assert (caminho_salvo / "index.pkl").exists()

        # Testa recuperação na inicialização
        doc_hash = calcular_hash_arquivo(pdf_fake)
        chunk_hash = calcular_hash_chunking(1000, 200)
        recuperado = recuperar_na_inicializacao(embeddings, doc_hash, chunk_hash)
        assert recuperado is not None
        assert recuperado.index.ntotal == 1
