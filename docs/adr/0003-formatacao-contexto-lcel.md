# ADR-0003 — Formatação Estrita do Contexto na Chain LCEL

- **Número:** ADR-0003
- **Título:** Formatação Estrita do Contexto na Chain LCEL
- **Status:** Aprovada
- **Data de Criação:** 15/11/2026
- **Data de Atualização:** 23/11/2026 (Refinamento e Aprovação V2)
- **Data de Aprovação:** 23/11/2026

---

## Contexto

A orquestração do pipeline RAG do projeto utiliza **LangChain Expression Language (LCEL)** no módulo `rag/chain.py`. O fluxo atual está montado da seguinte forma:

```python
prompt_template = ChatPromptTemplate.from_template(PROMPT_SISTEMA_RH)
buscador_contexto = banco_vetores.as_retriever(search_kwargs={"k": k_documentos})

chain = (
    {"context": buscador_contexto, "question": RunnablePassthrough()}
    | prompt_template
    | llm
    | StrOutputParser()
)
```

No ecossistema LangChain, o método `as_retriever()` retorna um objeto `List[Document]`, onde cada item possui atributos como `page_content` e o dicionário `metadata`.

---

## Problema que Precisa ser Resolvido

1. **Vazamento de Sintaxe de Classes Python no Prompt:** Como não existe uma função intermediária de transformação de tipo entre `buscador_contexto` e `prompt_template`, o formatador de string do Python interpola diretamente o `repr()` da lista de objetos:
   ```text
   Contexto:
   [Document(metadata={'page': 0, 'source': 'data/politica_rh_exemplo.pdf'}, page_content='MANUAL DE POLÍTICAS INTERNAS...'), Document(...)]
   ```
2. **Desperdício de Janela de Contexto e Tokens:** Metadados estruturais, aspas e a sintaxe de instâncias `Document` consomem tokens preciosos da janela de contexto.
3. **Degradação de Foco do Modelo:** Modelos locais de menor porte (como 4B e 8B) podem se confundir com a presença de sintaxe de programação dentro do bloco de texto rotulado como "Contexto", gerando respostas mal formatadas ou citando a estrutura do objeto Python na resposta final.

---

## Decisão Proposta

1. **Implementação de Função Pura de Formatação:** Criar uma função isolada, determinística e facilmente testável para processar os documentos recuperados:

   ```python
   def formatar_documentos(documentos: list[Document]) -> str:
       """
       Extrai o texto dos documentos recuperados e os concatena com espaçamento padronizado.
       Trata listas vazias retornando string informativa limpa.
       """
       if not documentos:
           return "Nenhum trecho relevante encontrado nas políticas internas."
       return "\n\n".join(documento.page_content.strip() for documento in documentos)
   ```

2. **Integração na Composição LCEL:** Aplicar a transformação no pipeline antes da entrada no prompt:

   ```python
   chain = (
       {
           "context": buscador_contexto | formatar_documentos,
           "question": RunnablePassthrough(),
       }
       | prompt_template
       | llm
       | StrOutputParser()
   )
   ```

---

## Alternativas Consideradas

1. **Passagem Direta sem Formatação (Situação Atual):**
   - *Motivo da Rejeição:* Gera poluição sintática comprovada no prompt.
2. **Inclusão de Cabeçalhos de Página no Texto do Contexto:**
   - *Descrição:* Formatar como `[Página X]: {page_content}` diretamente no bloco de contexto enviado ao LLM.
   - *Motivo da Rejeição:* Embora ajude na citação, consome tokens adicionais e pode induzir alucinações de formatação. A rastreabilidade de páginas deve ser tratada como canal paralelo de metadados na UI (ver ADR-0004 e Etapa 2).

---

## Justificativa Técnica

A separação de responsabilidades assegura que o modelo de linguagem receba estritamente linguagem natural no campo `{context}`. Isso maximiza a eficiência da janela de contexto e melhora a clareza e estrutura das respostas geradas pelo ChatOllama.

---

## Consequências

### Positivas
- Prompt 100% em linguagem natural, limpo e legível.
- Redução do consumo desnecessário de tokens.
- Comportamento testável de forma unitária sem necessidade de levantar serviços externos ou instâncias de LLM.
- Facilita a substituição futura da estratégia de chunking sem quebrar o prompt.

### Negativas ou Limitações
- A função pura descarta temporariamente os metadados (`page`, `source`) do fluxo imediato do prompt. A exibição de fontes na UI para o usuário final deve ser obtida recuperando os documentos fora da string única da chain na Etapa 2.

---

## Riscos

- **Alucinação Factual:**
  *Ressalva Obrigatória:* A formatação limpa do contexto melhora a higiene estrutural da entrada, mas **não elimina por si só o risco de alucinação factual** do modelo de linguagem. A fidelidade das respostas continuará dependendo da qualidade do retriever e da calibração das instruções do prompt de sistema.

---

## Critérios de Validação

1. **Tipo da Saída:** O contexto gerado para interpolação no prompt é estritamente uma `str`.
2. **Ausência de Metadados Crus:** Nenhuma ocorrência de `[Document(` ou `metadata=` deve estar presente na string final do prompt.
3. **Preservação do Conteúdo:** Todo o texto relevante dos blocos recuperados deve estar presente, separado por quebras de linha duplas (`\n\n`).
4. **Tratamento de Lista Vazia:** Ao passar uma lista vazia `[]`, a função deve retornar uma string informativa sem disparar exceção.
5. **Cobertura de Testes Unitários:** Testes unitários dedicados em `tests/unit/test_chain_formatting.py` validando entradas normais, listas vazias e documentos com espaços em branco excedentes.

---

## Referências

- **ADR-0002:** Fornece a instância do modelo LLM que consumirá o prompt formatado.
- **ADR-0004:** Fornece o índice vetorial FAISS que alimenta o `buscador_contexto`.
