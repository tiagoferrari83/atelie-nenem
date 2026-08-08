"""
Lógica compartilhada do formulário de Orçamento / Ordem de Serviço.
Chamada pelas páginas pages/51_Orcamento.py e pages/52_Ordem_Servico.py,
cada uma fixando o tipo de operação - evita ter os dois fluxos misturados
numa tela só (o que causava confusão e um bug de estado entre eles).
"""

import streamlit as st
from datetime import date, timedelta
from database import fetch_all_cached, execute
from pdf_generator import gerar_pdf
from storage import upload_foto
from constants import TIPO_PEDIDO_LABELS, TIPO_LABELS_SERVICO, TIPO_LABELS_MATERIAL


def render(tipo_operacao_fixo):
    """
    tipo_operacao_fixo: 'orcamento' ou 'ordem_servico' - define qual tela está sendo exibida.
    """
    titulo = "Orçamento" if tipo_operacao_fixo == "orcamento" else "Ordem de Serviço"

    # --- Se veio de "criar OS a partir de orçamento" (só relevante quando tipo_operacao_fixo == 'ordem_servico') ---
    origem = st.session_state.pop("criar_os_de_orcamento", None)
    if origem and tipo_operacao_fixo != "ordem_servico":
        origem = None  # ignora se por algum motivo caiu na tela errada

    # --- Se veio de "editar" um documento existente ---
    edicao = st.session_state.pop("editar_orcamento", None)
    if edicao and edicao.get("tipo_operacao") != tipo_operacao_fixo:
        edicao = None  # edição de um orçamento não deve abrir na tela de OS e vice-versa

    st.title(f"✏️ Editar {titulo}" if edicao else f"📄 Novo {titulo}")

    # --- Verificações iniciais ---
    prestadores = fetch_all_cached("prestador")
    if not prestadores:
        st.warning("Cadastre primeiro o Prestador de Serviço na página correspondente.")
        st.stop()
    prestador = prestadores[0]

    clientes = fetch_all_cached("clientes", order_by="nome")
    if not clientes:
        st.warning("Cadastre pelo menos um cliente antes de continuar.")
        st.stop()

    # --- Estado da sessão ---
    # Cada item da lista de "grupos" representa um serviço adicionado, com sua lista
    # de materiais (subitens) dentro. Um serviço sem materiais é um grupo com lista vazia.
    # IMPORTANTE: quando vem de edição ou de "criar OS a partir de orçamento", SEMPRE
    # reinicializa com os dados recebidos - não reaproveita o que já estava na sessão,
    # senão o formulário mistura dados de uma navegação anterior.
    chave_estado = f"grupos_{tipo_operacao_fixo}"
    if edicao:
        st.session_state[chave_estado] = edicao["grupos"]
    elif origem:
        st.session_state[chave_estado] = origem["grupos"]
    elif chave_estado not in st.session_state:
        st.session_state[chave_estado] = []

    tipo_operacao = tipo_operacao_fixo

    if edicao:
        st.markdown(f"**Editando {titulo} #{edicao['orcamento_id']}**")
    elif origem:
        st.info(f"Criando Ordem de Serviço a partir do Orçamento #{origem['orcamento_id']}.")

    tipo_pedido_default = edicao["tipo_pedido"] if edicao else (origem["tipo_pedido"] if origem else "confeccao")
    tipo_pedido = st.selectbox(
        "Tipo de pedido",
        options=list(TIPO_PEDIDO_LABELS.keys()),
        format_func=lambda x: TIPO_PEDIDO_LABELS[x],
        index=list(TIPO_PEDIDO_LABELS.keys()).index(tipo_pedido_default),
    )

    # --- Cliente ---
    cliente_opcoes = {c["nome"]: c for c in clientes}
    cliente_id_default = edicao["cliente_id"] if edicao else (origem["cliente_id"] if origem else None)
    if cliente_id_default:
        cliente_nome_default = next((c["nome"] for c in clientes if c["id"] == cliente_id_default), None)
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
                value=(edicao["data_validade"] if edicao and edicao.get("data_validade") else date.today() + timedelta(days=7)),
                help="Preenchida automaticamente para 7 dias a partir de hoje. Pode ajustar manualmente.",
            )
    else:
        with col_d1:
            data_entrega = st.date_input(
                "Data de entrega prevista",
                value=(edicao["data_entrega"] if edicao and edicao.get("data_entrega") else date.today() + timedelta(days=7)),
            )

    st.divider()

    # ============================================================
    # Popups de cadastro rápido (serviço / material)
    # ============================================================

    @st.dialog("Cadastro rápido de Serviço")
    def dialog_novo_servico():
        nome = st.text_input("Nome do serviço")
        tipo_cobranca = st.selectbox(
            "Tipo de cobrança",
            options=list(TIPO_LABELS_SERVICO.keys()),
            format_func=lambda x: {"unidade": "Por unidade", "tempo": "Por tempo (hora)", "metro": "Por metro"}[x],
        )
        valor = st.number_input("Valor (R$)", min_value=0.0, step=0.5, format="%.2f")
        if st.button("Salvar serviço", type="primary"):
            if not nome:
                st.error("O nome é obrigatório.")
            else:
                execute(
                    "INSERT INTO servicos (nome, tipo_cobranca, valor) VALUES (%s, %s, %s)",
                    (nome, tipo_cobranca, valor),
                )
                st.cache_data.clear()
                st.success(f"Serviço '{nome}' cadastrado!")
                st.rerun()

    @st.dialog("Cadastro rápido de Matéria-Prima")
    def dialog_novo_material():
        nome = st.text_input("Nome do material")
        tipo_medida = st.selectbox(
            "Tipo de medida",
            options=list(TIPO_LABELS_MATERIAL.keys()),
            format_func=lambda x: {"unidade": "Por unidade", "metro": "Por metro", "peso": "Por peso (kg)"}[x],
        )
        valor = st.number_input("Valor (R$)", min_value=0.0, step=0.5, format="%.2f")
        if st.button("Salvar material", type="primary"):
            if not nome:
                st.error("O nome é obrigatório.")
            else:
                execute(
                    "INSERT INTO materia_prima (nome, tipo_medida, valor) VALUES (%s, %s, %s)",
                    (nome, tipo_medida, valor),
                )
                st.cache_data.clear()
                st.success(f"Material '{nome}' cadastrado!")
                st.rerun()

    # ============================================================
    # Adicionar serviço (cria um novo grupo)
    # ============================================================

    st.subheader("Adicionar serviço")

    servicos = fetch_all_cached("servicos", order_by="nome")

    col_srv, col_btn_srv = st.columns([5, 1])
    with col_srv:
        if servicos:
            servico_opcoes = {
                f"{s['nome']} (R$ {s['valor']:.2f}/{TIPO_LABELS_SERVICO[s['tipo_cobranca']]})": s for s in servicos
            }
            servico_escolhido = st.selectbox("Serviço", options=list(servico_opcoes.keys()), key="sel_servico")
            qtd_servico = st.number_input("Quantidade do serviço", min_value=0.0, step=0.5, key="qtd_servico")
        else:
            st.caption("Nenhum serviço cadastrado ainda. Use o botão ao lado para cadastrar um.")
    with col_btn_srv:
        st.write("")
        st.write("")
        if st.button("➕ Novo serviço", key="btn_novo_servico"):
            dialog_novo_servico()

    if servicos and st.button("Adicionar serviço"):
        if qtd_servico > 0:
            s = servico_opcoes[servico_escolhido]
            st.session_state[chave_estado].append({
                "servico": {
                    "item_id": s["id"],
                    "descricao": s["nome"],
                    "quantidade": qtd_servico,
                    "valor_unitario": float(s["valor"]),
                    "valor_total": float(s["valor"]) * qtd_servico,
                },
                "materiais": [],
            })
            st.rerun()
        else:
            st.error("Informe uma quantidade maior que zero.")

    st.divider()

    # ============================================================
    # Lista de grupos (serviços com seus materiais)
    # ============================================================

    st.subheader("Itens")

    materiais_cadastrados = fetch_all_cached("materia_prima", order_by="nome")

    if not st.session_state[chave_estado]:
        st.info("Nenhum serviço adicionado ainda.")
    else:
        total_geral = 0

        for idx_grupo, grupo in enumerate(st.session_state[chave_estado]):
            servico_item = grupo["servico"]
            subtotal_materiais = sum(m["valor_total"] for m in grupo["materiais"])
            subtotal_grupo = servico_item["valor_total"] + subtotal_materiais

            with st.container(border=True):
                col_a, col_b = st.columns([5, 1])
                with col_a:
                    st.markdown(
                        f"**{servico_item['descricao']}** — {servico_item['quantidade']:.2f} x "
                        f"R$ {servico_item['valor_unitario']:.2f} = R$ {servico_item['valor_total']:.2f}"
                    )
                with col_b:
                    if st.button("Remover serviço", key=f"rem_servico_{idx_grupo}"):
                        st.session_state[chave_estado].pop(idx_grupo)
                        st.rerun()

                # Materiais (subitens) deste serviço
                if grupo["materiais"]:
                    st.caption("Materiais usados:")
                    for idx_mat, mat in enumerate(grupo["materiais"]):
                        col_m1, col_m2 = st.columns([5, 1])
                        with col_m1:
                            st.write(
                                f"　↳ {mat['descricao']} — {mat['quantidade']:.2f} x "
                                f"R$ {mat['valor_unitario']:.2f} = R$ {mat['valor_total']:.2f}"
                            )
                        with col_m2:
                            if st.button("Remover", key=f"rem_mat_{idx_grupo}_{idx_mat}"):
                                grupo["materiais"].pop(idx_mat)
                                st.rerun()

                # Adicionar material a este serviço
                with st.expander("➕ Adicionar matéria-prima a este serviço"):
                    if materiais_cadastrados:
                        col_mat, col_btn_mat = st.columns([5, 1])
                        with col_mat:
                            material_opcoes = {
                                f"{m['nome']} (R$ {m['valor']:.2f}/{TIPO_LABELS_MATERIAL[m['tipo_medida']]})": m
                                for m in materiais_cadastrados
                            }
                            material_escolhido = st.selectbox(
                                "Material", options=list(material_opcoes.keys()), key=f"sel_material_{idx_grupo}"
                            )
                            qtd_material = st.number_input(
                                "Quantidade", min_value=0.0, step=0.5, key=f"qtd_material_{idx_grupo}"
                            )
                        with col_btn_mat:
                            st.write("")
                            st.write("")
                            if st.button("➕ Novo", key=f"btn_novo_material_{idx_grupo}"):
                                dialog_novo_material()

                        if st.button("Adicionar material", key=f"add_material_{idx_grupo}"):
                            if qtd_material > 0:
                                m = material_opcoes[material_escolhido]
                                grupo["materiais"].append({
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
                        st.caption("Nenhum material cadastrado ainda.")
                        if st.button("➕ Cadastrar material agora", key=f"btn_novo_material_vazio_{idx_grupo}"):
                            dialog_novo_material()

                st.markdown(f"**Subtotal do serviço: R$ {subtotal_grupo:.2f}**")

            total_geral += subtotal_grupo

        st.markdown(f"### Total geral: R$ {total_geral:.2f}")

    observacoes = st.text_area("Observações (opcional)", value=(edicao.get("observacoes") or "") if edicao else "")

    st.divider()
    st.subheader("Fotos de referência (opcional)")
    st.caption("As fotos são armazenadas apenas para consulta - não entram no PDF.")

    fotos_upload = st.file_uploader(
        "Anexar fotos", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="upload_fotos"
    )

    st.divider()

    label_botao = "💾 Salvar edição e Gerar PDF" if edicao else f"💾 Salvar {titulo} e Gerar PDF"

    if st.button(label_botao, type="primary", disabled=not st.session_state[chave_estado]):
        if edicao:
            # Modo edição: atualiza o cabeçalho existente e substitui os itens antigos pelos novos
            orcamento_id = edicao["orcamento_id"]
            execute(
                """
                UPDATE orcamentos
                SET cliente_id = %s, tipo_pedido = %s, observacoes = %s,
                    data_validade = %s, data_entrega = %s
                WHERE id = %s
                """,
                (cliente_selecionado["id"], tipo_pedido, observacoes, data_validade, data_entrega, orcamento_id),
            )
            # Remove os itens antigos (cascade também remove materiais filhos) para substituir pelos atuais
            execute("DELETE FROM orcamento_itens WHERE orcamento_id = %s", (orcamento_id,))
        else:
            # Modo criação: insere um novo documento
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

        # Salva os grupos: cada serviço vira um item, e seus materiais viram itens
        # filhos, ligados pelo servico_pai_item_id
        itens_para_pdf = []

        for grupo in st.session_state[chave_estado]:
            s = grupo["servico"]
            resultado_item = execute(
                """
                INSERT INTO orcamento_itens
                    (orcamento_id, tipo_item, item_id, descricao, quantidade, valor_unitario, valor_total)
                VALUES (%s, 'servico', %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (orcamento_id, s["item_id"], s["descricao"], s["quantidade"], s["valor_unitario"], s["valor_total"]),
            )
            servico_item_id = resultado_item["id"]

            itens_para_pdf.append({
                "descricao": s["descricao"],
                "quantidade": s["quantidade"],
                "valor_unitario": s["valor_unitario"],
                "valor_total": s["valor_total"],
                "materiais": [],
            })

            for m in grupo["materiais"]:
                execute(
                    """
                    INSERT INTO orcamento_itens
                        (orcamento_id, tipo_item, item_id, descricao, quantidade, valor_unitario, valor_total, servico_pai_item_id)
                    VALUES (%s, 'materia_prima', %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        orcamento_id, m["item_id"], m["descricao"], m["quantidade"],
                        m["valor_unitario"], m["valor_total"], servico_item_id,
                    ),
                )
                itens_para_pdf[-1]["materiais"].append({
                    "descricao": m["descricao"],
                    "quantidade": m["quantidade"],
                    "valor_unitario": m["valor_unitario"],
                    "valor_total": m["valor_total"],
                })

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
            grupos=itens_para_pdf,
            observacoes=observacoes,
            tipo_pedido_label=TIPO_PEDIDO_LABELS[tipo_pedido],
            data_validade=data_validade,
            data_entrega=data_entrega,
        )

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        nome_arquivo = f"{'orcamento' if tipo_operacao == 'orcamento' else 'ordem_servico'}_{cliente_selecionado['nome'].replace(' ', '_')}.pdf"

        st.success("Alterações salvas e PDF gerado com sucesso!" if edicao else "Documento salvo e PDF gerado com sucesso!")
        st.download_button(
            label="⬇️ Baixar PDF",
            data=pdf_bytes,
            file_name=nome_arquivo,
            mime="application/pdf",
        )

        st.session_state[chave_estado] = []
