"""
Testes unitários para o módulo rag.chain e formatação LCEL (ADR-0003).
"""

from unittest.mock import MagicMock

from langchain_core.documents import Document

from rag.chain import criar_chain_rag, formatar_documentos


class TestFormatacaoDocumentos:
    """Validações da função pura formatar_documentos conforme ADR-0003."""

    def test_formata_lista_de_documentos_com_sucesso(self):
        docs = [
            Document(
                page_content="Política de Férias: 30 dias após 12 meses.", metadata={"page": 1}
            ),
            Document(
                page_content="Home office: Permitido 2 vezes por semana.", metadata={"page": 3}
            ),
        ]
        resultado = formatar_documentos(docs)

        # Deve ser estritamente uma string
        assert isinstance(resultado, str)
        # Não deve conter representação de classes ou metadados Python
        assert "Document(" not in resultado
        assert "metadata=" not in resultado
        # Deve conter o texto original dos trechos
        assert "Política de Férias: 30 dias após 12 meses." in resultado
        assert "Home office: Permitido 2 vezes por semana." in resultado
        # Deve separar os trechos com quebra de linha dupla
        assert "\n\n" in resultado

    def test_trata_lista_vazia(self):
        resultado = formatar_documentos([])
        assert resultado == "Nenhum trecho relevante encontrado nas políticas internas."

    def test_trata_espacos_em_branco_excedentes(self):
        docs = [
            Document(
                page_content="   Texto com espaços antes e depois.   \n", metadata={"page": 0}
            ),
            Document(page_content="Segundo documento sem espaços extras.", metadata={"page": 1}),
        ]
        resultado = formatar_documentos(docs)
        assert (
            resultado
            == "Texto com espaços antes e depois.\n\nSegundo documento sem espaços extras."
        )


class TestCriarChainRAG:
    """Testes de construção da chain RAG com LCEL."""

    def test_montagem_da_chain(self):
        mock_faiss = MagicMock()
        mock_retriever = MagicMock()
        mock_faiss.as_retriever.return_value = mock_retriever
        mock_llm = MagicMock()

        chain = criar_chain_rag(mock_faiss, mock_llm, k_documentos=4)

        mock_faiss.as_retriever.assert_called_once_with(search_kwargs={"k": 4})
        assert chain is not None
