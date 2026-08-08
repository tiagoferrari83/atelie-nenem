import streamlit as st
from datetime import date, timedelta
from database import fetch_all_cached, execute
from pdf_generator import gerar_pdf
from storage import upload_foto
from constants import TIPO_PEDIDO_LABELS, TIPO_LABELS_SERVICO, TIPO_LABELS_MATERIAL

st.title("📄 Novo Orçamento / Ordem de Serviço")

# --- Se veio de "criar OS a partir de orçamento", pega os dados pré-carregados ---
origem = st.session_state.pop("criar_os_de_orcamento", None)

# --- Verificações iniciais ---
# Usamos a versão cacheada (30s) porque esta tela tem muitos widgets (selects,
# number_inputs): o Streamlit reexecuta o script inteiro a cada clique, e sem
# cache isso refazia essas 4 queries a cada interação - era a causa principal
# da lentidão. Se você acabou de cadastrar um cliente/serviço/material novo e
# ele não aparecer aqui, é só esperar até 30s ou recarregar a página.
prestadores = fetch_all_cached("prestador")
if not prestadores:
    st.warning("Cadastre primeiro o Prestador de Serviço na página correspondente.")
    st.stop()
prestador = prestadores[0]

clientes = fetch_all_cached("clientes", order_by="nome")
if not clientes:
    st.warning("Cadastre pelo menos um cliente antes de criar um orçamento.")
    st.stop()

servicos = fetch_all_cached("servicos", order_by="nome")
materiais = fetch_all_cached("materia_prima", order_by="nome")

if not servicos and not materiais:
    st.warning("Cadastre ao menos um serviço ou material antes de criar um orçamento.")
    st.stop()

# --- Estado da sessão para os itens e fotos adicionados ---
if "itens_orcamento" not in st.session_state:
    st.session_state.itens_orcamento = origem["itens"] if origem else []
if "fotos_orcamento" not in st.session_state:
    st.session_state.fotos_orcamento = []

# --- Tipo de operação e tipo de pedido ---
if origem:
    st.info(f"Criando Ordem de Serviço a partir do Orçamento #{origem['orcamento_id']}.")
    tipo_operacao = "ordem_servico"
    st.markdown("**Tipo de documento:** Ordem de Serviço")
else:
    tipo_operacao = st.radio(
        "Tipo de documento",
        options=["orcamento", "ordem_servico"],
        format_func=lambda x: "Orçamento" if x == "orcamento" else "Ordem de Serviço",
        horizontal=True,
    )

tipo_pedido_default = origem["tipo_pedido"] if origem else "confeccao"
tipo_pedido = st.selectbox(
    "Tipo de pedido",
    options=list(TIPO_PEDIDO_LABELS.keys()),
    format_func=lambda x: TIPO_PEDIDO_LABELS[x],
    index=list(TIPO_PEDIDO_LABELS.keys()).index(tipo_pedido_default),
)

# --- Cliente ---
cliente_opcoes = {c["nome"]: c for c in clientes}
if origem:
    cliente_nome_default = next((c["nome"] for c in clientes if c["id"] == origem["cliente_id"]), None)
    idx_default = list(cliente_opcoes.keys()).index(cliente_nome_default) if cliente_nome_default else 0
else:
    idx_default = 0
cliente_nome = st.selectbox("Cliente", options=list(cliente_opcoes.keys()), index=idx_default)
cliente_selecionado = cliente_opcoes[cliente_nome]

# --- Datas ---
col_d1, col_d2 = st.columns(2)
data_validade = None
data_entrega = None

if tipo_operacao == "orcamento":
    with col_d1:
        data_validade = st.date_input(
            "Validade do orçamento",
            value=date.today() + timedelta(days=7),
            help="Preenchida automaticamente para 7 dias a partir de hoje. Pode ajustar manualmente.",
        )
else:
    with col_d1:
        data_entrega = st.date_input(
            "Data de entrega prevista",
            value=date.today() + timedelta(days=7),
        )

st.divider()
st.subheader("Adicionar itens")

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
st.subheader("Fotos de referência (opcional)")
st.caption("As fotos são armazenadas apenas para consulta - não entram no PDF.")

fotos_upload = st.file_uploader(
    "Anexar fotos", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="upload_fotos"
)

st.divider()

if st.button("💾 Salvar e Gerar PDF", type="primary", disabled=not st.session_state.itens_orcamento):
    # Salva o cabeçalho do orçamento
    resultado = execute(
        """
        INSERT INTO orcamentos
            (cliente_id, tipo_operacao, tipo_pedido, observacoes, data_validade, data_entrega, orcamento_origem_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            cliente_selecionado["id"], tipo_operacao, tipo_pedido, observacoes,
            data_validade, data_entrega, origem["orcamento_id"] if origem else None,
        ),
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

    # Faz upload das fotos e salva as URLs
    if fotos_upload:
        for foto in fotos_upload:
            extensao = foto.name.split(".")[-1].lower()
            try:
                url_publica, storage_path = upload_foto(orcamento_id, foto.read(), extensao)
                execute(
                    "INSERT INTO orcamento_fotos (orcamento_id, url, storage_path) VALUES (%s, %s, %s)",
                    (orcamento_id, url_publica, storage_path),
                )
            except Exception as e:
                st.warning(f"Não foi possível enviar a foto '{foto.name}': {e}")

    # Gera o PDF
    pdf_path = gerar_pdf(
        tipo=tipo_operacao,
        prestador=prestador,
        cliente=cliente_selecionado,
        itens=st.session_state.itens_orcamento,
        observacoes=observacoes,
        tipo_pedido_label=TIPO_PEDIDO_LABELS[tipo_pedido],
        data_validade=data_validade,
        data_entrega=data_entrega,
    )

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    nome_arquivo = f"{'orcamento' if tipo_operacao == 'orcamento' else 'ordem_servico'}_{cliente_selecionado['nome'].replace(' ', '_')}.pdf"

    st.success("Documento salvo e PDF gerado com sucesso!")
    st.download_button(
        label="⬇️ Baixar PDF",
        data=pdf_bytes,
        file_name=nome_arquivo,
        mime="application/pdf",
    )

    st.session_state.itens_orcamento = []
    st.session_state.fotos_orcamento = []
