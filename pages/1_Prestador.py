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
    st.subheader("Imagens")
    logo_file = st.file_uploader("Logo (opcional)", type=["png", "jpg", "jpeg"], key="upload_logo")
    assinatura_file = st.file_uploader(
        "Assinatura (opcional)",
        type=["png", "jpg", "jpeg"],
        key="upload_assinatura",
        help="Imagem usada no campo de assinatura do Prestador nos PDFs. "
             "Recomendado: fundo transparente (PNG) ou branco, proporção paisagem.",
    )

    st.divider()
    st.subheader("Cláusulas do Orçamento")
    st.caption(
        "Texto exibido na última página do PDF de Orçamento, após as fotos. "
        "Use para condições gerais, prazo de pagamento, política de alterações, etc."
    )
    clausulas = st.text_area(
        "Cláusulas",
        value=existente["clausulas"] if existente and existente.get("clausulas") else "",
        height=200,
        max_chars=3000,
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

            if assinatura_file:
                assinatura_bytes = assinatura_file.read()
            elif existente and existente.get("assinatura"):
                assinatura_bytes = bytes(existente["assinatura"])
            else:
                assinatura_bytes = None

            if existente:
                execute(
                    """
                    UPDATE prestador
                    SET nome = %s, telefone = %s, email = %s, cnpj = %s,
                        logo = %s, assinatura = %s, clausulas = %s
                    WHERE id = %s
                    """,
                    (nome, telefone, email, cnpj, logo_bytes, assinatura_bytes,
                     clausulas or None, existente["id"]),
                )
            else:
                execute(
                    """
                    INSERT INTO prestador (nome, telefone, email, cnpj, logo, assinatura, clausulas)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (nome, telefone, email, cnpj, logo_bytes, assinatura_bytes, clausulas or None),
                )
            st.success("Dados salvos com sucesso!")
            st.rerun()

# Pré-visualização das imagens atuais fora do form
if existente:
    col_logo, col_assin = st.columns(2)
    with col_logo:
        if existente.get("logo"):
            st.subheader("Logo atual")
            st.image(bytes(existente["logo"]), width=150)
    with col_assin:
        if existente.get("assinatura"):
            st.subheader("Assinatura atual")
            st.image(bytes(existente["assinatura"]), width=200)
