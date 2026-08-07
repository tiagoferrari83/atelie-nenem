import streamlit as st
from database import fetch_all, execute

st.title("🏢 Prestador de Serviço")
st.caption("Dados da sua empresa/ateliê, usados no cabeçalho dos PDFs.")

# Verifica se já existe um prestador cadastrado
prestadores = fetch_all("prestador")
existente = prestadores[0] if prestadores else None

if existente:
    st.success("Prestador já cadastrado. Você pode atualizar os dados abaixo.")

with st.form("form_prestador"):
    nome = st.text_input("Nome / Razão Social", value=existente["nome"] if existente else "")
    telefone = st.text_input("Telefone", value=existente["telefone"] if existente else "")
    email = st.text_input("Email", value=existente["email"] if existente else "")
    cnpj = st.text_input("CNPJ", value=existente["cnpj"] if existente else "")
    logo_file = st.file_uploader("Logo (opcional)", type=["png", "jpg", "jpeg"])

    submitted = st.form_submit_button("Salvar")

    if submitted:
        if not nome:
            st.error("O nome é obrigatório.")
        else:
            logo_bytes = logo_file.read() if logo_file else (existente["logo"] if existente else None)

            if existente:
                execute(
                    """
                    UPDATE prestador
                    SET nome = %s, telefone = %s, email = %s, cnpj = %s, logo = %s
                    WHERE id = %s
                    """,
                    (nome, telefone, email, cnpj, logo_bytes, existente["id"]),
                )
            else:
                execute(
                    """
                    INSERT INTO prestador (nome, telefone, email, cnpj, logo)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (nome, telefone, email, cnpj, logo_bytes),
                )
            st.success("Dados salvos com sucesso!")
            st.rerun()

if existente and existente["logo"]:
    st.subheader("Logo atual")
    st.image(existente["logo"], width=150)
