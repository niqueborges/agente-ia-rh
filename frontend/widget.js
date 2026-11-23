/**
 * Assistente de RH — Web Component Reutilizável (ADR-0006)
 * Permite que qualquer empresa ou intranet adicione o chat com apenas duas linhas de código:
 *
 * <script src="http://servidor:8000/static/widget.js" defer></script>
 * <assistente-rh-chat api-url="http://servidor:8000/api/v1"></assistente-rh-chat>
 */

class AssistenteRhChat extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.isOpen = false;
    this.isGenerating = false;
  }

  connectedCallback() {
    this.apiUrl = this.getAttribute("api-url") || "/api/v1";
    this.render();
    this.setupEvents();
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --widget-primary: #2563eb;
          --widget-primary-hover: #1d4ed8;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          z-index: 999999;
          position: fixed;
          bottom: 24px;
          right: 24px;
        }

        .launcher-btn {
          width: 56px;
          height: 56px;
          border-radius: 28px;
          background: var(--widget-primary);
          color: #ffffff;
          border: none;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 24px;
          transition: transform 0.2s, background 0.2s;
        }

        .launcher-btn:hover {
          background: var(--widget-primary-hover);
          transform: scale(1.05);
        }

        .chat-window {
          display: none;
          position: absolute;
          bottom: 70px;
          right: 0;
          width: 380px;
          height: 560px;
          background: #ffffff;
          border-radius: 16px;
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.18);
          border: 1px solid #e2e8f0;
          flex-direction: column;
          overflow: hidden;
        }

        .chat-window.open {
          display: flex;
        }

        .chat-header {
          background: var(--widget-primary);
          color: #ffffff;
          padding: 14px 16px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .chat-title {
          font-weight: 600;
          font-size: 0.95rem;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .close-btn {
          background: transparent;
          border: none;
          color: #ffffff;
          font-size: 20px;
          cursor: pointer;
          line-height: 1;
        }

        .messages {
          flex: 1;
          padding: 16px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 12px;
          background: #f8fafc;
        }

        .bubble {
          padding: 10px 14px;
          border-radius: 12px;
          font-size: 0.88rem;
          line-height: 1.4;
          max-width: 85%;
        }

        .bubble-bot {
          background: #ffffff;
          border: 1px solid #e2e8f0;
          align-self: flex-start;
          color: #1e293b;
        }

        .bubble-user {
          background: var(--widget-primary);
          color: #ffffff;
          align-self: flex-end;
        }

        .sources {
          margin-top: 8px;
          font-size: 0.75rem;
          color: #64748b;
          border-top: 1px dashed #cbd5e1;
          padding-top: 4px;
        }

        .input-bar {
          padding: 12px;
          background: #ffffff;
          border-top: 1px solid #e2e8f0;
          display: flex;
          gap: 8px;
        }

        .input-field {
          flex: 1;
          border: 1px solid #cbd5e1;
          border-radius: 8px;
          padding: 8px 12px;
          font-size: 0.88rem;
          outline: none;
        }

        .input-field:focus {
          border-color: var(--widget-primary);
        }

        .send-btn {
          background: var(--widget-primary);
          color: #ffffff;
          border: none;
          border-radius: 8px;
          padding: 0 14px;
          cursor: pointer;
          font-weight: 500;
        }

        .send-btn:disabled {
          background: #cbd5e1;
          cursor: not-allowed;
        }
      </style>

      <div class="chat-window" id="window">
        <div class="chat-header">
          <div class="chat-title">💼 Assistente de RH</div>
          <button class="close-btn" id="close">&times;</button>
        </div>
        <div class="messages" id="messages">
          <div class="bubble bubble-bot">
            Olá! Sou o Assistente de RH da empresa. Como posso te ajudar hoje?
          </div>
        </div>
        <div class="input-bar">
          <input type="text" class="input-field" id="input" placeholder="Digite sua dúvida..." />
          <button class="send-btn" id="send">Enviar</button>
        </div>
      </div>

      <button class="launcher-btn" id="launcher" title="Abrir Chat de RH">💼</button>
    `;
  }

  setupEvents() {
    const launcher = this.shadowRoot.getElementById("launcher");
    const closeBtn = this.shadowRoot.getElementById("close");
    const windowEl = this.shadowRoot.getElementById("window");
    const input = this.shadowRoot.getElementById("input");
    const sendBtn = this.shadowRoot.getElementById("send");
    const messages = this.shadowRoot.getElementById("messages");

    launcher.addEventListener("click", () => {
      this.isOpen = !this.isOpen;
      windowEl.classList.toggle("open", this.isOpen);
      if (this.isOpen) input.focus();
    });

    closeBtn.addEventListener("click", () => {
      this.isOpen = false;
      windowEl.classList.remove("open");
    });

    const enviar = async () => {
      const texto = input.value.trim();
      if (!texto || this.isGenerating) return;

      this.isGenerating = true;
      sendBtn.disabled = true;
      input.value = "";

      // Mensagem do usuário
      const userBubble = document.createElement("div");
      userBubble.className = "bubble bubble-user";
      userBubble.textContent = texto;
      messages.appendChild(userBubble);
      messages.scrollTop = messages.scrollHeight;

      // Mensagem do bot (streaming)
      const botBubble = document.createElement("div");
      botBubble.className = "bubble bubble-bot";
      botBubble.textContent = "Digitando...";
      messages.appendChild(botBubble);
      messages.scrollTop = messages.scrollHeight;

      let acumulado = "";
      let fontes = [];

      try {
        const resp = await fetch(`${this.apiUrl}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify({ question: texto, stream: true }),
        });

        if (!resp.ok) throw new Error("Erro de conexão");

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";

          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith("data:")) continue;
            const dataStr = line.replace(/^data:\s*/, "");
            try {
              const ev = JSON.parse(dataStr);
              if (ev.type === "token") {
                if (acumulado === "") botBubble.textContent = "";
                acumulado += ev.content;
                botBubble.textContent = acumulado;
                messages.scrollTop = messages.scrollHeight;
              } else if (ev.type === "sources") {
                fontes = ev.sources || [];
              }
            } catch (e) {}
          }
        }

        if (fontes.length > 0) {
          const sourcesDiv = document.createElement("div");
          sourcesDiv.className = "sources";
          sourcesDiv.textContent = `Fontes: Páginas ${fontes.map((f) => f.page).join(", ")}`;
          botBubble.appendChild(sourcesDiv);
        }
      } catch (err) {
        botBubble.textContent = "Desculpe, ocorreu um erro ao consultar as políticas internas.";
      } finally {
        this.isGenerating = false;
        sendBtn.disabled = false;
        messages.scrollTop = messages.scrollHeight;
      }
    };

    sendBtn.addEventListener("click", enviar);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") enviar();
    });
  }
}

customElements.define("assistente-rh-chat", AssistenteRhChat);
