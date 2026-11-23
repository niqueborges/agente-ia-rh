# Changelog — Agente IA RH

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.
O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

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
