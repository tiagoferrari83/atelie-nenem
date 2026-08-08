import streamlit as st
from database import fetch_all, execute

st.title("👤 Clientes")


@st.dialog("Editar cliente")
def dialog_editar_cliente(cliente):
    nome = st.text_input("Nome", value=cliente["nome"])
    telefone = st.text_input("Telefone", value=cliente["telefone"] or "")
    email = st.text_input("Email", value=cliente["email"] or "")
    endereco = st.text_area("Endereço", value=cliente["endereco"] or "")

    if st.button("Salvar alterações", type="primary"):
        if not nome:
            st.error("O nome é obrigatório.")
        else:
            execute(
                """
                UPDATE clientes
                SET nome = %s, telefone = %s, email = %s, endereco = %s, atualizado_em = NOW()
                WHERE id = %s
                """,
                (nome, telefone, email, endereco, cliente["id"]),
            )
            st.success("Cliente atualizado!")
            st.rerun()


with st.form("form_cliente", clear_on_submit=True):
    st.subheader("Novo cliente")
    nome = st.text_input("Nome")
    telefone = st.text_input("Telefone")
    email = st.text_input("Email")
    endereco = st.text_area("Endereço")

    submitted = st.form_submit_button("Cadastrar")

    if submitted:
        if not nome:
            st.error("O nome é obrigatório.")
        else:
            execute(
                """
                INSERT INTO clientes (nome, telefone, email, endereco)
                VALUES (%s, %s, %s, %s)
                """,
                (nome, telefone, email, endereco),
            )
            st.success(f"Cliente '{nome}' cadastrado com sucesso!")
            st.rerun()

st.divider()
st.subheader("Clientes cadastrados")

busca = st.text_input("🔎 Buscar cliente", placeholder="Digite o nome, telefone ou email...")

clientes = fetch_all("clientes", order_by="nome")

if busca:
    busca_lower = busca.lower()
    clientes = [
        c for c in clientes
        if busca_lower in (c["nome"] or "").lower()
        or busca_lower in (c["telefone"] or "").lower()
        or busca_lower in (c["email"] or "").lower()
    ]

if not clientes:
    st.info("Nenhum cliente encontrado." if busca else "Nenhum cliente cadastrado ainda.")
else:
    for c in clientes:
        with st.expander(f"{c['nome']}"):
            st.write(f"**Telefone:** {c['telefone'] or '-'}")
            st.write(f"**Email:** {c['email'] or '-'}")
            st.write(f"**Endereço:** {c['endereco'] or '-'}")
            st.caption(
                f"Cadastrado em {c['criado_em'].strftime('%d/%m/%Y %H:%M')} — "
                f"última edição em {c['atualizado_em'].strftime('%d/%m/%Y %H:%M')}"
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Editar", key=f"edit_cliente_{c['id']}"):
                    dialog_editar_cliente(c)
            with col2:
                if st.button("🗑️ Excluir", key=f"del_cliente_{c['id']}"):
                    execute("DELETE FROM clientes WHERE id = %s", (c["id"],))
                    st.rerun()
