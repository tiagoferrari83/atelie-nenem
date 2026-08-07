import streamlit as st
from database import query, fetch_all, execute
from pdf_generator import gerar_pdf
from storage import excluir_foto
from constants import TIPO_PEDIDO_LABELS, TIPO_OPERACAO_LABELS, STATUS_LABELS, STATUS_ORDEM, STATUS_CORES

st.title("📋 Orçamentos e Ordens de Serviço")
st.caption("Consulte os documentos já gerados, atualize o status e baixe o PDF novamente se precisar.")

# --- Filtros ---
col1, col2, col3 = st.columns(3)
with col1:
    filtro_tipo_op = st.selectbox(
        "Operação",
        options=["Todos"] + list(TIPO_OPERACAO_LABELS.keys()),
        format_func=lambda x: "Todos" if x == "Todos" else TIPO_OPERACAO_LABELS[x],
    )
with col2:
    clientes = fetch_all("clientes", order_by="nome")
    opcoes_cliente = {"Todos": None} | {c["nome"]: c["id"] for c in clientes}
    filtro_cliente = st.selectbox("Cliente", options=list(opcoes_cliente.keys()))
with col3:
    filtro_status = st.selectbox(
        "Status",
        options=["Todos"] + STATUS_ORDEM,
        format_func=lambda x: "Todos" if x == "Todos" else STATUS_LABELS[x],
    )

# --- Monta query com filtros ---
sql = """
    SELECT o.id, o.tipo_operacao, o.tipo_pedido, o.status, o.observacoes,
           o.data_validade, o.data_entrega, o.orcamento_origem_id, o.criado_em,
           c.nome AS cliente_nome, c.telefone AS cliente_telefone,
           c.email AS cliente_email, c.endereco AS cliente_endereco
    FROM orcamentos o
    JOIN clientes c ON c.id = o.cliente_id
    WHERE 1=1
"""
params = []

if filtro_tipo_op != "Todos":
    sql += " AND o.tipo_operacao = %s"
    params.append(filtro_tipo_op)

if opcoes_cliente[filtro_cliente] is not None:
    sql += " AND o.cliente_id = %s"
    params.append(opcoes_cliente[filtro_cliente])

if filtro_status != "Todos":
    sql += " AND o.status = %s"
    params.append(filtro_status)

sql += " ORDER BY o.criado_em DESC"

documentos = query(sql, params)

st.divider()

if not documentos:
    st.info("Nenhum orçamento ou ordem de serviço encontrado.")
