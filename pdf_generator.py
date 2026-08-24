"""
Gera PDFs de Orçamento ou Ordem de Serviço com base nos dados do prestador,
cliente e itens (serviços/matéria-prima) selecionados.
"""

from fpdf import FPDF
from datetime import datetime
import tempfile
import os
from constants import formatar_moeda


class DocumentoPDF(FPDF):
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


def _salvar_imagem_temp(dados_bytes, sufixo=".png"):
    """Salva bytes em arquivo temporário e retorna o caminho."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=sufixo)
    tmp.write(bytes(dados_bytes))
    tmp.close()
    return tmp.name


def gerar_pdf(tipo, prestador, cliente, grupos, observacoes="",
              data_validade=None, data_entrega=None):
    """
    tipo: 'orcamento' ou 'ordem_servico'
    prestador: dict com nome, telefone, email, cnpj, logo (bytes|None),
               assinatura (bytes|None)
    cliente: dict com nome, telefone, email, endereco
    grupos: lista de dicts:
        {descricao, quantidade, valor_unitario, valor_total, observacao_item,
         materiais: [{descricao, quantidade, valor_unitario, valor_total}]}
    observacoes: texto livre do documento
    data_validade: date (só orçamento)
    data_entrega: date (só OS)
    """
    titulo = "ORÇAMENTO" if tipo == "orcamento" else "ORDEM DE SERVIÇO"
    pdf = DocumentoPDF(titulo)
    pdf.add_page()

    # ------------------------------------------------------------------ #
    # Cabeçalho: logo + dados do prestador
    # ------------------------------------------------------------------ #
    logo_path = None
    if prestador.get("logo"):
        try:
            logo_path = _salvar_imagem_temp(prestador["logo"])
            pdf.image(logo_path, x=10, y=10, w=25)
        except Exception:
            logo_path = None

    x_texto = 40 if logo_path else 10
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(x_texto, 15)
    pdf.cell(0, 6, prestador.get("nome", ""), ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(x_texto)
    linha_contato = " | ".join(filter(None, [
        f"Tel: {prestador['telefone']}" if prestador.get("telefone") else "",
        f"Email: {prestador['email']}" if prestador.get("email") else "",
        f"CNPJ: {prestador['cnpj']}" if prestador.get("cnpj") else "",
    ]))
    pdf.cell(0, 6, linha_contato, ln=True)
    pdf.ln(6)

    # ------------------------------------------------------------------ #
    # Bloco duplo: Cliente (esquerda) | Datas do documento (direita)
    # ------------------------------------------------------------------ #
    largura_col = 90
    espaco_centro = 10
    x_esq = 10
    x_dir = x_esq + largura_col + espaco_centro
    y_bloco = pdf.get_y()

    # — Coluna esquerda: dados do cliente —
    pdf.set_xy(x_esq, y_bloco)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(largura_col, 6, "Cliente", ln=False)
    pdf.set_xy(x_dir, y_bloco)

    # — Coluna direita: dados do documento —
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(largura_col, 6, "Documento", ln=True)

    # Linha Nome do cliente / Data de emissão
    pdf.set_font("Helvetica", "", 9)
    y_linha = pdf.get_y()
    pdf.set_xy(x_esq, y_linha)
    pdf.cell(largura_col, 5, f"Nome: {cliente.get('nome', '')}", ln=False)
    pdf.set_xy(x_dir, y_linha)
    pdf.cell(largura_col, 5, f"Emissão: {datetime.now().strftime('%d/%m/%Y')}", ln=True)

    # Linha Telefone / Validade ou Entrega
    y_linha = pdf.get_y()
    pdf.set_xy(x_esq, y_linha)
    pdf.cell(largura_col, 5, f"Telefone: {cliente.get('telefone') or '-'}", ln=False)
    pdf.set_xy(x_dir, y_linha)
    if tipo == "orcamento" and data_validade:
        pdf.cell(largura_col, 5, f"Válido até: {data_validade.strftime('%d/%m/%Y')}", ln=True)
    elif tipo == "ordem_servico" and data_entrega:
        pdf.cell(largura_col, 5, f"Entrega prevista: {data_entrega.strftime('%d/%m/%Y')}", ln=True)
    else:
        pdf.cell(largura_col, 5, "", ln=True)

    # Linha Email
    y_linha = pdf.get_y()
    pdf.set_xy(x_esq, y_linha)
    pdf.cell(largura_col, 5, f"Email: {cliente.get('email') or '-'}", ln=True)

    # Linha Endereço (só na coluna esquerda)
    if cliente.get("endereco"):
        pdf.set_x(x_esq)
        pdf.cell(largura_col, 5, f"Endereço: {cliente['endereco']}", ln=True)

    pdf.ln(6)

    # ------------------------------------------------------------------ #
    # Tabela de itens
    # ------------------------------------------------------------------ #
    col_widths = [85, 25, 35, 35]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, ["Descrição", "Qtd.", "Valor Unit. (R$)", "Total (R$)"]):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    total_geral = 0
    for grupo in grupos:
        # Linha do serviço
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(col_widths[0], 7, str(grupo["descricao"])[:50], border=1)
        pdf.cell(col_widths[1], 7, f"{grupo['quantidade']:.2f}", border=1, align="C")
        pdf.cell(col_widths[2], 7, formatar_moeda(grupo["valor_unitario"]), border=1, align="C")
        pdf.cell(col_widths[3], 7, formatar_moeda(grupo["valor_total"]), border=1, align="C")
        pdf.ln()

        # Observação do serviço
        obs = grupo.get("observacao_item", "")
        if obs:
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(sum(col_widths), 5, f"  Obs: {obs[:100]}", border=0)
            pdf.ln()

        subtotal_grupo = grupo["valor_total"]

        # Materiais (subitens)
        pdf.set_font("Helvetica", "", 8)
        for mat in grupo.get("materiais", []):
            pdf.cell(col_widths[0], 6, f"   > {str(mat['descricao'])[:45]}", border=1)
            pdf.cell(col_widths[1], 6, f"{mat['quantidade']:.2f}", border=1, align="C")
            pdf.cell(col_widths[2], 6, formatar_moeda(mat["valor_unitario"]), border=1, align="C")
            pdf.cell(col_widths[3], 6, formatar_moeda(mat["valor_total"]), border=1, align="C")
            pdf.ln()
            subtotal_grupo += mat["valor_total"]

        if grupo.get("materiais"):
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(sum(col_widths[:3]), 6, "Subtotal do serviço", border=1, align="R")
            pdf.cell(col_widths[3], 6, formatar_moeda(subtotal_grupo), border=1, align="C")
            pdf.ln()

        total_geral += subtotal_grupo

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(sum(col_widths[:3]), 8, "TOTAL GERAL", border=1, align="R")
    pdf.cell(col_widths[3], 8, f"R$ {formatar_moeda(total_geral)}", border=1, align="C")
    pdf.ln(12)

    # ------------------------------------------------------------------ #
    # Observações gerais do documento
    # ------------------------------------------------------------------ #
    if observacoes:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Observações", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, observacoes)
        pdf.ln(4)

    # ------------------------------------------------------------------ #
    # Bloco de assinaturas
    # ------------------------------------------------------------------ #
    pdf.ln(10)
    largura_ass = 85
    espaco_ass = 10
    x_ass_esq = 10
    x_ass_dir = x_ass_esq + largura_ass + espaco_ass

    assinatura_path = None
    if prestador.get("assinatura"):
        try:
            assinatura_path = _salvar_imagem_temp(prestador["assinatura"])
        except Exception:
            assinatura_path = None

    y_ass = pdf.get_y()

    # — Coluna esquerda: assinatura do prestador —
    if assinatura_path:
        # Imagem da assinatura centralizada na coluna
        try:
            pdf.image(assinatura_path, x=x_ass_esq, y=y_ass, w=largura_ass, h=14)
            pdf.set_y(y_ass + 14)
        except Exception:
            # Fallback: linha em branco
            pdf.set_xy(x_ass_esq, y_ass)
            pdf.cell(largura_ass, 14, "", ln=False)
    else:
        # Linha em branco para assinar à mão
        pdf.set_xy(x_ass_esq, y_ass + 8)
        pdf.cell(largura_ass, 6, "_" * 40, align="C", ln=False)

    # — Coluna direita: linha em branco para o cliente —
    pdf.set_xy(x_ass_dir, y_ass + 8)
    pdf.cell(largura_ass, 6, "_" * 40, align="C", ln=True)

    # Labels "Assinatura do Prestador" / "Assinatura do Cliente"
    y_labels = pdf.get_y() + 1
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(x_ass_esq, y_labels)
    pdf.cell(largura_ass, 5, "Assinatura do Prestador", align="C", ln=False)
    pdf.set_xy(x_ass_dir, y_labels)
    pdf.cell(largura_ass, 5, "Assinatura do Cliente", align="C", ln=True)

    # Nomes por extenso
    pdf.set_font("Helvetica", "", 9)
    y_nomes = pdf.get_y()
    pdf.set_xy(x_ass_esq, y_nomes)
    pdf.cell(largura_ass, 5, prestador.get("nome", ""), align="C", ln=False)
    pdf.set_xy(x_ass_dir, y_nomes)
    pdf.cell(largura_ass, 5, cliente.get("nome", ""), align="C", ln=True)

    # Campos de data/hora
    y_datas = pdf.get_y() + 2
    pdf.set_xy(x_ass_esq, y_datas)
    pdf.cell(largura_ass, 5, "Data/Hora: ____/____/______  ____:____", align="C", ln=False)
    pdf.set_xy(x_ass_dir, y_datas)
    pdf.cell(largura_ass, 5, "Data/Hora: ____/____/______  ____:____", align="C", ln=True)

    # ------------------------------------------------------------------ #
    # Gera o arquivo temporário
    # ------------------------------------------------------------------ #
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    pdf.output(output_path)

    for p in [logo_path, assinatura_path]:
        if p and os.path.exists(p):
            os.remove(p)

    return output_path
