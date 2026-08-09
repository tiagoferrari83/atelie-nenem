import streamlit as st
from database import fetch_all, execute
from constants import formatar_moeda

st.title("🧵 Matéria-Prima")
st.caption("Cadastre tecidos, aviamentos e outros materiais, medidos por unidade, metro ou peso.")

TIPO_LABELS = {
    "unidade": "Por unidade",
    "metro": "Por metro",
    "peso": "Por peso (kg)",
}


@st.dialog("Editar material")
def dialog_editar_material(material):
    nome = st.text_input("Nome do material", value=material["nome"])
    tipo_medida = st.selectbox(
        "Tipo de medida",
        options=list(TIPO_LABELS.keys()),
        format_func=lambda x: TIPO_LABELS[x],
        index=list(TIPO_LABELS.keys()).index(material["tipo_medida"]),
    )
    valor = st.number_input("Valor (R$)", min_value=0.0, step=0.5, format="%.2f", value=float(material["valor"]))

    if st.button("Salvar alterações", type="primary"):
        if not nome:
            st.error("O nome é obrigatório.")
        else:
            execute(
                """
                UPDATE materia_prima
                SET nome = %s, tipo_medida = %s, valor = %s, atualizado_em = NOW()
                WHERE id = %s
                """,
                (nome, tipo_medida, valor, material["id"]),
            )
            st.success("Material atualizado!")
            st.rerun()


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

busca = st.text_input("🔎 Buscar material", placeholder="Digite o nome do material...")

materiais = fetch_all("materia_prima", order_by="nome")

if busca:
    busca_lower = busca.lower()
    materiais = [m for m in materiais if busca_lower in (m["nome"] or "").lower()]

if not materiais:
    st.info("Nenhum material encontrado." if busca else "Nenhum material cadastrado ainda.")
else:
    for m in materiais:
        with st.expander(f"{m['nome']} — R$ {formatar_moeda(float(m['valor']))} ({TIPO_LABELS[m['tipo_medida']]})"):
            data_edicao = m.get("atualizado_em") or m["criado_em"]
            st.caption(
                f"Cadastrado em {m['criado_em'].strftime('%d/%m/%Y %H:%M')} — "
                f"última edição em {data_edicao.strftime('%d/%m/%Y %H:%M')}"
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Editar", key=f"edit_materia_{m['id']}"):
                    dialog_editar_material(m)
            with col2:
                if st.button("🗑️ Excluir", key=f"del_materia_{m['id']}"):
                    execute("DELETE FROM materia_prima WHERE id = %s", (m["id"],))
                    st.rerun()
