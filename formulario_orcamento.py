"""
Lógica compartilhada do formulário de Orçamento / Ordem de Serviço.
Chamada pelas páginas pages/51_Orcamento.py e pages/52_Ordem_Servico.py.

A partir do Bloco E, os dois documentos têm estruturas distintas:
  - Ordem de Serviço: estrutura atual (serviços com materiais e observação por item)
  - Orçamento: nova estrutura com seções Tecido / Aviamentos / Outros / Serviços,
               campo de descrição livre e fotos com opção de página inteira no PDF
"""

import streamlit as st
from datetime import date, timedelta
from database import fetch_all_cached, query, execute
from pdf_generator import gerar_pdf_os, gerar_pdf_orcamento
from storage import upload_foto, excluir_foto
from constants import (
    TIPO_LABELS_SERVICO, TIPO_LABELS_MATERIAL, TIPO_MATERIAL_LABELS,
    COMPLEXIDADE_LABELS, COMPLEXIDADE_ACRESCIMO, valor_com_complexidade,
    formatar_moeda, formatar_reais,
)


# ════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ════════════════════════════════════════════════════════════════════

def render(tipo_operacao_fixo):
    if tipo_operacao_fixo == "ordem_servico":
        _render_os()
    else:
        _render_orcamento()


# ════════════════════════════════════════════════════════════════════
# HELPERS COMPARTILHADOS
# ════════════════════════════════════════════════════════════════════

def _carregar_contexto():
    """Retorna (prestador, clientes) com validações. Chama st.stop() se faltar."""
    prestadores = fetch_all_cached("prestador")
    if not prestadores:
        st.warning("Cadastre primeiro o Prestador de Serviço na página correspondente.")
        st.stop()
    clientes = fetch_all_cached("clientes", order_by="nome")
    if not clientes:
        st.warning("Cadastre pelo menos um cliente antes de continuar.")
        st.stop()
    return prestadores[0], clientes


def _selectbox_cliente(clientes, cliente_id_default):
    cliente_opcoes = {c["nome"]: c for c in clientes}
    if cliente_id_default:
        nome_default = next((c["nome"] for c in clientes if c["id"] == cliente_id_default), None)
        idx = list(cliente_opcoes.keys()).index(nome_default) if nome_default else 0
    else:
        idx = 0
    nome = st.selectbox("Cliente", options=list(cliente_opcoes.keys()), index=idx)
    return cliente_opcoes[nome]


@st.dialog("Cadastro rápido de Serviço")
def _dialog_novo_servico():
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
            execute("INSERT INTO servicos (nome, tipo_cobranca, valor) VALUES (%s, %s, %s)",
                    (nome, tipo_cobranca, valor))
            st.cache_data.clear()
            st.success(f"Serviço '{nome}' cadastrado!")
            st.rerun()


@st.dialog("Cadastro rápido de Matéria-Prima")
def _dialog_novo_material():
    nome = st.text_input("Nome do material")
    tipo_material = st.selectbox(
        "Tipo de material",
        options=list(TIPO_MATERIAL_LABELS.keys()),
        format_func=lambda x: TIPO_MATERIAL_LABELS[x],
    )
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
                "INSERT INTO materia_prima (nome, tipo_material, tipo_medida, valor) VALUES (%s, %s, %s, %s)",
                (nome, tipo_material, tipo_medida, valor),
            )
            st.cache_data.clear()
            st.success(f"Material '{nome}' cadastrado!")
            st.rerun()


def _salvar_fotos(orcamento_id, fotos_upload):
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


def _widget_fotos_existentes(orcamento_id_para_fotos, modo_edicao):
    """Exibe fotos já salvas com botão de remoção (só no modo edição)."""
    if not orcamento_id_para_fotos:
        return
    fotos = query(
        "SELECT id, url, storage_path FROM orcamento_fotos WHERE orcamento_id = %s ORDER BY id",
        (orcamento_id_para_fotos,),
    )
    if not fotos:
        return
    st.write("Fotos já anexadas:")
    cols = st.columns(min(len(fotos), 4))
    for i, foto in enumerate(fotos):
        with cols[i % 4]:
            st.image(foto["url"], use_container_width=True)
            if modo_edicao and st.button("Remover", key=f"rem_foto_exist_{foto['id']}"):
                try:
                    excluir_foto(foto["storage_path"])
                except Exception:
                    pass
                execute("DELETE FROM orcamento_fotos WHERE id = %s", (foto["id"],))
                st.rerun()


