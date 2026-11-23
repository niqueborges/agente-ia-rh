# Relatório de Avaliação Sistemática e Benchmark de RAG (Etapa 3)

**Data:** 23 de Novembro de 2026  
**Ambiente:** Ubuntu 26.04 LTS nativo | Intel® Core™ i7-1165G7 (4c/8t) | 16 GB RAM (CPU-only inference)  
**Banco Vetorial:** FAISS persistente (`data/faiss_index/`, 45 chunks, dimensão 768)  
**Modelo de Embeddings:** `nomic-embed-text:latest`  
**Modelos Avaliados:** `qwen3.5:4b` vs `llama3.1:8b` (Ollama 0.40.16)

---

## 1. Metodologia e Golden Dataset

Para a realização da **Etapa 3**, foi elaborado um conjunto curado de perguntas de referência (*golden dataset*) composto por **15 casos de teste** estruturados em `data/golden_dataset.json`:

- **12 Perguntas Positivas:** Cobrindo todos os 10 capítulos do Manual de Políticas Internas da Nexus Tecnologia S.A. (jornada, benefícios, férias, reembolsos, conduta, segurança da informação, capacitação, saúde ocupacional e desligamento), com páginas esperadas e gabarito formal de palavras-chave.
- **3 Perguntas de Controle Negativo (Out-of-Scope):** Perguntas sobre temas não previstos no documento (auxílio-pet, empréstimo consignado corporativo e veículo corporativo para fins de semana), desenhadas especificamente para avaliar a capacidade do modelo de **recusar responder** sem alucinar.

---

## 2. Resultados Consolidados do Benchmark

O teste foi executado através do script automatizado `scripts/avaliar_rag.py` com temperatura $T=0.0$ e janela de contexto controlada (`num_ctx=2048`).

| Métrica Avaliada | `qwen3.5:4b` | `llama3.1:8b` (num_ctx=2048) | Diagnóstico e Impacto Arquitetural |
| :--- | :--- | :--- | :--- |
| **Context Hit Rate @ 3** | **91.7%** (11/12) | **91.7%** (11/12) | A busca vetorial densa com `nomic-embed-text` localizou a página correta no top-3 em mais de 91% das consultas. |
| **Aderência ao Gabarito** | **38.9%** | **70.2%** | O `llama3.1:8b` capturou substancialmente mais detalhes factuais, valores monetários e prazos definidos na política. |
| **Taxa de Recusa Correta** | **0.0%** (emitiu resposta vazia) | **100.0%** (3/3 recusas claras) | O `llama3.1:8b` declarou expressamente *"não encontrei nenhuma informação nas políticas internas"*, sem alucinar. |
| **Tempo Médio de Resposta** | **163.4 s** (~2.7 min) | **51.5 s** (~0.8 min) | O `llama3.1:8b` foi **3.1 vezes mais rápido** na CPU por não gerar tokens de raciocínio intermediário (`<think>`). |
| **Throughput de Tokens (CPU)** | **0.2 tok/s** (texto final) | **1.6 tok/s** | Vazão de texto em linguagem natural significativamente superior no `llama3.1:8b`. |
| **Consumo de Memória e Estabilidade** | Estável (~3.8 GB) | Exige `num_ctx=2048` | Com a janela padrão de 128k, o `llama3.1:8b` causou OOM-kill; com `num_ctx=2048`, operou com 100% de estabilidade na RAM de 16 GB. |

---

## 3. Análise Qualitativa e Descobertas Críticas

### 3.1. Eficiência da Recuperação Vetorial (*Retrieval*)
- **Desempenho:** A taxa de acerto de **91.7%** comprova que o particionamento textual de 1000 caracteres com sobreposição de 200 caracteres (`chunk_size=1000`, `chunk_overlap=200`) e a vetorização com `nomic-embed-text:latest` são altamente eficientes para a base de políticas de RH.
- **Decisão sobre Busca Híbrida (BM25):** Como a taxa de recuperação pura já atingiu 91.7%, a introdução de busca híbrida (BM25) ou de rerankers pesados (como Cross-Encoders) **não se justifica no momento**, pois aumentaria a latência na CPU sem ganho perceptível para o usuário final.

### 3.2. Comparação Empírica entre os Modelos
1. **`llama3.1:8b` (Vencedor em Fidelidade e Usabilidade):**
   - Respostas completas, gramaticalmente polidas e com excelente estruturação em tópicos.
   - Excelente comportamento em perguntas negativas: recusou com precisão cirúrgica sem inventar regras fictícias.
   - Tempo de resposta viável para CPU (média de ~51s por pergunta).
2. **`qwen3.5:4b` (Limitações na CPU):**
   - Modelo com arquitetura de raciocínio encadeado (*thinking model*). Na CPU sem aceleração gráfica, o tempo de inferência é penalizado pelo processamento dos passos de raciocínio ocultos, levando quase 3 minutos por resposta.
   - Em perguntas negativas, o modelo gastou o orçamento de geração no bloco de raciocínio e retornou texto vazio para o usuário, demonstrando menor previsibilidade no contexto de RAG factual simples.

---

## 4. Recomendações Técnicas para a Aplicação

1. **Janela de Contexto Limitada (`num_ctx=2048`):**
   - Manter a configuração de `num_ctx=2048` como padrão no conector Ollama (`rag/ollama_client.py`), prevenindo estouro de memória (OOM) no host de 16 GB de RAM.
2. **Configuração de Modelo Padrão:**
   - Adotar **`llama3.1:8b`** como modelo preferencial de geração na interface do Streamlit quando disponível, mantendo `qwen3.5:4b` como alternativa secundária.
