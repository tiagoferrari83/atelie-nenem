import streamlit as st

st.title("📄 Novo")
st.caption("O que você deseja criar?")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Orçamento")
    st.write("Envie uma proposta de valores para o cliente antes de iniciar o serviço.")
    if st.button("➕ Criar Orçamento", type="primary", use_container_width=True):
        st.switch_page("pages/51_Orcamento.py")

with col2:
    st.subheader("Ordem de Serviço")
    st.write("Registre um serviço já aprovado, com prazo de entrega e acompanhamento de status.")
    if st.button("➕ Criar Ordem de Serviço", type="primary", use_container_width=True):
        st.switch_page("pages/52_Ordem_Servico.py")

st.divider()
st.caption(
    "Dica: se o cliente já aprovou um orçamento existente, use o botão "
    "\"➡️ Criar OS a partir daqui\" na tela Consultar em vez de começar do zero aqui - "
    "assim os itens do orçamento já vêm preenchidos."
)