# ════════════════════════════════════════════════════════════════════
# ORDEM DE SERVIÇO
# ════════════════════════════════════════════════════════════════════

def _render_os():
    chave_edicao_ativa = "edicao_ativa_ordem_servico"
    if "editar_orcamento" in st.session_state:
        st.session_state[chave_edicao_ativa] = st.session_state.pop("editar_orcamento")
    edicao = st.session_state.get(chave_edicao_ativa)
    if edicao and edicao.get("tipo_operacao") != "ordem_servico":
        edicao = None

    st.title("✏️ Editar Ordem de Serviço" if edicao else "📄 Nova Ordem de Serviço")

    prestador, clientes = _carregar_contexto()

    # Estado dos grupos (serviços + materiais)
    chave_estado = "grupos_ordem_servico"
    chave_carregado_id = "carregado_orcamento_id_ordem_servico"
    id_a_carregar = edicao["orcamento_id"] if edicao else None

    if id_a_carregar is not None and st.session_state.get(chave_carregado_id) != id_a_carregar:
        st.session_state[chave_estado] = edicao["grupos"]
        st.session_state[chave_carregado_id] = id_a_carregar
    elif id_a_carregar is None and chave_estado not in st.session_state:
        st.session_state[chave_estado] = []

    if edicao:
        st.markdown(f"**Editando Ordem de Serviço #{edicao['orcamento_id']}**")

    cliente_selecionado = _selectbox_cliente(clientes, edicao["cliente_id"] if edicao else None)

    data_entrega = st.date_input(
        "Data de entrega prevista",
        value=(edicao["data_entrega"] if edicao and edicao.get("data_entrega")
               else date.today() + timedelta(days=7)),
        format="DD/MM/YYYY",
    )

    st.divider()

    # — Adicionar serviço —
    st.subheader("Adicionar serviço")
    servicos = fetch_all_cached("servicos", order_by="nome")

    col_srv, col_btn_srv = st.columns([5, 1])
    with col_srv:
        if servicos:
            servico_opcoes = {
                f"{s['nome']} (R$ {formatar_moeda(float(s['valor']))}/{TIPO_LABELS_SERVICO[s['tipo_cobranca']]})": s
                for s in servicos
            }
            servico_escolhido = st.selectbox("Serviço", options=list(servico_opcoes.keys()), key="os_sel_servico")
            complexidade = st.selectbox(
                "Complexidade",
                options=list(COMPLEXIDADE_LABELS.keys()),
                format_func=lambda x: COMPLEXIDADE_LABELS[x],
                key="os_sel_complexidade",
                help="Aplica acréscimo percentual sobre o valor base.",
            )
            s_prev = servico_opcoes[servico_escolhido]
            vb = float(s_prev["valor"])
            vf = valor_com_complexidade(vb, complexidade)
            ac = COMPLEXIDADE_ACRESCIMO[complexidade]
            un = TIPO_LABELS_SERVICO[s_prev["tipo_cobranca"]]
            if ac > 0:
                st.caption(f"R\\$ {formatar_moeda(vb)}/{un} → com +{int(ac*100)}%: **R\\$ {formatar_moeda(vf)}/{un}**")
            else:
                st.caption(f"R\\$ {formatar_moeda(vb)}/{un} (sem acréscimo)")
            qtd_servico = st.number_input("Quantidade", min_value=0.0, step=0.5, key="os_qtd_servico")
        else:
            st.caption("Nenhum serviço cadastrado ainda.")
    with col_btn_srv:
        st.write("")
        st.write("")
        if st.button("➕ Novo serviço", key="os_btn_novo_servico"):
            _dialog_novo_servico()

    if servicos and st.button("Adicionar serviço", key="os_add_servico"):
        if qtd_servico > 0:
            s = servico_opcoes[servico_escolhido]
            vb = float(s["valor"])
            vu = valor_com_complexidade(vb, complexidade)
            un = TIPO_LABELS_SERVICO[s["tipo_cobranca"]]
            ac = COMPLEXIDADE_ACRESCIMO[complexidade]
            desc = f"{s['nome']}/{un}"
            st.session_state[chave_estado].append({
                "servico": {
                    "item_id": s["id"], "descricao": desc,
                    "quantidade": qtd_servico, "valor_unitario": vu,
                    "valor_total": round(vu * qtd_servico, 2),
                    "observacao_item": "",
                },
                "materiais": [],
            })
            st.rerun()
        else:
            st.error("Informe uma quantidade maior que zero.")

    st.divider()

    # — Lista de grupos —
    st.subheader("Itens")
    materiais_cadastrados = fetch_all_cached("materia_prima", order_by="nome")

    if not st.session_state[chave_estado]:
        st.info("Nenhum serviço adicionado ainda.")
    else:
        total_geral = 0
        for idx_g, grupo in enumerate(st.session_state[chave_estado]):
            s_item = grupo["servico"]
            subtotal_mat = sum(m["valor_total"] for m in grupo["materiais"])
            subtotal_g = s_item["valor_total"] + subtotal_mat

            with st.container(border=True):
                col_a, col_b = st.columns([5, 1])
                with col_a:
                    st.markdown(
                        f"**{s_item['descricao']}** — {s_item['quantidade']:.2f} x "
                        f"{formatar_reais(s_item['valor_unitario'])} = {formatar_reais(s_item['valor_total'])}"
                    )
                with col_b:
                    if st.button("Remover", key=f"os_rem_srv_{idx_g}"):
                        st.session_state[chave_estado].pop(idx_g)
                        st.rerun()

                obs_nova = st.text_input(
                    "Observação (opcional)",
                    value=s_item.get("observacao_item", ""),
                    key=f"os_obs_{idx_g}",
                    placeholder="Ex: reforçar costura lateral...",
                )
                st.session_state[chave_estado][idx_g]["servico"]["observacao_item"] = obs_nova

                if grupo["materiais"]:
                    st.caption("Materiais:")
                    for idx_m, mat in enumerate(grupo["materiais"]):
                        col_m1, col_m2 = st.columns([5, 1])
                        with col_m1:
                            st.write(
                                f"　↳ {mat['descricao']} — {mat['quantidade']:.2f} x "
                                f"{formatar_reais(mat['valor_unitario'])} = {formatar_reais(mat['valor_total'])}"
                            )
                        with col_m2:
                            if st.button("Remover", key=f"os_rem_mat_{idx_g}_{idx_m}"):
                                grupo["materiais"].pop(idx_m)
                                st.rerun()

                with st.expander("➕ Adicionar matéria-prima"):
                    if materiais_cadastrados:
                        col_mat, col_btn_mat = st.columns([5, 1])
                        with col_mat:
                            mat_opcoes = {
                                f"{m['nome']} (R$ {formatar_moeda(float(m['valor']))}/{TIPO_LABELS_MATERIAL[m['tipo_medida']]})": m
                                for m in materiais_cadastrados
                            }
                            mat_esc = st.selectbox("Material", options=list(mat_opcoes.keys()), key=f"os_sel_mat_{idx_g}")
                            qtd_mat = st.number_input("Quantidade", min_value=0.0, step=0.5, key=f"os_qtd_mat_{idx_g}")
                        with col_btn_mat:
                            st.write("")
                            st.write("")
                            if st.button("➕ Novo", key=f"os_btn_novo_mat_{idx_g}"):
                                _dialog_novo_material()
                        if st.button("Adicionar material", key=f"os_add_mat_{idx_g}"):
                            if qtd_mat > 0:
                                m = mat_opcoes[mat_esc]
                                un_m = TIPO_LABELS_MATERIAL[m["tipo_medida"]]
                                grupo["materiais"].append({
                                    "item_id": m["id"],
                                    "descricao": f"{m['nome']}/{un_m}",
                                    "quantidade": qtd_mat,
                                    "valor_unitario": float(m["valor"]),
                                    "valor_total": round(float(m["valor"]) * qtd_mat, 2),
                                })
                                st.rerun()
                            else:
                                st.error("Quantidade deve ser maior que zero.")
                    else:
                        st.caption("Nenhum material cadastrado.")
                        if st.button("➕ Cadastrar material agora", key=f"os_btn_mat_vazio_{idx_g}"):
                            _dialog_novo_material()

                st.markdown(f"**Subtotal: {formatar_reais(subtotal_g)}**")
            total_geral += subtotal_g

        st.markdown(f"### Total geral: {formatar_reais(total_geral)}")

    observacoes = st.text_area(
        "Observações gerais (opcional)",
        value=(edicao.get("observacoes") or "") if edicao else "",
    )

    st.divider()
    st.subheader("Fotos de referência (opcional)")
    st.caption("Armazenadas para consulta — não entram no PDF da OS.")
    _widget_fotos_existentes(edicao["orcamento_id"] if edicao else None, modo_edicao=bool(edicao))
    fotos_upload = st.file_uploader(
        "Anexar fotos", type=["png", "jpg", "jpeg"],
        accept_multiple_files=True, key="os_upload_fotos",
    )

    st.divider()
    label_botao = "💾 Salvar edição e Gerar PDF" if edicao else "💾 Salvar OS e Gerar PDF"

    if st.button(label_botao, type="primary", disabled=not st.session_state[chave_estado]):
        if edicao:
            orcamento_id = edicao["orcamento_id"]
            execute(
                "UPDATE orcamentos SET cliente_id=%s, observacoes=%s, data_entrega=%s WHERE id=%s",
                (cliente_selecionado["id"], observacoes, data_entrega, orcamento_id),
            )
            execute("DELETE FROM orcamento_itens WHERE orcamento_id=%s", (orcamento_id,))
        else:
            res = execute(
                """INSERT INTO orcamentos
                    (cliente_id, tipo_operacao, tipo_pedido, status, observacoes, data_entrega)
                   VALUES (%s, 'ordem_servico', 'confeccao', 'nova', %s, %s)
                   RETURNING id""",
                (cliente_selecionado["id"], observacoes, data_entrega),
            )
            orcamento_id = res["id"]

        itens_pdf = []
        for grupo in st.session_state[chave_estado]:
            s = grupo["servico"]
            obs = s.get("observacao_item") or None
            res_item = execute(
                """INSERT INTO orcamento_itens
                    (orcamento_id, tipo_item, item_id, descricao, quantidade,
                     valor_unitario, valor_total, observacao_item)
                   VALUES (%s,'servico',%s,%s,%s,%s,%s,%s) RETURNING id""",
                (orcamento_id, s["item_id"], s["descricao"], s["quantidade"],
                 s["valor_unitario"], s["valor_total"], obs),
            )
            srv_item_id = res_item["id"]
            itens_pdf.append({
                "descricao": s["descricao"], "quantidade": s["quantidade"],
                "valor_unitario": s["valor_unitario"], "valor_total": s["valor_total"],
                "observacao_item": obs or "", "materiais": [],
            })
            for m in grupo["materiais"]:
                execute(
                    """INSERT INTO orcamento_itens
                        (orcamento_id, tipo_item, item_id, descricao, quantidade,
                         valor_unitario, valor_total, servico_pai_item_id)
                       VALUES (%s,'materia_prima',%s,%s,%s,%s,%s,%s)""",
                    (orcamento_id, m["item_id"], m["descricao"], m["quantidade"],
                     m["valor_unitario"], m["valor_total"], srv_item_id),
                )
                itens_pdf[-1]["materiais"].append({
                    "descricao": m["descricao"], "quantidade": m["quantidade"],
                    "valor_unitario": m["valor_unitario"], "valor_total": m["valor_total"],
                })

        _salvar_fotos(orcamento_id, fotos_upload or [])

        pdf_path = gerar_pdf_os(
            prestador=prestador,
            cliente=cliente_selecionado,
            grupos=itens_pdf,
            observacoes=observacoes,
            data_entrega=data_entrega,
        )
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        st.success("Alterações salvas!" if edicao else "OS salva!")
        st.download_button(
            "⬇️ Baixar PDF",
            data=pdf_bytes,
            file_name=f"ordem_servico_{cliente_selecionado['nome'].replace(' ','_')}.pdf",
            mime="application/pdf",
        )
        st.session_state[chave_estado] = []
        st.session_state.pop(chave_edicao_ativa, None)
        st.session_state.pop(chave_carregado_id, None)


