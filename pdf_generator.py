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
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")


def gerar_pdf(tipo, prestador, cliente, grupos, observacoes="", tipo_pedido_label=None,
              data_validade=None, data_entrega=None):
    """
    tipo: 'orcamento' ou 'ordem_servico'
    prestador: dict com nome, telefone, email, cnpj, logo (bytes ou None)
    cliente: dict com nome, telefone, email, endereco
    grupos: lista de dicts, cada um um serviço:
        {descricao, quantidade, valor_unitario, valor_total, unidade (opcional),
         observacao (opcional),
         materiais: [{descricao, quantidade, valor_unitario, valor_total,
                      unidade (opcional), observacao (opcional)}, ...]}
    observacoes: texto livre (campo geral do documento)
    tipo_pedido_label: rótulo do tipo de pedido (ex: "Personalização")
    data_validade: date - validade do orçamento (só para tipo='orcamento')
    data_entrega: date - entrega prevista (só para tipo='ordem_servico')
    """
    titulo = "ORÇAMENTO" if tipo == "orcamento" else "ORDEM DE SERVIÇO"
    pdf = DocumentoPDF(titulo)
    pdf.add_page()

    # --- Logo (se houver) ---
    logo_path = None
    if prestador.get("logo"):
        logo_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        with open(logo_path, "wb") as f:
            f.write(bytes(prestador["logo"]))
        try:
            pdf.image(logo_path, x=10, y=18, w=25)
        except Exception:
            pass  # se o formato da imagem falhar, segue sem logo

    # --- Dados do prestador ---
    # O header() já imprimiu o título e adicionou ln(4), então get_y() está logo abaixo do título.
    pdf.set_font("Helvetica", "B", 11)
    if logo_path:
        pdf.set_x(40)
    pdf.cell(0, 6, prestador.get("nome", ""), ln=True)

    pdf.set_font("Helvetica", "", 9)
    if logo_path:
        pdf.set_x(40)
    linha_contato = " | ".join(
        filter(None, [
            f"Tel: {prestador.get('telefone')}" if prestador.get("telefone") else "",
            f"Email: {prestador.get('email')}" if prestador.get("email") else "",
            f"CNPJ: {prestador.get('cnpj')}" if prestador.get("cnpj") else "",
        ])
    )
    pdf.cell(0, 6, linha_contato, ln=True)

    # Espaço generoso entre dados da empresa e metadados do documento
    pdf.ln(8)

    # --- Dados do documento ---
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    if tipo_pedido_label:
        pdf.cell(0, 5, f"Tipo: {tipo_pedido_label}", ln=True)
    if tipo == "orcamento" and data_validade:
        pdf.cell(0, 5, f"Válido até: {data_validade.strftime('%d/%m/%Y')}", ln=True)
    if tipo == "ordem_servico" and data_entrega:
        pdf.cell(0, 5, f"Entrega prevista: {data_entrega.strftime('%d/%m/%Y')}", ln=True)

    # Espaço entre metadados e dados do cliente
    pdf.ln(6)

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

    pdf.ln(8)

    # --- Tabela de itens ---
    # Ordem das colunas: Qtd. | Descrição | Valor Unit. (R$) | Total (R$)
    col_widths = [20, 90, 35, 35]
    headers = ["Qtd.", "Descrição", "Valor Unit. (R$)", "Total (R$)"]

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    total_geral = 0

    for grupo in grupos:
        # Monta o texto da descrição do serviço: "Nome/unidade - observação" (se houver)
        descricao_srv = str(grupo["descricao"])
        unidade_srv = grupo.get("unidade", "")
        obs_srv = grupo.get("observacao", "") or grupo.get("observacoes", "")
        if unidade_srv:
            descricao_srv = f"{descricao_srv}/{unidade_srv}"
        if obs_srv:
            descricao_srv = f"{descricao_srv} - {obs_srv}"

        # Linha do serviço (negrito)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(col_widths[0], 7, f"{grupo['quantidade']:.2f}", border=1, align="C")
        pdf.cell(col_widths[1], 7, descricao_srv[:55], border=1)
        pdf.cell(col_widths[2], 7, formatar_moeda(grupo['valor_unitario']), border=1, align="C")
        pdf.cell(col_widths[3], 7, formatar_moeda(grupo['valor_total']), border=1, align="C")
        pdf.ln()

        subtotal_grupo = grupo["valor_total"]

        # Materiais (subitens) deste serviço, indentados
        pdf.set_font("Helvetica", "", 8)
        for mat in grupo.get("materiais", []):
            descricao_mat = str(mat["descricao"])
            unidade_mat = mat.get("unidade", "")
            obs_mat = mat.get("observacao", "") or mat.get("observacoes", "")
            if unidade_mat:
                descricao_mat = f"{descricao_mat}/{unidade_mat}"
            if obs_mat:
                descricao_mat = f"{descricao_mat} - {obs_mat}"

            pdf.cell(col_widths[0], 6, f"{mat['quantidade']:.2f}", border=1, align="C")
            pdf.cell(col_widths[1], 6, f"  > {descricao_mat[:50]}", border=1)
            pdf.cell(col_widths[2], 6, formatar_moeda(mat['valor_unitario']), border=1, align="C")
            pdf.cell(col_widths[3], 6, formatar_moeda(mat['valor_total']), border=1, align="C")
            pdf.ln()
            subtotal_grupo += mat["valor_total"]

        # Subtotal do grupo (só exibe se houver materiais)
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

    # --- Observações gerais do documento ---
    if observacoes:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Observações", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, observacoes)
        pdf.ln(4)

    # --- Cláusulas e Condições (somente para Orçamento) ---
    if tipo == "orcamento":
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Cláusulas e Condições", ln=True)
        pdf.set_font("Helvetica", "", 9)
        clausulas = [
            "1. Este orçamento é válido até a data indicada acima.",
            "2. O início dos serviços está condicionado à aprovação formal deste orçamento pelo cliente.",
            "3. Eventuais alterações no escopo dos serviços poderão implicar revisão de valores.",
            "4. O prazo de entrega será definido após a aprovação e confirmação de pagamento.",
            "5. Em caso de cancelamento após o início dos serviços, poderá ser cobrada taxa proporcional ao trabalho executado.",
        ]
        for c in clausulas:
            pdf.multi_cell(0, 5, c)
        pdf.ln(6)

    # --- Assinaturas ---
    pdf.ln(10)

    largura_col = 85
    espaco = 10
    x_inicial = pdf.get_x()
    y_assinatura = pdf.get_y()

    pdf.set_xy(x_inicial, y_assinatura)
    pdf.cell(largura_col, 6, "_" * 35, ln=False, align="C")
    pdf.set_xy(x_inicial + largura_col + espaco, y_assinatura)
    pdf.cell(largura_col, 6, "_" * 35, ln=True, align="C")

    pdf.set_xy(x_inicial, pdf.get_y())
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(largura_col, 5, "Assinatura do Prestador", align="C")
    pdf.set_xy(x_inicial + largura_col + espaco, pdf.get_y())
    pdf.cell(largura_col, 5, "Assinatura do Cliente", align="C")
    pdf.ln(5)

    pdf.set_x(x_inicial)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(largura_col, 5, prestador.get("nome", ""), align="C")
    pdf.set_x(x_inicial + largura_col + espaco)
    pdf.cell(largura_col, 5, cliente.get("nome", ""), align="C")
    pdf.ln(8)

    pdf.set_x(x_inicial)
    pdf.cell(largura_col, 5, "Data/Hora: ____/____/______  ____:____", align="C")
    pdf.set_x(x_inicial + largura_col + espaco)
    pdf.cell(largura_col, 5, "Data/Hora: ____/____/______  ____:____", align="C")

    # --- Gera o arquivo temporário ---
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    pdf.output(output_path)

    if logo_path and os.path.exists(logo_path):
        os.remove(logo_path)

    return output_path
