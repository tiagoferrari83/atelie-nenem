import streamlit as st
from datetime import date, timedelta
from database import query
from constants import TIPO_PEDIDO_LABELS, STATUS_LABELS, STATUS_CORES

st.title("🧵 Gestão do Ateliê")

# --- Reabertas primeiro (prioridade no dashboard) ---
reabertas = query(
    """
    SELECT o.id, o.tipo_pedido, o.data_entrega, c.nome AS cliente_nome
    FROM orcamentos o
    JOIN clientes c ON c.id = o.cliente_id
    WHERE o.tipo_operacao = 'ordem_servico' AND o.status = 'reaberta'
    ORDER BY o.criado_em DESC
    """
)

if reabertas:
    st.error(f"🔴 {len(reabertas)} Ordem(ns) de Serviço reaberta(s) — atenção!")
    for os_ in reabertas:
        entrega = f" — entrega: {os_['data_entrega'].strftime('%d/%m/%Y')}" if os_["data_entrega"] else ""
        label = f"#{os_['id']} {os_['cliente_nome']} ({TIPO_PEDIDO_LABELS.get(os_['tipo_pedido'], os_['tipo_pedido'])}){entrega}"
        if st.button(label, key=f"reaberta_{os_['id']}", use_container_width=True):
            st.session_state["consultar_id_foco"] = os_["id"]
            st.session_state["consultar_tipo_foco"] = "ordem_servico"
            st.switch_page("pages/6_Consultar.py")
    st.divider()

# --- Ordens recentes (não entregues) ---
st.subheader("📋 Ordens de Serviço em aberto")

ordens_abertas = query(
    """
    SELECT o.id, o.tipo_pedido, o.status, o.data_entrega, c.nome AS cliente_nome
    FROM orcamentos o
    JOIN clientes c ON c.id = o.cliente_id
    WHERE o.tipo_operacao = 'ordem_servico' AND o.status != 'entregue'
    ORDER BY
        CASE WHEN o.status = 'reaberta' THEN 0 ELSE 1 END,
        o.data_entrega ASC NULLS LAST
    LIMIT 10
    """
)

if not ordens_abertas:
    st.info("Nenhuma ordem de serviço em aberto no momento.")
else:
    for os_ in ordens_abertas:
        cor = STATUS_CORES.get(os_["status"], "")
        entrega = os_["data_entrega"].strftime("%d/%m/%Y") if os_["data_entrega"] else "sem data definida"
        label = (
            f"{cor} #{os_['id']} {os_['cliente_nome']} — "
            f"{TIPO_PEDIDO_LABELS.get(os_['tipo_pedido'], os_['tipo_pedido'])} — "
            f"{STATUS_LABELS.get(os_['status'], os_['status'])} — entrega: {entrega}"
        )
        if st.button(label, key=f"aberta_{os_['id']}", use_container_width=True):
            st.session_state["consultar_id_foco"] = os_["id"]
            st.session_state["consultar_tipo_foco"] = "ordem_servico"
            st.switch_page("pages/6_Consultar.py")

st.divider()

# --- Agenda: próximas entregas (7 dias) ---
st.subheader("📅 Próximas entregas (7 dias)")

limite = date.today() + timedelta(days=7)
proximas_entregas = query(
    """
    SELECT o.id, o.tipo_pedido, o.status, o.data_entrega, c.nome AS cliente_nome
    FROM orcamentos o
    JOIN clientes c ON c.id = o.cliente_id
    WHERE o.tipo_operacao = 'ordem_servico'
        AND o.status != 'entregue'
        AND o.data_entrega IS NOT NULL
        AND o.data_entrega <= %s
    ORDER BY o.data_entrega ASC
    """,
    (limite,),
)

if not proximas_entregas:
    st.info("Nenhuma entrega prevista para os próximos 7 dias.")
else:
    for os_ in proximas_entregas:
        cor = STATUS_CORES.get(os_["status"], "")
        atraso = " ⚠️ atrasada" if os_["data_entrega"] < date.today() else ""
        label = (
            f"{cor} {os_['data_entrega'].strftime('%d/%m/%Y')} — "
            f"#{os_['id']} {os_['cliente_nome']} — {TIPO_PEDIDO_LABELS.get(os_['tipo_pedido'], os_['tipo_pedido'])}{atraso}"
        )
        if st.button(label, key=f"entrega_{os_['id']}", use_container_width=True):
            st.session_state["consultar_id_foco"] = os_["id"]
            st.session_state["consultar_tipo_foco"] = "ordem_servico"
            st.switch_page("pages/6_Consultar.py")

st.divider()
st.caption("Use o menu lateral para cadastros, criação de orçamentos e consultas.")
