"""
Módulo de conexão, resolução e catálogo do cliente Ollama.
Implementa resolução determinística de URL (ADR-0001) e catálogo dinâmico de modelos (ADR-0002).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from langchain_ollama import ChatOllama, OllamaEmbeddings

# Configurações canônicas de modelos provisórios
MODELO_EMBEDDINGS_PADRAO = "nomic-embed-text:latest"
MODELO_CHAT_PADRAO = "qwen3.5:4b"
MODELOS_CHAT_HOMOLOGADOS = [
    "qwen3.5:4b",
    "llama3.1:8b",
    "llama3.2:3b",
    "qwen2.5:7b",
]


class OllamaConfigurationError(ValueError):
    """Exceção levantada quando a configuração da URL base do Ollama é inválida."""


def validar_e_normalizar_url_ollama(url: str) -> str:
    """
    Valida e normaliza estritamente uma URL base do Ollama conforme a ADR-0001.

    Regras aplicadas:
    - Rejeição de query strings e fragmentos
    - Pré-normalização de URLs sem esquema adicionando 'http://'
    - Validação de esquema estritamente 'http' ou 'https'
    - Rejeição de credenciais embutidas (username / password)
    - Validação de hostname presente
    - Validação de porta (padrão 11434 quando omitida, intervalo 1-65535, rejeição de vazia ou não numérica)
    - Suporte canônico a IPv6
    - Preservação de subcaminhos de proxy reverso e rejeição de rotas de API duplicadas
    """
    if not isinstance(url, str):
        raise OllamaConfigurationError(f"A URL deve ser uma string, recebido: {type(url).__name__}")

    url_limpa = url.strip()
    if not url_limpa:
        return "http://127.0.0.1:11434"

    if "?" in url_limpa:
        raise OllamaConfigurationError("Query strings não são permitidas na URL base do Ollama.")
    if "#" in url_limpa:
        raise OllamaConfigurationError("Fragmentos não são permitidos na URL base do Ollama.")

    # Pré-normalização de URLs sem esquema
    if "://" not in url_limpa:
        url_analise = f"http://{url_limpa}"
    else:
        url_analise = url_limpa

    parsed = urllib.parse.urlsplit(url_analise)

    # Esquema
    esquema = parsed.scheme.lower()
    if esquema not in ("http", "https"):
        raise OllamaConfigurationError(
            f"Esquema de protocolo inválido '{parsed.scheme}'. Deve ser 'http' ou 'https'."
        )

    # Credenciais
    if parsed.username or parsed.password:
        raise OllamaConfigurationError(
            "Credenciais de autenticação embutidas na URL não são permitidas."
        )

    # Hostname
    hostname = parsed.hostname
    if not hostname:
        raise OllamaConfigurationError("Hostname ausente ou vazio na URL do Ollama.")

    # Validação da porta
    netloc_sem_credenciais = parsed.netloc.split("@")[-1]
    if "]" in netloc_sem_credenciais:
        parte_depois_ipv6 = netloc_sem_credenciais.split("]")[-1]
        tem_dois_pontos_porta = ":" in parte_depois_ipv6
        sufixo_porta = parte_depois_ipv6.lstrip(":")
    else:
        partes = netloc_sem_credenciais.split(":")
        tem_dois_pontos_porta = len(partes) > 1
        sufixo_porta = partes[1] if tem_dois_pontos_porta else ""

    if tem_dois_pontos_porta:
        porta_str = sufixo_porta.split("/")[0]
        if not porta_str:
            raise OllamaConfigurationError("Porta vazia especificada na URL do Ollama.")
        if not porta_str.isdigit():
            raise OllamaConfigurationError("Porta não numérica especificada na URL do Ollama.")
        porta = int(porta_str)
        if not (1 <= porta <= 65535):
            raise OllamaConfigurationError(f"Porta {porta} fora do intervalo TCP válido (1-65535).")
    else:
        porta = 11434

    # Caminho (path)
    caminho = parsed.path.rstrip("/")
    caminho_partes = [p for p in caminho.split("/") if p]
    if "api" in caminho_partes:
        raise OllamaConfigurationError(
            "A URL base não deve conter caminhos reservados da API (/api, /api/tags, etc.)."
        )

    # Formatação do Hostname para IPv6
    if ":" in hostname and not hostname.startswith("["):
        host_formatado = f"[{hostname}]"
    else:
        host_formatado = hostname

    return f"{esquema}://{host_formatado}:{porta}{caminho}"


def obter_url_ollama() -> str:
    """
    Retorna a URL base normalizada do Ollama.
    Prioridade 1: OLLAMA_BASE_URL (se definida e não vazia).
    Prioridade 2: Fallback canônico http://127.0.0.1:11434.
    """
    env_url = os.getenv("OLLAMA_BASE_URL")
    if env_url is not None and env_url.strip():
        return validar_e_normalizar_url_ollama(env_url)
    return "http://127.0.0.1:11434"


def verificar_conexao_ollama(base_url: str | None = None, timeout: float = 1.0) -> bool:
    """
    Verifica a saúde operacional do endpoint do Ollama consultando GET /api/version.
    Exige HTTP 200 e resposta JSON estruturada com chave 'version' não vazia.
    """
    url_base = (base_url or obter_url_ollama()).rstrip("/")
    # Valida antes de disparar I/O
    validar_e_normalizar_url_ollama(url_base)

    url_api = f"{url_base}/api/version"
    req = urllib.request.Request(
        url_api,
        headers={"User-Agent": "agente-ia-rh/2.0"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = response.read().decode("utf-8")
            dados = json.loads(payload)
            if not isinstance(dados, dict):
                return False
            versao = dados.get("version")
            return isinstance(versao, str) and bool(versao.strip())
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        KeyError,
        ConnectionResetError,
    ):
        return False


def listar_modelos_ollama(
    base_url: str | None = None, timeout: float = 2.0
) -> list[dict[str, Any]]:
    """
    Consulta o endpoint GET /api/tags e retorna os dados brutos dos modelos disponíveis.
    """
    url_base = (base_url or obter_url_ollama()).rstrip("/")
    url_api = f"{url_base}/api/tags"
    req = urllib.request.Request(
        url_api,
        headers={"User-Agent": "agente-ia-rh/2.0"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return []
            dados = json.loads(response.read().decode("utf-8"))
            if isinstance(dados, dict) and isinstance(dados.get("models"), list):
                return dados["models"]
            return []
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []


def listar_modelos_chat(base_url: str | None = None, timeout: float = 2.0) -> list[str]:
    """
    Lista modelos aptos para chat instrucional e RAG, excluindo modelos de embeddings
    e variantes de código bruto não homologadas (ADR-0002).
    """
    modelos_brutos = listar_modelos_ollama(base_url=base_url, timeout=timeout)
    modelos_chat: list[str] = []

    for item in modelos_brutos:
        nome = item.get("name") or item.get("model")
        if not nome or not isinstance(nome, str):
            continue

        capacidades = item.get("capabilities", [])

        # Exclusão estrita de modelos de embedding
        if "embedding" in capacidades:
            continue
        if "embed" in nome.lower() or "bge-m3" in nome.lower():
            continue

        # Exclusão de modelos de código puro não conversacionais (base completion)
        if "base" in nome.lower() and "tools" not in capacidades and "thinking" not in capacidades:
            continue

        modelos_chat.append(nome)

    return modelos_chat


def verificar_modelo_disponivel(modelo: str, base_url: str | None = None) -> bool:
    """Verifica se um modelo específico está instalado no Ollama."""
    modelos = listar_modelos_ollama(base_url=base_url)
    nome_alvo = modelo.strip().lower()
    for item in modelos:
        nome = str(item.get("name", "")).strip().lower()
        if nome == nome_alvo or nome.split(":")[0] == nome_alvo.split(":")[0]:
            return True
    return False


def obter_embeddings(model: str | None = None, base_url: str | None = None) -> OllamaEmbeddings:
    """Retorna uma instância de OllamaEmbeddings configurada."""
    url = base_url or obter_url_ollama()
    modelo = model or os.getenv("OLLAMA_EMBED_MODEL", MODELO_EMBEDDINGS_PADRAO)
    return OllamaEmbeddings(model=modelo, base_url=url)


def obter_llm(
    model: str | None = None,
    temperature: float = 0.2,
    base_url: str | None = None,
    num_ctx: int = 2048,
) -> ChatOllama:
    """Retorna uma instância de ChatOllama configurada com janela de contexto segura para CPU."""
    url = base_url or obter_url_ollama()
    modelo = model or os.getenv("OLLAMA_CHAT_MODEL", MODELO_CHAT_PADRAO)
    return ChatOllama(model=modelo, base_url=url, temperature=temperature, num_ctx=num_ctx)
