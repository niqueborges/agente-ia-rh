# 💼 Assistente Virtual de RH — Políticas Internas

O **Assistente Virtual de RH** é uma solução inteligente desenvolvida para esclarecer dúvidas de colaboradores sobre as diretrizes, benefícios e normas da empresa (como férias, atestados, jornada de trabalho, home office e conduta), consultando diretamente o regulamento oficial interno.

> 🔒 **100% Privado e Seguro:** Todo o processamento funciona dentro do ambiente da empresa, sem enviar perguntas, documentos ou dados confidenciais para servidores externos na internet.

---

## 🧭 Como Este Manual Está Organizado

Escolha a seção adequada para o seu perfil:

- [👥 Parte 1 — Guia do Colaborador (Para Leigos)](#guia-colaborador): Como fazer perguntas, usar sugestões rápidas e conferir informações no dia a dia.
- [💼 Parte 2 — Guia do Administrador e RH (Para Gestores e TI)](#guia-administrador): Como colocar o sistema no ar, atualizar manuais e integrar à intranet da empresa.
- [🛠️ Documentação Técnica e de Engenharia](#documentacao-tecnica): Detalhes de arquitetura, código e infraestrutura para desenvolvedores e equipe de TI.

---

<a id="guia-colaborador"></a>
## 👥 Parte 1 — Guia do Colaborador (Para Leigos)

Esta parte foi feita para qualquer colaborador da empresa que precisa consultar regras ou tirar dúvidas de RH sem complicações.

### 1. O Que o Assistente Faz Por Você?
Em vez de procurar em manuais extensos de dezenas de páginas em PDF ou esperar dias por um retorno manual, você pode conversar com o assistente em linguagem comum e receber uma resposta resumida, clara e oficial em segundos.

### 2. Como Acessar
Abra o navegador no seu computador ou celular conectado à rede da empresa e acesse o endereço fornecido pelo time de RH/TI:
👉 **`http://localhost:8000/`** (ou o endereço interno de intranet da sua organização).

### 3. O Que Você Pode Perguntar?
Você pode digitar qualquer dúvida sobre o cotidiano da empresa, como por exemplo:
- *"Como funciona o período de férias e com quantos dias de antecedência devo solicitar?"*
- *"Qual é o prazo para entregar meu atestado médico e quais são os requisitos?"*
- *"Quais são as regras para o trabalho remoto ou modelo híbrido?"*
- *"Como funciona o benefício do vale-refeição e o plano de saúde?"*
- *"Como funciona a compensação de horas no banco de horas?"*
- *"Como funciona a política de reembolso para cursos ou viagens a trabalho?"*

### 4. Usando as Sugestões Rápidas (Chips)
Na parte inferior da tela, você encontrará botões com temas frequentes (🌴 **Férias**, 🏥 **Saúde e Atestados**, 🏠 **Trabalho Remoto**, 💳 **Benefícios**, ⏰ **Jornada e Ponto**). Basta clicar em um deles para fazer a pergunta instantaneamente!

### 5. Como Conferir a Resposta Oficial (Rastreabilidade)
Abaixo de cada resposta, você verá o botão:
> **📄 Trechos consultados no Manual de Políticas (Página X)**

Ao clicar nele, você visualiza o trecho exato do regulamento da empresa utilizado para responder, com o número da página correspondente. Isso garante total transparência e segurança de que a resposta não é uma "opinião", mas sim a política real da empresa.

### 6. E Se Minha Dúvida Não Estiver no Regulamento?
Se você fizer uma pergunta sobre um assunto que não esteja previsto nas regras internas da empresa, o assistente responderá educadamente que **não encontrou essa informação no manual** e orientará você a procurar o time de Recursos Humanos. Ele nunca inventa respostas!

---

<a id="guia-administrador"></a>
## 💼 Parte 2 — Guia do Administrador e RH (Para Gestores e TI)

Esta parte orienta gestores de RH e administradores de TI sobre como operar o sistema na rede da empresa, atualizar políticas e integrar a outras ferramentas.

### 1. Principais Benefícios para a Empresa
- **Redução de Chamados Repetitivos:** Resolve dúvidas rotineiras de colaboradores instantaneamente.
- **Padronização:** Garante que todos recebam exatamente a mesma orientação oficial baseada na política vigente.
- **Conformidade com a LGPD:** Os dados dos funcionários e as diretrizes corporativas permanecem restritos à infraestrutura interna da empresa.
- **Portabilidade Total:** O backend é desacoplado, permitindo que a empresa use a interface padrão ou desenvolva seu próprio portal.

### 2. Como Iniciar o Assistente na Rede Interna

#### Pré-requisitos Básicos
- Servidor ou computador Linux/Windows com **Python** e o serviço gratuito **Ollama** instalado.

#### Opção Principal: Portal da Intranet (Para Todos os Colaboradores)
Inicia o servidor web leve com a interface amigável e a API de consultas:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```
- **Acesso do Funcionário:** [`http://localhost:8000/`](http://localhost:8000/) (Chat visual amigável com chips e streaming).
- **Documentação da API:** [`http://localhost:8000/docs`](http://localhost:8000/docs) (Catálogo interativo para integrações).

#### Opção Administrativa: Console de Gestão (Streamlit)
Inicia o painel de monitoramento técnico e reindexação:
```bash
streamlit run app.py
```
- **Acesso da Gestão:** [`http://localhost:8501/`](http://localhost:8501/) (Visualização de latência, seleção de modelos e botão de reindexação).

### 3. Como Atualizar as Políticas da Empresa
Sempre que a diretoria ou o RH atualizar o manual interno:
1. Substitua o arquivo PDF em: `data/politica_rh_exemplo.pdf` (ou no caminho configurado).
2. O sistema reconhece a alteração automaticamente e atualiza o catálogo de busca inteligente sem necessidade de comandos complexos.

### 4. Como Integrar em Outras Intranets ou Portais da Empresa (Widget)
Se a sua empresa já possui uma intranet pronta (SharePoint, WordPress, portal interno em PHP, Java, React, etc.), qualquer desenvolvedor pode incluir o chat flutuante adicionando apenas **duas linhas de código HTML**:

```html
<!-- 1. Carrega o componente do assistente -->
<script src="http://servidor-rh:8000/widget.js" defer></script>

<!-- 2. Adiciona o botão de chat no rodapé da página -->
<assistente-rh-chat api-url="http://servidor-rh:8000/api/v1"></assistente-rh-chat>
```

### 5. Como Monitorar a Saúde do Sistema
- Na interface do colaborador, há um indicador visual no cabeçalho (*Online* 🟢 ou *Degradado* 🟡).
- Para monitoramento automatizado de TI, consulte o endereço:
  `GET http://localhost:8000/api/v1/health`

---

<a id="documentacao-tecnica"></a>
## 🛠️ Documentação Técnica e de Engenharia

Para desenvolvedores, engenheiros de IA e equipes de arquitetura de TI que desejam inspecionar o código-fonte, pipeline RAG ou reproduzir testes automatizados:

- 📖 **[Manual Técnico e de Arquitetura (docs/README.md)](docs/README.md):** Diagramas detalhados do pipeline LCEL, fluxo de vetorização FAISS, contratos de streaming Server-Sent Events (SSE) e governança de dependências.
- ⚖️ **[Decisões de Arquitetura — ADRs (docs/adr/)](docs/adr/README.md):** Registro das 7 decisões estruturantes (conectividade Ollama, separação de modelos, formatação pura LCEL, persistência atômica, dependências, desacoplamento de frontend e blindagem de segurança).
- 🔬 **[Benchmark e Avaliação de Qualidade (docs/avaliacao-qualidade-etapa3.md)](docs/avaliacao-qualidade-etapa3.md):** Avaliação de recuperação documental (*91.7% Context Hit Rate*) e fidelidade contra o conjunto de perguntas de referência (*Golden Dataset*).
- 🧪 **[Suíte de Testes Automatizados (tests/)](tests/):** 52 testes unitários e de integração com `pytest` cobrindo cliente, chain, persistência, endpoints REST/SSE e blindagem de segurança.
- 📋 **[Histórico de Versões e Mudanças (CHANGELOG.md)](CHANGELOG.md):** Registro detalhado das melhorias por versão segundo o padrão Keep a Changelog.