# ════════════════════════════════════════════════════════════════════
# ORÇAMENTO — nova estrutura (Bloco E)
# ════════════════════════════════════════════════════════════════════

def _render_orcamento():
    chave_edicao_ativa = "edicao_ativa_orcamento"
    if "editar_orcamento" in st.session_state:
        st.session_state[chave_edicao_ativa] = st.session_state.pop("editar_orcamento")
    edicao = st.session_state.get(chave_edicao_ativa)
    if edicao and edicao.get("tipo_operacao") != "orcamento":
        edicao = None

    st.title("✏️ Editar Orçamento" if edicao else "📄 Novo Orçamento")

    prestador, clientes = _carregar_contexto()

    # Estado: 4 seções independentes + metadados de fotos
    chave_tecidos   = "orc_tecidos"
    chave_aviamentos = "orc_aviamentos"
    chave_outros    = "orc_outros"
    chave_servicos  = "orc_servicos"
    chave_fotos_cfg = "orc_fotos_cfg"   # {foto_id: bool pagina_inteira}
    chave_carregado = "orc_carregado_id"

    id_a_carregar = edicao["orcamento_id"] if edicao else None

    if id_a_carregar is not None and st.session_state.get(chave_carregado) != id_a_carregar:
        # Pré-carrega itens do orçamento existente nas seções corretas
        _carregar_itens_orcamento(id_a_carregar,
                                  chave_tecidos, chave_aviamentos,
                                  chave_outros, chave_servicos)
        st.session_state[chave_carregado] = id_a_carregar
    else:
        for ch in [chave_tecidos, chave_aviamentos, chave_outros, chave_servicos]:
            if ch not in st.session_state:
                st.session_state[ch] = []
    if chave_fotos_cfg not in st.session_state:
        st.session_state[chave_fotos_cfg] = {}

    if edicao:
        st.markdown(f"**Editando Orçamento #{edicao['orcamento_id']}**")

    cliente_selecionado = _selectbox_cliente(clientes, edicao["cliente_id"] if edicao else None)

    data_validade = st.date_input(
        "Validade do orçamento",
        value=(edicao["data_validade"] if edicao and edicao.get("data_validade")
               else date.today() + timedelta(days=7)),
        format="DD/MM/YYYY",
        help="Preenchida automaticamente para 7 dias a partir de hoje.",
    )

    st.divider()

    # ── Seções de material por tipo ──
    materiais_cadastrados = fetch_all_cached("materia_prima", order_by="nome")
    mat_por_tipo = {"tecido": [], "aviamento": [], "outros": []}
    for m in materiais_cadastrados:
        t = m.get("tipo_material") or "outros"
        mat_por_tipo.setdefault(t, []).append(m)

    _secao_material(
        titulo="🧵 Tecidos",
        chave=chave_tecidos,
        materiais=mat_por_tipo["tecido"],
        tipo_material_key="tecido",
    )
    _secao_material(
        titulo="🪡 Aviamentos",
        chave=chave_aviamentos,
        materiais=mat_por_tipo["aviamento"],
        tipo_material_key="aviamento",
    )
    _secao_material(
        titulo="📦 Outros materiais",
        chave=chave_outros,
        materiais=mat_por_tipo["outros"],
        tipo_material_key="outros",
    )

    # ── Seção de Serviços ──
    st.subheader("✂️ Serviços")
    servicos = fetch_all_cached("servicos", order_by="nome")
    col_srv, col_btn_srv = st.columns([5, 1])
    with col_srv:
        if servicos:
            srv_opcoes = {
                f"{s['nome']} (R$ {formatar_moeda(float(s['valor']))}/{TIPO_LABELS_SERVICO[s['tipo_cobranca']]})": s
                for s in servicos
            }
            srv_esc = st.selectbox("Serviço", options=list(srv_opcoes.keys()), key="orc_sel_srv")
            complexidade = st.selectbox(
                "Complexidade",
                options=list(COMPLEXIDADE_LABELS.keys()),
                format_func=lambda x: COMPLEXIDADE_LABELS[x],
                key="orc_sel_complexidade",
                help="Aplica acréscimo percentual sobre o valor base.",
            )
            s_prev = srv_opcoes[srv_esc]
            vb = float(s_prev["valor"])
            vf = valor_com_complexidade(vb, complexidade)
            ac = COMPLEXIDADE_ACRESCIMO[complexidade]
            un = TIPO_LABELS_SERVICO[s_prev["tipo_cobranca"]]
            if ac > 0:
                st.caption(f"R\\$ {formatar_moeda(vb)}/{un} → com +{int(ac*100)}%: **R\\$ {formatar_moeda(vf)}/{un}**")
            else:
                st.caption(f"R\\$ {formatar_moeda(vb)}/{un} (sem acréscimo)")
            qtd_srv = st.number_input("Quantidade", min_value=0.0, step=0.5, key="orc_qtd_srv")
            obs_srv_add = st.text_input(
                "Observação (opcional)", key="orc_obs_srv_add",
                placeholder="Ex: reforçar costura, acabamento especial...",
            )
        else:
            st.caption("Nenhum serviço cadastrado.")
    with col_btn_srv:
        st.write("")
        st.write("")
        if st.button("➕ Novo", key="orc_btn_novo_srv"):
            _dialog_novo_servico()

    if servicos and st.button("Adicionar serviço", key="orc_add_srv"):
        if qtd_srv > 0:
            s = srv_opcoes[srv_esc]
            vb = float(s["valor"])
            vu = valor_com_complexidade(vb, complexidade)
            un = TIPO_LABELS_SERVICO[s["tipo_cobranca"]]
            ac = COMPLEXIDADE_ACRESCIMO[complexidade]
            desc = f"{s['nome']}/{un}"
            st.session_state[chave_servicos].append({
                "item_id": s["id"], "descricao": desc,
                "quantidade": qtd_srv, "valor_unitario": vu,
                "valor_total": round(vu * qtd_srv, 2),
                "observacao_item": obs_srv_add,
            })
            st.rerun()
        else:
            st.error("Quantidade deve ser maior que zero.")

    _listar_itens_simples(chave_servicos, prefixo="srv")

    # ── Total geral ──
    total = (
        sum(i["valor_total"] for i in st.session_state[chave_tecidos])
        + sum(i["valor_total"] for i in st.session_state[chave_aviamentos])
        + sum(i["valor_total"] for i in st.session_state[chave_outros])
        + sum(i["valor_total"] for i in st.session_state[chave_servicos])
    )
    if total > 0:
        st.markdown(f"### Total geral: {formatar_reais(total)}")

    st.divider()

    # ── Descrição livre ──
    st.subheader("📝 Descrição")
    descricao_livre_default = edicao.get("descricao_livre", "") if edicao else ""
    descricao_livre = st.text_area(
        "Descrição livre (opcional)",
        value=descricao_livre_default or "",
        max_chars=1000,
        height=150,
        placeholder="Descreva detalhes adicionais do projeto, referências estéticas, etc.",
    )

    st.divider()

    # ── Fotos ──
    st.subheader("📷 Fotos de referência")
    st.caption("As fotos aparecem nas páginas seguintes do PDF. Marque 'Página inteira' para exibir a foto sozinha em uma página.")

    fotos_existentes = []
    if edicao:
        fotos_existentes = query(
            "SELECT id, url, storage_path FROM orcamento_fotos WHERE orcamento_id=%s ORDER BY id",
            (edicao["orcamento_id"],),
        )
    if fotos_existentes:
        st.write("Fotos já anexadas:")
        for foto in fotos_existentes:
            col_img, col_chk, col_rem = st.columns([3, 2, 1])
            with col_img:
                st.image(foto["url"], use_container_width=True)
            with col_chk:
                cfg_key = f"foto_pi_{foto['id']}"
                val_atual = st.session_state[chave_fotos_cfg].get(foto["id"], False)
                nova_val = st.checkbox("Página inteira", value=val_atual, key=cfg_key)
                st.session_state[chave_fotos_cfg][foto["id"]] = nova_val
            with col_rem:
                st.write("")
                if st.button("🗑️", key=f"orc_rem_foto_{foto['id']}"):
                    try:
                        excluir_foto(foto["storage_path"])
                    except Exception:
                        pass
                    execute("DELETE FROM orcamento_fotos WHERE id=%s", (foto["id"],))
                    st.rerun()

    fotos_upload = st.file_uploader(
        "Adicionar fotos", type=["png", "jpg", "jpeg"],
        accept_multiple_files=True, key="orc_upload_fotos",
    )
    # Checkboxes para novas fotos (antes de salvar)
    cfg_novas = {}
    if fotos_upload:
        st.write("Configurar novas fotos:")
        for foto in fotos_upload:
            cfg_novas[foto.name] = st.checkbox(
                f"Página inteira — {foto.name}",
                key=f"orc_pi_nova_{foto.name}",
            )

    st.divider()

    qualquer_item = any(
        st.session_state[ch]
        for ch in [chave_tecidos, chave_aviamentos, chave_outros, chave_servicos]
    )
    label_botao = "💾 Salvar edição e Gerar PDF" if edicao else "💾 Salvar Orçamento e Gerar PDF"

    if st.button(label_botao, type="primary", disabled=not qualquer_item):
        if edicao:
            orcamento_id = edicao["orcamento_id"]
            execute(
                """UPDATE orcamentos
                   SET cliente_id=%s, observacoes=%s, data_validade=%s, descricao_livre=%s
                   WHERE id=%s""",
                (cliente_selecionado["id"], None, data_validade,
                 descricao_livre or None, orcamento_id),
            )
            execute("DELETE FROM orcamento_itens WHERE orcamento_id=%s", (orcamento_id,))
        else:
            res = execute(
                """INSERT INTO orcamentos
                    (cliente_id, tipo_operacao, tipo_pedido, status,
                     data_validade, descricao_livre)
                   VALUES (%s,'orcamento','confeccao','aguardando_aprovacao',%s,%s)
                   RETURNING id""",
                (cliente_selecionado["id"], data_validade, descricao_livre or None),
            )
            orcamento_id = res["id"]

        # Salva itens das 4 seções como materia_prima ou servico
        secoes_material = [
            (chave_tecidos, "tecido"),
            (chave_aviamentos, "aviamento"),
            (chave_outros, "outros"),
        ]
        for chave_sec, _ in secoes_material:
            for item in st.session_state[chave_sec]:
                execute(
                    """INSERT INTO orcamento_itens
                        (orcamento_id, tipo_item, item_id, descricao, quantidade,
                         valor_unitario, valor_total, observacao_item)
                       VALUES (%s,'materia_prima',%s,%s,%s,%s,%s,%s)""",
                    (orcamento_id, item["item_id"], item["descricao"], item["quantidade"],
                     item["valor_unitario"], item["valor_total"],
                     item.get("observacao_item") or None),
                )
        for item in st.session_state[chave_servicos]:
            execute(
                """INSERT INTO orcamento_itens
                    (orcamento_id, tipo_item, item_id, descricao, quantidade,
                     valor_unitario, valor_total, observacao_item)
                   VALUES (%s,'servico',%s,%s,%s,%s,%s,%s)""",
                (orcamento_id, item["item_id"], item["descricao"], item["quantidade"],
                 item["valor_unitario"], item["valor_total"],
                 item.get("observacao_item") or None),
            )

        # Salva novas fotos e registra configuração página inteira
        fotos_para_pdf_existentes = []
        if fotos_existentes:
            for foto in fotos_existentes:
                fotos_para_pdf_existentes.append({
                    "url": foto["url"],
                    "pagina_inteira": st.session_state[chave_fotos_cfg].get(foto["id"], False),
                })

        fotos_para_pdf_novas = []
        if fotos_upload:
            for foto in fotos_upload:
                extensao = foto.name.split(".")[-1].lower()
                try:
                    url_pub, spath = upload_foto(orcamento_id, foto.read(), extensao)
                    execute(
                        "INSERT INTO orcamento_fotos (orcamento_id, url, storage_path) VALUES (%s,%s,%s)",
                        (orcamento_id, url_pub, spath),
                    )
                    fotos_para_pdf_novas.append({
                        "url": url_pub,
                        "pagina_inteira": cfg_novas.get(foto.name, False),
                    })
                except Exception as e:
                    st.warning(f"Não foi possível enviar '{foto.name}': {e}")

        todas_fotos_pdf = fotos_para_pdf_existentes + fotos_para_pdf_novas

        # Monta estrutura para o PDF
        secoes_pdf = {
            "tecidos": st.session_state[chave_tecidos],
            "aviamentos": st.session_state[chave_aviamentos],
            "outros": st.session_state[chave_outros],
            "servicos": st.session_state[chave_servicos],
        }

        pdf_path = gerar_pdf_orcamento(
            prestador=prestador,
            cliente=cliente_selecionado,
            secoes=secoes_pdf,
            descricao_livre=descricao_livre or "",
            data_validade=data_validade,
            fotos=todas_fotos_pdf,
        )
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        st.success("Alterações salvas!" if edicao else "Orçamento salvo!")
        st.download_button(
            "⬇️ Baixar PDF",
            data=pdf_bytes,
            file_name=f"orcamento_{cliente_selecionado['nome'].replace(' ','_')}.pdf",
            mime="application/pdf",
        )

        for ch in [chave_tecidos, chave_aviamentos, chave_outros, chave_servicos]:
            st.session_state[ch] = []
        st.session_state.pop(chave_edicao_ativa, None)
        st.session_state.pop(chave_carregado, None)
        st.session_state[chave_fotos_cfg] = {}


