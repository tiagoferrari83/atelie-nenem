import streamlit as st
from database import query, fetch_all, execute, montar_grupos_orcamento, marcar_orcamentos_vencidos
from pdf_generator import gerar_pdf
from storage import excluir_foto
from constants import (
    TIPO_PEDIDO_LABELS,
    STATUS_LABELS, STATUS_ORDEM, STATUS_CORES,
    STATUS_ORCAMENTO_LABELS, STATUS_ORCAMENTO_ORDEM, STATUS_ORCAMENTO_CORES,
)


@st.dialog("Confirmar exclusão")
def dialog_confirmar_exclusao(doc_id, descricao):
    st.warning(f"Excluir **{descricao}** permanentemente? Essa ação não pode ser desfeita.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sim, excluir", type="primary", use_container_width=True):
            fotos_do_doc = query(
                "SELECT storage_path FROM orcamento_fotos WHERE orcamento_id = %s",
                (doc_id,),
            )
            for f in fotos_do_doc:
                try:
                    excluir_foto(f["storage_path"])
                except Exception:
                    pass
            execute("DELETE FROM orcamentos WHERE id = %s", (doc_id,))
            st.success("Excluído com sucesso.")
            st.rerun()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()


def renderizar_documento(doc, clientes, id_foco, tipo_operacao):
    """Renderiza o expander de um orçamento ou OS, com status, itens, fotos e ações."""
    is_orcamento = tipo_operacao == "orcamento"
    status_labels = STATUS_ORCAMENTO_LABELS if is_orcamento else STATUS_LABELS
    status_ordem = STATUS_ORCAMENTO_ORDEM if is_orcamento else STATUS_ORDEM
    status_cores = STATUS_ORCAMENTO_CORES if is_orcamento else STATUS_CORES

    tipo_pedido_label = TIPO_PEDIDO_LABELS.get(doc["tipo_pedido"], doc["tipo_pedido"])
    data_fmt = doc["criado_em"].strftime("%d/%m/%Y %H:%M")
    cor_status = status_cores.get(doc["status"], "")

    titulo_expander = f"{cor_status} #{doc['id']} — {tipo_pedido_label} — {doc['cliente_nome']} — {data_fmt}"

    with st.expander(titulo_expander, expanded=(id_foco == doc["id"])):
        col_status, col_datas = st.columns(2)

        with col_status:
            status_atual = doc["status"] if doc["status"] in status_ordem else status_ordem[0]
            novo_status = st.selectbox(
                "Status",
                options=status_ordem,
                index=status_ordem.index(status_atual),
                format_func=lambda x: status_labels[x],
                key=f"status_{tipo_operacao}_{doc['id']}",
            )
            if novo_status != doc["status"]:
                execute("UPDATE orcamentos SET status = %s WHERE id = %s", (novo_status, doc["id"]))
                st.rerun()

        with col_datas:
            if is_orcamento and doc["data_validade"]:
                st.write(f"**Válido até:** {doc['data_validade'].strftime('%d/%m/%Y')}")
            if not is_orcamento and doc["data_entrega"]:
                st.write(f"**Entrega prevista:** {doc['data_entrega'].strftime('%d/%m/%Y')}")

        if doc["orcamento_origem_id"]:
            st.caption(f"Gerada a partir do Orçamento #{doc['orcamento_origem_id']}")

        if doc["observacoes"]:
            st.write(f"**Observações:** {doc['observacoes']}")

        grupos = montar_grupos_orcamento(doc["id"])

        total = 0
        st.write("**Itens:**")
        for grupo in grupos:
            s = grupo["servico"]
            subtotal_grupo = s["valor_total"] + sum(m["valor_total"] for m in grupo["materiais"])
            total += subtotal_grupo

            st.write(
                f"**{s['descricao']}** — {s['quantidade']:.2f} x "
                f"R$ {s['valor_unitario']:.2f} = R$ {s['valor_total']:.2f}"
            )
            for m in grupo["materiais"]:
                st.write(
                    f"　↳ {m['descricao']}: {m['quantidade']:.2f} x "
                    f"R$ {m['valor_unitario']:.2f} = R$ {m['valor_total']:.2f}"
                )
            if grupo["materiais"]:
                st.caption(f"Subtotal do serviço: R$ {subtotal_grupo:.2f}")

        st.write(f"**Total: R$ {total:.2f}**")

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
                    if st.button("Excluir foto", key=f"del_foto_{tipo_operacao}_{foto['id']}"):
                        try:
                            excluir_foto(foto["storage_path"])
                        except Exception:
                            pass
                        execute("DELETE FROM orcamento_fotos WHERE id = %s", (foto["id"],))
                        st.rerun()

        st.divider()

        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)

        with col_btn1:
            if st.button("✏️ Editar", key=f"editar_{tipo_operacao}_{doc['id']}"):
                cliente_obj = next((c for c in clientes if c["nome"] == doc["cliente_nome"]), None)
                st.session_state["editar_orcamento"] = {
                    "orcamento_id": doc["id"],
                    "tipo_operacao": doc["tipo_operacao"],
                    "cliente_id": cliente_obj["id"] if cliente_obj else None,
                    "tipo_pedido": doc["tipo_pedido"],
                    "observacoes": doc["observacoes"],
                    "data_validade": doc["data_validade"],
                    "data_entrega": doc["data_entrega"],
                    "grupos": [
                        {"servico": g["servico"], "materiais": g["materiais"]}
                        for g in grupos
                    ],
                }
                pagina_destino = "pages/51_Orcamento.py" if is_orcamento else "pages/52_Ordem_Servico.py"
                st.switch_page(pagina_destino)

        with col_btn2:
            if st.button("🔄 Gerar PDF novamente", key=f"pdf_{tipo_operacao}_{doc['id']}"):
                prestadores = fetch_all("prestador")
                if not prestadores:
                    st.error("Cadastre o Prestador de Serviço antes de gerar o PDF.")
                else:
                    prestador_pdf = prestadores[0]
                    cliente_pdf = {
                        "nome": doc["cliente_nome"],
                        "telefone": doc["cliente_telefone"],
                        "email": doc["cliente_email"],
                        "endereco": doc["cliente_endereco"],
                    }
                    grupos_pdf = [
                        {
                            "descricao": g["servico"]["descricao"],
                            "quantidade": g["servico"]["quantidade"],
                            "valor_unitario": g["servico"]["valor_unitario"],
                            "valor_total": g["servico"]["valor_total"],
                            "materiais": g["materiais"],
                        }
                        for g in grupos
                    ]

                    pdf_path = gerar_pdf(
                        tipo=doc["tipo_operacao"],
                        prestador=prestador_pdf,
                        cliente=cliente_pdf,
                        grupos=grupos_pdf,
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
                        key=f"download_{tipo_operacao}_{doc['id']}",
                    )

        with col_btn3:
            if is_orcamento:
                if st.button("✅ Aprovar Orçamento", key=f"aprovar_{doc['id']}"):
                    # Marca o orçamento como aprovado e leva para criar a OS com os itens já preenchidos
                    execute("UPDATE orcamentos SET status = 'aprovado' WHERE id = %s", (doc["id"],))
                    cliente_obj = next((c for c in clientes if c["nome"] == doc["cliente_nome"]), None)
                    st.session_state["criar_os_de_orcamento"] = {
                        "orcamento_id": doc["id"],
                        "cliente_id": cliente_obj["id"] if cliente_obj else None,
                        "tipo_pedido": doc["tipo_pedido"],
                        "grupos": [
                            {"servico": g["servico"], "materiais": g["materiais"]}
                            for g in grupos
                        ],
                    }
                    st.switch_page("pages/52_Ordem_Servico.py")

        with col_btn4:
            if st.button("🗑️ Excluir", key=f"excluir_{tipo_operacao}_{doc['id']}"):
                descricao_doc = f"#{doc['id']} — {doc['cliente_nome']}"
                dialog_confirmar_exclusao(doc["id"], descricao_doc)


