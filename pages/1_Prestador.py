import streamlit as st
from database import fetch_all, execute

st.title("🏢 Prestador de Serviço")
st.caption("Dados da sua empresa/ateliê, usados no cabeçalho dos PDFs.")

prestadores = fetch_all("prestador")
existente = prestadores[0] if prestadores else None

if existente:
    st.success("Prestador já cadastrado. Você pode atualizar os dados abaixo.")

with st.form("form_prestador"):
    nome = st.text_input("Nome / Razão Social", value=existente["nome"] if existente else "")
    telefone = st.text_input("Telefone", value=existente["telefone"] if existente else "")
    email = st.text_input("Email", value=existente["email"] if existente else "")
    cnpj = st.text_input("CNPJ", value=existente["cnpj"] if existente else "")

    st.divider()
    st.subheader("Logotipo")
    logo_file = st.file_uploader("Logo da empresa (opcional)", type=["png", "jpg", "jpeg"], key="upload_logo")

    st.divider()
    st.subheader("Cláusulas do Orçamento")
    st.caption(
        "Texto exibido na última página do PDF de Orçamento, após as fotos. "
        "Use para condições gerais, prazo de pagamento, política de alterações, etc."
    )
    clausulas = st.text_area(
        "Cláusulas",
        value=existente["clausulas"] if existente and existente.get("clausulas") else "",
        height=250,
        placeholder="Ex:\n1. O prazo de entrega começa a contar após a aprovação e pagamento do sinal.\n"
                    "2. Alterações solicitadas após o início da produção poderão gerar custos adicionais.\n"
                    "3. ...",
    )

    submitted = st.form_submit_button("Salvar")

    if submitted:
        if not nome:
            st.error("O nome é obrigatório.")
        else:
            if logo_file:
                logo_bytes = logo_file.read()
            elif existente and existente.get("logo"):
                logo_bytes = bytes(existente["logo"])
            else:
                logo_bytes = None

            if existente:
                execute(
                    """
                    UPDATE prestador
                    SET nome = %s, telefone = %s, email = %s, cnpj = %s,
                        logo = %s, clausulas = %s
                    WHERE id = %s
                    """,
                    (nome, telefone, email, cnpj, logo_bytes,
                     clausulas or None, existente["id"]),
                )
            else:
                execute(
                    """
                    INSERT INTO prestador (nome, telefone, email, cnpj, logo, clausulas)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (nome, telefone, email, cnpj, logo_bytes, clausulas or None),
                )
            st.cache_data.clear()
            st.success("Dados salvos com sucesso!")
            st.rerun()

# Pré-visualização do logotipo atual fora do form
if existente and existente.get("logo"):
    st.subheader("Logo atual")
    st.image(bytes(existente["logo"]), width=150)

