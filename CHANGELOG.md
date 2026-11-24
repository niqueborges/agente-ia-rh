# Changelog — Agente IA RH

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.
O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [2.1.0] — 2026-11-23

### 🏛️ Governança Arquitetural
- **ADR-0006:** Desacoplamento do Backend RAG via API REST/SSE e Frontend Independente para Intranet (`docs/adr/0006-desacoplamento-api-frontend.md`).
- **ADR-0007:** Blindagem de Segurança da API, Controle de Concorrência e Defesa em Profundidade (`docs/adr/0007-blindagem-seguranca-api.md`).

### 🛡️ Blindagem de Segurança e Resiliência (api/security.py)
- **Controle de Concorrência Anti-DoS:** Semáforo estrito (`ConcurrencyLimiter`) limitando inferências paralelas na CPU (máx. 2), prevenindo congelamento do host.
- **Rate Limiting em Memória:** Limitador de taxa baseado em janela deslizante por endereço IP (máx. 10 requisições/minuto), emitindo HTTP 429 com cabeçalho `Retry-After`.
- **Sanitização de Prompts (Guardrails):** Inspeção e bloqueio proativo de comandos adversariais de injeção de prompt, tentativas de jailbreak e desvio de diretrizes.
- **Cabeçalhos de Segurança HTTP:** Injeção de `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection` e `Referrer-Policy`.
- **CORS Restrito:** Substituição do wildcard irrestrito por lista configurável via `ALLOWED_ORIGINS` para domínios homologados da intranet.
- **Autenticação Opcional por API Key:** Suporte nativo à variável `API_KEY` corporativa no cabeçalho `X-API-Key`.

### 🚀 Funcionalidades e Melhorias
- **Camada de API Headless Desacoplada (api/):**
  - Construção do pacote `api/` com FastAPI (`api/main.py`, `api/schemas.py`, `api/routes/`).
  - Endpoint `POST /api/v1/chat` com suporte nativo a streaming em tempo real via Server-Sent Events (SSE: `text/event-stream`) e modo síncrono consolidado (`stream=false`).
  - Endpoint `GET /api/v1/health` para monitoramento de conectividade do Ollama, estado e manifesto do índice FAISS e modelo ativo.
  - Endpoint `GET /api/v1/faq` com catálogo categorizado de perguntas frequentes do cotidiano corporativo.
  - Endpoints defensivos `/favicon.ico` e `/sw.js` eliminando ruídos 404 de navegadores.
  - Documentação OpenAPI controlada por ambiente via `ENABLE_DOCS`.
- **Frontend Independente para Usuários Não Técnicos (frontend/):**
  - Interface web 100% estática (`frontend/index.html`, `frontend/styles.css`, `frontend/app.js`), sem necessidade de bundlers (Webpack, Vite) ou Node.js.
  - Design acessível e acolhedor focado em colaboradores leigos (sem jargões técnicos de ML, embeddings ou parâmetros de rede neural).
  - Chips clicáveis de perguntas frequentes, indicador visual de digitação (*typing indicator*), balões conversacionais e citações amigáveis do manual interno ("Página X do Manual de RH").
- **Widget Embutível / Web Component (frontend/widget.js):**
  - Criação do Custom Element `<assistente-rh-chat>` encapsulado em Shadow DOM para que qualquer empresa possa plugar o chat em sua intranet legada (WordPress, SharePoint, portal estático) com apenas 2 linhas de código.
- **Coexistência de Interfaces:**
  - O console administrativo e analítico em Streamlit (`app.py`) permanece 100% funcional, enquanto o servidor FastAPI atende as consultas da intranet.

### 🧪 Testes e Qualidade de Código
- Suíte expandida para **52 testes automatizados** com pytest cobrindo saúde, FAQ, streaming SSE, persistência, cliente Ollama, rate limiting, semáforo anti-DoS, guardrails de prompt injection, cabeçalhos de segurança e autenticação.

---

## [2.0.0] — 2026-11-23

### 🏛️ Governança Arquitetural
- Formalização de 5 Architecture Decision Records (ADRs) aprovadas em `docs/adr/`:
  - **ADR-0001:** Resolução determinística e verificação de saúde do Ollama.
  - **ADR-0002:** Catálogo dinâmico e separação de modelos de chat e embeddings.
  - **ADR-0003:** Formatação estrita do contexto na chain LCEL.
  - **ADR-0004:** Persistência controlada e recuperação do índice FAISS.
  - **ADR-0005:** Governança de dependências e compatibilidade de ambiente.

