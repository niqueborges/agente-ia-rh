# 💼 Assistente de RH com IA (RAG Local & Privado)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-red.svg)](https://streamlit.io/)
[![LangChain](https://img.shields.io/badge/LangChain-LCEL-green.svg)](https://www.langchain.com/)
[![FAISS](https://img.shields.io/badge/FAISS-VectorStore-orange.svg)](https://github.com/facebookresearch/faiss)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-black.svg)](https://ollama.com/)

Assistente inteligente de Recursos Humanos para consulta de políticas internas corporativas (férias, benefícios, jornada de trabalho e conduta), desenvolvido com a arquitetura **RAG (Retrieval-Augmented Generation)**.

A aplicação opera **100% localmente e com privacidade total**, garantindo que nenhum dado sensível da empresa seja transmitido para APIs de terceiros.

---

## 📖 Evolução do Projeto

O projeto não nasceu como uma versão estática, mas passou por um ciclo real de engenharia e refatoração:

```text
OpenAI (PoC inicial com gpt-4o-mini + text-embedding-3-small)
  │
  ▼
Dependência e esgotamento de cota de API externa
  │
  ▼
Migração para IA Local (Ollama: nomic-embed-text + Mistral/Qwen)
  │
  ▼
Ambiente Híbrido de Desenvolvimento (Windows Host + WSL2 Ubuntu)
  │
  ▼
Detecção Dinâmica de Host via Socket (obter_url_ollama)
  │
  ▼
Modularização da Arquitetura (rag/ package + app.py UI)
  │
  ▼
Containerização e Orquestração (Dockerfile + Docker Compose)
  │
  ▼
Documentação de Decisões de Engenharia e Topologias
```

1. **Prova de Conceito Inicial (OpenAI):** O protótipo inicial utilizava APIs da OpenAI (`text-embedding-3-small` e `gpt-4o-mini`) em um script único.
2. **Transição para IA Local (Ollama):** Diante da dependência de cotas pagas e buscando total privacidade de dados, o pipeline foi adaptado para **Ollama** (`nomic-embed-text` para embeddings e modelos como `mistral:7b`, `qwen2.5-coder` e `qwen3` para geração).
3. **Modularização e Engenharia de Produção:** O código foi desacoplado em módulos independentes (`rag/` para lógica de negócio e `app.py` estritamente para interface Streamlit), com detecção dinâmica de ambiente de rede (WSL/Docker) e containerização.

---

## 🏛️ Arquitetura do Pipeline RAG

```mermaid
flowchart TD
    subgraph Ingestao["1. Ingestão e Vetorização (Cache @st.cache_resource)"]
        PDF["📄 Documento de Políticas (PDF)"] --> Splitter["✂️ RecursiveCharacterTextSplitter<br/>(chunk: 1000, overlap: 200)"]
        Splitter --> Chunks["📦 Blocos de Texto"]
        Chunks --> Embeddings["🧠 nomic-embed-text<br/>(Ollama Embeddings)"]
        Embeddings --> FAISS_DB[("🗄️ Banco Vetorial FAISS<br/>(Índice em Memória)")]
    end

    subgraph Consulta["2. Consulta e Recuperação RAG"]
        User(["👤 Colaborador"]) -->|Digita Pergunta| UI["💻 Interface Streamlit (app.py)"]
        UI --> Retriever["🔍 FAISS Retriever (k=3)"]
        FAISS_DB -.->|Busca Semântica| Retriever
        Retriever --> Contexto["📑 Trechos Relevantes"]
    end

    subgraph Geracao["3. Orquestração e Geração"]
        Contexto --> Prompt["📝 ChatPromptTemplate (LCEL)"]
        UI -.->|Pergunta| Prompt
        Prompt --> LLM["🤖 ChatOllama<br/>(Mistral / Qwen / Llama)"]
        LLM -->|Streaming de Tokens| StreamOutput["⚡ st.write_stream"]
        StreamOutput --> User
    end
```

---

## 🖥️ Topologia de Execução: Desenvolvimento vs Produção

### Ambiente Real de Desenvolvimento (Windows Host + WSL2)

No cenário de desenvolvimento, o servidor Ollama executa no Windows (aproveitando aceleração de hardware) enquanto a aplicação Python roda no subsistema Linux (WSL2):

```text
┌──────────────────────────────────────────────┐
│                Windows Host                  │
│                                              │
│               Servidor Ollama                │
│             http://localhost:11434           │
└──────────────────────┬───────────────────────┘
                       │
             Rede Virtual WSL2 / Gateway
                       │
┌──────────────────────▼───────────────────────┐
│                 WSL2: Ubuntu                 │
│                                              │
│  app.py (Streamlit UI)                       │
│     └── rag/                                 │
│          ├── ollama_client.py (Host Resolver)│
│          ├── ingest.py (PyPDF + FAISS)       │
│          └── chain.py (LangChain LCEL)       │
└──────────────────────────────────────────────┘
```

### Arquitetura Alvo em Produção Corporativa

Para um ambiente corporativo real, a aplicação não é exposta diretamente na porta 8501, mas sim protegida por camadas de segurança de rede e identidade:

```text
[ Colaborador ]
       │ (HTTPS / VPN Corporativa)
       ▼
[ Reverse Proxy / Ingress (Nginx / Traefik) ] ─── [ SSO / OIDC (Microsoft Entra / Okta) ]
       │
       ▼
[ Container Streamlit (app.py + rag) ]
       ├── [ Banco Vetorial (FAISS / PgVector) ]
       └── [ Servidor de Inferência Dedicado (Ollama / vLLM com GPU corporativa) ]
```

---

## ⚖️ Decisões de Engenharia e Arquitetura

| Decisão Técnica | Implementação | Motivo / Impacto |
| :--- | :--- | :--- |
| **Separação UI vs RAG** | `app.py` + pacote `rag/` | Desacopla a camada de apresentação Streamlit da lógica de processamento e recuperação de dados. |
| **Otimização de Cache** | `@st.cache_resource` | Evita a releitura do PDF e a regeneração de embeddings a cada interação ou re-execução do Streamlit. |
| **Banco Vetorial em Memória** | `FAISS (faiss-cpu)` | Busca vetorial semântica de altíssima velocidade sem a necessidade de infraestrutura pesada de banco externo. |
| **Filtro de Relevância ($k=3$)** | `as_retriever(k=3)` | Balanço ideal entre contexto suficiente e economia da janela de contexto da LLM, reduzindo alucinações. |
| **Baixa Latência Percebida** | `chain.stream()` + `st.write_stream` | Streaming de resposta token a token, entregando feedback imediato ao usuário (baixo Time-To-First-Token). |
| **Portabilidade de Ambiente** | `obter_url_ollama()` via socket | Resolução de rede não-bloqueante (0.3s timeout) compatível com Linux nativo, Docker e WSL2. |
| **Desacoplamento do Pipeline** | LangChain Expression Language (LCEL) | Facilita a substituição transparente de componentes (LLMs, prompts e retrievers). |

---

## 📁 Estrutura Modular do Projeto

```text
agente-ia-rh/
├── app.py                      # Interface de usuário interativa (Streamlit)
├── rag/                        # Módulo central de RAG (Lógica de Negócio)
│   ├── __init__.py             # Exportações públicas do pacote
│   ├── ollama_client.py        # Conector Ollama e resolução dinâmica de host
│   ├── ingest.py               # Extração de texto, chunking e indexação FAISS
│   └── chain.py                # Composição da chain RAG com LCEL
├── data/
│   └── politica_rh_exemplo.pdf # Documento fictício para demonstração
├── Dockerfile                  # Imagem de produção containerizada
├── docker-compose.yml          # Orquestração do serviço
├── .env.example                # Template documentado de variáveis de ambiente
├── .gitignore                  # Exclusão de caches, ambientes e segredos
├── requirements.txt            # Dependências fixadas do projeto
└── README.md                   # Documentação arquitetural e técnica
```

---

## 🚀 Como Executar

### 1. Pré-requisitos
- **Python 3.10+**
- **Ollama** instalado e em execução ([Download Ollama](https://ollama.com/download))

Baixe os modelos necessários no Ollama:
```bash
# Modelo de Embeddings (obrigatório)
ollama pull nomic-embed-text

# Modelos de Linguagem (baixe um ou mais)
ollama pull mistral:7b
ollama pull qwen2.5-coder:7b
ollama pull qwen3:4b
```

---

### Opção A: Execução Local com Python Virtualenv

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/niqueborges/agente-ia-rh.git
   cd agente-ia-rh
   ```

2. **Crie e ative o ambiente virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # No Windows: .venv\Scripts\activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Inicie a aplicação:**
   ```bash
   streamlit run app.py
   ```

---

### Opção B: Execução via Docker Compose

Caso prefira rodar a aplicação em container:

```bash
docker compose up --build
```

Acesse a interface no navegador: `http://localhost:8501`.

---

## 🔒 Nota de Confidencialidade e Dados Fictícios

> [!NOTE]
> O arquivo [`data/politica_rh_exemplo.pdf`](data/politica_rh_exemplo.pdf) incluído neste repositório contém **dados e regras fictícias**, gerado exclusivamente para fins didáticos e demonstração do pipeline RAG, em conformidade com as diretrizes de privacidade e LGPD.

---

## 📌 Limitações Conhecidas e Próximos Passos

Como parte das boas práticas de engenharia de software, o escopo atual está delimitado como um protótipo funcional e modular. As seguintes oportunidades de evolução técnica e avaliação sistemática foram mapeadas como próximas fronteiras:

### 1. Avaliação Sistemática de RAG (Qualidade e Confiabilidade)
Em vez de depender apenas de validações manuais, a evolução natural para ambientes críticos envolve:
- **Golden Dataset & Testes de Regressão:** Criação de um conjunto curado de perguntas, contextos esperados e gabaritos de resposta.
- **Métricas de Recuperação (*Retrieval*):**
  - *Context Precision:* Avaliar se os trechos recuperados pelo FAISS são estritamente relevantes para a consulta.
  - *Context Recall:* Avaliar se todas as informações necessárias para responder à pergunta foram devidamente recuperadas.
- **Métricas de Geração:**
  - *Faithfulness (Fidelidade):* Medir se a resposta gerada pela LLM está 100% ancorada no contexto recuperado, eliminando alucinações.
  - *Answer Correctness:* Comparar a resposta produzida com a resposta de referência do gabarito.
- **Casos Negativos (Ausência de Contexto):** Testar sistematicamente perguntas sobre tópicos inexistentes no documento para validar se o modelo responde estritamente que a informação não foi encontrada.

### 2. Infraestrutura e Persistência
- [ ] **Persistência de Índice Vetorial:** Persistir os índices FAISS em disco ou migrar para bancos vetoriais gerenciados (Chroma / PgVector / Qdrant) para bases com múltiplos documentos.
- [ ] **Filtros por Metadados:** Permitir segmentação por departamento (ex: políticas de RH vs TI vs Financeiro).
- [ ] **Autenticação Corporativa (SSO):** Integração com OpenID Connect (OIDC) / Microsoft Entra ID para controle de acesso baseado em perfis (RBAC).

---

## 🎯 Síntese

O projeto foi estruturado com foco em modularidade, execução local, reprodutibilidade do ambiente e separação clara entre interface, ingestão, recuperação e geração. A arquitetura evita dependência de APIs externas de IA durante a execução e documenta caminhos claros de evolução para um cenário corporativo privado.
