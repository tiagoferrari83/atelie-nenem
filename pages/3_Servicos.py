import streamlit as st
from database import fetch_all, execute

st.title("✂️ Serviços")
st.caption("Cadastre os serviços oferecidos, cobrados por unidade, tempo (hora) ou metro.")

TIPO_LABELS = {
    "unidade": "Por unidade",
    "tempo": "Por tempo (hora)",
    "metro": "Por metro",
}

with st.form("form_servico", clear_on_submit=True):
    st.subheader("Novo serviço")
    nome = st.text_input("Nome do serviço")
    tipo_cobranca = st.selectbox(
        "Tipo de cobrança",
        options=list(TIPO_LABELS.keys()),
        format_func=lambda x: TIPO_LABELS[x],
    )
    valor = st.number_input("Valor (R$)", min_value=0.0, step=0.5, format="%.2f")

    submitted = st.form_submit_button("Cadastrar")

    if submitted:
        if not nome:
            st.error("O nome é obrigatório.")
        else:
            execute(
                """
                INSERT INTO servicos (nome, tipo_cobranca, valor)
                VALUES (%s, %s, %s)
                """,
                (nome, tipo_cobranca, valor),
            )
            st.success(f"Serviço '{nome}' cadastrado com sucesso!")
            st.rerun()

st.divider()
st.subheader("Serviços cadastrados")

busca = st.text_input("🔎 Buscar serviço", placeholder="Digite o nome do serviço...")

servicos = fetch_all("servicos", order_by="nome")

if busca:
    busca_lower = busca.lower()
    servicos = [s for s in servicos if busca_lower in (s["nome"] or "").lower()]

if not servicos:
    st.info("Nenhum serviço encontrado." if busca else "Nenhum serviço cadastrado ainda.")
else:
    for s in servicos:
        with st.expander(f"{s['nome']} — R$ {s['valor']:.2f} ({TIPO_LABELS[s['tipo_cobranca']]})"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Excluir", key=f"del_servico_{s['id']}"):
                    execute("DELETE FROM servicos WHERE id = %s", (s["id"],))
                    st.rerun()
