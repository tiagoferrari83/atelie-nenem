import streamlit as st
from database import query, fetch_all
from pdf_generator import gerar_pdf

st.title("📋 Orçamentos e Ordens de Serviço")
st.caption("Consulte os documentos já gerados e baixe o PDF novamente se precisar.")

# --- Filtros ---
col1, col2 = st.columns(2)
with col1:
    filtro_tipo = st.selectbox(
        "Tipo",
        options=["Todos", "orcamento", "ordem_servico"],
        format_func=lambda x: {"Todos": "Todos", "orcamento": "Orçamento", "ordem_servico": "Ordem de Serviço"}[x],
    )
with col2:
    clientes = fetch_all("clientes", order_by="nome")
    opcoes_cliente = {"Todos": None} | {c["nome"]: c["id"] for c in clientes}
    filtro_cliente = st.selectbox("Cliente", options=list(opcoes_cliente.keys()))

# --- Monta query com filtros ---
sql = """
    SELECT o.id, o.tipo, o.status, o.observacoes, o.criado_em,
           c.nome AS cliente_nome, c.telefone AS cliente_telefone,
           c.email AS cliente_email, c.endereco AS cliente_endereco
    FROM orcamentos o
    JOIN clientes c ON c.id = o.cliente_id
    WHERE 1=1
"""
params = []

if filtro_tipo != "Todos":
    sql += " AND o.tipo = %s"
    params.append(filtro_tipo)

if opcoes_cliente[filtro_cliente] is not None:
    sql += " AND o.cliente_id = %s"
    params.append(opcoes_cliente[filtro_cliente])

sql += " ORDER BY o.criado_em DESC"

documentos = query(sql, params)

st.divider()

if not documentos:
    st.info("Nenhum orçamento ou ordem de serviço encontrado.")
else:
    st.caption(f"{len(documentos)} documento(s) encontrado(s).")

    for doc in documentos:
        tipo_label = "Orçamento" if doc["tipo"] == "orcamento" else "Ordem de Serviço"
        data_fmt = doc["criado_em"].strftime("%d/%m/%Y %H:%M")

        with st.expander(f"#{doc['id']} — {tipo_label} — {doc['cliente_nome']} — {data_fmt}"):
            st.write(f"**Status:** {doc['status']}")
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
                        tipo=doc["tipo"],
                        prestador=prestador,
                        cliente=cliente,
                        itens=itens_pdf,
                        observacoes=doc["observacoes"] or "",
                    )

                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()

                    nome_arquivo = f"{doc['tipo']}_{doc['cliente_nome'].replace(' ', '_')}_{doc['id']}.pdf"

                    st.download_button(
                        label="⬇️ Baixar PDF",
                        data=pdf_bytes,
                        file_name=nome_arquivo,
                        mime="application/pdf",
                        key=f"download_{doc['id']}",
                    )
