# ADR-0002 — Catálogo Dinâmico e Separação de Modelos Ollama

- **Número:** ADR-0002
- **Título:** Catálogo Dinâmico e Separação de Modelos Ollama
- **Status:** Aprovada
- **Data de Criação:** 15/11/2026
- **Data de Atualização:** 23/11/2026 (Refinamento e Aprovação V2)
- **Data de Aprovação:** 23/11/2026

---

## Contexto

A Prova de Conceito (V1) do **agente-ia-rh** possui uma lista estática de modelos codificada diretamente em `app.py`:

```python
modelos_disponiveis = [
    "mistral:7b",
    "qwen2.5-coder:7b",
    "qwen3:4b",
    "neural-chat:7b",
    "qwen2.5-coder:1.5b",
]
```

E define `mistral:7b` como padrão em `rag/ollama_client.py`. No entanto, o hardware do ambiente de desenvolvimento é composto por um processador **Intel Core i7-1165G7 (4 núcleos / 8 threads), 16 GB de memória RAM e GPU integrada Intel Iris Xe** (sem GPU dedicada NVIDIA), executando em Ubuntu 26.04 nativo.

A inspeção real do servidor Ollama local revelou os seguintes modelos instalados no host:

- `qwen3.5:4b` (modelo com suporte a raciocínio encadeado)
- `llama3.1:8b` (modelo conversacional de 8 bilhões de parâmetros)
- `qwen2.5-coder:1.5b-base` (modelo base de completude de código)
- `nomic-embed-text:latest` (modelo especializado em geração de embeddings)

A usuária autorizou expressamente considerar a avaliação e futura instalação de modelos adicionais no Ollama que apresentem justificativa técnica para o hardware disponível e para tarefas de RAG em português do Brasil.

---

## Problema que Precisa ser Resolvido

1. **Falha Imediata por Modelo Inexistente:** O modelo padrão estático (`mistral:7b`) não existe localmente, interrompendo a execução com erro 404/not found.
2. **Insuficiência de Heurísticas Simples de Nome:** Classificar modelos baseando-se apenas em substrings no nome (como `-base`, `embed` ou `chat`) é frágil e insuficiente. A presença de um modelo retornado por `/api/tags` atesta apenas que ele está gravado no disco local, mas **não garante sua finalidade, capacidades de diálogo ou adequação para RAG corporativo**.
3. **Confusão entre Geração e Embeddings:** A aplicação não isola formalmente o ciclo de vida dos modelos. Se um modelo de embeddings fosse selecionado para chat, a inferência falharia fatalmente.
4. **Adequação ao Hardware Disponível:** Modelos executados puramente na CPU i7 com 16 GB de RAM precisam equilibrar o tempo de resposta percebido pelo usuário e a ocupação de memória do sistema operacional com a capacidade de interpretação de regras documentais.

---

## Decisão Proposta

1. **Consulta Dinâmica e Inspeção Aprofundada na API do Ollama:**
   - Consultar o endpoint `GET /api/tags` utilizando a URL base resolvida pela ADR-0001 para identificar os modelos instalados.
   - Quando necessário para desambiguação de capacidades, consultar `POST /api/show` para inspecionar os parâmetros do modelo, template de prompt, família e capacidades arquiteturais declaradas (`capabilities`).
2. **Classificação e Filtragem Sem Dependência Cega de Nomes:**
   - Reconhecer que a presença na lista do Ollama não implica aptidão para chat instrucional.
   - Modelos cujos metadados indiquem finalidade exclusiva de embedding são compulsoriamente excluídos do seletor de geração.
   - Variantes cuja arquitetura seja de modelo base (completude bruta de texto) não devem ser recomendadas automaticamente para diálogo instrucional.
   - Permitir a definição de uma lista explícita de modelos homologados/permitidos para chat (`CHAT_MODELS_ALLOWED`), garantindo que apenas modelos validados em língua portuguesa e instruções sejam apresentados ao colaborador.
3. **Separação Estrita entre Embeddings e Geração:**
   - **Modelo de Embeddings:** Configuração independente e isolada. Mantém-se provisoriamente o candidato inicial `nomic-embed-text:latest` (ou via variável `OLLAMA_EMBED_MODEL`), verificado separadamente quanto à sua disponibilidade no servidor.
   - **Modelo de Geração (Chat):** Selecionado de forma independente na interface. A troca de modelo de chat na barra lateral recria apenas o cliente LLM, **sem reinvocar a leitura do PDF nem recalcular embeddings vetoriais**.
