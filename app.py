import streamlit as st
from database import init_db

st.set_page_config(
    page_title="Ateliê - Gestão",
    page_icon="🧵",
    layout="centered",
)

# Cria as tabelas no banco (se ainda não existirem) toda vez que o app sobe
try:
    init_db()
except Exception as e:
    st.error(f"Erro ao conectar/preparar o banco de dados: {e}")
    st.stop()

st.title("🧵 Gestão do Ateliê")
st.write("Use o menu lateral para navegar entre os cadastros e a geração de orçamentos/ordens de serviço.")

st.info(
    "Comece cadastrando o **Prestador de Serviço** (dados da sua empresa), "
    "depois clientes, serviços e matéria-prima."
)
