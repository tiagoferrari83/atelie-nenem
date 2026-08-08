import streamlit as st
from database import query, fetch_all, execute, montar_grupos_orcamento
from pdf_generator import gerar_pdf
from storage import excluir_foto
from constants import TIPO_PEDIDO_LABELS, TIPO_OPERACAO_LABELS, STATUS_LABELS, STATUS_ORDEM, STATUS_CORES

st.title("📋 Orçamentos e Ordens de Serviço")
st.caption("Consulte os documentos já gerados, edite, atualize o status e baixe o PDF novamente se precisar.")

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

# --- Se um id específico foi passado (ex: clique no dashboard), força esse filtro ---
id_foco = st.session_state.pop("consultar_id_foco", None)

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

if id_foco is not None:
    sql += " AND o.id = %s"
    params.append(id_foco)
else:
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

        with st.expander(titulo_expander, expanded=(id_foco == doc["id"])):
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

            # Busca e monta os grupos (serviço + materiais) desse orçamento
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

            col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)

            with col_btn1:
                if st.button("✏️ Editar", key=f"editar_{doc['id']}"):
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
                    pagina_destino = "pages/51_Orcamento.py" if doc["tipo_operacao"] == "orcamento" else "pages/52_Ordem_Servico.py"
                    st.switch_page(pagina_destino)

            with col_btn2:
                if st.button("🔄 Gerar PDF novamente", key=f"pdf_{doc['id']}"):
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
                            key=f"download_{doc['id']}",
                        )

            with col_btn3:
                if doc["tipo_operacao"] == "orcamento":
                    if st.button("➡️ Criar OS a partir daqui", key=f"criar_os_{doc['id']}"):
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
                chave_confirmacao = f"confirmar_exclusao_{doc['id']}"
                if not st.session_state.get(chave_confirmacao):
                    if st.button("🗑️ Excluir", key=f"excluir_{doc['id']}"):
                        st.session_state[chave_confirmacao] = True
                        st.rerun()
                else:
                    st.warning("Excluir permanentemente? Essa ação não pode ser desfeita.")
                    col_conf1, col_conf2 = st.columns(2)
                    with col_conf1:
                        if st.button("Sim, excluir", key=f"confirmar_sim_{doc['id']}", type="primary"):
                            # Exclui as fotos do Storage antes de remover o registro do banco
                            fotos_do_doc = query(
                                "SELECT storage_path FROM orcamento_fotos WHERE orcamento_id = %s",
                                (doc["id"],),
                            )
                            for f in fotos_do_doc:
                                try:
                                    excluir_foto(f["storage_path"])
                                except Exception:
                                    pass
                            # O DELETE em orcamentos já remove itens e fotos em cascata (ON DELETE CASCADE)
                            execute("DELETE FROM orcamentos WHERE id = %s", (doc["id"],))
                            del st.session_state[chave_confirmacao]
                            st.success("Excluído com sucesso.")
                            st.rerun()
                    with col_conf2:
                        if st.button("Cancelar", key=f"confirmar_nao_{doc['id']}"):
                            del st.session_state[chave_confirmacao]
                            st.rerun()
