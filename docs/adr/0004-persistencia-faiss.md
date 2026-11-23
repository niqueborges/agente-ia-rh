# ADR-0004 — Persistência Controlada do Índice FAISS

- **Número:** ADR-0004
- **Título:** Persistência Controlada do Índice FAISS
- **Status:** Aprovada
- **Data de Criação:** 15/11/2026
- **Data de Atualização:** 23/11/2026 (Refinamento e Aprovação V2)
- **Data de Aprovação:** 23/11/2026

---

## Contexto

A Prova de Conceito (V1) reconstrói o índice vetorial FAISS integralmente em memória RAM a cada inicialização da aplicação, através de `@st.cache_resource` em `app.py`. Para o documento de demonstração de 8 páginas (aproximadamente 45 fatias textuais), a leitura do PDF, o fatiamento e as chamadas síncronas de embedding ao Ollama consomem tempo de CPU e geram latência na inicialização. Em bases corporativas maiores ou durante reinicializações frequentes de desenvolvimento, recalcular embeddings repetidamente gera desperdício de processamento e lentidão desnecessária.

A persistência do índice em disco permite o carregamento quase instantâneo do estado vetorial. Contudo, no ecossistema LangChain Community com FAISS, a persistência envolve a serialização de dados de catálogo e metadados (`index.pkl`) através do módulo `pickle` do Python, introduzindo considerações críticas de segurança, integridade estrutural, sincronização física em disco (`fsync`), concorrência no ambiente Streamlit e tolerância a falhas na inicialização (*Startup Recovery*).

---

## Problema que Precisa ser Resolvido

1. **Desperdício de Processamento:** A ausência de persistência força a recomputação de todos os embeddings em toda inicialização do Streamlit.
2. **Risco de Segurança com `pickle`:** O método `FAISS.load_local()` requer o parâmetro explícito `allow_dangerous_deserialization=True` devido à natureza do formato pickle. A desserialização de arquivos binários não autenticados pode permitir Execução Remota de Código (RCE) se o arquivo for adulterado ou substituído por agentes maliciosos.
3. **Invalidação Silenciosa:** Se o documento PDF for modificado, ou se os parâmetros de fatiamento (`chunk_size`, `chunk_overlap`) ou o modelo de embeddings forem alterados, um índice previamente salvo em disco se torna incompatível ou semanticamente defasado, induzindo o modelo a respostas errôneas.
4. **Vulnerabilidade a Interrupções Abruptas:** Falhas de energia, encerramentos forçados de processo (`kill -9`, cancelamento pelo kernel por OOM) ou travamentos durante a gravação de novos índices podem corromper os arquivos em disco ou deixar o sistema sem nenhum índice operacional se o índice anterior for apagado prematuramente.
5. **Concorrência entre Sessões Streamlit:** O Streamlit permite que múltiplos usuários ou abas acessem a aplicação simultaneamente. Sem coordenação formal entre leitores e escritores, uma sessão pode tentar carregar o índice enquanto outra substitui seus arquivos em disco, ou duas sessões podem tentar reconstruir o índice simultaneamente, gerando condições de corrida (*race conditions*) e corrupção de dados.
6. **Limitações de Atomicidade no Sistema de Arquivos:** Operações de renomeação de diretórios não possuem semântica transacional atômica universal em Linux quando o destino já existe preenchido, e utilitários como `shutil.move` recorrem a cópias recursivas não atômicas quando a renomeação direta não é suportada.
7. **Validações Incompletas que Desencadeiam Embeddings Desnecessários:** Validações de integridade baseadas em buscas textuais (e.g. `similarity_search("teste")`) disparam chamadas de rede ao Ollama para vetorizar o texto da busca, violando a premissa de que a carga de um índice persistido válido deve ocorrer sem nenhuma requisição de embedding.

---

## Decisão Proposta

### 1. Persistência Local Controlada

Implementar a gravação e leitura local do índice vetorial FAISS em um diretório controlado pela aplicação (`data/faiss_index/`), respeitando rigorosas regras de integridade, permissões de acesso do sistema operacional e validação de compatibilidade.

---

### 2. Adoção de Manifesto de Metadados Expandido (`manifest.json`)

Acompanhar os arquivos do índice (`index.faiss` e `index.pkl`) de um manifesto estruturado em formato JSON com versionamento de esquema.

Para garantir validação precisa e detecção de incompatibilidades em $O(1)$, o manifesto incorpora três campos especializados:

