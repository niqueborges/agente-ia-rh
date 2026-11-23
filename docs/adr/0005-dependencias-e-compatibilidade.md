# ADR-0005 — Governança de Dependências e Compatibilidade

- **Número:** ADR-0005
- **Título:** Governança de Dependências e Compatibilidade
- **Status:** Aprovada
- **Data de Criação:** 15/11/2026
- **Data de Atualização:** 23/11/2026 (Refinamento e Aprovação V2)
- **Data de Aprovação:** 23/11/2026

---

## Contexto

O arquivo `requirements.txt` atual do projeto declara nove dependências sem fixação ou restrição de versões:

```text
streamlit
langchain
langchain-community
langchain-openai
langchain-text-splitters
langchain-ollama
faiss-cpu
pypdf
python-dotenv
```

O `README.md` (linha 156) afirma erroneamente que o arquivo contém *"Dependências fixadas do projeto"*. Na prática, qualquer nova instalação com `pip install -r requirements.txt` baixa as versões mais recentes disponíveis no PyPI no momento da execução, expondo o projeto a quebras por mudanças de API (*breaking changes*).

Além disso:
- O pacote `langchain-openai` não possui nenhuma importação ou uso no código ativo de `app.py` e `rag/`.
- O interpretador padrão no host Ubuntu 26.04 nativo é o **Python 3.14.4**, enquanto a imagem Docker utiliza **Python 3.11-slim**.
- Componentes modernos da interface (`submit_mode="disable"` no chat input e `width="stretch"` no botão) exigem versões recentes do Streamlit (>= 1.59.0), gerando conflito com a informação do badge do README (`Streamlit-1.40+`).

---

## Problema que Precisa ser Resolvido

1. **Risco de Quebra por Atualizações Não Controladas:** A ausência de pinagem ou faixas de compatibilidade permite a instalação de versões incompatíveis de bibliotecas em rápida evolução (ecossistema LangChain e Streamlit).
2. **Dependência Órfã:** A presença de `langchain-openai` adiciona tempo de instalação e superfície de dependências desnecessárias para um projeto 100% local com Ollama.
3. **Incerteza sobre Python 3.14:** O suporte do `faiss-cpu` e extensões binárias de C++ no interpretador Python 3.14 precisa ser formalmente testado antes de ser considerado homologado.

---

## Decisão Proposta

1. **Estratégia de Execução Principal:** Definir a execução nativa no Ubuntu com ambiente virtual isolado (`.venv`) como **caminho principal e prioritário** de desenvolvimento e validação.
2. **Docker como Alternativa Secundária:** Manter `Dockerfile` e `docker-compose.yml` como empacotamento secundário, com validação e documentação dedicadas, sem que questões de rede do Docker bloqueiem a evolução nativa.
3. **Status da Matriz: Hipótese a Ser Validada:** Tratar a matriz de dependências estritamente como uma **hipótese técnica** até que uma instalação limpa em `.venv` e a execução da suíte de testes confirmem a ausência de conflitos. Não inventar pinagens arbitrárias.
4. **Matriz Candidata Completa:**

   | Dependência | Papel no Projeto | Avaliação e Condição |
   | :--- | :--- | :--- |
   | **python** | Runtime | Validar `3.14.x` no host e `3.11.x` no Docker. |
   | **streamlit** | Interface de Usuário | Versão candidata `>= 1.59.0` para suportar `submit_mode="disable"`. |
   | **langchain** | Metapacote Agregador | Manter como hipótese candidata; avaliar se pacotes especializados abaixo bastam. |
   | **langchain-core** | Interfaces LCEL | Obrigatório (Prompts, Runnables, Parsers). |
   | **langchain-community** | Integrações | Obrigatório para wrapper `FAISS` e `PyPDFLoader`. |
   | **langchain-ollama** | Integração Ollama | Obrigatório para `ChatOllama` e `OllamaEmbeddings`. |
   | **langchain-text-splitters**| Fatiamento | Obrigatório para particionamento de texto. |
   | **faiss-cpu** | Mecanismo Vetorial | Versão `>= 1.16.0` (fornece wheel `cp310-abi3`). |
   | **pypdf** | Leitura de PDF | Obrigatório para ingestão de documentos. |
   | **python-dotenv** | Configuração | Conveniência para variáveis de ambiente locais. |
   | **pytest** *(dev)* | Automação de Testes | Dependência de desenvolvimento para a suíte unitária. |

