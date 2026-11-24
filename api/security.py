"""
Módulo de segurança, controle de concorrência, rate limiting e sanitização de prompts (ADR-0007).
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager

from fastapi import HTTPException, Request, status

# Limites operacionais seguros para CPU
MAX_CONCURRENT_INFERENCES = int(os.getenv("MAX_CONCURRENT_INFERENCES", "2"))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Padrões conhecidos de Prompt Injection e Jailbreak
PADROES_INJECAO = [
    re.compile(
        r"\b(?:ignore|esqueça|desconsidere|forget)\b.+(?:instruç|diretriz|regr|prompt|sistema|rules)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:revele|mostre|liste|print)\b.+(?:prompt de sistema|instruções secretas|system prompt)",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:dan mode|jailbreak|unrestricted mode)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:você agora é|you are now|aja como|act as)\b.+(?:desbloqueado|sem restrições|unfiltered|evil)",
        re.IGNORECASE,
    ),
]


class RateLimiter:
    """Limitador de taxa por endereço IP baseado em janela deslizante em memória."""

    def __init__(
        self, max_requests: int = RATE_LIMIT_REQUESTS, window: int = RATE_LIMIT_WINDOW_SECONDS
    ):
        self.max_requests = max_requests
        self.window = window
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def verificar(self, ip: str) -> tuple[bool, int]:
        """
        Verifica se a requisição é permitida para o IP especificado.
        Retorna (permitido, segundos_para_reset).
        """
        agora = time.time()
        with self._lock:
            historico = self._history[ip]
            # Remove timestamps fora da janela
            self._history[ip] = [t for t in historico if agora - t < self.window]

            if len(self._history[ip]) >= self.max_requests:
                mais_antigo = self._history[ip][0]
                tempo_restante = max(1, int(self.window - (agora - mais_antigo)))
                return False, tempo_restante

            self._history[ip].append(agora)
            return True, 0

    def resetar(self) -> None:
        """Limpa o histórico de requisições (útil para testes unitários)."""
        with self._lock:
            self._history.clear()


class ConcurrencyLimiter:
    """Controlador de concorrência com semáforo estrito para proteger a CPU do host."""

    def __init__(self, limite_maximo: int = MAX_CONCURRENT_INFERENCES):
        self.limite_maximo = limite_maximo
        self._ativos = 0
        self._lock = threading.Lock()

    @property
    def em_execucao(self) -> int:
        with self._lock:
            return self._ativos

    def tentar_adquirir(self) -> bool:
        """Tenta reservar um slot de execução. Retorna True se concedido, False se lotado."""
        with self._lock:
            if self._ativos < self.limite_maximo:
                self._ativos += 1
                return True
            return False

    def liberar(self) -> None:
        """Libera o slot de execução após a conclusão da consulta."""
        with self._lock:
            if self._ativos > 0:
                self._ativos -= 1

    @contextmanager
    def slot(self) -> Generator[bool, None, None]:
        """Gerenciador de contexto que adquire e libera um slot com segurança."""
        adquirido = self.tentar_adquirir()
        try:
            yield adquirido
        finally:
            if adquirido:
                self.liberar()


# Instâncias globais de segurança
rate_limiter = RateLimiter()
concurrency_limiter = ConcurrencyLimiter()


def validar_prompt_seguro(pergunta: str) -> tuple[bool, str | None]:
    """
    Inspeciona a pergunta em busca de padrões típicos de injeção de prompt ou jailbreak.
    Retorna (valido, motivo_recusa).
    """
    if not pergunta:
        return True, None

    texto_limpo = pergunta.strip()

    for padrao in PADROES_INJECAO:
        if padrao.search(texto_limpo):
            return (
                False,
                "A consulta contém comandos adversariais não permitidos pelas diretrizes de segurança.",
            )

    return True, None


def extrair_ip_cliente(request: Request) -> str:
    """Extrai com segurança o IP do cliente considerando proxies corporativos."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def verificar_autenticacao_opcional(request: Request) -> None:
    """
    Valida a presença de API Key quando a variável corporativa API_KEY estiver configurada.
    Se API_KEY não estiver definida, permite o tráfego aberto na intranet.
    """
    chave_esperada = os.getenv("API_KEY", "").strip()
    if not chave_esperada:
        return

    chave_recebida = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if chave_recebida != chave_esperada:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso não autorizado: API Key corporativa inválida ou ausente.",
        )
