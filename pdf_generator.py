"""
Geração de PDFs:
  gerar_pdf_os()        — Ordem de Serviço
  gerar_pdf_orcamento() — Orçamento (nova estrutura Bloco F)
"""

from fpdf import FPDF
from datetime import datetime
import tempfile, os, urllib.request
from constants import formatar_moeda, formatar_quantidade, separar_descricao_unidade



# ════════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ════════════════════════════════════════════════════════════════════

def _txt(texto):
    """
    Sanitiza texto para uso com fontes core do fpdf2 (Latin-1 / cp1252).
    Substitui caracteres fora do range por equivalentes ASCII ou os remove,
    evitando FPDFUnicodeEncodingException em qualquer entrada do usuário.
    """
    if not texto:
        return ""
    SUBSTITUICOES = {
        "\u2192": "->", "\u2190": "<-", "\u2194": "<->",
        "\u21b3": ">",  "\u2713": "OK", "\u2714": "OK",
        "\u2718": "X",  "\u2022": "-",  "\u2026": "...",
        "\u2018": "'",  "\u2019": "'",  "\u201c": '"',  "\u201d": '"',
        "\u2013": "-",  "\u2014": "--", "\u00b0": "o",
    }
    resultado = []
    for c in str(texto):
        c2 = SUBSTITUICOES.get(c, c)
        for ch in c2:
            try:
                ch.encode("latin-1")
                resultado.append(ch)
            except UnicodeEncodeError:
                resultado.append("?")
    return "".join(resultado)


def _tmp(dados_bytes, sufixo=".png"):
    """Salva bytes em arquivo temporário e retorna o caminho."""
    t = tempfile.NamedTemporaryFile(delete=False, suffix=sufixo)
    t.write(bytes(dados_bytes))
    t.close()
    return t.name

def _baixar_imagem(url):
    """Baixa uma imagem de URL pública para arquivo temporário. Retorna path ou None."""
    try:
        sufixo = "." + url.split(".")[-1].split("?")[0].lower()
        if sufixo not in (".png", ".jpg", ".jpeg"):
            sufixo = ".jpg"
        t = tempfile.NamedTemporaryFile(delete=False, suffix=sufixo)
        urllib.request.urlretrieve(url, t.name)
        return t.name
    except Exception:
        return None

def _limpar(*paths):
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


class _PDF(FPDF):
    def __init__(self, titulo):
        super().__init__()
        self.titulo_doc = titulo
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, self.titulo_doc, ln=True, align="C")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")