1. **`total_chunks`:** Quantidade exata de fatias textuais indexadas.
   - *Justificativa técnica:* Permite verificar a integridade estrutural comparando `manifest["total_chunks"] == faiss_index.index.ntotal == len(docstore)`. Detecta instantaneamente truncamento silencioso de arquivos durante gravação ou falhas na serialização do docstore, sem necessidade de iterar sobre todos os nós em memória.
2. **`chunking_config_hash`:** Hash determinístico (SHA256) dos parâmetros canônicos de fatiamento (`splitter`, `chunk_size`, `chunk_overlap`, separadores ordenados).
   - *Justificativa técnica:* Permite comparação rápida e infalível de configurações em uma única operação de string, eliminando divergências sutis de tipagem ou formatação ao validar se a configuração de fatiamento atual coincide com a do índice salvo.
3. **`collection_id`:** Identificador estruturado da coleção documental (composto pelo identificador do documento e prefixo do hash do PDF, e.g. `politica_rh_exemplo:4a5e62f1`).
   - *Justificativa técnica:* Garante que o índice em disco pertence estritamente à coleção documental pretendida pela aplicação, prevenindo carregamento acidental de índices de coleções distintas caso múltiplos índices coexistam no mesmo ambiente de dados.

Estrutura formal do manifesto:

```json
{
  "manifest_version": "1.1",
  "created_at": "2026-11-15T15:45:00Z",
  "collection_id": "politica_rh_exemplo:4a5e62f1",
  "pdf_source": {
    "path": "data/politica_rh_exemplo.pdf",
    "sha256": "4a5e...hash_hex_do_conteudo_atual..."
  },
  "embedding": {
    "model": "nomic-embed-text:latest",
    "dimensions": 768
  },
  "chunking": {
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "splitter": "RecursiveCharacterTextSplitter",
    "chunking_config_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "retrieval": {
    "total_chunks": 45,
    "distance_strategy": "EUCLIDEAN_DISTANCE"
  },
  "environment": {
    "faiss_version": "1.16.0",
    "langchain_community_version": "0.3.x"
  }
}
```

---

### 3. Fronteira de Confiança e Segurança de Desserialização

- **Registro Expressamente Documentado:** O parâmetro `allow_dangerous_deserialization=True` autoriza a desserialização via `pickle`.
- **Limitação do Manifesto:** O arquivo `manifest.json` atua estritamente como uma **verificação de compatibilidade operacional** (checando se o índice em disco corresponde aos parâmetros de configuração atuais). Ele **não autentica nem assina criptograficamente** o arquivo binário `index.pkl`.
- Um invasor com privilégios de escrita local no sistema de arquivos capaz de substituir o `index.pkl` também poderia substituir o `manifest.json`.
- **Regra Mandatória de Segurança:** A aplicação aceitará carregar **estritamente índices gerados e mantidos localmente pela própria aplicação**, em diretório local protegido, sob uma fronteira de confiança local explícita.
- **Proibição de Índices de Terceiros:** A aplicação nunca deve importar ou descompactar índices FAISS recebidos de fontes externas ou não confiáveis.
- O diretório `data/faiss_index/` deve possuir permissões restritivas do sistema operacional (permissão exclusiva de leitura e escrita para o usuário de execução, e.g. `chmod 700` no diretório e `chmod 600` nos arquivos).

---

### 4. Renomeação, Atomicidade, Limitações de `shutil.move` e Durabilidade em Linux

O processo de atualização e substituição de índices em disco não é uma transação atômica ACID de banco de dados. Para fundamentar a engenharia do mecanismo, diferenciam-se formalmente as seguintes camadas:

#### 4.1. Atomicidade de `os.rename` no mesmo Filesystem
No Linux (POSIX), a chamada de sistema `rename(2)` / `os.rename` é atômica estritamente quando opera dentro do mesmo sistema de arquivos (mesmo ponto de montagem) e sob duas condições:
1. Se o destino (`dst`) não existe;
2. Se o destino (`dst`) é um diretório estritamente vazio.

Caso o destino seja um diretório preenchido com arquivos, `os.rename` falha obrigatoriamente com `OSError: [Errno 39] Directory not empty` ou `EEXIST`. Consequentemente, substituir diretamente um diretório não vazio por outro não é uma operação atômica de passo único no kernel Linux.