4. **Candidatos Iniciais Provisórios no Host:**
   - Manter **`qwen3.5:4b`** como modelo de chat padrão provisório para os testes iniciais da V2, por estar disponível no host e possuir tamanho intermediário (4.2B parâmetros).
   - Manter **`llama3.1:8b`** como alternativa de comparação de maior contagem de parâmetros (8B).
   - *Nota de Governança:* Nenhuma dessas duas opções constitui decisão definitiva ou requisito permanente; a seleção final dependerá de avaliação empírica na Etapa 3.
5. **Tratamento Resiliente de Cenários de Falha:**
   - *API Indisponível:* Exibir aviso estruturado na interface (`st.warning`/`st.error`), orientando verificar o serviço (`systemctl status ollama`), bloqueando o chat sem gerar exceções não tratadas. Nunca apresentar modelos fictícios como detectados.
   - *Resposta Inválida:* Tratar exceções de decodificação JSON sem expor tracebacks de sistema.
   - *Nenhum Modelo de Chat Adequado:* Apresentar mensagem orientativa indicando o comando exato para download do modelo recomendado.
   - *Modelo de Embeddings Ausente:* Bloquear o carregamento documental e informar expressamente o comando necessário para baixar o modelo de vetorização.

---

## Avaliação de Modelos Candidatos para o Hardware

Considerando o processador Intel Core i7-1165G7 (4 núcleos / 8 threads), 16 GB de RAM e ausência de GPU dedicada, foram identificados modelos candidatos com justificativa técnica para tarefas de RAG.

> **Importante:**
> - Nenhum modelo foi baixado nesta tarefa.
> - As opções abaixo constituem **candidatos sob hipótese**, não decisões aprovadas ou definitivas.
> - **Desempenho medido:** Não há medições de tokens/s executadas neste equipamento; taxas de transferência serão aferidas em testes práticos controlados na Etapa 3.
> - **Qualidade observada:** A aderência às políticas de RH e a qualidade em português dependem de avaliação prática com perguntas de referência e gabarito (*golden dataset*).

### Modelos de Geração (Chat / RAG)

| Modelo no Ollama | Finalidade | Download Aprox. | Memória Estimada | Desempenho Medido no Hardware | Qualidade Observada no Projeto | Hipóteses Técnicas a Validar | Comando `ollama pull` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`llama3.2:3b`** | Chat / RAG | ~2.0 GB | ~2.8 a 3.2 GB | Não medido neste equipamento | Pendente de avaliação com o PDF de RH | **Hipótese favorável:** Treinamento multilíngue oficial documentado pela Meta (incluindo português); tamanho reduzido (3.2B) tende a demandar menor tempo de computação por token na CPU.<br/>**Hipótese de limitação:** Menor capacidade analítica para interpretar exceções contratuais complexas. | `ollama pull llama3.2:3b` |
| **`qwen2.5:7b`** | Chat / RAG | ~4.7 GB | ~5.5 a 6.5 GB | Não medido neste equipamento | Pendente de avaliação com o PDF de RH | **Hipótese favorável:** Documentação técnica da família Qwen relata especialização em seguimento estrito de instruções e suporte multilíngue abrangente; quantização Q4 cabe na RAM de 16 GB.<br/>**Hipótese de limitação:** Tempo de inferência em CPU pura tende a ser perceptivelmente superior a modelos de 3B/4B. | `ollama pull qwen2.5:7b` |
| **`qwen3.5:4b`** *(Instalado)* | Chat / RAG | ~3.3 GB | ~3.5 a 4.0 GB | Não medido neste equipamento | Pendente de avaliação com o PDF de RH | **Hipótese favorável:** Modelo moderno de escala intermediária com suporte nativo a etapas de raciocínio.<br/>**Hipótese de limitação:** Estabilidade na geração de respostas estruturadas em português ainda a avaliar no domínio de RH. | Já disponível no host |
| **`llama3.1:8b`** *(Instalado)* | Chat / RAG | ~4.9 GB | ~5.5 a 6.0 GB | Não medido neste equipamento | Pendente de avaliação com o PDF de RH | **Hipótese favorável:** Ampla maturidade de mercado e vocabulário extenso.<br/>**Hipótese de limitação:** Modelo de 8 bilhões de parâmetros executado em 4 núcleos de CPU pode apresentar latência elevada para uso interativo. | Já disponível no host |

### Modelos de Embeddings (Vetorização para FAISS)

