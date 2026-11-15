# ADR-0001 — Resolução e Verificação de Conectividade do Ollama

- **Número:** ADR-0001
- **Título:** Resolução e Verificação de Conectividade do Ollama
- **Status:** Aprovada
- **Data de Criação:** 15/11/2026
- **Data de Atualização:** 15/11/2026 (Refinamento Pós-Revisão Técnica)
- **Data de Aprovação:** 15/11/2026

---

## Contexto

O projeto **agente-ia-rh** opera como uma aplicação RAG local que depende do servidor Ollama para geração de embeddings e inferência de modelos de linguagem. O ambiente principal e suportado de desenvolvimento e execução é o **Ubuntu 26.04 LTS nativo**, onde o daemon do Ollama está instalado e em execução como serviço gerenciado pelo systemd (`/usr/local/bin/ollama`), escutando na interface de loopback IPv4 na porta TCP `11434` (`127.0.0.1:11434`).

Na implementação herdada da Prova de Conceito (V1), o módulo `rag/ollama_client.py` inclui um mecanismo de descoberta de rede concebido originalmente para um ambiente híbrido Windows + WSL2, utilizando o seguinte trecho:

```python
host_ip = (
    subprocess.check_output(
        "ip route | grep default | awk '{print $3}'",
        shell=True,
        stderr=subprocess.DEVNULL,
    )
    .decode()
    .strip()
)
if host_ip and testar_conexao(host_ip, 11434):
    return f"http://{host_ip}:11434"
```

---

## Problema que Precisa ser Resolvido

1. **Tentativa Indevida de Conexão contra o Gateway da Rede Física:** No Ubuntu nativo, o comando `ip route | grep default | awk '{print $3}'` retorna o endereço IP do gateway da interface física do sistema operacional (por exemplo, `192.168.1.254`, o roteador de borda da rede local). Caso a conexão local falhe temporariamente, a aplicação tenta abrir conexão TCP na porta 11434 especificamente contra o roteador físico da rede, o que é conceitualmente incorreto em um ambiente Linux nativo.
2. **Subprocesso Desnecessário e Dependência de Utilitários Externos:** O uso de `subprocess.check_output` com `shell=True` inicia um subshell para encadear utilitários externos do sistema operacional (`ip`, `grep`, `awk`), gerando overhead de processo desnecessário, fragilidade diante de variações nos pacotes do sistema e inadequação conceitual à execução em host nativo, onde o serviço encontra-se no próprio loopback local.
3. **Código Residual de Ambiente Descontinuado (WSL2):** O ambiente WSL2 não é mais utilizado pelo projeto. Manter mecanismos concebidos para a topologia de rede virtualizada do WSL2 introduz complexidade desnecessária e comportamentos imprevistos.
4. **Acoplamento entre Resolução de Configuração e Diagnóstico de Rede:** Na implementação da V1, a função `obter_url_ollama()` mistura a determinação da URL com tentativas síncronas de conexão de rede via socket. Se as conexões falharem, a função retorna silenciosamente `http://localhost:11434` ao final, sem diferenciar erro de configuração de indisponibilidade de serviço, postergando o diagnóstico para exceções não tratadas durante a execução do Streamlit.

---

## Decisão Proposta

### 1. Remoção Total de Subprocessos de Rede
Eliminar integralmente qualquer chamada ao módulo `subprocess`, comandos de subshell ou invocação de utilitários de roteamento (`ip route`) em `rag/ollama_client.py`.

---

### 2. Resolução Determinística de Configuração (`obter_url_ollama() -> str`)

A função `obter_url_ollama()` é definida como uma **rotina determinística de resolução de configuração**, sem I/O de rede e sem efeitos colaterais. Por consultar o estado externo das variáveis de ambiente (`os.environ`), ela não é classificada como estritamente pura, mas opera de forma previsível e instantânea ($O(1)$).

A ordem de resolução é estrita:

1. **Prioridade 1:** Variável de ambiente `OLLAMA_BASE_URL`, quando definida e não vazia.
2. **Prioridade 2 (Fallback Canônico Padrão):** Retorno estrito de `http://127.0.0.1:11434`.
   - Adota-se explicitamente o literal IPv4 `127.0.0.1` em substituição a `localhost` para eliminar ambiguidades de resolução DNS/nsswitch ou tentativas preferenciais de IPv6 (`::1`) na pilha de rede do Ubuntu nativo, uma vez que o serviço Ollama no systemd escuta em IPv4.

#### Validação e Normalização Estrita de `OLLAMA_BASE_URL`
Caso a variável `OLLAMA_BASE_URL` esteja presente, a aplicação aplica regras formais de sanitização, pré-normalização e validação sintática:

- **Valor Ausente ou em Branco:** Se a variável não estiver definida, for vazia ou contiver apenas espaços (`None`, `""` ou `"   "`), aplica-se automaticamente o fallback padrão (`http://127.0.0.1:11434`).
- **Remoção de Espaços:** Aplicar `.strip()` sobre a string configurada antes de qualquer análise.
- **Pré-normalização de URLs sem Esquema:**
  - A ausência de esquema deve ser identificada **antes** da chamada a `urllib.parse.urlsplit()`, inspecionando se a string contém o delimitador `://`.
  - Se a string não contiver `://`, prepende-se obrigatoriamente o prefixo padrão `http://`.
  - Essa etapa prévia impede que `urlsplit()` interprete equivocadamente o nome do host como esquema (por exemplo, `urlsplit("localhost:11434")` interpreta `localhost` como esquema e `11434` como caminho).
  - Casos explicitamente cobertos:
    - `localhost:11434` $\rightarrow$ pré-normalizado para `http://localhost:11434`
    - `127.0.0.1:11434` $\rightarrow$ pré-normalizado para `http://127.0.0.1:11434`
    - `servidor:11434` $\rightarrow$ pré-normalizado para `http://servidor:11434`
    - `[::1]:11434` $\rightarrow$ pré-normalizado para `http://[::1]:11434`
- **Protocolo (Esquema):**
  - O esquema deve ser estritamente `http` ou `https`.
  - Caso seja informado qualquer outro esquema (por exemplo, `ftp://`), a configuração é considerada inválida.
- **Hostname:** Deve ser extraído e validado (não vazio). A ausência de hostname invalida a configuração.
- **Validação de Porta:**
  - **Regra de Porta Padrão:** Caso a porta não seja especificada na URL, adota-se a porta padrão `11434`, tanto para `http` quanto para `https` (por exemplo, `http://localhost` normaliza para `http://localhost:11434`, `https://servidor` normaliza para `https://servidor:11434`, e `http://servidor/ollama` normaliza para `http://servidor:11434/ollama`).
  - **Rejeição de Porta Vazia Explícita:** URLs que terminam com `:` sem dígitos (por exemplo, `http://localhost:` ou `http://localhost:/ollama`) são rejeitadas.
  - **Rejeição de Porta Não Numérica:** URLs com caracteres não numéricos no campo de porta (por exemplo, `http://localhost:abc`) são rejeitadas.
  - **Validação de Intervalo Válido:** Quando especificada, a porta deve ser um número inteiro no intervalo TCP canônico de 1 a 65535 ($1 \le \text{porta} \le 65535$). Portas fora do intervalo (por exemplo, `http://localhost:0` ou `http://localhost:99999`) são rejeitadas.
- **Rejeição Estrita de Credenciais Embutidas:** URLs contendo usuário ou senha inline (`username` ou `password` presentes no split, por exemplo, `http://user:pass@host:11434`) são rejeitadas para prevenir riscos de segurança e vazamentos acidentais em logs.
- **Rejeição Estrita de Fragmentos:** URLs contendo fragmentos (`#fragmento`, por exemplo, `http://host:11434#secao`) são rejeitadas.
- **Rejeição Estrita de Parâmetros de Consulta (Query Strings):** URLs contendo query strings (`?param=valor`, por exemplo, `http://localhost:11434?model=qwen`) são terminantemente rejeitadas. A URL base de um serviço de API não comporta parâmetros globais de consulta, e sua presença causa corrupção de rotas em concatenações subsequentes.
- **Tratamento de Caminhos Adicionais (*Path*):**
  - Se a URL contiver apenas a raiz (`/` ou vazia), normaliza-se para a base sem barra final (por exemplo, `http://127.0.0.1:11434`).
  - Se a URL contiver um subcaminho legítimo de proxy reverso (por exemplo, `http://servidor:11434/ollama` ou `https://api.empresa.corp/ia/ollama`), o caminho é preservado e sanitizado sem barra final (`/ollama`), garantindo que o endpoint de verificação seja composto deterministicamente como `http://servidor:11434/ollama/api/version`.
  - Se o caminho configurado já contiver sufixos reservados de API (por exemplo, `/api`, `/api/tags`, `/api/generate`), a configuração é considerada inválida para prevenir duplicações de rota (`/ollama/api/api/version`).
