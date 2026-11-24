# ADR-0007 — Blindagem de Segurança da API, Controle de Concorrência e Defesa em Profundidade na Intranet

- **Número:** ADR-0007
- **Título:** Blindagem de Segurança da API, Controle de Concorrência e Defesa em Profundidade na Intranet
- **Status:** Aprovada
- **Data de Criação:** 23/11/2026
- **Data de Aprovação:** 23/11/2026

---

## Contexto

Com a entrega da ADR-0006, o assistente passou a expor uma API REST/SSE com FastAPI e um frontend estático para a intranet corporativa. 

Contudo, auditorias de segurança apontaram que em redes corporativas com presença de visitantes, consultores externos ou dispositivos pessoais (BYOD), a aplicação não pode operar sob a suposição de que todo tráfego interno é confiável (*premissa Zero Trust*). Os seguintes fatores de vulnerabilidade foram diagnosticados:

1. **Exaustão de Recursos de CPU (DoS em IA Local):** A inferência de modelos como `llama3.1:8b` ou `qwen3.5:4b` na CPU Intel i7 consome 100% dos núcleos de processamento por 10 a 50 segundos por consulta. A ausência de limitação de concorrência permitia que poucas requisições paralelas paralisassem o host do servidor.
2. **Flooding de Requisições:** A falta de *Rate Limiting* por IP permitia varreduras automatizadas ou loops de teste exaustivos.
3. **CORS Excessivamente Aberto:** A utilização de `allow_origins=["*"]` com `allow_credentials=True` violava o princípio do menor privilégio, permitindo ataques do tipo Cross-Origin a partir de navegadores de colaboradores na mesma rede.
4. **Vulnerabilidade a Injeção de Prompt (*Prompt Injection*):** Perguntas adversariais tentavam subverter as instruções do sistema ("*ignore todas as instruções anteriores*", jailbreaks).
5. **Reconhecimento Facilitado:** A exposição incondicional do Swagger UI (`/docs`) e schema OpenAPI revelava toda a estrutura interna do serviço.

---

## Decisão Proposta e Aprovada

Fica estabelecida uma estratégia de **Defesa em Profundidade** implementada diretamente na camada de aplicação:

### 1. Semáforo de Concorrência de Inferência (Anti-DoS)
- Limite estrito de no máximo **2 inferências simultâneas** rodando no modelo local.
- Se uma terceira requisição chegar enquanto duas já estão em processamento, a API responde imediatamente com status HTTP 429 (*Too Many Requests*) ou evento SSE de recusa educada (*"O assistente está atendendo a capacidade máxima de consultas simultâneas no momento. Por favor, aguarde alguns instantes."*), protegendo o processador do host contra travamento.

### 2. Rate Limiting por IP (Janela Deslizante em Memória)
- Implementação de limitador de taxa nativo e leve em memória, sem necessidade de Redis ou dependências pesadas externas.
- Limite padrão: **10 consultas por minuto por endereço IP** no endpoint `POST /api/v1/chat`.
- Ao estourar o limite, retorna HTTP 429 com cabeçalho `Retry-After: 60`.

### 3. Filtro de Sanitização contra Injeção de Prompt (*Guardrail*)
- Mecanismo de inspeção prévia no payload da pergunta antes de submeter ao LCEL.
- Identificação de padrões adversariais comuns (ex.: "*ignore (all|todas|as) (previous|anteriores) (instructions|instruções)*", "*esqueça suas regras*", "*revele seu prompt de sistema*", "*dan mode*", "*jailbreak*").
- Bloqueio imediato com resposta defensiva estruturada, impedindo que o modelo seja instruído a vazar dados ou assumir persona inadequada.

### 4. Restrição de CORS e Origens Homologadas
- Substituição do wildcard irrestrito `["*"]` por lista controlada via variável de ambiente `ALLOWED_ORIGINS`.
- Padrão seguro para intranets locais: origens `localhost` e `127.0.0.1` nas portas `8000` e `8501`, além do suporte a configuração de domínios corporativos (`https://intranet.empresa.com.br`).

### 5. Cabeçalhos de Segurança HTTP (*Security Headers*)
- Inclusão de middleware que adiciona cabeçalhos defensivos a todas as respostas:
  - `X-Content-Type-Options: nosniff` (impede MIME-sniffing)
  - `X-Frame-Options: SAMEORIGIN` (protege contra clickjacking)
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `X-XSS-Protection: 1; mode=block`

### 6. Proteção de Documentação e Endpoints de Diagnóstico
- Swagger UI (`/docs`) e ReDoc (`/redoc`) desativados quando `ENABLE_DOCS=false` ou quando o ambiente estiver definido como `ENV=production`.

### 7. Suporte a Autenticação por API Key (Opcional)
- Quando a variável de ambiente `API_KEY` for definida no servidor, o endpoint `/api/v1/chat` exige o cabeçalho `X-API-Key` ou parâmetro de consulta correspondente. Se `API_KEY` não for definida, opera no modo intranet protegido pelas camadas 1 a 6.

---

## Consequências

### Positivas
- **Imunidade contra Travamento de CPU:** O host Ubuntu mantém-se fluido mesmo sob ataques volumétricos ou testes simultâneos de usuários.
- **Conformidade com Boas Práticas OWASP:** Aplicação de *Rate Limiting*, *Security Headers* e sanitização de entrada.
- **Transparência para o Usuário Legítimo:** Mensagens amigáveis de retorno em caso de fila ou termos inadequados.
- **Zero Dependências Pesadas:** Toda a proteção de concorrência e taxa foi construída com estruturas assíncronas padrão do Python (`asyncio.Semaphore`, `collections.defaultdict`), mantendo a matriz de dependências limpa.

### Negativas / Mitigações
- **Memória de Rate Limit Volátil:** O controle por IP em memória reinicia caso o servidor uvicorn seja reiniciado.
  *Mitigação:* Perfeitamente aceitável para o escopo intranet e máquinas locais de departamento.

---

## Critérios de Homologação

1. Requisições concorrentes além do limite do semáforo devem receber status HTTP 429 ou mensagem de capacidade máxima sem que a CPU do servidor trave.
2. Mais de 10 requisições do mesmo IP no intervalo de 1 minuto devem ser bloqueadas com HTTP 429.
3. Perguntas contendo injeção de prompt devem ser rejeitadas com recusa antes de acionar o Ollama.
4. Cabeçalhos de segurança (`X-Content-Type-Options`, `X-Frame-Options`) devem constar em todas as respostas HTTP.
5. Suíte de testes automatizados deve validar 100% dos controles defensivos.