#### 4.2. Limitações Críticas de `shutil.move`
O utilitário `shutil.move(src, dst)` da biblioteca padrão do Python tenta inicialmente executar `os.rename(src, dst)`. Contudo:
- Se o destino existir como diretório não vazio, ou se origem e destino residirem em sistemas de arquivos distintos (pontos de montagem diferentes), `shutil.move` recorre internamente a uma cópia recursiva em árvore (`shutil.copytree`) seguida da remoção recursiva da origem (`shutil.rmtree`).
- A cópia recursiva **não é atômica**: uma interrupção inesperada (falha de energia, `kill -9` ou cancelamento do processo) durante `shutil.copytree` deixa diretórios em estado corrompido ou incompleto.
- **Diretriz:** A aplicação não deve confiar em `shutil.move` para substituição atômica de diretórios ativos. Deve utilizar renomeações explícitas via `os.rename` entre nomes não colidentes no mesmo ponto de montagem ext4.

#### 4.3. Sequência Rigorosa de `fsync` e Sincronização Física em Disco
Gravar arquivos no Linux deposita os blocos de dados inicialmente no cache de páginas do kernel (*dirty pages*). Em caso de corte abrupto de energia, esses dados podem se perder antes da descarga física para o dispositivo de armazenamento. Para mitigar esse risco durante a geração de um novo índice, a aplicação deve executar a seguinte sequência exata de sincronização:

1. **Sincronização dos Arquivos de Dados:**
   - Gravar `index.faiss`, `index.pkl` e `manifest.json` no diretório temporário isolado `data/faiss_index_tmp/`.
   - Para cada arquivo, executar `file.flush()` seguido imediatamente de `os.fsync(file.fileno())` no descritor de arquivo aberto antes de fechá-lo.
2. **Sincronização do Diretório Temporário:**
   - Abrir o descritor de arquivo do diretório temporário com `dir_fd = os.open("data/faiss_index_tmp", os.O_RDONLY | os.O_DIRECTORY)`.
   - Executar `os.fsync(dir_fd)` e fechar `dir_fd`, garantindo que as entradas de diretório (*dentries*) dos novos arquivos foram gravadas no disco.
3. **Renomeação dos Diretórios no mesmo Ponto de Montagem:**
   - Havendo índice ativo anterior, executar `os.rename("data/faiss_index", "data/faiss_index_backup")`.
   - Executar `os.rename("data/faiss_index_tmp", "data/faiss_index")`.
4. **Sincronização do Diretório Pai:**
   - Abrir o descritor do diretório pai com `parent_fd = os.open("data", os.O_RDONLY | os.O_DIRECTORY)`.
   - Executar `os.fsync(parent_fd)` e fechar `parent_fd`, garantindo que as alterações nas entradas do diretório `data/` (as renomeações dos diretórios filhos) foram persistidas no journal/metadados do ext4.

#### 4.4. Limites Físicos da Durabilidade
Deve-se registrar formalmente que a chamada `os.fsync()` instrui o kernel a descarregar as páginas sujas para a controladora de armazenamento. Contudo, a durabilidade física real depende de fatores externos à aplicação:
- Opções de montagem do sistema de arquivos (e.g. `data=ordered` vs `data=journal`, barreiras de escrita `barrier=1` no ext4);
- Política de cache de escrita do hardware (controladoras de SSD/NVMe com cache volátil sem bateria podem perder escritas não descarregadas em queda brusca de energia).

Diferencia-se expressamente a **atomicidade de metadados de `os.rename`** (garantida pelo kernel Linux no mesmo filesystem) da **durabilidade física dos blocos de dados em hardware** (maximizada via `fsync`, mas sujeita às configurações de montagem e armazenamento do host).

---

### 5. Coordenação de Concorrência entre Leitores e Escritores no Streamlit

O Streamlit opera com um modelo multithread/multissessão, no qual múltiplos usuários ou abas podem interagir com a aplicação simultaneamente. A coordenação de concorrência é gerenciada com base nas seguintes definições arquiteturais:

#### 5.1. Ciclo de Vida em Memória vs. Acesso a Disco no Streamlit
- Uma vez concluído o carregamento pelo LangChain (`FAISS.load_local()`), os descritores dos arquivos binários são fechados. O índice C++ do FAISS e a docstore Python passam a residir integralmente na memória RAM do processo Streamlit.
- O decorador `@st.cache_resource` armazena a instância em memória e a reutiliza entre todas as sessões e requisições do processo.
- **Consequência Fundamental:** Consultas de usuários em tempo de execução são atendidas **exclusivamente a partir da memória RAM**, sem manter arquivos abertos em disco e sem disputar travas durante as buscas.

