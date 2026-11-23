"""
Testes unitários para o módulo rag.ollama_client (ADR-0001 e ADR-0002).
"""

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from rag.ollama_client import (
    MODELO_CHAT_PADRAO,
    MODELO_EMBEDDINGS_PADRAO,
    OllamaConfigurationError,
    listar_modelos_chat,
    listar_modelos_ollama,
    obter_embeddings,
    obter_llm,
    obter_url_ollama,
    validar_e_normalizar_url_ollama,
    verificar_conexao_ollama,
    verificar_modelo_disponivel,
)


class TestValidacaoUrlOllama:
    """Testes para a função validar_e_normalizar_url_ollama (ADR-0001)."""

    def test_url_vazia_retorna_padrao(self):
        assert validar_e_normalizar_url_ollama("") == "http://127.0.0.1:11434"
        assert validar_e_normalizar_url_ollama("   ") == "http://127.0.0.1:11434"

    def test_url_sem_esquema_adiciona_http(self):
        assert validar_e_normalizar_url_ollama("localhost:11434") == "http://localhost:11434"
        assert validar_e_normalizar_url_ollama("127.0.0.1:11434") == "http://127.0.0.1:11434"
        assert validar_e_normalizar_url_ollama("servidor:8080") == "http://servidor:8080"
        assert validar_e_normalizar_url_ollama("[::1]:11434") == "http://[::1]:11434"

    def test_url_sem_porta_adiciona_11434(self):
        assert validar_e_normalizar_url_ollama("http://localhost") == "http://localhost:11434"
        assert validar_e_normalizar_url_ollama("https://servidor.remoto") == "https://servidor.remoto:11434"

    def test_url_com_caminho_proxy_reverso(self):
        assert validar_e_normalizar_url_ollama("http://servidor:11434/ollama") == "http://servidor:11434/ollama"
        assert validar_e_normalizar_url_ollama("http://servidor/ollama/") == "http://servidor:11434/ollama"

    def test_rejeicao_esquema_invalido(self):
        with pytest.raises(OllamaConfigurationError, match="Esquema de protocolo inválido"):
            validar_e_normalizar_url_ollama("ftp://localhost:11434")

    def test_rejeicao_query_string(self):
        with pytest.raises(OllamaConfigurationError, match="Query strings não são permitidas"):
            validar_e_normalizar_url_ollama("http://localhost:11434?param=1")

    def test_rejeicao_fragmento(self):
        with pytest.raises(OllamaConfigurationError, match="Fragmentos não são permitidos"):
            validar_e_normalizar_url_ollama("http://localhost:11434#secao")

    def test_rejeicao_credenciais_embutidas(self):
        with pytest.raises(OllamaConfigurationError, match="Credenciais de autenticação"):
            validar_e_normalizar_url_ollama("http://user:pass@localhost:11434")

    def test_rejeicao_porta_vazia(self):
        with pytest.raises(OllamaConfigurationError, match="Porta vazia especificada"):
            validar_e_normalizar_url_ollama("http://localhost:")

    def test_rejeicao_porta_nao_numerica(self):
        with pytest.raises(OllamaConfigurationError, match="Porta não numérica"):
            validar_e_normalizar_url_ollama("http://localhost:abc")

    def test_rejeicao_porta_fora_do_intervalo(self):
        with pytest.raises(OllamaConfigurationError, match="fora do intervalo TCP válido"):
            validar_e_normalizar_url_ollama("http://localhost:0")
        with pytest.raises(OllamaConfigurationError, match="fora do intervalo TCP válido"):
            validar_e_normalizar_url_ollama("http://localhost:65536")

    def test_rejeicao_caminho_com_api_duplicada(self):
        with pytest.raises(OllamaConfigurationError, match="caminhos reservados da API"):
            validar_e_normalizar_url_ollama("http://localhost:11434/api")
        with pytest.raises(OllamaConfigurationError, match="caminhos reservados da API"):
            validar_e_normalizar_url_ollama("http://localhost:11434/api/tags")


