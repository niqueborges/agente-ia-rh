"""
Módulo raiz da API Headless do Assistente de RH.
Fornece endpoints REST e Server-Sent Events (SSE) desacoplados (ADR-0006).
"""

from .main import app

__all__ = ["app"]
