"""
Aplicação principal FastAPI com suporte a CORS corporativo, cabeçalhos de segurança e montagem de frontend estático (ADR-0006 e ADR-0007).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .routes import chat, faq, health

DIRETORIO_RAIZ = Path(__file__).resolve().parent.parent
DIRETORIO_FRONTEND = DIRETORIO_RAIZ / "frontend"

# Controle de documentação OpenAPI (desativada em produção ou quando ENABLE_DOCS=false)
docs_ativo = (
    os.getenv("ENABLE_DOCS", "true").lower() in ("1", "true", "yes")
    and os.getenv("ENV") != "production"
)

app = FastAPI(
    title="Assistente de RH — API Headless",
    version="2.0.0",
    description=(
        "API REST e SSE desacoplada para consultas de políticas internas de Recursos Humanos via RAG. "
        "Permite integração com intranets corporativas, portais web, chatbots e widgets embutíveis."
    ),
    docs_url="/docs" if docs_ativo else None,
    redoc_url="/redoc" if docs_ativo else None,
    openapi_url="/openapi.json" if docs_ativo else None,
)


# 1. Middleware de Cabeçalhos de Segurança HTTP (ADR-0007)
@app.middleware("http")
async def aplicar_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# 2. Configuração de CORS Restrito para Intranet (ADR-0007)
origens_raw = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000,http://localhost:8501,http://127.0.0.1:8501",
)
origens_lista = [origem.strip() for origem in origens_raw.split(",") if origem.strip()]
permite_credenciais = "*" not in origens_lista

app.add_middleware(
    CORSMiddleware,
    allow_origins=origens_lista,
    allow_credentials=permite_credenciais,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 3. Inclusão dos roteadores da API v1
app.include_router(health.router, prefix="/api/v1", tags=["Saúde e Diagnóstico"])
app.include_router(faq.router, prefix="/api/v1", tags=["Perguntas Frequentes (FAQ)"])
app.include_router(chat.router, prefix="/api/v1", tags=["Conversação RAG"])


# Rota raiz servindo a página principal do frontend para usuários da intranet
@app.get("/", include_in_schema=False)
def servir_home():
    arquivo_index = DIRETORIO_FRONTEND / "index.html"
    if arquivo_index.exists():
        return FileResponse(arquivo_index)
    return {"message": "Assistente de RH API está ativa. Acesse /docs para documentação OpenAPI."}


@app.get("/widget.js", include_in_schema=False)
def servir_widget():
    arquivo_widget = DIRETORIO_FRONTEND / "widget.js"
    if arquivo_widget.exists():
        return FileResponse(arquivo_widget, media_type="application/javascript")
    return {"message": "Widget não encontrado."}


@app.get("/favicon.ico", include_in_schema=False)
def servir_favicon():
    """Retorna ícone emoji 💼 em SVG para evitar erro 404 de favicon no navegador."""
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">💼</text></svg>'
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/sw.js", include_in_schema=False)
def servir_service_worker():
    """Responde a requisições residuais de Service Worker da porta 8000 para evitar 404."""
    return Response(content="", media_type="application/javascript")


# Servir arquivos estáticos do frontend (CSS, JS, widgets) caso o diretório exista
if DIRETORIO_FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(DIRETORIO_FRONTEND)), name="static")
