"""
Suíte de testes automatizados para a API Headless FastAPI e endpoints REST/SSE (ADR-0006).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from api.main import app

client = TestClient(app)


def test_endpoint_health():
    """Testa se o endpoint /api/v1/health responde com estrutura válida."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    dados = response.json()
    assert "status" in dados
    assert "ollama" in dados
    assert "faiss" in dados
    assert "model" in dados
    assert isinstance(dados["ollama"]["connected"], bool)


def test_endpoint_faq():
    """Testa se o endpoint /api/v1/faq retorna lista de perguntas frequentes."""
    response = client.get("/api/v1/faq")
    assert response.status_code == 200
    dados = response.json()
    assert "faqs" in dados
    assert len(dados["faqs"]) > 0
    primeiro = dados["faqs"][0]
    assert "category" in primeiro
    assert "question" in primeiro
    assert "icon" in primeiro


def test_servir_arquivos_estaticos():
    """Testa se os arquivos do frontend e widget são servidos corretamente."""
    resp_home = client.get("/")
    assert resp_home.status_code == 200
    assert "text/html" in resp_home.headers["content-type"]
    assert "Assistente de RH" in resp_home.text

    resp_widget = client.get("/widget.js")
    assert resp_widget.status_code == 200
    assert "assistente-rh-chat" in resp_widget.text

    resp_css = client.get("/static/styles.css")
    assert resp_css.status_code == 200
    assert "--primary" in resp_css.text


def test_chat_validacao_pergunta_vazia():
    """Testa validação de entrada rejeitando perguntas vazias ou só espaços."""
    resp_vazia = client.post("/api/v1/chat", json={"question": ""})
    assert resp_vazia.status_code == 422

    resp_espacos = client.post("/api/v1/chat", json={"question": "   "})
    assert resp_espacos.status_code == 422


@patch("api.routes.chat.verificar_conexao_ollama", return_value=True)
@patch("api.routes.chat.obter_banco_vetores")
@patch("api.routes.chat.criar_chain_rag")
@patch("api.routes.chat.obter_llm")
def test_chat_modo_sincrono(mock_llm, mock_chain, mock_banco, mock_conexao):
    """Testa consulta síncrona retornando resposta completa e lista de fontes."""
    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = [
        Document(page_content="O período de férias é de 30 dias.", metadata={"page": 2}),
    ]
    mock_banco_inst = MagicMock()
    mock_banco_inst.as_retriever.return_value = mock_retriever
    mock_banco.return_value = mock_banco_inst

    mock_chain_inst = MagicMock()
    mock_chain_inst.invoke.return_value = "As férias têm duração legal de 30 dias após 12 meses."
    mock_chain.return_value = mock_chain_inst

    response = client.post(
        "/api/v1/chat",
        json={"question": "Como funcionam as férias?", "stream": False},
    )

    assert response.status_code == 200
    dados = response.json()
    assert "answer" in dados
    assert "sources" in dados
    assert len(dados["sources"]) == 1
    assert dados["sources"][0]["page"] == 3  # base 0 (page 2) convertida para base 1 (page 3)
    assert "férias" in dados["answer"].lower()


@patch("api.routes.chat.verificar_conexao_ollama", return_value=True)
@patch("api.routes.chat.obter_banco_vetores")
@patch("api.routes.chat.criar_chain_rag")
@patch("api.routes.chat.obter_llm")
def test_chat_modo_streaming_sse(mock_llm, mock_chain, mock_banco, mock_conexao):
    """Testa consulta com streaming de Server-Sent Events (SSE)."""
    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = [
        Document(page_content="Regras do trabalho remoto.", metadata={"page": 0}),
    ]
    mock_banco_inst = MagicMock()
    mock_banco_inst.as_retriever.return_value = mock_retriever
    mock_banco.return_value = mock_banco_inst

    mock_chain_inst = MagicMock()
    mock_chain_inst.stream.return_value = iter(["O ", "trabalho ", "remoto ", "é ", "permitido."])
    mock_chain.return_value = mock_chain_inst

    response = client.post(
        "/api/v1/chat",
        json={"question": "Como funciona o home office?", "stream": True},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    corpo = response.text
    assert "data: " in corpo
    assert '"type": "token"' in corpo
    assert '"type": "sources"' in corpo
    assert '"type": "done"' in corpo


@patch("api.routes.chat.verificar_conexao_ollama", return_value=False)
def test_chat_falha_ollama_indisponivel_sync(mock_conexao):
    """Testa retorno 503 quando Ollama está offline no modo síncrono."""
    response = client.post(
        "/api/v1/chat",
        json={"question": "Qual o prazo do atestado?", "stream": False},
    )
    assert response.status_code == 503
    assert "indisponível" in response.json()["detail"].lower()


@patch("api.routes.chat.verificar_conexao_ollama", return_value=False)
def test_chat_falha_ollama_indisponivel_streaming(mock_conexao):
    """Testa emissão de evento de erro via SSE quando Ollama está offline."""
    response = client.post(
        "/api/v1/chat",
        json={"question": "Qual o prazo do atestado?", "stream": True},
    )
    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert "indisponível" in response.text.lower()