- **Suporte a IPv6:** Endereços IPv6 literais são suportados mediante a notação canônica RFC 3986 com colchetes (por exemplo, `http://[::1]:11434` ou `[::1]:11434`).
- **URL Remota Explicitamente Configurada:** URLs apontando para outros hosts são aceitas e preservadas quando intencionalmente configuradas pelo usuário.
- **Tratamento de Configuração Inválida com Exceção Especializada (`OllamaConfigurationError`):**
  Se a string configurada em `OLLAMA_BASE_URL` violar qualquer uma das regras acima (porta fora do intervalo, porta vazia, porta não numérica, credenciais embutidas, fragmento, query string, esquema inválido, hostname ausente, caminho com endpoint duplicado), a aplicação deve lançar a exceção especializada **`OllamaConfigurationError`** (definida em `rag/ollama_client.py`), interrompendo a inicialização e impedindo que erros de configuração sejam confundidos com indisponibilidade de serviço.

---

### 3. Contrato de Verificação de Conectividade e Saúde (`verificar_conexao_ollama`)

A verificação de conectividade é desacoplada da resolução da URL, ficando concentrada na função especializada:

```python
def verificar_conexao_ollama(base_url: str, timeout: float = 1.0) -> bool:
    """Verifica a acessibilidade operacional do endpoint configurado do Ollama."""
```

#### Contrato e Comportamento:
1. **Tratamento Separado de Configuração Inválida:** Antes de disparar qualquer operação de rede, a função valida a sintaxe da `base_url`. Se a URL for inválida, lança `OllamaConfigurationError` imediatamente (falha rápida que não mascara erro de configuração como indisponibilidade).
2. **Timeout Configurável:** O parâmetro `timeout` possui valor padrão de `1.0` segundo, ajustável programmaticamente ou via configuração, sem impor limites arbitrários e rígidos.
3. **Composição Não Ingênua de URLs:**
   A montagem da URL de verificação de saúde deve preservar adequadamente eventuais subcaminhos de proxy reverso e evitar concatenações ingênuas de strings que possam duplicar barras ou suprimir caminhos:
   ```python
   # Composição determinística a partir da base_url normalizada sem barra final
   url_verificacao = f"{base_url.rstrip('/')}/api/version"
   ```
   Exemplo: `http://servidor:11434/ollama` $\rightarrow$ `http://servidor:11434/ollama/api/version`.
4. **Validação Rigorosa da Resposta `GET /api/version`:**
   Para atestar que o serviço acessado é legitimamente o Ollama, a requisição deve cumprir **cumulativamente** os seguintes requisitos:
   - **Status HTTP 200 (OK):** Códigos HTTP de erro ou respostas de erro (por exemplo, 404 Not Found, 502 Bad Gateway) resultam em falha de verificação.
   - **JSON Válido:** O corpo da resposta deve ser decodificado com sucesso como JSON estruturado (`json.loads`).
   - **Tipo Estruturado Objeto/Dicionário:** A raiz decodificada do JSON deve ser obrigatoriamente um objeto/dicionário (`isinstance(dados, dict)`). Um JSON válido que seja lista (`[]`), número (`123`), string pura (`"ok"`), booleano (`true`) ou nulo (`null`) **não é considerado resposta saudável do Ollama** e resulta em retorno `False`.
   - **Atributo `"version"` Presente e Não Vazio:** O dicionário deve conter obrigatoriamente a chave `"version"`, e seu valor deve ser uma string não vazia (`isinstance(dados["version"], str)` e `bool(dados["version"].strip())`).
   > [!IMPORTANT]
   > Uma resposta HTTP genérica (como um código 200 de um servidor web ou proxy servindo uma página HTML padrão) **não comprova a identidade do Ollama**. A confirmação do daemon Ollama requer status 200 com payload JSON do tipo objeto contendo o campo `"version"` como string não vazia.
5. **Tratamento Específico de Exceções de Rede (`urllib.error`):**
   Apenas falhas de conectividade de rede previstas são capturadas e convertidas em retorno booleano `False`:
   - `urllib.error.HTTPError`: respostas HTTP de erro ou endpoints inexistentes;
   - `urllib.error.URLError`: falha de resolução DNS, conexão recusada ou host inalcançável;
   - `TimeoutError` / `socket.timeout`: esgotamento do tempo limite;
   - `json.JSONDecodeError` / `KeyError`: payload malformado ou ausência do campo `"version"`.
6. **Não Mascaramento de Erros de Programação:**
   Erros inesperados de implementação ou bugs internos de código (como `TypeError`, `AttributeError`, `NameError`) **nunca devem ser capturados por blocos genéricos `except Exception:` que retornem `False`**. Esses erros devem propagar livremente para permitir depuração imediata.
7. **Retorno Booleano:**
   - Retorna `True` caso o endpoint cumpra integralmente os critérios de saúde do Ollama.
   - Retorna `False` diante das falhas de rede e protocolo esperadas listadas no item 5.