#### 5.2. Protocolo de Travamento em Disco (`data/faiss_index.lock`)
Para coordenar os momentos em que o disco precisa ser acessado (leitura inicial do índice ou reconstrução completa), adota-se o mecanismo de travas `fcntl.flock` do Linux:

1. **Leitores (Abertura e Carga do Disco para a RAM):**
   - Ao executar a rotina de carga em disco, a sessão adquire uma trava compartilhada: `fcntl.flock(fd, fcntl.LOCK_SH)`.
   - Vários leitores podem carregar concorrentemente do disco sob `LOCK_SH`.
   - Assim que o carregamento em memória é concluído, o leitor libera imediatamente a trava (`fcntl.flock(fd, fcntl.LOCK_UN)`) e fecha o descritor de arquivo.
   - *Timeout de leitura:* Se um escritor estiver ativo, o leitor aguarda até 10 segundos para obter `LOCK_SH`. Se o timeout expirar, emite aviso na interface informando que o índice está sendo atualizado.
2. **Escritores / Rotina de Reindexação:**
   - A rotina de reconstrução do índice adquire uma trava exclusiva: `fcntl.flock(fd, fcntl.LOCK_EX)`.
   - O escritor aguarda a liberação de eventuais leitores que estejam ativamente carregando arquivos do disco naquele instante. Novas leituras de disco ficam bloqueadas até a conclusão da escrita.
   - *Timeout de escrita:* A obtenção de `LOCK_EX` aguarda até 60 segundos. Se outra sessão já estiver gravando, a requisição concorrente falha de forma controlada (`BlockingIOError`) e aguarda a conclusão da gravação em andamento, evitando duplicação de processamento.
   - Toda a fase de processamento pesado (fatiamento de texto e geração de embeddings via Ollama) é realizada no diretório isolado `data/faiss_index_tmp/`.
   - A substituição dos diretórios em disco (`backup -> ativo`) ocorre sob a posse da trava exclusiva `LOCK_EX`.
   - A trava exclusiva é liberada (`LOCK_UN`) imediatamente após a sincronização do diretório pai (`fsync`).

#### 5.3. Resiliência a Travas Órfãs (*Stale Locks*)
No Linux, as travas `fcntl.flock` estão vinculadas à entrada na tabela de arquivos abertos do kernel associada ao descritor de arquivo do processo. Se o processo Streamlit for finalizado abruptamente (`kill -9`, erro fatal de segmentação ou cancelamento por OOM), o kernel do sistema operacional fecha automaticamente todos os descritores de arquivo abertos e **libera a trava de imediato**. Isso elimina o problema de bloqueios permanentes (*stale locks*) característico de arquivos de trava estáticos baseados em texto.

#### 5.4. Alternativa Arquitetural Avaliada: Diretórios Versionados com Ponteiro Atômico
- Para bases documentais futuras em expansão, avalia-se a substituição do modelo de substituição in-place por diretórios imutáveis versionados:
  - Cada novo índice é gravado em um diretório próprio e imutável: `data/indices/idx_<timestamp>_<sha256[:8]>/`.
  - A ativação do índice ocorre através da atualização atômica de um arquivo de ponteiro (`data/active_index.json` gravado em arquivo temporário e ativado com `os.replace`), ou através de link simbólico atômico (`os.symlink` temporário substituído com `os.replace`).
  - As sessões leitoras consultam o ponteiro e abrem o diretório versionado correspondente. Como o diretório antigo nunca é renomeado ou excluído enquanto houver leitores referenciando-o, leitores e escritores tornam-se desacoplados no sistema de arquivos, dispensando travas de leitura em disco.
- **Decisão para a V2:** Mantém-se o modelo conservador de diretório local com backup, quarentena e travas `fcntl.flock`, por apresentar menor complexidade de gestão de ciclo de vida e limpeza de lixo (*garbage collection*) no escopo mono-PDF da V2.

---

### 6. Procedimento de Substituição e Validação Funcional sem Embeddings Desnecessários

Para garantir que um índice gerado em disco esteja 100% íntegro antes de descartar o backup funcional anterior, adota-se um procedimento rigoroso com validação funcional estrutural.

