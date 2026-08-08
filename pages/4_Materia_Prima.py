import streamlit as st
from database import fetch_all, execute

st.title("🧶 Matéria-Prima")
st.caption("Cadastre tecidos, aviamentos e outros materiais, medidos por unidade, metro ou peso.")

TIPO_LABELS = {
    "unidade": "Por unidade",
    "metro": "Por metro",
    "peso": "Por peso (kg)",
}

with st.form("form_materia", clear_on_submit=True):
    st.subheader("Novo material")
    nome = st.text_input("Nome do material")
    tipo_medida = st.selectbox(
        "Tipo de medida",
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
                INSERT INTO materia_prima (nome, tipo_medida, valor)
                VALUES (%s, %s, %s)
                """,
                (nome, tipo_medida, valor),
            )
            st.success(f"Material '{nome}' cadastrado com sucesso!")
            st.rerun()

st.divider()
st.subheader("Materiais cadastrados")

materiais = fetch_all("materia_prima", order_by="nome")

if not materiais:
    st.info("Nenhum material cadastrado ainda.")
else:
    for m in materiais:
        with st.expander(f"{m['nome']} — R$ {m['valor']:.2f} ({TIPO_LABELS[m['tipo_medida']]})"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Excluir", key=f"del_materia_{m['id']}"):
                    execute("DELETE FROM materia_prima WHERE id = %s", (m["id"],))
                    st.rerun()
