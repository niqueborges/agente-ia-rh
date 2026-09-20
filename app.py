"""
Assistente RAG de Políticas Internas (RH)
Aplicação interativa desenvolvida com Streamlit e LangChain.
"""

import streamlit as st
from dotenv import load_dotenv

from rag.ollama_client import obter_url_ollama, obter_embeddings, obter_llm
from rag.ingest import carregar_e_indexar_pdf
from rag.chain import criar_chain_rag

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
# Inicialização dos Recursos (Cache)
# ==========================================
@st.cache_resource(show_spinner="Indexando documento PDF no banco vetorial...")
def carregar_recursos():
    """Inicializa os embeddings e o banco vetorial FAISS com cache de recurso."""
    url_ollama = obter_url_ollama()
    embeddings = obter_embeddings(base_url=url_ollama)
    banco_vetores = carregar_e_indexar_pdf(
        caminho_pdf="data/politica_rh_exemplo.pdf",
        embeddings=embeddings,
    )
    return banco_vetores, url_ollama


# ==========================================
# Barra Lateral (Configurações)
# ==========================================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    modelos_disponiveis = [
        "mistral:7b",
        "qwen2.5-coder:7b",
        "qwen3:4b",
        "neural-chat:7b",
        "qwen2.5-coder:1.5b",
    ]
    
    modelo_selecionado = st.selectbox(
        "Modelo de Linguagem (LLM):",
        options=modelos_disponiveis,
        index=0,
        help="Modelos locais executados através do Ollama.",
    )

    temperatura = st.slider(
        "Temperatura:",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
        step=0.1,
        help="Valores mais baixos geram respostas mais diretas e factuais.",
    )

    banco_vetores, url_detectada = carregar_recursos()

    st.divider()
    st.markdown(f"**Embeddings:** `nomic-embed-text`")
    st.markdown(f"**Ollama Host:** `{url_detectada}`")

    if st.button("🗑️ Limpar conversa", width="stretch"):
        st.session_state["messages"] = []
        st.rerun()

# Inicializa a Chain RAG com o modelo selecionado
llm = obter_llm(model=modelo_selecionado, temperature=temperatura, base_url=url_detectada)
chain = criar_chain_rag(banco_vetores=banco_vetores, llm=llm, k_documentos=3)

# ==========================================
# Interface de Chat
# ==========================================
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Exibe o histórico de mensagens
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Processamento da entrada do usuário
prompt = st.chat_input("Pergunte sobre as políticas da empresa...", submit_mode="disable")
if prompt:
    # Registra e exibe a mensagem do usuário
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Gera e exibe a resposta com streaming
    with st.chat_message("assistant"):
        with st.spinner("Consultando políticas internas..."):
            stream_generator = chain.stream(prompt)
            resposta = st.write_stream(stream_generator)

    st.session_state["messages"].append({"role": "assistant", "content": resposta})