st.title("🔍 Consultar")
st.caption("Consulte os documentos já gerados, edite, atualize o status e baixe o PDF novamente se precisar.")

marcar_orcamentos_vencidos()

clientes = fetch_all("clientes", order_by="nome")

id_foco = st.session_state.pop("consultar_id_foco", None)

aba_orcamento, aba_os = st.tabs(["📝 Orçamento", "🧾 Ordem de Serviço"])

with aba_orcamento:
    col1, col2 = st.columns(2)
    with col1:
        opcoes_cliente = {"Todos": None} | {c["nome"]: c["id"] for c in clientes}
        filtro_cliente_orc = st.selectbox("Cliente", options=list(opcoes_cliente.keys()), key="filtro_cliente_orc")
    with col2:
        filtro_status_orc = st.selectbox(
            "Status",
            options=["Todos"] + STATUS_ORCAMENTO_ORDEM,
            format_func=lambda x: "Todos" if x == "Todos" else STATUS_ORCAMENTO_LABELS[x],
            key="filtro_status_orc",
        )

    sql = """
        SELECT o.id, o.tipo_operacao, o.tipo_pedido, o.status, o.observacoes,
               o.data_validade, o.data_entrega, o.orcamento_origem_id, o.criado_em,
               c.nome AS cliente_nome, c.telefone AS cliente_telefone,
               c.email AS cliente_email, c.endereco AS cliente_endereco
        FROM orcamentos o
        JOIN clientes c ON c.id = o.cliente_id
        WHERE o.tipo_operacao = 'orcamento'
    """
    params = []

    if id_foco is not None:
        sql += " AND o.id = %s"
        params.append(id_foco)
    else:
        if opcoes_cliente[filtro_cliente_orc] is not None:
            sql += " AND o.cliente_id = %s"
            params.append(opcoes_cliente[filtro_cliente_orc])
        if filtro_status_orc != "Todos":
            sql += " AND o.status = %s"
            params.append(filtro_status_orc)

    sql += " ORDER BY o.criado_em DESC"
    orcamentos_doc = query(sql, params)

    st.divider()

    if not orcamentos_doc:
        st.info("Nenhum orçamento encontrado.")
    else:
        st.caption(f"{len(orcamentos_doc)} orçamento(s) encontrado(s).")
        for doc in orcamentos_doc:
            renderizar_documento(doc, clientes, id_foco, "orcamento")