#### 6.1. Diferenciação Crucial entre Operações de Embedding e Validação
Para assegurar conformidade com a eficiência energética e evitar chamadas indevidas ao Ollama, diferenciam-se formalmente três conceitos:
1. **Reindexação dos Documentos:** Leitura do PDF, quebra em fatias e envio de todos os textos à API do Ollama (`POST /api/embeddings`) para vetorização completa. Ocorre estritamente quando o índice não existe ou foi invalidado.
2. **Embedding da Consulta (Query Embedding):** Envio de uma string de texto à API do Ollama para gerar o vetor de consulta. Ocorre durante a interação do usuário com o chat.
3. **Validação Estrutural e Funcional do Índice:** Verificação da integridade dos arquivos binários, da docstore em memória e dos grafos de busca em C++.

> [!IMPORTANT]
> A chamada `similarity_search("teste", k=1)` utiliza internamente o método `embed_query("teste")`, gerando uma requisição de rede desnecessária ao Ollama. Para que a validação estrutural do índice seja **100% local e autônoma**, deve-se utilizar busca vetorial direta com vetor sintético predefinido: `similarity_search_by_vector(embedding=[0.0] * dim, k=1)` ou inspeção direta dos atributos do índice FAISS e de sua docstore.

#### 6.2. Fluxo de Substituição em 7 Etapas

1. **Construção Isolada:** Fatiar documentos e gerar novos embeddings gravando em `data/faiss_index_tmp/`.
2. **Garantia de Durabilidade Física:** Executar `flush()` e `os.fsync()` nos arquivos de dados e no diretório temporário.
3. **Preservação do Índice Anterior:** Existindo `data/faiss_index/`, renomeá-lo para `data/faiss_index_backup/` via `os.rename` (sob `LOCK_EX`).
4. **Ativação Provisória:** Mover `data/faiss_index_tmp/` para `data/faiss_index/` via `os.rename`.
5. **Validação Funcional Rigorosa em 5 Critérios (Zero Chamadas ao Ollama):**
   - *1. Validação de Manifesto e Compatibilidade:* Verificar conformidade do esquema JSON, versão do manifesto, hash do PDF, parâmetros de fatiamento e hash de configuração `chunking_config_hash`.
   - *2. Carregamento Efetivo em Memória:* Executar `FAISS.load_local()` comprovando que o cabeçalho binário C++ e a docstore pickle são desserializados sem exceções.
   - *3. Verificação de Dimensão e Contagem de Vetores:* Verificar se `faiss_index.index.d == manifest["embedding"]["dimensions"]` e se `faiss_index.index.ntotal == manifest["retrieval"]["total_chunks"] == len(faiss_index.docstore._dict)`.
   - *4. Consulta Vetorial de Sanidade sem Requisição ao Ollama:* Executar `faiss_index.similarity_search_by_vector(embedding=[0.0] * dim, k=1)`. Esta chamada executa exclusivamente nos algoritmos de busca vetorial em C++ em memória RAM, sem efetuar qualquer requisição externa ou de rede.
   - *5. Conferência de Integridade Documental e Metadados:* Validar se o objeto `Document` retornado pela busca vetorial contém texto legível não vazio e metadados estruturados obrigatórios (`source`, `page`).
6. **Descarte Seguro do Backup:**
   O diretório `data/faiss_index_backup/` **só será removido se e somente se todos os 5 critérios de validação forem aprovados com sucesso absoluto**.
7. **Rollback Imediato de Exceção:**
   Caso qualquer um dos 5 critérios falhe:
   - Move o diretório defeituoso `data/faiss_index/` para quarentena técnica com identificador único (`data/faiss_index_quarantine_failed_activation_<timestamp>/`);
   - Restaura imediatamente `data/faiss_index_backup/` de volta para `data/faiss_index/`;
   - Registra log de erro estruturado alertando a falha de ativação e mantém a aplicação funcional atendendo pelo backup restaurado.

---

### 7. Estratégia Consolidada de Recuperação na Inicialização (Startup Recovery)

Na inicialização da aplicação, o sistema deve inspecionar a árvore de diretórios em `data/` para sanar estados inconsistentes deixados por eventuais encerramentos abruptos anteriores (falha de energia, reinicialização forçada do host ou crash de processos).