def _cabecalho_prestador(pdf, prestador, logo_path):
    """Imprime logo + dados do prestador. Retorna y após o bloco."""
    x_txt = 40 if logo_path else 10
    if logo_path:
        try:
            pdf.image(logo_path, x=10, y=20, w=25)
        except Exception:
            x_txt = 10
    # Desce para dar espaço entre o título do documento (header) e os dados da empresa
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(x_txt, 26)
    pdf.cell(0, 6, _txt(prestador.get("nome", "")), ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(x_txt)
    contato = " | ".join(filter(None, [
        f"Tel: {prestador['telefone']}" if prestador.get("telefone") else "",
        f"Email: {prestador['email']}"  if prestador.get("email")    else "",
        f"CNPJ: {prestador['cnpj']}"   if prestador.get("cnpj")     else "",
    ]))
    pdf.cell(0, 6, _txt(contato), ln=True)
    pdf.ln(8)


def _bloco_cliente_datas(pdf, cliente, label_data, valor_data):
    """Bloco duplo Cliente (esq) | Documento (dir)."""
    lc = 90
    esp = 10
    xe, xd = 10, 10 + lc + esp
    y0 = pdf.get_y()

    pdf.set_xy(xe, y0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(lc, 6, "Cliente", ln=False)
    pdf.set_xy(xd, y0)
    pdf.cell(lc, 6, "Documento", ln=True)

    pdf.set_font("Helvetica", "", 9)
    linhas_esq = [
        f"Nome: {cliente.get('nome', '')}",
        f"Telefone: {cliente.get('telefone') or '-'}",
        f"Email: {cliente.get('email') or '-'}",
    ]
    if cliente.get("endereco"):
        linhas_esq.append(f"Endereço: {cliente['endereco']}")

    linhas_dir = [f"Emissão: {datetime.now().strftime('%d/%m/%Y')}"]
    if label_data and valor_data:
        linhas_dir.append(f"{label_data}: {valor_data.strftime('%d/%m/%Y')}")

    max_linhas = max(len(linhas_esq), len(linhas_dir))
    for i in range(max_linhas):
        y_l = pdf.get_y()
        pdf.set_xy(xe, y_l)
        pdf.cell(lc, 5, _txt(linhas_esq[i]) if i < len(linhas_esq) else "", ln=False)
        pdf.set_xy(xd, y_l)
        pdf.cell(lc, 5, _txt(linhas_dir[i]) if i < len(linhas_dir) else "", ln=True)
    pdf.ln(9)


def _bloco_assinaturas(pdf, prestador, cliente):
    if pdf.get_y() > pdf.h - 45:
        pdf.add_page()
    pdf.ln(8)
    la = 85
    esp = 10
    xe, xd = 10, 10 + la + esp
    y0 = pdf.get_y()

    pdf.set_xy(xe, y0 + 6)
    pdf.cell(la, 6, "_" * 40, align="C", ln=False)

    pdf.set_xy(xd, y0 + 6)
    pdf.cell(la, 6, "_" * 40, align="C", ln=True)

    y1 = y0 + 12
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(xe, y1); pdf.cell(la, 5, "Assinatura do Prestador", align="C", ln=False)
    pdf.set_xy(xd, y1); pdf.cell(la, 5, "Assinatura do Cliente",   align="C", ln=True)

    y2 = pdf.get_y()
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(xe, y2); pdf.cell(la, 5, _txt(prestador.get("nome", "")), align="C", ln=False)
    pdf.set_xy(xd, y2); pdf.cell(la, 5, _txt(cliente.get("nome", "")),   align="C", ln=True)

    y3 = pdf.get_y() + 2
    pdf.set_xy(xe, y3); pdf.cell(la, 5, "Data/Hora: ____/____/______  ____:____", align="C", ln=False)
    pdf.set_xy(xd, y3); pdf.cell(la, 5, "Data/Hora: ____/____/______  ____:____", align="C", ln=True)


# ════════════════════════════════════════════════════════════════════
# ORDEM DE SERVIÇO
# ════════════════════════════════════════════════════════════════════

def gerar_pdf_os(prestador, cliente, grupos, observacoes="", data_entrega=None):
    """
    grupos: [{descricao, quantidade, valor_unitario, valor_total,
              observacao_item, materiais:[{descricao,quantidade,valor_unitario,valor_total}]}]
    """
    pdf = _PDF("ORDEM DE SERVIÇO")
    pdf.add_page()

    logo_path = _tmp(prestador["logo"]) if prestador.get("logo") else None

    _cabecalho_prestador(pdf, prestador, logo_path)
    _bloco_cliente_datas(pdf, cliente,
                         "Entrega prevista" if data_entrega else None,
                         data_entrega)

    # Tabela de itens — ordem: Qtd. | Descrição | Valor Unit. | Total
    cw = [24, 86, 35, 35]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(cw, ["Qtd.", "Descrição", "Valor Unit. (R$)", "Total (R$)"]):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    total_geral = 0
    for g in grupos:
        desc_limpa, un = separar_descricao_unidade(str(g.get("descricao", "")))
        desc_final = _txt(desc_limpa)
        if g.get("observacao_item"):
            desc_final = f"{desc_final} - {_txt(g['observacao_item'])}"

        qtd_str = formatar_quantidade(g["quantidade"], un)

        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(cw[0], 7, _txt(qtd_str), border=1, align="C")
        pdf.cell(cw[1], 7, desc_final[:60], border=1)
        pdf.cell(cw[2], 7, formatar_moeda(g["valor_unitario"]), border=1, align="C")
        pdf.cell(cw[3], 7, formatar_moeda(g["valor_total"]),    border=1, align="C")
        pdf.ln()

        subtotal = g["valor_total"]
        pdf.set_font("Helvetica", "", 8)
        for m in g.get("materiais", []):
            desc_m_limpa, un_m = separar_descricao_unidade(str(m.get("descricao", "")))
            desc_m_final = _txt(desc_m_limpa)
            if m.get("observacao_item"):
                desc_m_final = f"{desc_m_final} - {_txt(m['observacao_item'])}"
            qtd_m_str = formatar_quantidade(m["quantidade"], un_m)

            pdf.cell(cw[0], 6, _txt(qtd_m_str), border=1, align="C")
            pdf.cell(cw[1], 6, _txt(f"  > {desc_m_final[:50]}"), border=1)
            pdf.cell(cw[2], 6, formatar_moeda(m["valor_unitario"]), border=1, align="C")
            pdf.cell(cw[3], 6, formatar_moeda(m["valor_total"]),    border=1, align="C")
            pdf.ln()
            subtotal += m["valor_total"]

        if g.get("materiais"):
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(sum(cw[:3]), 6, "Subtotal do serviço", border=1, align="R")
            pdf.cell(cw[3], 6, formatar_moeda(subtotal), border=1, align="C")
            pdf.ln()

        total_geral += subtotal

    # Coleta descontos dos serviços
    descontos_os = []
    for g in grupos:
        d_val = float(g.get("desconto_calculado") or 0.0)
        if d_val > 0:
            motivo = (g.get("motivo_desconto") or "").strip() or "Desconto"
            descontos_os.append({"motivo": motivo, "valor": d_val})

    if descontos_os:
        # Seção de Descontos na tabela
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(210, 210, 210)
        pdf.cell(sum(cw), 6, _txt("  Descontos"), border=1, fill=True, ln=True)

        pdf.set_font("Helvetica", "", 9)
        total_descontos = 0.0
        for d in descontos_os:
            pdf.cell(cw[0], 6, "-", border=1, align="C")
            pdf.cell(cw[1], 6, _txt(d["motivo"])[:60], border=1)
            pdf.cell(cw[2], 6, "-", border=1, align="C")
            pdf.cell(cw[3], 6, f"- {formatar_moeda(d['valor'])}", border=1, align="C")
            pdf.ln()
            total_descontos += d["valor"]

        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(sum(cw[:3]), 7, "Subtotal dos itens", border=1, align="R")
        pdf.cell(cw[3], 7, f"R$ {formatar_moeda(total_geral)}", border=1, align="C")
        pdf.ln()

        pdf.cell(sum(cw[:3]), 7, "Subtotal dos descontos", border=1, align="R")
        pdf.cell(cw[3], 7, f"- R$ {formatar_moeda(total_descontos)}", border=1, align="C")
        pdf.ln()

        total_liquido = max(0.0, total_geral - total_descontos)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(sum(cw[:3]), 8, "TOTAL GERAL", border=1, align="R")
        pdf.cell(cw[3], 8, f"R$ {formatar_moeda(total_liquido)}", border=1, align="C")
        pdf.ln(8)
    else:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(sum(cw[:3]), 8, "TOTAL GERAL", border=1, align="R")
        pdf.cell(cw[3], 8, f"R$ {formatar_moeda(total_geral)}", border=1, align="C")
        pdf.ln(8)

    if observacoes:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Observações", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _txt(observacoes))
        pdf.ln(4)

    # Assinaturas removidas da Ordem de Serviço conforme solicitação
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    pdf.output(out)
    _limpar(logo_path)
    return out



# ════════════════════════════════════════════════════════════════════
# ORÇAMENTO — nova estrutura (Bloco F)
# ════════════════════════════════════════════════════════════════════

def gerar_pdf_orcamento(prestador, cliente, secoes, descricao_livre="",
                        data_validade=None, fotos=None):
    """
    secoes: {
      'tecidos':    [{item_id, descricao, quantidade, valor_unitario, valor_total, observacao_item}],
      'aviamentos': [...],
      'outros':     [...],
      'servicos':   [...],
    }
    fotos: [{url, pagina_inteira}]
    """
    fotos = fotos or []
    pdf = _PDF("ORÇAMENTO")
    pdf.add_page()

    logo_path = _tmp(prestador["logo"]) if prestador.get("logo") else None

    _cabecalho_prestador(pdf, prestador, logo_path)
    _bloco_cliente_datas(pdf, cliente,
                         "Válido até" if data_validade else None,
                         data_validade)

    pdf.ln(2)

    # ── Tabela única de itens com seções ──
    # Cabeçalho das colunas aparece UMA VEZ só no topo da tabela
    # Títulos de seção (Tecidos, Aviamentos…) usam a mesma largura total das colunas
    secoes_config = [
        ("tecidos",    "Tecidos"),
        ("aviamentos", "Aviamentos"),
        ("outros",     "Outros materiais"),
        ("servicos",   "Serviços"),
    ]

    cw = [24, 93, 35, 28]   # Qtd | Descrição | Valor unit | Total
    largura_total = sum(cw)  # 180 mm — mesma largura para títulos e cabeçalho
    total_geral = 0

    # Filtra seções que têm itens
    secoes_com_itens = [
        (chave, titulo, secoes.get(chave, []))
        for chave, titulo in secoes_config
        if secoes.get(chave)
    ]

    if secoes_com_itens:
        # Cabeçalho único das colunas
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(235, 235, 235)
        for w, h in zip(cw, ["Qtd.", "Descrição", "Valor Unit. (R$)", "Total (R$)"]):
            pdf.cell(w, 6, h, border=1, fill=True, align="C")
        pdf.ln()

        for chave_sec, titulo_sec, itens in secoes_com_itens:
            # Título da seção com largura igual à soma das colunas
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(210, 210, 210)
            pdf.cell(largura_total, 6, _txt(f"  {titulo_sec}"), border=1, fill=True, ln=True)

            pdf.set_font("Helvetica", "", 9)
            for item in itens:
                desc_limpa, un = separar_descricao_unidade(str(item.get("descricao", "")))
                desc_final = _txt(desc_limpa)
                if item.get("observacao_item"):
                    desc_final = f"{desc_final} - {_txt(item['observacao_item'])}"

                qtd_str = formatar_quantidade(item["quantidade"], un)

                pdf.cell(cw[0], 6, _txt(qtd_str), border=1, align="C")
                pdf.cell(cw[1], 6, desc_final[:60], border=1)
                pdf.cell(cw[2], 6, formatar_moeda(item["valor_unitario"]), border=1, align="C")
                pdf.cell(cw[3], 6, formatar_moeda(item["valor_total"]),    border=1, align="C")
                pdf.ln()
                total_geral += item["valor_total"]

        # Coleta descontos dos serviços
        descontos_orc = []
        for srv in secoes.get("servicos", []):
            d_val = float(srv.get("desconto_calculado") or 0.0)
            if d_val > 0:
                motivo = (srv.get("motivo_desconto") or "").strip() or "Desconto"
                descontos_orc.append({"motivo": motivo, "valor": d_val})

        if descontos_orc:
            # Seção de Descontos na tabela
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(210, 210, 210)
            pdf.cell(largura_total, 6, _txt("  Descontos"), border=1, fill=True, ln=True)

            pdf.set_font("Helvetica", "", 9)
            total_descontos = 0.0
            for d in descontos_orc:
                pdf.cell(cw[0], 6, "-", border=1, align="C")
                pdf.cell(cw[1], 6, _txt(d["motivo"])[:60], border=1)
                pdf.cell(cw[2], 6, "-", border=1, align="C")
                pdf.cell(cw[3], 6, f"- {formatar_moeda(d['valor'])}", border=1, align="C")
                pdf.ln()
                total_descontos += d["valor"]

            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(sum(cw[:3]), 7, "Subtotal dos itens", border=1, align="R")
            pdf.cell(cw[3], 7, f"R$ {formatar_moeda(total_geral)}", border=1, align="C")
            pdf.ln()

            pdf.cell(sum(cw[:3]), 7, "Subtotal dos descontos", border=1, align="R")
            pdf.cell(cw[3], 7, f"- R$ {formatar_moeda(total_descontos)}", border=1, align="C")
            pdf.ln()

            total_liquido = max(0.0, total_geral - total_descontos)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(sum(cw[:3]), 8, "TOTAL GERAL", border=1, align="R")
            pdf.cell(cw[3], 8, f"R$ {formatar_moeda(total_liquido)}", border=1, align="C")
            pdf.ln(8)
        else:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(sum(cw[:3]), 8, "TOTAL GERAL", border=1, align="R")
            pdf.cell(cw[3], 8, f"R$ {formatar_moeda(total_geral)}", border=1, align="C")
            pdf.ln(8)

    # ── Descrição livre ──
    if descricao_livre:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Descrição", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _txt(descricao_livre))
        pdf.ln(4)

    # ── Fotos ──
    # Baixa e comprime todas as imagens antes de inserir no PDF
    imgs_baixadas = []
    if fotos:
        for cfg in fotos:
            path_img = _baixar_e_comprimir(cfg["url"])
            if path_img:
                imgs_baixadas.append({
                    "path": path_img,
                    "pagina_inteira": cfg.get("pagina_inteira", False),
                })

    # ── Cláusulas ──
    clausulas = _txt(prestador.get("clausulas") or "")

    # Altura estimada do bloco de assinaturas
    ALTURA_ASSINATURA = 42  # mm
    MARGEM_INF = 20  # mesma margem inferior do set_auto_page_break

    # Processa fotos: página inteira separada, normais em grade 2×2 com proporção
    buf_normais = []

    def descarregar_buf():
        nonlocal buf_normais
        if buf_normais:
            _pagina_fotos_grade_prop(pdf, buf_normais)
            buf_normais = []

    for img in imgs_baixadas:
        if img["pagina_inteira"]:
            descarregar_buf()
            _pagina_foto_inteira_prop(pdf, img["path"])
        else:
            buf_normais.append(img["path"])
            if len(buf_normais) == 4:
                descarregar_buf()

    # Último lote de fotos normais (< 4 fotos)
    if buf_normais:
        n = len(buf_normais)
        linhas_grade = 1 if n <= 2 else 2
        altura_fotos = linhas_grade * 110

        altura_cls = 0
        if clausulas:
            n_linhas_cls = sum(
                max(1, len(linha) // 80 + 1) for linha in clausulas.split("\n")
            )
            altura_cls = 8 + n_linhas_cls * 5 + 4

        altura_necessaria = altura_fotos + altura_cls + ALTURA_ASSINATURA + 10
        area_util = pdf.h - MARGEM_INF - 25

        if altura_necessaria <= area_util:
            pdf.add_page()
            _inserir_fotos_grade_prop_na_pagina_atual(pdf, buf_normais)
            buf_normais = []
            _inserir_clausulas_e_assinaturas(pdf, clausulas, prestador, cliente)
        else:
            descarregar_buf()
            _inserir_clausulas_e_assinaturas(pdf, clausulas, prestador, cliente)
    else:
        _inserir_clausulas_e_assinaturas(pdf, clausulas, prestador, cliente)

    _limpar(*[i["path"] for i in imgs_baixadas])

    out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    pdf.output(out)
    _limpar(logo_path)
    return out



# ── Helpers de foto e layout ──────────────────────────────────────────

def _baixar_e_comprimir(url):
    """
    Baixa imagem da URL, comprime para JPEG (qualidade 60) usando Pillow se
    disponível, e retorna o path do arquivo temporário resultante.
    Sem Pillow, apenas baixa sem comprimir.
    """
    path_orig = _baixar_imagem(url)
    if not path_orig:
        return None
    try:
        from PIL import Image as PilImage
        img = PilImage.open(path_orig)
        # Converte para RGB (JPEG não suporta transparência)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        # Redimensiona se muito grande (max 1200px no maior lado)
        max_px = 1200
        if max(img.width, img.height) > max_px:
            img.thumbnail((max_px, max_px), PilImage.LANCZOS)
        out = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        img.save(out.name, "JPEG", quality=60, optimize=True)
        out.close()
        _limpar(path_orig)
        return out.name
    except Exception:
        # Pillow não disponível ou falha — usa o arquivo original
        return path_orig


def _dimensoes_proporcional(img_w_px, img_h_px, max_w_mm, max_h_mm):
    """
    Calcula (w_mm, h_mm) mantendo a proporção original dentro da caixa max.
    Usa 96 dpi como referência de conversão px → mm.
    """
    if img_w_px <= 0 or img_h_px <= 0:
        return max_w_mm, max_h_mm
    px_por_mm = 96 / 25.4
    img_w_mm = img_w_px / px_por_mm
    img_h_mm = img_h_px / px_por_mm
    escala = min(max_w_mm / img_w_mm, max_h_mm / img_h_mm, 1.0)
    return img_w_mm * escala, img_h_mm * escala


def _dimensoes_imagem(path):
    """Retorna (largura_px, altura_px) da imagem, ou (0,0) se falhar."""
    try:
        from PIL import Image as PilImage
        with PilImage.open(path) as img:
            return img.width, img.height
    except Exception:
        return 0, 0


def _pagina_foto_inteira_prop(pdf, img_path):
    """Página com foto em proporção original, centralizada na área útil."""
    pdf.add_page()
    max_w, max_h = 190, 245
    w_px, h_px = _dimensoes_imagem(img_path)
    w_mm, h_mm = _dimensoes_proporcional(w_px, h_px, max_w, max_h)
    x = 10 + (max_w - w_mm) / 2
    y = 25 + (max_h - h_mm) / 2
    try:
        pdf.image(img_path, x=x, y=y, w=w_mm, h=h_mm)
    except Exception:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_y(120)
        pdf.cell(0, 6, "[Imagem não pôde ser carregada]", align="C", ln=True)


def _pagina_fotos_grade_prop(pdf, paths):
    """Nova página com até 4 fotos em grade 2×2, proporção mantida."""
    pdf.add_page()
    _inserir_fotos_grade_prop_na_pagina_atual(pdf, paths)


def _inserir_fotos_grade_prop_na_pagina_atual(pdf, paths):
    """
    Insere até 4 fotos em grade 2×2 NA PÁGINA ATUAL (sem add_page).
    Cada célula: 90×110 mm. Foto centralizada dentro da célula com proporção.
    Após inserir, avança o cursor para abaixo da última linha ocupada,
    garantindo que o conteúdo seguinte não sobreponha as fotos.
    """
    celulas = [
        (10,  25, 90, 110),
        (110, 25, 90, 110),
        (10, 145, 90, 110),
        (110, 145, 90, 110),
    ]
    n = len(paths[:4])
    y_max = 25  # rastreia o ponto mais baixo ocupado pelas fotos
    for i in range(n):
        cx, cy, cw_c, ch_c = celulas[i]
        w_px, h_px = _dimensoes_imagem(paths[i])
        w_mm, h_mm = _dimensoes_proporcional(w_px, h_px, cw_c, ch_c)
        x = cx + (cw_c - w_mm) / 2
        y = cy + (ch_c - h_mm) / 2
        try:
            pdf.image(paths[i], x=x, y=y, w=w_mm, h=h_mm)
        except Exception:
            pdf.set_xy(cx, cy + ch_c / 2)
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(cw_c, 6, "[Imagem indisponível]", align="C")
        # Registra o fundo da célula (não da imagem) como limite inferior
        y_max = max(y_max, cy + ch_c)
    # Posiciona o cursor logo abaixo das fotos com folga de 6 mm
    pdf.set_y(y_max + 6)


def _inserir_clausulas_e_assinaturas(pdf, clausulas, prestador, cliente):
    """Insere bloco de cláusulas (se houver) e assinaturas na posição atual."""
    if clausulas:
        # Se não couber minimamente na página atual, quebra para nova
        if pdf.get_y() > pdf.h - 60:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Cláusulas e Condições", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, clausulas)
        pdf.ln(4)
    _bloco_assinaturas(pdf, prestador, cliente)

