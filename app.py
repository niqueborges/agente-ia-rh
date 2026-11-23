"""
Assistente RAG de Políticas Internas (RH) — Versão 2.0
Aplicação interativa desenvolvida com Streamlit e LangChain.
Implementa governança de dependências (ADR-0005), conectividade determinística (ADR-0001),
catálogo dinâmico (ADR-0002), formatação de contexto LCEL (ADR-0003) e persistência FAISS (ADR-0004).
"""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from rag.chain import criar_chain_rag
from rag.ingest import carregar_ou_criar_indice
from rag.ollama_client import (
    MODELO_CHAT_PADRAO,
    MODELO_EMBEDDINGS_PADRAO,
    OllamaConfigurationError,
    listar_modelos_chat,
    obter_embeddings,
    obter_llm,
    obter_url_ollama,
    verificar_conexao_ollama,
)

load_dotenv()

# ==========================================
# Configuração da Página
# ==========================================
st.set_page_config(
    page_title="Assistente de RH — Políticas Internas",
    page_icon="💼",
    layout="centered",
)

st.title("💼 Assistente de RH — Políticas Internas")
st.caption("Consulte informações sobre benefícios, férias, jornada e políticas da empresa (100% local e privado).")

# ==========================================
# Verificação de Conectividade do Ollama (ADR-0001)
# ==========================================
try:
    url_ollama = obter_url_ollama()
except OllamaConfigurationError as exc:
    st.error(f"❌ **Erro de Configuração do Ollama:** {exc}")
    st.info("Verifique a variável de ambiente `OLLAMA_BASE_URL` ou mantenha o padrão `http://127.0.0.1:11434`.")
    st.stop()

if not verificar_conexao_ollama(url_ollama, timeout=1.5):
    st.error(
        f"❌ **Servidor Ollama indisponível em `{url_ollama}`.**\n\n"
        "Certifique-se de que o serviço está ativo no sistema executando:\n"
        "```bash\nsudo systemctl status ollama\n```"
    )
    st.stop()


# ==========================================
# Inicialização dos Recursos Vetoriais (ADR-0004)
# ==========================================
@st.cache_resource(show_spinner="Carregando índice vetorial FAISS...")
def carregar_recursos(base_url: str):
    """Inicializa os embeddings e o índice vetorial FAISS com cache de recurso e persistência atômica."""
    embeddings = obter_embeddings(base_url=base_url)
    banco_vetores = carregar_ou_criar_indice(
        caminho_pdf="data/politica_rh_exemplo.pdf",
        embeddings=embeddings,
    )
    return banco_vetores


try:
    banco_vetores = carregar_recursos(url_ollama)
except Exception as exc:
    st.error(f"❌ **Erro ao inicializar o banco vetorial FAISS:** {exc}")
    st.stop()


# ==========================================
# Barra Lateral (Catálogo Dinâmico e Controles) (ADR-0002)
# ==========================================
with st.sidebar:
    st.header("⚙️ Configurações")

    modelos_chat = listar_modelos_chat(base_url=url_ollama)
    if not modelos_chat:
        st.error(
            "Nenhum modelo conversacional detectado no Ollama.\n\n"
            "Instale o modelo padrão recomendado executando:\n"
            "```bash\nollama pull qwen3.5:4b\n```"
        )
        st.stop()

    # Seleciona o modelo recomendado com base no benchmark empírico (Etapa 3)
    indice_padrao = 0
    if "llama3.1:8b" in modelos_chat:
        indice_padrao = modelos_chat.index("llama3.1:8b")
    elif MODELO_CHAT_PADRAO in modelos_chat:
        indice_padrao = modelos_chat.index(MODELO_CHAT_PADRAO)

    modelo_selecionado = st.selectbox(
        "Modelo de Linguagem (LLM):",
        options=modelos_chat,
        index=indice_padrao,
        help="Modelos conversacionais detectados dinamicamente no Ollama local.",
    )

    temperatura = st.slider(
        "Temperatura:",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
        step=0.1,
        help="Valores mais baixos geram respostas mais diretas e factuais.",
    )

    k_documentos = st.slider(
        "Trechos recuperados ($k$):",
        min_value=1,
        max_value=5,
        value=3,
        step=1,
        help="Quantidade de fatias mais relevantes recuperadas do PDF.",
    )

    st.divider()
    st.markdown(f"**Embeddings:** `{MODELO_EMBEDDINGS_PADRAO}`")
    st.markdown(f"**Ollama Host:** `{url_ollama}`")
    st.markdown(f"**Fatias no Índice:** `{banco_vetores.index.ntotal}`")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🗑️ Limpar chat", width="stretch"):
            st.session_state["messages"] = []
            st.rerun()
    with col_btn2:
        if st.button("🔄 Reindexar", width="stretch", help="Força a recriação do índice FAISS a partir do PDF."):
            st.cache_resource.clear()
            carregar_ou_criar_indice(
                caminho_pdf="data/politica_rh_exemplo.pdf",
                embeddings=obter_embeddings(base_url=url_ollama),
                forcar_reindexacao=True,
            )
            st.success("Índice reindexado com sucesso!")
            st.rerun()


# ==========================================
# Inicialização da Chain RAG (ADR-0003)
# ==========================================
llm = obter_llm(model=modelo_selecionado, temperature=temperatura, base_url=url_ollama)
chain = criar_chain_rag(banco_vetores=banco_vetores, llm=llm, k_documentos=k_documentos)


# ==========================================
# Interface de Chat Interativo
# ==========================================
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Exibe o histórico de mensagens
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sources" in msg and msg["sources"]:
            with st.expander("📄 Trechos consultados"):
                for idx, src in enumerate(msg["sources"], start=1):
                    st.markdown(f"**Trecho {idx} (Página {src.get('page', '?')}):**\n>{src.get('text', '')}")

# Processamento da entrada do usuário
prompt = st.chat_input("Pergunte sobre as políticas da empresa...", submit_mode="disable")
if prompt:
    # Registra e exibe a pergunta
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Recupera trechos para rastreabilidade de fontes
    docs_recuperados = banco_vetores.similarity_search(prompt, k=k_documentos)
    fontes = [
        {"page": doc.metadata.get("page", 0) + 1, "text": doc.page_content.strip()}
        for doc in docs_recuperados
    ]

    # Gera e exibe a resposta com streaming
    with st.chat_message("assistant"):
        with st.spinner("Consultando políticas internas..."):
            stream_generator = chain.stream(prompt)
            resposta = st.write_stream(stream_generator)

        with st.expander("📄 Trechos consultados"):
            for idx, src in enumerate(fontes, start=1):
                st.markdown(f"**Trecho {idx} (Página {src['page']}):**\n>{src['text']}")

    st.session_state["messages"].append({"role": "assistant", "content": resposta, "sources": fontes})