---

### 4. Avaliação Comparativa: Socket TCP vs. `GET /api/version`

Avalia-se a técnica a ser empregada para a verificação de saúde do Ollama:

| Critério | Verificação via Socket TCP (`socket.create_connection`) | Verificação via Requisição HTTP (`GET /api/version`) |
| :--- | :--- | :--- |
| **O que comprova** | Comprova apenas que uma porta TCP está aberta e aceitando conexões no host e porta indicados. | Comprova que a porta TCP está aberta, que a pilha HTTP do servidor está operacional e que o serviço respondendo é comprovadamente o Ollama (validação de HTTP 200 e payload JSON do tipo objeto com chave `"version"` preenchida). |
| **O que NÃO comprova** | Não comprova que o serviço em execução é o Ollama (pode ser outro processo ou porta travada) e não valida a camada HTTP. | Não comprova que os modelos de embeddings ou LLMs necessários ao RAG estão baixados, íntegros ou carregados em memória (validação de competência da ADR-0002). |
| **Complexidade** | Utiliza `socket` da biblioteca padrão. | Utiliza `urllib.request` e `json` da biblioteca padrão (sem dependências externas). |

**Decisão Técnica:** Adota-se a requisição semântica `GET /api/version` com timeout configurável (utilizando `urllib.request` da stdlib) como método principal de verificação de saúde, pois comprova a identidade do serviço sem acoplar a validação à existência de modelos específicos. A verificação do catálogo de modelos é responsabilidade downstream da ADR-0002 (`GET /api/tags`).

---

### 5. Tratamento de Indisponibilidade no Streamlit

A aplicação (`app.py`) deve executar a verificação de saúde antes de inicializar recursos pesados em cache:

- **Se houver Erro de Configuração (`OllamaConfigurationError`):**
  - Exibe mensagem informando que a configuração de `OLLAMA_BASE_URL` é inválida e detalha o motivo (porta inválida, credenciais indevidas, query strings proibidas, formato incorreto).
  - Interrompe a execução controladamente (`st.stop()`).
- **Se houver Indisponibilidade do Serviço (`verificar_conexao_ollama` retornou `False`):**
  - Exibe mensagem clara e amigável:
    `"Servidor Ollama indisponível no endpoint {url}. Verifique se o serviço está ativo executando: sudo systemctl status ollama"`
  - Interrompe a execução controladamente com `st.stop()`, evitando que exceções não tratadas de conexão do LangChain poluam a interface com tracebacks.

---

## Alternativas Consideradas

1. **Manter a Descoberta Automática de WSL2 com Detecção Condicional de Kernel:**
   - *Descrição:* Verificar `/proc/version` antes de executar comandos de rede.
   - *Motivo da Rejeição:* O WSL2 foi completamente descontinuado do projeto. Manter código legado para cenários não suportados adiciona complexidade e débitos técnicos.
2. **Fixar Exclusivamente `127.0.0.1` sem Possibilidade de Variável de Ambiente:**
   - *Descrição:* Hardcodar `http://127.0.0.1:11434` no código.
   - *Motivo da Rejeição:* Inviabiliza a utilização de instâncias remotas do Ollama em servidores dedicados com GPU.
3. **Manter Resolução e Teste de Conexão Acoplados na Mesma Função:**
   - *Descrição:* `obter_url_ollama()` executando socket ou HTTP internamente a cada chamada.
   - *Motivo da Rejeição:* Acopla leitura de configuração com latência de I/O, prejudica testes unitários e induz efeitos colaterais.

---

## Justificativa Técnica

O desacoplamento entre resolução determinística de configuração e diagnóstico semântico de saúde estabelece clareza arquitetural. Elimina o uso inadequado de subprocessos no host nativo, sanitiza a configuração contra erros de formatação com validação estrita de portas, query strings e credenciais, protege a rede local contra conexões acidentais ao gateway e garante uma interface amigável caso o daemon do Ollama não esteja em execução.

---

## Consequências

### Positivas
- Elimina tentativas de conexão ao roteador físico da rede local.
- Elimina a dependência de `subprocess`, `shell=True` e utilitários externos (`ip`, `grep`, `awk`).
- Resolução de configuração rápida, determinística ($O(1)$) e sem I/O de rede.
- Pré-normalização robusta que impede que hosts sem esquema sejam interpretados erroneamente como esquema pelo `urlsplit`.
- Validação sintática robusta que previne credenciais embutidas, portas inválidas, fragmentos e query strings em `OLLAMA_BASE_URL`.
- Exceção especializada `OllamaConfigurationError` que impede o mascaramento de erros de configuração como falhas de rede.
- Testes unitários para resolução de URL executam sem mocks de rede e sem dependência de instâncias ativas do Ollama.
- Diagnóstico semântico via `GET /api/version` (HTTP 200 + objeto JSON com `"version"` string não vazia) confirma com precisão a identidade do serviço Ollama sem capturar bugs de código.
- Interface Streamlit resiliente com mensagens orientativas de recuperação via `systemctl`.