| Modelo no Ollama | Finalidade | Download Aprox. | Memória Estimada | Desempenho Medido no Hardware | Qualidade Observada no Projeto | Hipóteses Técnicas a Validar | Comando `ollama pull` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`nomic-embed-text:latest`** *(Instalado)* | Embeddings FAISS | ~274 MB | ~0.5 GB | Não medido neste equipamento | Pendente de avaliação comparativa | **Hipótese favorável:** Modelo leve (137M parâmetros), dimensão 768, vetorização rápida com baixo consumo de RAM.<br/>**Hipótese de limitação:** Treinamento predominantemente em língua inglesa pode apresentar menor poder de discriminação semântica em termos jurídicos/trabalhistas brasileiros. | Já disponível no host |
| **`bge-m3:latest`** | Embeddings FAISS | ~1.2 GB | ~1.5 GB | Não medido neste equipamento | Pendente de avaliação comparativa | **Hipótese favorável:** Documentação acadêmica (BAAI) atesta arquitetura multilíngue nativa com suporte a mais de 100 idiomas (incluindo português), dimensão 1024 e janela de 8192 tokens.<br/>**Hipótese de limitação:** Dimensão vetorial maior (1024 vs 768) eleva o consumo de memória do índice FAISS e o tempo de vetorização por fatia. | `ollama pull bge-m3` |

---

## Metodologia para Avaliação Futura (Etapa 3)

A seleção definitiva dos modelos para a V2 não será baseada em percepções subjetivas ou popularidade, mas em um protocolo estruturado na Etapa 3:

1. **Conjunto de Perguntas Representativas:** Curadoria de 15 a 20 perguntas em português baseadas nas políticas da Nexus Tecnologia S.A. (férias, jornada, home office, licenças e reembolsos).
2. **Critérios de Geração:**
   - *Fidelidade ao Contexto (Faithfulness):* Ausência de afirmações não fundamentadas nos trechos recuperados.
   - *Compreensão do Português:* Correção gramatical, clareza e estrutura da resposta.
   - *Aderência a Recusas:* Capacidade de informar com clareza quando uma informação não consta no documento.
3. **Critérios Operacionais no Hardware:**
   - *Latência Total:* Tempo até o primeiro token (*Time-to-First-Token*) e tempo total de geração na CPU Intel i7.
   - *Consumo de Memória:* Monitoramento da memória residente (RSS) durante a inferência concorrente.
4. **Critérios de Recuperação (para Embeddings):**
   - *Context Recall:* Percentual de perguntas em que o artigo correto da política foi recuperado entre os top-$k$ trechos.

---

## Alternativas Consideradas

1. **Classificação Exclusiva por Nome de Arquivo/Tag:**
   - *Motivo da Rejeição:* Sufixos como `-coder` ou `-base` não cobrem todos os modelos de terceiros e podem classificar erroneamente modelos afinados pela comunidade.
2. **Uso Indiferenciado de Qualquer Modelo Instalado:**
   - *Motivo da Rejeição:* Expor modelos não alinhados para instrução gera respostas desconexas e quebra a experiência do usuário de RH.

---

## Justificativa Técnica

A combinação de consulta a `/api/tags`, inspeção complementar com `/api/show` e controle por lista explícita de modelos permitidos assegura governança operacional. O projeto mantém a flexibilidade para avaliar modelos com melhor relação entre fidelidade em português e velocidade na CPU, sem antecipar conclusões que dependem de testes no equipamento.

---

## Consequências

### Positivas
- Elimina falhas de execução por modelos ausentes.
- Separa formalmente o modelo de embeddings do seletor de chat.
- Não expõe modelos incompatíveis com diálogo instrucional.
- Documenta candidatos fundamentados tecnicamente para avaliação futura autorizada (`llama3.2:3b`, `qwen2.5:7b`, `bge-m3`).

### Negativas ou Limitações
- Chamadas a `/api/show` adicionam pequena latência de inspeção na inicialização (mitigada com cache em nível de aplicação).

---

## Critérios de Validação

1. **Descoberta Real:** Modelos instalados no Ollama são detectados dinamicamente na inicialização.
2. **Exclusão de Embeddings do Chat:** O modelo `nomic-embed-text` (ou `bge-m3`) jamais aparece no seletor de LLMs de chat.
3. **Resiliência a Falhas:** Desligar o Ollama exibe notificação amigável na UI sem quebrar a aplicação.
4. **Independência de Geração e Vetores:** A seleção de um novo modelo de chat altera apenas o LLM sem disparar reindexação vetorial.
5. **Cobertura de Testes:** Testes unitários com mocks cobrindo os cenários de detecção, filtragem e tratamento de erros em `tests/unit/test_model_catalog.py`.

---

## Referências

- **ADR-0001:** Fornece a URL base para conexão na API do Ollama.
- **ADR-0004:** O modelo de embeddings aqui isolado é validado no manifesto do índice FAISS.
