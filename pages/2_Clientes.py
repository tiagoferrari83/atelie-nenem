import streamlit as st
from database import fetch_all, query, execute
from storage import excluir_foto

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


def _excluir_cliente_e_documentos(cliente_id, documentos_vinculados):
    """
    Apaga o cliente e todos os orçamentos/OS vinculados a ele.
    cliente_id em orcamentos NÃO tem ON DELETE CASCADE (de propósito, para não
    apagar documentos sem aviso em nenhum outro fluxo) - por isso os orçamentos
    precisam ser apagados explicitamente aqui, antes do cliente. Cada orçamento
    apagado já leva junto seus itens e fotos no banco (essas sim têm cascade).
    Só as fotos no Storage (fora do Postgres) precisam ser limpas manualmente.
    """
    for doc in documentos_vinculados:
        fotos_do_doc = query(
            "SELECT storage_path FROM orcamento_fotos WHERE orcamento_id = %s",
            (doc["id"],),
        )
        for f in fotos_do_doc:
            try:
                excluir_foto(f["storage_path"])
            except Exception:
                pass
        execute("DELETE FROM orcamentos WHERE id = %s", (doc["id"],))

    execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))


@st.dialog("Excluir cliente")
def dialog_excluir_cliente(cliente):
    documentos_vinculados = query(
        """
        SELECT id, tipo_operacao, tipo_pedido, criado_em
        FROM orcamentos
        WHERE cliente_id = %s
        ORDER BY criado_em DESC
        """,
        (cliente["id"],),
    )

    if not documentos_vinculados:
        st.warning(f"Excluir **{cliente['nome']}** permanentemente? Essa ação não pode ser desfeita.")
    else:
        n_orcamentos = sum(1 for d in documentos_vinculados if d["tipo_operacao"] == "orcamento")
        n_os = sum(1 for d in documentos_vinculados if d["tipo_operacao"] == "ordem_servico")
        partes = []
        if n_orcamentos:
            partes.append(f"{n_orcamentos} orçamento(s)")
        if n_os:
            partes.append(f"{n_os} ordem(ns) de serviço")
        st.warning(
            f"**{cliente['nome']}** tem {' e '.join(partes)} vinculado(s). "
            f"Excluir o cliente vai apagar **também** todos esses documentos "
            f"(itens e fotos inclusos). Essa ação não pode ser desfeita."
        )
        with st.expander("Ver documentos que serão apagados"):
            for d in documentos_vinculados:
                tipo_label = "Orçamento" if d["tipo_operacao"] == "orcamento" else "Ordem de Serviço"
                st.write(f"- #{d['id']} — {tipo_label} — {d['criado_em'].strftime('%d/%m/%Y')}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sim, excluir tudo" if documentos_vinculados else "Sim, excluir", type="primary", width='stretch'):
            _excluir_cliente_e_documentos(cliente["id"], documentos_vinculados)
            st.success("Excluído com sucesso.")
            st.rerun()
    with col2:
        if st.button("Cancelar", width='stretch'):
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
            data_edicao = c.get("atualizado_em") or c["criado_em"]
            st.caption(
                f"Cadastrado em {c['criado_em'].strftime('%d/%m/%Y %H:%M')} — "
                f"última edição em {data_edicao.strftime('%d/%m/%Y %H:%M')}"
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Editar", key=f"edit_cliente_{c['id']}"):
                    dialog_editar_cliente(c)
            with col2:
                if st.button("🗑️ Excluir", key=f"del_cliente_{c['id']}"):
                    dialog_excluir_cliente(c)