with aba_os:
    col1, col2 = st.columns(2)
    with col1:
        opcoes_cliente = {"Todos": None} | {c["nome"]: c["id"] for c in clientes}
        filtro_cliente_os = st.selectbox("Cliente", options=list(opcoes_cliente.keys()), key="filtro_cliente_os")
    with col2:
        filtro_status_os = st.selectbox(
            "Status",
            options=["Todos"] + STATUS_ORDEM,
            format_func=lambda x: "Todos" if x == "Todos" else STATUS_LABELS[x],
            key="filtro_status_os",
        )

    sql = """
        SELECT o.id, o.tipo_operacao, o.tipo_pedido, o.status, o.observacoes,
               o.data_validade, o.data_entrega, o.orcamento_origem_id, o.criado_em,
               c.nome AS cliente_nome, c.telefone AS cliente_telefone,
               c.email AS cliente_email, c.endereco AS cliente_endereco
        FROM orcamentos o
        JOIN clientes c ON c.id = o.cliente_id
        WHERE o.tipo_operacao = 'ordem_servico'
    """
    params = []

    if id_foco is not None:
        sql += " AND o.id = %s"
        params.append(id_foco)
    else:
        if opcoes_cliente[filtro_cliente_os] is not None:
            sql += " AND o.cliente_id = %s"
            params.append(opcoes_cliente[filtro_cliente_os])
        if filtro_status_os != "Todos":
            sql += " AND o.status = %s"
            params.append(filtro_status_os)

    sql += " ORDER BY o.criado_em DESC"
    os_doc = query(sql, params)

    st.divider()

    if not os_doc:
        st.info("Nenhuma ordem de serviço encontrada.")
    else:
        st.caption(f"{len(os_doc)} ordem(ns) de serviço encontrada(s).")
        for doc in os_doc:
            renderizar_documento(doc, clientes, id_foco, "ordem_servico")
