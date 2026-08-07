import streamlit as st
from database import fetch_all, execute
from pdf_generator import gerar_pdf

st.title("📄 Orçamento / Ordem de Serviço")

# --- Verificações iniciais ---
prestadores = fetch_all("prestador")
if not prestadores:
    st.warning("Cadastre primeiro o Prestador de Serviço na página correspondente.")
    st.stop()
prestador = prestadores[0]

clientes = fetch_all("clientes", order_by="nome")
if not clientes:
    st.warning("Cadastre pelo menos um cliente antes de criar um orçamento.")
    st.stop()

servicos = fetch_all("servicos", order_by="nome")
materiais = fetch_all("materia_prima", order_by="nome")

if not servicos and not materiais:
    st.warning("Cadastre ao menos um serviço ou material antes de criar um orçamento.")
    st.stop()

# --- Estado da sessão para os itens adicionados ---
if "itens_orcamento" not in st.session_state:
    st.session_state.itens_orcamento = []

# --- Seleção do tipo de documento e cliente ---
tipo_doc = st.radio("Tipo de documento", options=["orcamento", "ordem_servico"],
                     format_func=lambda x: "Orçamento" if x == "orcamento" else "Ordem de Serviço",
                     horizontal=True)

cliente_opcoes = {c["nome"]: c for c in clientes}
cliente_nome = st.selectbox("Cliente", options=list(cliente_opcoes.keys()))
cliente_selecionado = cliente_opcoes[cliente_nome]

st.divider()
st.subheader("Adicionar itens")

TIPO_LABELS_SERVICO = {"unidade": "un.", "tempo": "h", "metro": "m"}
TIPO_LABELS_MATERIAL = {"unidade": "un.", "metro": "m", "peso": "kg"}

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Serviço**")
    if servicos:
        servico_opcoes = {f"{s['nome']} (R$ {s['valor']:.2f}/{TIPO_LABELS_SERVICO[s['tipo_cobranca']]})": s for s in servicos}
        servico_escolhido = st.selectbox("Selecione o serviço", options=list(servico_opcoes.keys()), key="sel_servico")
        qtd_servico = st.number_input("Quantidade", min_value=0.0, step=0.5, key="qtd_servico")
        if st.button("Adicionar serviço"):
            s = servico_opcoes[servico_escolhido]
            if qtd_servico > 0:
                st.session_state.itens_orcamento.append({
                    "tipo_item": "servico",
                    "item_id": s["id"],
                    "descricao": s["nome"],
                    "quantidade": qtd_servico,
                    "valor_unitario": float(s["valor"]),
                    "valor_total": float(s["valor"]) * qtd_servico,
                })
                st.rerun()
            else:
                st.error("Informe uma quantidade maior que zero.")
    else:
        st.caption("Nenhum serviço cadastrado.")

with col2:
    st.markdown("**Matéria-Prima**")
    if materiais:
        material_opcoes = {f"{m['nome']} (R$ {m['valor']:.2f}/{TIPO_LABELS_MATERIAL[m['tipo_medida']]})": m for m in materiais}
        material_escolhido = st.selectbox("Selecione o material", options=list(material_opcoes.keys()), key="sel_material")
        qtd_material = st.number_input("Quantidade", min_value=0.0, step=0.5, key="qtd_material")
        if st.button("Adicionar material"):
            m = material_opcoes[material_escolhido]
            if qtd_material > 0:
                st.session_state.itens_orcamento.append({
                    "tipo_item": "materia_prima",
                    "item_id": m["id"],
                    "descricao": m["nome"],
                    "quantidade": qtd_material,
                    "valor_unitario": float(m["valor"]),
                    "valor_total": float(m["valor"]) * qtd_material,
                })
                st.rerun()
            else:
                st.error("Informe uma quantidade maior que zero.")
    else:
        st.caption("Nenhum material cadastrado.")

st.divider()
st.subheader("Itens adicionados")

if not st.session_state.itens_orcamento:
    st.info("Nenhum item adicionado ainda.")
else:
    total = 0
    for idx, item in enumerate(st.session_state.itens_orcamento):
        col_a, col_b = st.columns([5, 1])
        with col_a:
            st.write(
                f"**{item['descricao']}** — {item['quantidade']:.2f} x "
                f"R$ {item['valor_unitario']:.2f} = R$ {item['valor_total']:.2f}"
            )
        with col_b:
            if st.button("Remover", key=f"rem_{idx}"):
                st.session_state.itens_orcamento.pop(idx)
                st.rerun()
        total += item["valor_total"]

    st.markdown(f"### Total: R$ {total:.2f}")

observacoes = st.text_area("Observações (opcional)")

st.divider()

if st.button("💾 Salvar e Gerar PDF", type="primary", disabled=not st.session_state.itens_orcamento):
    # Salva o cabeçalho do orçamento
    resultado = execute(
        """
        INSERT INTO orcamentos (cliente_id, tipo, observacoes)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (cliente_selecionado["id"], tipo_doc, observacoes),
    )
    orcamento_id = resultado["id"]

    # Salva os itens
    for item in st.session_state.itens_orcamento:
        execute(
            """
            INSERT INTO orcamento_itens
                (orcamento_id, tipo_item, item_id, descricao, quantidade, valor_unitario, valor_total)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                orcamento_id, item["tipo_item"], item["item_id"], item["descricao"],
                item["quantidade"], item["valor_unitario"], item["valor_total"],
            ),
        )

    # Gera o PDF
    pdf_path = gerar_pdf(
        tipo=tipo_doc,
        prestador=prestador,
        cliente=cliente_selecionado,
        itens=st.session_state.itens_orcamento,
        observacoes=observacoes,
    )

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    nome_arquivo = f"{'orcamento' if tipo_doc == 'orcamento' else 'ordem_servico'}_{cliente_selecionado['nome'].replace(' ', '_')}.pdf"

    st.success("Documento salvo e PDF gerado com sucesso!")
    st.download_button(
        label="⬇️ Baixar PDF",
        data=pdf_bytes,
        file_name=nome_arquivo,
        mime="application/pdf",
    )

    st.session_state.itens_orcamento = []
