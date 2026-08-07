"""
Gera PDFs de Orçamento ou Ordem de Serviço com base nos dados do prestador,
cliente e itens (serviços/matéria-prima) selecionados.
"""

from fpdf import FPDF
from datetime import datetime
import tempfile
import os


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


def gerar_pdf(tipo, prestador, cliente, itens, observacoes=""):
    """
    tipo: 'orcamento' ou 'ordem_servico'
    prestador: dict com nome, telefone, email, cnpj, logo (bytes ou None)
    cliente: dict com nome, telefone, email, endereco
    itens: lista de dicts com descricao, quantidade, valor_unitario, valor_total
    observacoes: texto livre
    """
    titulo = "ORÇAMENTO" if tipo == "orcamento" else "ORDEM DE SERVIÇO"
    pdf = DocumentoPDF(titulo)
    pdf.add_page()

    # --- Logo (se houver) ---
    logo_path = None
    if prestador.get("logo"):
        logo_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        with open(logo_path, "wb") as f:
            f.write(prestador["logo"])
        try:
            pdf.image(logo_path, x=10, y=10, w=25)
        except Exception:
            pass  # se o formato da imagem falhar, segue sem logo

    # --- Dados do prestador ---
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(40 if logo_path else 10, 25)
    pdf.cell(0, 6, prestador.get("nome", ""), ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(40 if logo_path else 10)
    linha_contato = " | ".join(
        filter(None, [
            f"Tel: {prestador.get('telefone')}" if prestador.get("telefone") else "",
            f"Email: {prestador.get('email')}" if prestador.get("email") else "",
            f"CNPJ: {prestador.get('cnpj')}" if prestador.get("cnpj") else "",
        ])
    )
    pdf.cell(0, 6, linha_contato, ln=True)

    pdf.ln(10)

    # --- Dados do documento ---
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(2)

    # --- Dados do cliente ---
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Cliente", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Nome: {cliente.get('nome', '')}", ln=True)
    if cliente.get("telefone"):
        pdf.cell(0, 5, f"Telefone: {cliente['telefone']}", ln=True)
    if cliente.get("email"):
        pdf.cell(0, 5, f"Email: {cliente['email']}", ln=True)
    if cliente.get("endereco"):
        pdf.cell(0, 5, f"Endereço: {cliente['endereco']}", ln=True)

    pdf.ln(6)

    # --- Tabela de itens ---
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    col_widths = [85, 25, 35, 35]
    headers = ["Descrição", "Qtd.", "Valor Unit. (R$)", "Total (R$)"]
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    total_geral = 0
    for item in itens:
        pdf.cell(col_widths[0], 7, str(item["descricao"])[:50], border=1)
        pdf.cell(col_widths[1], 7, f"{item['quantidade']:.2f}", border=1, align="C")
        pdf.cell(col_widths[2], 7, f"{item['valor_unitario']:.2f}", border=1, align="C")
        pdf.cell(col_widths[3], 7, f"{item['valor_total']:.2f}", border=1, align="C")
        pdf.ln()
        total_geral += item["valor_total"]

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(sum(col_widths[:3]), 8, "TOTAL GERAL", border=1, align="R")
    pdf.cell(col_widths[3], 8, f"R$ {total_geral:.2f}", border=1, align="C")
    pdf.ln(12)

    # --- Observações ---
    if observacoes:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Observações", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, observacoes)

    # --- Assinatura (só para Ordem de Serviço) ---
    if tipo == "ordem_servico":
        pdf.ln(20)
        pdf.cell(0, 6, "_" * 40, ln=True, align="C")
        pdf.cell(0, 6, "Assinatura do Cliente", ln=True, align="C")

    # --- Gera o arquivo temporário ---
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    pdf.output(output_path)

    if logo_path and os.path.exists(logo_path):
        os.remove(logo_path)

    return output_path
