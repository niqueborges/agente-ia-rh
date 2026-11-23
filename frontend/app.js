/**
 * Assistente de RH — Lógica do Cliente Web (ADR-0006)
 * Comunicação direta com a API REST/SSE sem intermediários ou dependências externas.
 */

const API_BASE = "/api/v1";

document.addEventListener("DOMContentLoaded", () => {
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const sendButton = document.getElementById("send-button");
  const faqChipsContainer = document.getElementById("faq-chips");
  const statusBadge = document.getElementById("status-badge");
  const statusText = document.getElementById("status-text");

  let isGenerating = false;

  // 1. Verificar Saúde do Sistema
  async function verificarSaude() {
    try {
      const resp = await fetch(`${API_BASE}/health`);
      if (!resp.ok) throw new Error("Erro HTTP");
      const dados = await resp.json();

      if (dados.status === "ok") {
        statusBadge.className = "status-badge online";
        statusText.textContent = "Online";
      } else {
        statusBadge.className = "status-badge degraded";
        statusText.textContent = "Degradado";
      }
    } catch (err) {
      statusBadge.className = "status-badge offline";
      statusText.textContent = "Offline";
    }
  }

  // 2. Carregar Perguntas Frequentes (FAQ Chips)
  async function carregarFaq() {
    try {
      const resp = await fetch(`${API_BASE}/faq`);
      if (!resp.ok) return;
      const data = await resp.json();

      faqChipsContainer.innerHTML = "";
      data.faqs.forEach((faq) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "chip-btn";
        btn.innerHTML = `<span>${faq.icon}</span> ${faq.category}`;
        btn.title = faq.question;
        btn.addEventListener("click", () => {
          if (!isGenerating) {
            userInput.value = faq.question;
            enviarMensagem(faq.question);
          }
        });
        faqChipsContainer.appendChild(btn);
      });
    } catch (err) {
      console.warn("Não foi possível carregar FAQs dinâmicas:", err);
    }
  }

  // 3. Scroll Automático
  function rolarParaFim() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // 4. Renderizar Mensagem do Usuário
  function adicionarMensagemUsuario(texto) {
    const msgDiv = document.createElement("div");
    msgDiv.className = "message message-user";
    msgDiv.innerHTML = `
      <div class="avatar">👤</div>
      <div class="bubble">
        <p>${escaparHtml(texto)}</p>
      </div>
    `;
    chatMessages.appendChild(msgDiv);
    rolarParaFim();
  }

  // 5. Criar Bolha do Bot com Indicador de Digitação
  function criarBolhaBot() {
    const msgDiv = document.createElement("div");
    msgDiv.className = "message message-bot";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "🤖";

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const contentArea = document.createElement("div");
    contentArea.className = "bot-content";
    contentArea.innerHTML = `
      <div class="typing-indicator">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>
    `;

    bubble.appendChild(contentArea);
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);
    chatMessages.appendChild(msgDiv);
    rolarParaFim();

    return { msgDiv, bubble, contentArea };
  }

  // 6. Formatar Texto com Quebras e Listas Simples
  function formatarTextoMarkdown(texto) {
    if (!texto) return "";
    let formatado = escaparHtml(texto);
    // Negrito **texto**
    formatado = formatado.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Quebras de linha duplas viram parágrafos
    const paragrafos = formatado.split(/\n\n+/);
    return paragrafos.map((p) => `<p>${p.replace(/\n/g, "<br>")}</p>`).join("");
  }

  function escaparHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // 7. Renderizar Cartão Amigável de Fontes
  function anexarFontes(bubble, fontes) {
    if (!fontes || fontes.length === 0) return;

    const sourcesCard = document.createElement("details");
    sourcesCard.className = "sources-card";

    const resumo = document.createElement("summary");
    resumo.innerHTML = `📄 Trechos consultados no Manual de Políticas (${fontes.length})`;
    sourcesCard.appendChild(resumo);

    const lista = document.createElement("div");
    lista.className = "sources-list";

    fontes.forEach((fonte) => {
      const item = document.createElement("div");
      item.className = "source-item";
      item.innerHTML = `
        <div class="source-page">📍 Página ${fonte.page}</div>
        <div class="source-snippet">"${escaparHtml(fonte.text)}"</div>
      `;
      lista.appendChild(item);
    });

    sourcesCard.appendChild(lista);
    bubble.appendChild(sourcesCard);
    rolarParaFim();
  }

  // 8. Envio de Pergunta e Consumo via SSE
  async function enviarMensagem(pergunta) {
    if (isGenerating || !pergunta.trim()) return;

    isGenerating = true;
    sendButton.disabled = true;
    userInput.value = "";
    adicionarMensagemUsuario(pergunta);

    const { bubble, contentArea } = criarBolhaBot();
    let textoAcumulado = "";
    let fontesRecebidas = [];
    let primeiroToken = true;

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ question: pergunta, stream: true }),
      });

      if (!response.ok) {
        throw new Error(`Erro na comunicação com a API: HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const linhas = buffer.split("\n\n");
        buffer = linhas.pop() || "";

        for (const linha of linhas) {
          const trimLinha = linha.trim();
          if (!trimLinha.startsWith("data:")) continue;

          const jsonStr = trimLinha.replace(/^data:\s*/, "").trim();
          if (!jsonStr) continue;

          try {
            const evento = JSON.parse(jsonStr);

            if (evento.type === "token") {
              if (primeiroToken) {
                contentArea.innerHTML = "";
                primeiroToken = false;
              }
              textoAcumulado += evento.content;
              contentArea.innerHTML = formatarTextoMarkdown(textoAcumulado);
              rolarParaFim();
            } else if (evento.type === "sources") {
              fontesRecebidas = evento.sources || [];
            } else if (evento.type === "error") {
              contentArea.innerHTML = `<p style="color: var(--error);">⚠️ ${escaparHtml(evento.message)}</p>`;
            } else if (evento.type === "done") {
              // Finalizado
            }
          } catch (e) {
            console.error("Erro ao decodificar evento SSE:", e, jsonStr);
          }
        }
      }

      if (primeiroToken && !textoAcumulado) {
        contentArea.innerHTML = "<p>Não foi possível obter uma resposta do assistente no momento.</p>";
      }

      if (fontesRecebidas.length > 0) {
        anexarFontes(bubble, fontesRecebidas);
      }
    } catch (err) {
      contentArea.innerHTML = `<p style="color: var(--error);">⚠️ Falha ao consultar o assistente: ${escaparHtml(err.message)}</p>`;
    } finally {
      isGenerating = false;
      sendButton.disabled = false;
      userInput.focus();
      rolarParaFim();
    }
  }

  // 9. Event Listeners do Formulário
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const texto = userInput.value.trim();
    if (texto) {
      enviarMensagem(texto);
    }
  });

  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  // Inicialização
  verificarSaude();
  carregarFaq();
  userInput.focus();
});