### Negativas ou Limitações
- Conexões a servidores remotos do Ollama não são descobertas automaticamente, exigindo declaração explícita da variável `OLLAMA_BASE_URL`.

---

## Riscos e Escopo

- **Ambientes Containerizados (Docker):**
  A conectividade do Ollama a partir de containers Docker está **fora do escopo de solução desta ADR**. O caminho de execução principal e prioritário da V2 é a execução nativa no Ubuntu 26.04 com `.venv`. Qualquer execução em container depende de configurações de rede externas ao código da aplicação, a serem tratadas no escopo de documentação de deploy (ADR-0005).
- **Diferenciação entre Falha de Serviço e Erro de Configuração:**
  Erros sintáticos na variável de ambiente são interceptados como `OllamaConfigurationError` e não como simples indisponibilidade de porta.

---

## Critérios de Validação

1. **Ausência Total de Subprocessos:** A execução de `rag/ollama_client.py` não deve invocar `subprocess`, `os.system` ou utilitários de shell.
2. **Resolução Determinística e Sanitização:**
   - Variável ausente ou em branco retorna estritamente `http://127.0.0.1:11434`.
   - `OLLAMA_BASE_URL="  http://servidor:11434/ "` retorna `http://servidor:11434`.
   - `OLLAMA_BASE_URL="127.0.0.1:11434"` normaliza para `http://127.0.0.1:11434`.
   - `OLLAMA_BASE_URL="localhost:11434"` normaliza para `http://localhost:11434` sem confundir `localhost` com esquema.
   - `OLLAMA_BASE_URL="[::1]:11434"` normaliza para `http://[::1]:11434`.
   - `OLLAMA_BASE_URL="http://localhost"` normaliza com porta padrão para `http://localhost:11434`.
   - `OLLAMA_BASE_URL="https://servidor-remoto"` normaliza para `https://servidor-remoto:11434`.
   - `OLLAMA_BASE_URL="http://servidor:11434/ollama"` normaliza preservando subcaminho para `http://servidor:11434/ollama`.
3. **Rejeição Estrita de Configuração Inválida com `OllamaConfigurationError`:**
   - Dispara exceção para esquemas não suportados (ex: `ftp://servidor`).
   - Dispara exceção para portas fora do intervalo $1 \le \text{porta} \le 65535$ (ex: `http://localhost:0`, `http://localhost:99999`).
   - Dispara exceção para portas vazias explícitas (ex: `http://localhost:`).
   - Dispara exceção para portas não numéricas (ex: `http://localhost:abc`).
   - Dispara exceção para credenciais inline (ex: `http://user:pass@localhost:11434`).
   - Dispara exceção para fragmentos (ex: `http://localhost:11434#frag`).
   - Dispara exceção para query strings (ex: `http://localhost:11434?model=qwen`).
   - Dispara exceção para caminhos com endpoints duplicados (ex: `http://localhost:11434/api/tags`).
4. **Isolamento de Rede:**
   - O fallback padrão restringe-se exclusivamente a `127.0.0.1`.
   - Conexões a endereços externos ocorrem única e exclusivamente quando `OLLAMA_BASE_URL` for definida de forma deliberada para um host remoto.
5. **Diagnóstico Semântico e Validação de Resposta:**
   - `verificar_conexao_ollama()` exige HTTP 200, JSON válido decodificado como objeto/dicionário e campo `"version"` como string não vazia para retornar `True`.
   - Respostas JSON válidas que sejam listas, números, booleanos ou strings primitivas retornam `False`.
   - Retorna `False` diante de `urllib.error.HTTPError`, `urllib.error.URLError` ou timeout.
   - Não suprime erros de programação (`TypeError`, `AttributeError`).
6. **Testabilidade Unitária sem Ollama:** Testes de `obter_url_ollama()` executam sem dependência de rede; testes de `verificar_conexao_ollama()` utilizam mocks simples da camada de transporte.

---

## Referências

- **ADR-0002:** Utiliza a URL resolvida para consulta da API dinâmica de modelos (`/api/tags`).
- **ADR-0005:** Especifica o ambiente Ubuntu 26.04 nativo com `.venv` como caminho principal de execução da V2.