5. **Uso de Mocks com Biblioteca Padrão:** Não adicionar `pytest-mock` inicialmente. A suíte de testes unitários utilizará o módulo nativo `unittest.mock` da biblioteca padrão do Python, mantendo o ambiente mais enxuto.
6. **Remoção Condicionada de `langchain-openai`:** A remoção de `langchain-openai` permanece recomendada, mas deve ser confirmada formalmente mediante validação de imports e verificação de dependências transitórias no momento do teste da matriz.
7. **Integração Contínua (CI):**
   - Propor para a Etapa 1 a criação de workflow em GitHub Actions rodando linting com **Ruff** e testes unitários com **pytest**.
   - Avaliar a matriz de teste cobrindo Python 3.11 e Python 3.14.
   - O arquivo do workflow não deve ser criado nesta tarefa de documentação.

---

## Procedimento de Validação Prática da Hipótese

A validação da matriz de dependências seguirá o seguinte protocolo em 7 passos:

1. Criar ambiente virtual limpo: `python3 -m venv .venv_validacao`.
2. Instalar o conjunto candidato de dependências.
3. Executar `pip check` para verificar que não há incompatibilidades de versão declaradas entre pacotes.
4. Executar verificação de imports dos módulos reais do projeto (`rag` e `app`).
5. Executar teste do ciclo de vida completo do FAISS (criação, persistência com manifesto, recarga e consulta).
6. Rodar os testes automatizados da suíte.
7. Repetir as etapas nos ambientes Python definidos (Python 3.14 nativo e Python 3.11 no container).

---

## Alternativas Consideradas

1. **Pinar Todas as Dependências Arbitrariamente Agora:**
   - *Motivo da Rejeição:* Viola a metodologia de validação empírica. Pinar versões sem teste real de instalação em ambiente isolado pode introduzir conflitos que bloqueiem a instalação.
2. **Adicionar Imediatamente Frameworks de API (FastAPI) ou Agentes (LangGraph):**
   - *Motivo da Rejeição:* Injustificado. Aumenta desnecessariamente a árvore de dependências e a complexidade arquitetural sem demanda funcional fundamentada.

---

## Justificativa Técnica

Tratar a governança de dependências através de uma hipótese testável assegura estabilidade, reprodutibilidade em novos ambientes e conformidade com a realidade do sistema operacional do desenvolvedor (Ubuntu 26.04).

---

## Consequências

### Positivas
- Elimina surpresas e quebras silenciosas provocadas por releases externas do PyPI.
- Remove pacotes mortos e desnecessários (`langchain-openai`).
- Estabelece uma base de qualidade profissional com `pytest` e `Ruff`.
- Sincroniza a documentação pública com o comportamento real da aplicação.

### Negativas ou Limitações
- Exige disciplina contínua de atualização periódica e teste de regressão antes de atualizar dependências pinadas.

---

## Riscos

- **Comportamento da ABI3 do FAISS sob Python 3.14:**
  Embora o wheel `cp310-abi3-manylinux_2_28_x86_64` seja compatível, a ausência de segfaults sob carga pesada precisa ser atestada pelo teste prático do procedimento de validação.

---

## Critérios de Validação

1. **Ambiente Limpo:** Conclusão bem-sucedida do procedimento de validação em 7 passos no `.venv`.
2. **pip check 100% Limpo:** Nenhum conflito de dependências relatado pela ferramenta.
3. **Ausência de Erros de Importação:** Todos os módulos de `rag/` e `app.py` importam sem advertências críticas de obsolescência imediata.
4. **Alinhamento do README:** O arquivo `README.md` deve refletir estritamente as versões testadas (`streamlit>=1.59.0` e faixas validadas).

---

## Referências

- **ADR-0001 a ADR-0004:** Todas as decisões dependem da estabilidade desta matriz de execução para operarem sem erros de runtime.