else:
    st.caption(f"{len(documentos)} documento(s) encontrado(s).")

    for doc in documentos:
        tipo_op_label = TIPO_OPERACAO_LABELS[doc["tipo_operacao"]]
        tipo_pedido_label = TIPO_PEDIDO_LABELS.get(doc["tipo_pedido"], doc["tipo_pedido"])
        data_fmt = doc["criado_em"].strftime("%d/%m/%Y %H:%M")
        cor_status = STATUS_CORES.get(doc["status"], "")

        titulo_expander = f"{cor_status} #{doc['id']} — {tipo_op_label} ({tipo_pedido_label}) — {doc['cliente_nome']} — {data_fmt}"

        with st.expander(titulo_expander):
            col_status, col_datas = st.columns(2)

            with col_status:
                status_atual = doc["status"] if doc["status"] in STATUS_ORDEM else STATUS_ORDEM[0]
                novo_status = st.selectbox(
                    "Status",
                    options=STATUS_ORDEM,
                    index=STATUS_ORDEM.index(status_atual),
                    format_func=lambda x: STATUS_LABELS[x],
                    key=f"status_{doc['id']}",
                )
                if novo_status != doc["status"]:
                    execute("UPDATE orcamentos SET status = %s WHERE id = %s", (novo_status, doc["id"]))
                    st.rerun()

            with col_datas:
                if doc["tipo_operacao"] == "orcamento" and doc["data_validade"]:
                    st.write(f"**Válido até:** {doc['data_validade'].strftime('%d/%m/%Y')}")
                if doc["tipo_operacao"] == "ordem_servico" and doc["data_entrega"]:
                    st.write(f"**Entrega prevista:** {doc['data_entrega'].strftime('%d/%m/%Y')}")

            if doc["orcamento_origem_id"]:
                st.caption(f"Gerada a partir do Orçamento #{doc['orcamento_origem_id']}")

            if doc["observacoes"]:
                st.write(f"**Observações:** {doc['observacoes']}")

            # Busca os itens desse orçamento
            itens = query(
                "SELECT descricao, quantidade, valor_unitario, valor_total FROM orcamento_itens WHERE orcamento_id = %s ORDER BY id",
                (doc["id"],),
            )

            total = sum(float(i["valor_total"]) for i in itens)

            st.write("**Itens:**")
            for i in itens:
                st.write(
                    f"- {i['descricao']}: {float(i['quantidade']):.2f} x "
                    f"R$ {float(i['valor_unitario']):.2f} = R$ {float(i['valor_total']):.2f}"
                )
            st.write(f"**Total: R$ {total:.2f}**")

            # --- Fotos anexadas ---
            fotos = query(
                "SELECT id, url, storage_path FROM orcamento_fotos WHERE orcamento_id = %s ORDER BY id",
                (doc["id"],),
            )
            if fotos:
                st.write("**Fotos de referência:**")
                cols_fotos = st.columns(min(len(fotos), 4))
                for i, foto in enumerate(fotos):
                    with cols_fotos[i % 4]:
                        st.image(foto["url"], use_container_width=True)
                        if st.button("Excluir foto", key=f"del_foto_{foto['id']}"):
                            try:
                                excluir_foto(foto["storage_path"])
                            except Exception:
                                pass  # se já não existir no storage, seguimos removendo do banco
                            execute("DELETE FROM orcamento_fotos WHERE id = %s", (foto["id"],))
                            st.rerun()

            st.divider()

            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                if st.button("🔄 Gerar PDF novamente", key=f"pdf_{doc['id']}"):
                    prestadores = fetch_all("prestador")
                    if not prestadores:
                        st.error("Cadastre o Prestador de Serviço antes de gerar o PDF.")
                    else:
                        prestador = prestadores[0]
                        cliente = {
                            "nome": doc["cliente_nome"],
                            "telefone": doc["cliente_telefone"],
                            "email": doc["cliente_email"],
                            "endereco": doc["cliente_endereco"],
                        }
                        itens_pdf = [
                            {
                                "descricao": i["descricao"],
                                "quantidade": float(i["quantidade"]),
                                "valor_unitario": float(i["valor_unitario"]),
                                "valor_total": float(i["valor_total"]),
                            }
                            for i in itens
                        ]

                        pdf_path = gerar_pdf(
                            tipo=doc["tipo_operacao"],
                            prestador=prestador,
                            cliente=cliente,
                            itens=itens_pdf,
                            observacoes=doc["observacoes"] or "",
                            tipo_pedido_label=tipo_pedido_label,
                            data_validade=doc["data_validade"],
                            data_entrega=doc["data_entrega"],
                        )

                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()

                        nome_arquivo = f"{doc['tipo_operacao']}_{doc['cliente_nome'].replace(' ', '_')}_{doc['id']}.pdf"

                        st.download_button(
                            label="⬇️ Baixar PDF",
                            data=pdf_bytes,
                            file_name=nome_arquivo,
                            mime="application/pdf",
                            key=f"download_{doc['id']}",
                        )

            with col_btn2:
                if doc["tipo_operacao"] == "orcamento":
                    if st.button("➡️ Criar Ordem de Serviço a partir daqui", key=f"criar_os_{doc['id']}"):
                        cliente_obj = next((c for c in clientes if c["nome"] == doc["cliente_nome"]), None)
                        st.session_state["criar_os_de_orcamento"] = {
                            "orcamento_id": doc["id"],
                            "cliente_id": cliente_obj["id"] if cliente_obj else None,
                            "tipo_pedido": doc["tipo_pedido"],
                            "itens": [
                                {
                                    "tipo_item": i.get("tipo_item", "servico"),
                                    "item_id": i.get("item_id", 0),
                                    "descricao": i["descricao"],
                                    "quantidade": float(i["quantidade"]),
                                    "valor_unitario": float(i["valor_unitario"]),
                                    "valor_total": float(i["valor_total"]),
                                }
                                for i in query(
                                    "SELECT * FROM orcamento_itens WHERE orcamento_id = %s ORDER BY id",
                                    (doc["id"],),
                                )
                            ],
                        }
                        st.switch_page("pages/5_Orcamento.py")
