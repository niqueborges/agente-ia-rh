"""
Módulo de conexão e configuração do cliente Ollama.
Implementa detecção dinâmica de host para portabilidade entre Linux nativo, Docker e WSL.
"""

import os
import socket
import subprocess
from langchain_ollama import OllamaEmbeddings, ChatOllama


def testar_conexao(host: str, port: int = 11434, timeout: float = 0.3) -> bool:
    """Testa rapidamente se uma porta TCP está respondendo no host indicado."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def obter_url_ollama() -> str:
    """
    Detecta automaticamente a URL base do Ollama.
    
    Ordem de resolução:
    1. Variável de ambiente OLLAMA_BASE_URL (se definida explicitamente)
    2. Localhost / 127.0.0.1 (execução local nativa)
    3. Gateway IP do Windows Host (execução dentro do WSL2)
    4. Fallback padrão para http://localhost:11434
    """
    if os.getenv("OLLAMA_BASE_URL"):
        return os.getenv("OLLAMA_BASE_URL")

    # 1. Testa localhost e 127.0.0.1
    for host in ["localhost", "127.0.0.1"]:
        if testar_conexao(host, 11434):
            return f"http://{host}:11434"

    # 2. Se estiver no WSL2, busca o IP do gateway do host Windows
    try:
        host_ip = (
            subprocess.check_output(
                "ip route | grep default | awk '{print $3}'",
                shell=True,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        if host_ip and testar_conexao(host_ip, 11434):
            return f"http://{host_ip}:11434"
    except Exception:
        pass

    return "http://localhost:11434"


def obter_embeddings(model: str = "nomic-embed-text", base_url: str | None = None) -> OllamaEmbeddings:
    """Retorna uma instância de OllamaEmbeddings configurada."""
    url = base_url or obter_url_ollama()
    return OllamaEmbeddings(model=model, base_url=url)


def obter_llm(model: str = "mistral:7b", temperature: float = 0.2, base_url: str | None = None) -> ChatOllama:
    """Retorna uma instância de ChatOllama configurada."""
    url = base_url or obter_url_ollama()
    return ChatOllama(model=model, base_url=url, temperature=temperature)