class TestObterUrlOllama:
    """Testes para resolução de variável de ambiente OLLAMA_BASE_URL."""

    def test_fallback_padrao_quando_variavel_ausente(self):
        with patch.dict("os.environ", {}, clear=True):
            assert obter_url_ollama() == "http://127.0.0.1:11434"

    def test_fallback_padrao_quando_variavel_em_branco(self):
        with patch.dict("os.environ", {"OLLAMA_BASE_URL": "   "}, clear=True):
            assert obter_url_ollama() == "http://127.0.0.1:11434"

    def test_resolucao_quando_variavel_valida(self):
        with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://meu-ollama:11434"}, clear=True):
            assert obter_url_ollama() == "http://meu-ollama:11434"

    def test_lanca_excecao_quando_variavel_invalida(self):
        with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://localhost:99999"}, clear=True):
            with pytest.raises(OllamaConfigurationError):
                obter_url_ollama()


class TestVerificarConexaoOllama:
    """Testes para verificar_conexao_ollama via GET /api/version."""

    def test_sucesso_quando_retorna_versao_valida(self):
        payload = json.dumps({"version": "0.4.0"}).encode("utf-8")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = payload
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert verificar_conexao_ollama("http://127.0.0.1:11434") is True

    def test_falha_quando_versao_ausente_ou_vazia(self):
        payload = json.dumps({"version": ""}).encode("utf-8")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = payload
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert verificar_conexao_ollama("http://127.0.0.1:11434") is False

    def test_falha_quando_json_nao_e_objeto(self):
        payload = json.dumps(["version", "0.4.0"]).encode("utf-8")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = payload
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert verificar_conexao_ollama("http://127.0.0.1:11434") is False

    def test_falha_quando_servidor_retorna_erro_http(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 404, "Not Found", {}, None)):
            assert verificar_conexao_ollama("http://127.0.0.1:11434") is False

    def test_falha_quando_servidor_inalcancavel(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            assert verificar_conexao_ollama("http://127.0.0.1:11434") is False

    def test_lanca_excecao_para_url_malformada_sem_disparar_rede(self):
        with pytest.raises(OllamaConfigurationError):
            verificar_conexao_ollama("http://localhost:invalid")


class TestCatalogoModelosOllama:
    """Testes para o catálogo dinâmico de modelos (ADR-0002)."""

    def test_listar_modelos_chat_filtra_embeddings_e_base(self):
        dados_api = {
            "models": [
                {
                    "name": "qwen3.5:4b",
                    "capabilities": ["completion", "tools", "thinking"],
                },
                {
                    "name": "llama3.1:8b",
                    "capabilities": ["completion", "tools"],
                },
                {
                    "name": "qwen2.5-coder:1.5b-base",
                    "capabilities": ["completion", "insert"],
                },
                {
                    "name": "nomic-embed-text:latest",
                    "capabilities": ["embedding"],
                },
            ]
        }
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(dados_api).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            chat_models = listar_modelos_chat("http://127.0.0.1:11434")
            assert "qwen3.5:4b" in chat_models
            assert "llama3.1:8b" in chat_models
            assert "nomic-embed-text:latest" not in chat_models
            assert "qwen2.5-coder:1.5b-base" not in chat_models

    def test_verificar_modelo_disponivel(self):
        dados_api = {"models": [{"name": "qwen3.5:4b"}]}
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(dados_api).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert verificar_modelo_disponivel("qwen3.5:4b", "http://127.0.0.1:11434") is True
            assert verificar_modelo_disponivel("mistral:7b", "http://127.0.0.1:11434") is False

    def test_obter_llm_e_embeddings_com_padroes(self):
        with patch.dict("os.environ", {}, clear=True):
            llm = obter_llm(base_url="http://127.0.0.1:11434")
            assert llm.model == MODELO_CHAT_PADRAO

            embed = obter_embeddings(base_url="http://127.0.0.1:11434")
            assert embed.model == MODELO_EMBEDDINGS_PADRAO