### 🚀 Funcionalidades e Melhorias
- **Conectividade Determinística (rag/ollama_client.py):**
  - Remoção de subprocessos legados (`ip route`) do ambiente WSL2.
  - Resolução direta de `OLLAMA_BASE_URL` ou fallback canônico `http://127.0.0.1:11434`.
  - Validação rigorosa de URL (porta 1-65535, suporte a IPv6, rejeição de query strings e credenciais embutidas).
  - Healthcheck semântico via `GET /api/version` com `OllamaConfigurationError`.
- **Catálogo Dinâmico de Modelos:**
  - Consulta dinâmica ao endpoint `/api/tags` do Ollama.
  - Exclusão estrita de modelos de embedding (`nomic-embed-text:latest`) e modelos base de código (`qwen2.5-coder:1.5b-base`) da interface de chat.
  - Configuração de janela de contexto segura (`num_ctx=2048`) prevenindo estouro de memória (OOM).
- **Higiene do Contexto RAG (rag/chain.py):**
  - Implementação da função pura `formatar_documentos()` integrada ao LCEL, eliminando representações brutas de classes Python (`Document(metadata=...)`) do prompt.
- **Persistência Atômica FAISS (rag/ingest.py):**
  - Armazenamento persistente em `data/faiss_index/` acompanhado de manifesto estruturado (`manifest.json`).
  - Escrita atômica com sincronização `fsync`, travas `fcntl` (`LOCK_EX`/`LOCK_SH`) e backup funcional.
  - Validação funcional sem requisições de embedding ao Ollama via `similarity_search_by_vector()`.
  - Mecanismo não destrutivo de *Startup Recovery* e quarentena de índices corrompidos.
  - Redução do tempo de carregamento de documentos para ~38ms via cache persistente em disco.
- **Transparência e Rastreabilidade na UI (app.py):**
  - Exibição de trechos e páginas recuperadas do PDF em componente expansível (`st.expander`).
  - Botão de reindexação forçada sob demanda na barra lateral.
  - Priorização automática do modelo `llama3.1:8b` (quando disponível) conforme resultados do benchmark empírico.
- **Avaliação Sistemática e Benchmark de Qualidade (Etapa 3):**
  - Curadoria de Golden Dataset com 15 perguntas de referência (`data/golden_dataset.json`).
  - Script de avaliação automatizada (`scripts/avaliar_rag.py`).
  - *Context Hit Rate @ 3* de **91.7%** na recuperação vetorial.
  - Comprovação empírica da superioridade do `llama3.1:8b` na CPU (70.2% aderência, 100% recusa sem alucinação, 3.1x mais rápido que `qwen3.5:4b`).
  - Relatório técnico completo publicado em `docs/avaliacao-qualidade-etapa3.md`.

### 🧪 Testes e Qualidade de Código
- Suíte automatizada com 39 testes unitários e de integração cobrindo:
  - Resolução e validação de URL do Ollama (`tests/test_ollama_client.py`).
  - Formatação e composição de chain LCEL (`tests/test_chain.py`).
  - Persistência, manifesto e recuperação FAISS (`tests/test_ingest.py`).
  - Interface Streamlit e tratamento de indisponibilidade (`tests/test_app.py`).
- Configuração de linter e formatador de alto desempenho com **Ruff** (`pyproject.toml`).
- Pipeline de Integração Contínua (CI) automatizado via GitHub Actions (`.github/workflows/ci.yml`).

### 📦 Saneamento de Dependências
- Remoção definitiva da biblioteca órfã `langchain-openai`.
- Homologação de `faiss-cpu>=1.16.0` compatível com ABI3 e Python 3.14.
- Criação de `requirements-dev.txt` para ferramentas de desenvolvimento e testes.

---

## [1.0.0] — 2024-11-15

### Versão Inicial (Prova de Conceito)
- Implementação inicial de assistente RAG com Streamlit e LangChain.
- Ingestão básica de PDF em memória com FAISS.
- Resolução dinâmica de host orientada a ambiente híbrido Windows + WSL2.
- Containerização preliminar com Dockerfile e docker-compose.yml.
