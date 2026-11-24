"""
Aplicação principal FastAPI com suporte a CORS corporativo e montagem de frontend estático (ADR-0006).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .routes import chat, faq, health

DIRETORIO_RAIZ = Path(__file__).resolve().parent.parent
DIRETORIO_FRONTEND = DIRETORIO_RAIZ / "frontend"

app = FastAPI(
    title="Assistente de RH — API Headless",
    version="2.0.0",
    description=(
        "API REST e SSE desacoplada para consultas de políticas internas de Recursos Humanos via RAG. "
        "Permite integração com intranets corporativas, portais web, chatbots e widgets embutíveis."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configuração de CORS para permitir acesso por qualquer frontend na rede interna / intranet
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão dos roteadores da API v1
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
