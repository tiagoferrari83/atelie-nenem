import streamlit as st
from database import fetch_all, execute
from constants import formatar_moeda, COMPLEXIDADE_LABELS, COMPLEXIDADE_ACRESCIMO, valor_com_complexidade

st.title("✂️ Serviços")
st.caption("Cadastre os serviços oferecidos, cobrados por unidade, tempo (hora) ou metro.")

TIPO_LABELS = {
    "unidade": "Por unidade",
    "tempo": "Por tempo (hora)",
    "metro": "Por metro",
}


@st.dialog("Editar serviço")
def dialog_editar_servico(servico):
    nome = st.text_input("Nome do serviço", value=servico["nome"])
    tipo_cobranca = st.selectbox(
        "Tipo de cobrança",
        options=list(TIPO_LABELS.keys()),
        format_func=lambda x: TIPO_LABELS[x],
        index=list(TIPO_LABELS.keys()).index(servico["tipo_cobranca"]),
    )
    valor = st.number_input(
        "Valor base (R$)",
        min_value=0.0,
        step=0.5,
        format="%.2f",
        value=float(servico["valor"]),
        help="Valor sem acréscimo de complexidade. O acréscimo é aplicado na hora de adicionar ao orçamento/OS.",
    )
    complexidade_atual = int(servico.get("complexidade") or 1)
    complexidade = st.selectbox(
        "Complexidade",
        options=list(COMPLEXIDADE_LABELS.keys()),
        format_func=lambda x: COMPLEXIDADE_LABELS[x],
        index=complexidade_atual - 1,
        help="Define o acréscimo percentual aplicado sobre o valor base.",
    )

    valor_final = valor_com_complexidade(valor, complexidade)
    acrescimo = COMPLEXIDADE_ACRESCIMO[complexidade]
    if acrescimo > 0:
        st.caption(
            f"Valor com acréscimo de {int(acrescimo * 100)}%: "
            f"R$ {formatar_moeda(valor_final)}"
        )

    if st.button("Salvar alterações", type="primary"):
        if not nome:
            st.error("O nome é obrigatório.")
        else:
            execute(
                """
                UPDATE servicos
                SET nome = %s, tipo_cobranca = %s, valor = %s, complexidade = %s,
                    atualizado_em = NOW()
                WHERE id = %s
                """,
                (nome, tipo_cobranca, valor, complexidade, servico["id"]),
            )
            st.success("Serviço atualizado!")
            st.rerun()


with st.form("form_servico", clear_on_submit=True):
    st.subheader("Novo serviço")
    nome = st.text_input("Nome do serviço")
    tipo_cobranca = st.selectbox(
        "Tipo de cobrança",
        options=list(TIPO_LABELS.keys()),
        format_func=lambda x: TIPO_LABELS[x],
    )
    valor = st.number_input(
        "Valor base (R$)",
        min_value=0.0,
        step=0.5,
        format="%.2f",
        help="Valor sem acréscimo de complexidade.",
    )
    complexidade = st.selectbox(
        "Complexidade",
        options=list(COMPLEXIDADE_LABELS.keys()),
        format_func=lambda x: COMPLEXIDADE_LABELS[x],
        help="Define o acréscimo percentual aplicado sobre o valor base.",
    )

    submitted = st.form_submit_button("Cadastrar")

    if submitted:
        if not nome:
            st.error("O nome é obrigatório.")
        else:
            execute(
                """
                INSERT INTO servicos (nome, tipo_cobranca, valor, complexidade)
                VALUES (%s, %s, %s, %s)
                """,
                (nome, tipo_cobranca, valor, complexidade),
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
        complexidade = int(s.get("complexidade") or 1)
        valor_base = float(s["valor"])
        valor_final = valor_com_complexidade(valor_base, complexidade)
        acrescimo = COMPLEXIDADE_ACRESCIMO[complexidade]

        label_complexidade = COMPLEXIDADE_LABELS[complexidade]
        label_tipo = TIPO_LABELS[s["tipo_cobranca"]]

        if acrescimo > 0:
            titulo = (
                f"{s['nome']} — "
                f"R$ {formatar_moeda(valor_base)} base → "
                f"R$ {formatar_moeda(valor_final)} ({label_complexidade}) / {label_tipo}"
            )
        else:
            titulo = (
                f"{s['nome']} — "
                f"R$ {formatar_moeda(valor_base)} ({label_complexidade}) / {label_tipo}"
            )

        with st.expander(titulo):
            data_edicao = s.get("atualizado_em") or s["criado_em"]
            st.caption(
                f"Cadastrado em {s['criado_em'].strftime('%d/%m/%Y %H:%M')} — "
                f"última edição em {data_edicao.strftime('%d/%m/%Y %H:%M')}"
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Editar", key=f"edit_servico_{s['id']}"):
                    dialog_editar_servico(s)
            with col2:
                if st.button("🗑️ Excluir", key=f"del_servico_{s['id']}"):
                    execute("DELETE FROM servicos WHERE id = %s", (s["id"],))
                    st.rerun()