# ── helpers internos do orçamento ──

def _secao_material(titulo, chave, materiais, tipo_material_key):
    """Renderiza uma seção de material (Tecido / Aviamento / Outros) no orçamento."""
    st.subheader(titulo)
    col_mat, col_btn = st.columns([5, 1])
    with col_mat:
        if materiais:
            mat_opcoes = {
                f"{m['nome']} (R$ {formatar_moeda(float(m['valor']))}/{TIPO_LABELS_MATERIAL[m['tipo_medida']]})": m
                for m in materiais
            }
            mat_esc = st.selectbox("Material", options=list(mat_opcoes.keys()), key=f"orc_sel_{tipo_material_key}")
            qtd = st.number_input("Quantidade", min_value=0.0, step=0.5, key=f"orc_qtd_{tipo_material_key}")
            obs_add = st.text_input(
                "Observação (opcional)", key=f"orc_obs_{tipo_material_key}",
                placeholder="Ex: cor azul marinho, largura 1,50m...",
            )
        else:
            st.caption(f"Nenhum material do tipo '{TIPO_MATERIAL_LABELS[tipo_material_key]}' cadastrado.")
    with col_btn:
        st.write("")
        st.write("")
        if st.button("➕ Novo", key=f"orc_btn_novo_{tipo_material_key}"):
            _dialog_novo_material()

    if materiais and st.button("Adicionar", key=f"orc_add_{tipo_material_key}"):
        if qtd > 0:
            m = mat_opcoes[mat_esc]
            un = TIPO_LABELS_MATERIAL[m["tipo_medida"]]
            st.session_state[chave].append({
                "item_id": m["id"],
                "descricao": f"{m['nome']}/{un}",
                "quantidade": qtd,
                "valor_unitario": float(m["valor"]),
                "valor_total": round(float(m["valor"]) * qtd, 2),
                "observacao_item": obs_add,
            })
            st.rerun()
        else:
            st.error("Quantidade deve ser maior que zero.")

    _listar_itens_simples(chave, prefixo=tipo_material_key)