#### 7.1. Diretrizes Norteadoras
- **Preservação Estrita:** Nenhum artefato existente deve ser descartado antes de se comprovar a disponibilidade e integridade de uma alternativa funcional.
- **Quarentena Técnica Não Destrutiva:** Diretórios com arquivos corrompidos, incompletos ou inválidos são movidos para subpastas de quarentena com carimbo de data/hora único (e.g. `data/faiss_index_quarantine_<origem>_<YYYYMMDD_HHMMSS_ffffff>/`), garantindo que quarentenas anteriores **nunca sejam sobrescritas**.
- **Independência do Resíduo Temporário (`tmp`):** O diretório `data/faiss_index_tmp/` representa sempre uma escrita interrompida. Ele é isolado ou removido logo no início da rotina de recuperação, permitindo que a decisão principal seja tomada com clareza com base nos diretórios `faiss_index` e `faiss_index_backup`.

#### 7.2. Matriz Consolidada de Cenários e Ações de Recuperação

A tabela a seguir consolida e elimina sobreposições de decisão, baseando-se no estado real dos diretórios encontrados em `data/`:

| Estado Encontrado em `data/` | Diagnóstico Técnico | Sequência Decisória e Ação Conservadora |
| :--- | :--- | :--- |
| **Cenário 1: Existe apenas `faiss_index`** (sem `backup` e sem `tmp`) | Estado nominal padrão de operação. | 1. Submete `faiss_index` à validação funcional completa (5 critérios).<br/>2. *Se válido:* Carrega o índice e inicia a aplicação normalmente.<br/>3. *Se inválido:* Move `faiss_index` para quarentena (`quarantine_main_<ts>`). Se o arquivo PDF original estiver presente e acessível, inicia reindexação limpa do zero. Se o PDF estiver inacessível, dispara **falha controlada com parada do serviço** e orientação explícita para recuperação manual. |
| **Cenário 2: Existe apenas `faiss_index_backup`** (sem `faiss_index`, com ou sem `tmp`) | Interrupção após mover o índice antigo para backup e antes da ativação do novo. | 1. Isola/descarta `tmp` residual, se houver.<br/>2. Submete `faiss_index_backup` à validação funcional (5 critérios).<br/>3. *Se válido:* Restaura o backup para índice ativo (`os.rename("data/faiss_index_backup", "data/faiss_index")`), sincroniza o diretório pai e inicia a aplicação.<br/>4. *Se inválido:* Move para quarentena (`quarantine_backup_<ts>`). Se PDF acessível, reconstrói do zero. Se PDF indisponível, aciona parada controlada. |
| **Cenário 3: Existem tanto `faiss_index` quanto `faiss_index_backup`** (com ou sem `tmp`) | Interrupção ocorreu após a movimentação do novo índice para a pasta ativa, antes do descarte do backup anterior. | 1. Isola/descarta `tmp` residual, se houver.<br/>2. Submete `faiss_index` à validação funcional prioritária.<br/>3. *Se `faiss_index` for 100% válido:* O novo índice foi ativado com sucesso antes da interrupção. Remove o `backup` residual com segurança e conclui a inicialização.<br/>4. *Se `faiss_index` for inválido:* Move `faiss_index` para quarentena (`quarantine_main_<ts>`). Em seguida, valida `faiss_index_backup`:<br/>&nbsp;&nbsp;&nbsp;&nbsp;a) *Se `backup` for válido:* Restaura `backup` para `faiss_index` via `os.rename`, sincroniza com `fsync` e inicia a aplicação operando pelo backup.<br/>&nbsp;&nbsp;&nbsp;&nbsp;b) *Se `backup` também for inválido:* Move `backup` para quarentena (`quarantine_backup_<ts>`). Se o PDF original estiver acessível, aciona reindexação completa do zero. Se o PDF estiver indisponível, dispara **falha controlada com parada do serviço**, preservando todos os artefatos em quarentena para perícia técnica e exigindo intervenção manual. |
| **Cenário 4: Existe apenas `faiss_index_tmp`** (sem `faiss_index` e sem `backup`) | Processo de geração inicial foi interrompido antes da conclusão da primeira indexação. | 1. Move `tmp` para quarentena (`quarantine_tmp_<ts>`) ou remove com segurança.<br/>2. Identifica ausência total de índices válidos.<br/>3. Se PDF acessível, executa construção inicial nominal. Se PDF indisponível, aciona parada controlada. |
| **Cenário 5: Nenhum diretório de índice existe em `data/`** | Estado de instalação limpa (*fresh start*). | 1. Inicia a construção limpa do índice a partir do PDF original conforme fluxo padrão. |

---

### 8. Momento de Execução no Ciclo de Vida da Aplicação

Esclarece-se formalmente o momento em que a rotina de recuperação e carga é executada:

- A recuperação de inicialização **não é implementada como um serviço daemon externo do sistema operacional**, nem requer scripts prévios de inicialização em bash antes do comando `streamlit run app.py`. Essa abordagem externa aumentaria o atrito de implantação e a fragilidade operacional.
- Em contrapartida, a rotina de recuperação é executada **dentro da função de inicialização do recurso em cache** no código da aplicação (e.g. dentro da função decorada com `@st.cache_resource def get_vector_store(): ...`), **sob proteção estrita de trava exclusiva `fcntl.flock(LOCK_EX)`**, ANTES de qualquer requisição ler ou carregar o índice em memória.
- **Detalhamento da Sequência no Ciclo de Vida:**
  1. O Streamlit inicia o processo Python e começa a interpretar o script `app.py`.
  2. A primeira requisição que necessita do banco vetorial chama `get_vector_store()`.
  3. A função abre o arquivo `data/faiss_index.lock` e adquire a trava exclusiva `LOCK_EX`.
  4. Sob a posse de `LOCK_EX`, executa a rotina de recuperação (*Startup Recovery*), inspecionando o sistema de arquivos, resolvendo diretórios `tmp` ou `backup` pendentes e validando o diretório ativo conforme a Seção 7.
  5. Se o índice ativo estiver íntegro, executa a carga para a memória via `FAISS.load_local()`.
  6. Se o índice precisar ser reconstruído, todo o processo de leitura do PDF, cálculo de embeddings via Ollama e validação estrutural é executado sob a mesma trava `LOCK_EX`.
  7. Concluída a inicialização com sucesso, o recurso fica retido na memória RAM pelo `@st.cache_resource`, e a trava `LOCK_EX` é liberada de imediato.
  8. Todas as requisições subsequentes da aplicação (inclusive de outras abas ou usuários concorrentes) recebem diretamente a referência do objeto em memória RAM, sem executar verificações de disco ou disputar travas.

---

### 9. Critério Fundamental de Eficiência

Não se estabelece um limite arbitrário de tempo (como 500 ms) para a inicialização da aplicação, pois o tempo de carga em disco varia conforme o hardware de armazenamento.

O critério primário objetivo de eficiência técnica é: **comprovar que o carregamento de um índice persistido válido em disco executa sem realizar nenhuma chamada de embedding à API do Ollama** (zero requisições a `POST /api/embeddings`).

---

## Alternativas Consideradas

1. **Armazenamento Não Executável (FAISS Nativo + SQLite / DuckDB / Parquet):**
   - *Descrição:* Salvar apenas o binário C++ do FAISS (`index.faiss`) e gravar os metadados dos documentos em tabela relacional SQLite ou Parquet, sem utilizar o serializador `pickle` do LangChain Community.
   - *Vantagens:* Elimina integralmente o risco de RCE associado à desserialização por `pickle`.
   - *Custos:* Exige implementar uma camada personalizada de vinculação entre IDs vetoriais e objetos `Document` fora das abstrações nativas do LangChain Community, aumentando o esforço inicial de implementação e manutenção.
   - *Decisão:* Registrada como evolução arquitetural recomendada caso a aplicação passe a receber ou compartilhar índices vetoriais através de redes ou origens externas. Para a V2, mantém-se o LangChain Community com fronteira de confiança local estrita.
2. **Manter Banco Vetorial Exclusivamente em Memória Volátil (Status Quo da V1):**
   - *Motivo da Rejeição:* Inviabiliza a escalabilidade da base documental e penaliza o desenvolvedor e o usuário com lentidão em cada reinicialização da aplicação.
3. **Diretórios Versionados com Ponteiro Atômico:**
   - *Motivo da Postergação:* Embora elimine a necessidade de travas compartilhadas para leitura em disco, introduz a necessidade de um subsistema de limpeza e remoção de versões obsoletas (*garbage collection*). Fica registrado como diretriz de evolução para futuras versões multi-PDF.

---

## Justificativa Técnica

A combinação de persistência local controlada, manifesto estruturado com `total_chunks`, `chunking_config_hash` e `collection_id`, sincronização física em disco com `fsync` em múltiplos níveis, controle de concorrência com travas `fcntl.flock`, validação vetorial sintética sem chamadas ao Ollama e recuperação determinística na inicialização estabelece tolerância a falhas profissional. Preserva sempre a cópia mais íntegra disponível, protege contra concorrência multissessão e garante integridade dos dados sem presumir comportamentos mágicos do sistema de arquivos.

