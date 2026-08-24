"""
Geração de PDFs:
  gerar_pdf_os()        — Ordem de Serviço
  gerar_pdf_orcamento() — Orçamento (nova estrutura Bloco F)
"""

from fpdf import FPDF
from datetime import datetime
import tempfile, os, urllib.request
from constants import formatar_moeda


# ════════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ════════════════════════════════════════════════════════════════════

def _tmp(dados_bytes, sufixo=".png"):
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
            pdf.image(logo_path, x=10, y=15, w=25)
        except Exception:
            x_txt = 10
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(x_txt, 15)
    pdf.cell(0, 6, prestador.get("nome", ""), ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(x_txt)
    contato = " | ".join(filter(None, [
        f"Tel: {prestador['telefone']}" if prestador.get("telefone") else "",
        f"Email: {prestador['email']}"  if prestador.get("email")    else "",
        f"CNPJ: {prestador['cnpj']}"   if prestador.get("cnpj")     else "",
    ]))
    pdf.cell(0, 6, contato, ln=True)
    pdf.ln(4)


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
        pdf.cell(lc, 5, linhas_esq[i] if i < len(linhas_esq) else "", ln=False)
        pdf.set_xy(xd, y_l)
        pdf.cell(lc, 5, linhas_dir[i] if i < len(linhas_dir) else "", ln=True)
    pdf.ln(5)


def _bloco_assinaturas(pdf, prestador, cliente, assinatura_path):
    pdf.ln(10)
    la = 85
    esp = 10
    xe, xd = 10, 10 + la + esp
    y0 = pdf.get_y()

    if assinatura_path:
        try:
            pdf.image(assinatura_path, x=xe, y=y0, w=la, h=14)
        except Exception:
            pdf.set_xy(xe, y0 + 8)
            pdf.cell(la, 6, "_" * 40, align="C", ln=False)
    else:
        pdf.set_xy(xe, y0 + 8)
        pdf.cell(la, 6, "_" * 40, align="C", ln=False)

    pdf.set_xy(xd, y0 + 8)
    pdf.cell(la, 6, "_" * 40, align="C", ln=True)

    y1 = max(pdf.get_y(), y0 + 14) + 1
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(xe, y1); pdf.cell(la, 5, "Assinatura do Prestador", align="C", ln=False)
    pdf.set_xy(xd, y1); pdf.cell(la, 5, "Assinatura do Cliente",   align="C", ln=True)

    y2 = pdf.get_y()
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(xe, y2); pdf.cell(la, 5, prestador.get("nome", ""), align="C", ln=False)
    pdf.set_xy(xd, y2); pdf.cell(la, 5, cliente.get("nome", ""),   align="C", ln=True)

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
    assinatura_path = _tmp(prestador["assinatura"]) if prestador.get("assinatura") else None

    _cabecalho_prestador(pdf, prestador, logo_path)
    _bloco_cliente_datas(pdf, cliente,
                         "Entrega prevista" if data_entrega else None,
                         data_entrega)

    # Tabela de itens
    cw = [85, 25, 35, 35]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(cw, ["Descrição", "Qtd.", "Valor Unit. (R$)", "Total (R$)"]):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    total_geral = 0
    for g in grupos:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(cw[0], 7, str(g["descricao"])[:50], border=1)
        pdf.cell(cw[1], 7, f"{g['quantidade']:.2f}", border=1, align="C")
        pdf.cell(cw[2], 7, formatar_moeda(g["valor_unitario"]), border=1, align="C")
        pdf.cell(cw[3], 7, formatar_moeda(g["valor_total"]),    border=1, align="C")
        pdf.ln()

        if g.get("observacao_item"):
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(sum(cw), 5, f"  Obs: {g['observacao_item'][:100]}", border=0)
            pdf.ln()

        subtotal = g["valor_total"]
        pdf.set_font("Helvetica", "", 8)
        for m in g.get("materiais", []):
            pdf.cell(cw[0], 6, f"   > {str(m['descricao'])[:45]}", border=1)
            pdf.cell(cw[1], 6, f"{m['quantidade']:.2f}", border=1, align="C")
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

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(sum(cw[:3]), 8, "TOTAL GERAL", border=1, align="R")
    pdf.cell(cw[3], 8, f"R$ {formatar_moeda(total_geral)}", border=1, align="C")
    pdf.ln(12)

    if observacoes:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Observações", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, observacoes)
        pdf.ln(4)

    _bloco_assinaturas(pdf, prestador, cliente, assinatura_path)

    out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    pdf.output(out)
    _limpar(logo_path, assinatura_path)
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
    assinatura_path = _tmp(prestador["assinatura"]) if prestador.get("assinatura") else None

    # ── Página 1: cabeçalho + cliente/datas ──
    _cabecalho_prestador(pdf, prestador, logo_path)
    _bloco_cliente_datas(pdf, cliente,
                         "Válido até" if data_validade else None,
                         data_validade)

    pdf.ln(2)

    # ── Seções de itens ──
    secoes_config = [
        ("tecidos",    "Tecidos"),
        ("aviamentos", "Aviamentos"),
        ("outros",     "Outros materiais"),
        ("servicos",   "Serviços"),
    ]

    cw = [95, 22, 35, 28]   # Descrição | Qtd | Valor unit | Total
    total_geral = 0
    alguma_secao = False

    for chave_sec, titulo_sec in secoes_config:
        itens = secoes.get(chave_sec, [])
        if not itens:
            continue
        alguma_secao = True

        # Título da seção
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(210, 210, 210)
        pdf.cell(0, 7, f"  {titulo_sec}", border=1, fill=True, ln=True)

        # Cabeçalho da tabela
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(235, 235, 235)
        for w, h in zip(cw, ["Descrição", "Qtd.", "Valor Unit. (R$)", "Total (R$)"]):
            pdf.cell(w, 6, h, border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 9)
        for item in itens:
            # Linha principal do item
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(cw[0], 6, str(item["descricao"])[:55], border=1)
            pdf.cell(cw[1], 6, f"{item['quantidade']:.2f}", border=1, align="C")
            pdf.cell(cw[2], 6, formatar_moeda(item["valor_unitario"]), border=1, align="C")
            pdf.cell(cw[3], 6, formatar_moeda(item["valor_total"]),    border=1, align="C")
            pdf.ln()

            # Observação na linha seguinte, em itálico
            if item.get("observacao_item"):
                pdf.set_font("Helvetica", "I", 8)
                pdf.cell(sum(cw), 5, f"  ↳ {item['observacao_item'][:110]}", border=0)
                pdf.ln()

            total_geral += item["valor_total"]

        pdf.ln(2)

    if alguma_secao:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(sum(cw[:3]), 8, "TOTAL GERAL", border=1, align="R")
        pdf.cell(cw[3], 8, f"R$ {formatar_moeda(total_geral)}", border=1, align="C")
        pdf.ln(8)

    # ── Descrição livre ──
    if descricao_livre:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Descrição", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, descricao_livre)
        pdf.ln(4)

    # ── Assinaturas (ainda na página 1 / continua na mesma) ──
    _bloco_assinaturas(pdf, prestador, cliente, assinatura_path)

    # ── Páginas seguintes: fotos ──
    if fotos:
        imgs_baixadas = []
        for cfg in fotos:
            path_img = _baixar_imagem(cfg["url"])
            if path_img:
                imgs_baixadas.append({"path": path_img, "pagina_inteira": cfg.get("pagina_inteira", False)})

        # Separa fotos de página inteira das normais (até 4 por página)
        buf_normais = []
        for img in imgs_baixadas:
            if img["pagina_inteira"]:
                # Descarrega buffer de normais antes
                if buf_normais:
                    _pagina_fotos_grade(pdf, buf_normais)
                    buf_normais = []
                _pagina_foto_inteira(pdf, img["path"])
            else:
                buf_normais.append(img["path"])
                if len(buf_normais) == 4:
                    _pagina_fotos_grade(pdf, buf_normais)
                    buf_normais = []

        if buf_normais:
            _pagina_fotos_grade(pdf, buf_normais)

        _limpar(*[i["path"] for i in imgs_baixadas])

    # ── Cláusulas (última página) ──
    clausulas = prestador.get("clausulas") or ""
    if clausulas:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Cláusulas e Condições", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, clausulas)

    out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    pdf.output(out)
    _limpar(logo_path, assinatura_path)
    return out


def _pagina_foto_inteira(pdf, img_path):
    """Adiciona uma página com a foto ocupando toda a área útil."""
    pdf.add_page()
    try:
        pdf.image(img_path, x=10, y=25, w=190, h=245)
    except Exception:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_y(120)
        pdf.cell(0, 6, "[Imagem não pôde ser carregada]", align="C", ln=True)


def _pagina_fotos_grade(pdf, paths):
    """Adiciona uma página com até 4 fotos em grade 2x2."""
    pdf.add_page()
    posicoes = [
        (10,  25, 90, 110),
        (110, 25, 90, 110),
        (10, 145, 90, 110),
        (110, 145, 90, 110),
    ]
    for i, path in enumerate(paths[:4]):
        x, y, w, h = posicoes[i]
        try:
            pdf.image(path, x=x, y=y, w=w, h=h)
        except Exception:
            pdf.set_xy(x, y + h / 2)
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(w, 6, "[Imagem indisponível]", align="C")