def _listar_itens_simples(chave, prefixo):
    """Lista itens de uma seção com opção de remover."""
    itens = st.session_state.get(chave, [])
    if not itens:
        return
    for idx, item in enumerate(itens):
        col_a, col_b = st.columns([5, 1])
        with col_a:
            linha = (
                f"**{item['descricao']}** — {item['quantidade']:.2f} x "
                f"{formatar_reais(item['valor_unitario'])} = {formatar_reais(item['valor_total'])}"
            )
            if item.get("observacao_item"):
                linha += f"  \n　*{item['observacao_item']}*"
            st.markdown(linha)
        with col_b:
            if st.button("Remover", key=f"orc_rem_{prefixo}_{idx}"):
                st.session_state[chave].pop(idx)
                st.rerun()


def _carregar_itens_orcamento(orcamento_id, chave_tecidos, chave_aviamentos, chave_outros, chave_servicos):
    """
    Ao editar um orçamento existente, redistribui os itens salvos
    nas quatro seções corretas consultando o tipo_material do cadastro.
    """
    from database import query as db_query
    itens = db_query(
        """SELECT oi.*, mp.tipo_material
           FROM orcamento_itens oi
           LEFT JOIN materia_prima mp ON mp.id = oi.item_id AND oi.tipo_item = 'materia_prima'
           WHERE oi.orcamento_id = %s AND oi.servico_pai_item_id IS NULL
           ORDER BY oi.id""",
        (orcamento_id,),
    )
    tecidos, aviamentos, outros, servicos = [], [], [], []
    for i in itens:
        entry = {
            "item_id": i["item_id"],
            "descricao": i["descricao"],
            "quantidade": float(i["quantidade"]),
            "valor_unitario": float(i["valor_unitario"]),
            "valor_total": float(i["valor_total"]),
            "observacao_item": i.get("observacao_item") or "",
        }
        if i["tipo_item"] == "servico":
            servicos.append(entry)
        else:
            tipo_mat = i.get("tipo_material") or "outros"
            if tipo_mat == "tecido":
                tecidos.append(entry)
            elif tipo_mat == "aviamento":
                aviamentos.append(entry)
            else:
                outros.append(entry)

    st.session_state[chave_tecidos] = tecidos
    st.session_state[chave_aviamentos] = aviamentos
    st.session_state[chave_outros] = outros
    st.session_state[chave_servicos] = servicos