---

## Consequências

### Positivas
- Inicialização praticamente instantânea da aplicação quando o documento PDF e as configurações não sofrerem alterações.
- Proteção contra condições de corrida entre leitores e escritores no Streamlit via travas de kernel `fcntl.flock` e escrita isolada em diretório temporário.
- Salvaguarda rigorosa contra índices defeituosos através da validação funcional completa em 5 critérios antes do descarte do backup.
- Ausência total de requisições de embedding ao Ollama durante a validação estrutural do índice, através do uso de consulta vetorial direta (`similarity_search_by_vector`).
- Capacidade autônoma de recuperação (*Startup Recovery*) em todos os cenários possíveis de interrupção ou falha de processos.
- Preservação de dados defeituosos em diretórios de quarentena técnica únicos e carimbados por timestamp, viabilizando auditoria técnica sem perda de dados.
- Liberação automática de travas pelo kernel Linux em caso de encerramento abrupto do processo (`kill -9`, SIGSEGV ou OOM), eliminando bloqueios permanentes (*stale locks*).

### Negativas ou Limitações
- Consumo adicional temporário de espaço em disco durante o processo de reindexação para acomodar os diretórios temporário e de backup.
- Dependência de disciplina de segurança e permissões de sistema operacional no host para proteger os arquivos de índice locais contra adulteração não autorizada.

---

## Riscos

- **Falha de Permissão no Sistema de Arquivos:** Se o processo Streamlit não possuir privilégios de escrita no diretório `data/`, a rotina de persistência falhará.
  - *Mitigação:* Tratar exceções de permissão (`PermissionError`) de forma controlada, emitindo aviso legível na interface e realizando fallback temporário para índice volátil em memória RAM.
- **Esgotamento de Espaço em Disco:** Falha no meio da gravação de um índice por falta de espaço no dispositivo de armazenamento.
  - *Mitigação:* A gravação em diretório temporário isolado protege o índice ativo contra corrupção por disco cheio; falhas de I/O abortam o processo antes da substituição do diretório ativo.

---

## Critérios de Validação

A suíte de testes unitários e de integração deve cobrir com sucesso os seguintes cenários:

1. **Criação de Índice Inexistente:** Aplicação gera com sucesso `index.faiss`, `index.pkl` e `manifest.json` com permissões adequadas.
2. **Carga sem Embeddings:** Carregamento de índice válido comprovando documentalmente e por telemetria zero chamadas à API de embeddings do Ollama.
3. **Validação Vetorial sem Rede:** Teste comprova que a validação estrutural do índice utiliza busca por vetor sintético (`similarity_search_by_vector`) sem acionar `embed_query`.
4. **Detecção de Alteração de PDF:** Alteração no hash SHA256 do arquivo PDF aciona invalidação do índice existente e regeração completa.
5. **Detecção de Alteração de Modelo ou Dimensão:** Alteração no modelo de embeddings ou discrepância no número de dimensões no manifesto provoca invalidação e reconstrução.
6. **Detecção de Alteração de Fatiamento via Hash:** Alteração nos parâmetros de fatiamento detectada pelo `chunking_config_hash` aciona regeração do índice.
7. **Detecção de Inconsistência Estrutural:** Divergência entre `total_chunks`, `index.ntotal` e o tamanho da docstore aborta a ativação e restaura o backup funcional.
8. **Recuperação Pós-Interrupção (Startup Recovery):** Testes unitários simulando os cenários da Matriz de Recuperação comprovam a restauração do estado funcional e a transferência de diretórios anômalos para quarentena técnica com identificador único.
9. **Coordenação de Concorrência:** Simulação com múltiplos processos concorrentes comprova que a trava exclusiva `fcntl.flock(LOCK_EX)` impede escrita simultânea e que a liberação de travas ocorre confiavelmente em encerramentos forçados.

---

## Referências

- **ADR-0001:** Define a resolução de conectividade com a API local do Ollama (`127.0.0.1:11434`).
- **ADR-0002:** Catálogo de modelos de embeddings candidatos cujos metadados e dimensões vetoriais são registrados no manifesto.
- **ADR-0003:** O recuperador FAISS carregado em memória alimenta a pipeline de recuperação e formatação contextual via LCEL.
- **ADR-0005:** Especifica as dependências `faiss-cpu` e `langchain-community` no ambiente Ubuntu 26.04 nativo.
