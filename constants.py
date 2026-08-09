"""
Constantes compartilhadas entre as páginas: tipos de pedido, status, labels.
"""

TIPO_PEDIDO_LABELS = {
    "confeccao": "Confecção",
    "personalizacao": "Personalização",
    "criacao": "Criação",
}

TIPO_OPERACAO_LABELS = {
    "orcamento": "Orçamento",
    "ordem_servico": "Ordem de Serviço",
}

# Status de Ordem de Serviço
STATUS_LABELS = {
    "nova": "Nova",
    "aguardando_aprovacao": "Aguardando aprovação",
    "em_atendimento": "Em atendimento",
    "entregue": "Entregue",
    "reaberta": "Reaberta",
}

# Ordem em que os status de OS aparecem em selects
STATUS_ORDEM = ["nova", "aguardando_aprovacao", "em_atendimento", "entregue", "reaberta"]

STATUS_CORES = {
    "nova": "🔵",
    "aguardando_aprovacao": "🟡",
    "em_atendimento": "🟠",
    "entregue": "🟢",
    "reaberta": "🔴",
}

# Status de Orçamento (próprios, diferentes dos de OS)
# "aprovado" pode ser marcado manualmente OU automaticamente pelo botão "Aprovar Orçamento".
# "vencido" é calculado automaticamente (data_validade < hoje) e nunca sobrescreve "aprovado".
STATUS_ORCAMENTO_LABELS = {
    "aguardando_aprovacao": "Aguardando Aprovação",
    "aprovado": "Aprovado",
    "vencido": "Vencido",
}

STATUS_ORCAMENTO_ORDEM = ["aguardando_aprovacao", "aprovado", "vencido"]

STATUS_ORCAMENTO_CORES = {
    "aguardando_aprovacao": "🟡",
    "aprovado": "🟢",
    "vencido": "🔴",
}

TIPO_LABELS_SERVICO = {"unidade": "un.", "tempo": "h", "metro": "m"}
TIPO_LABELS_MATERIAL = {"unidade": "un.", "metro": "m", "peso": "kg"}


def formatar_moeda(valor):
    """Formata um número no padrão brasileiro: ponto para milhar, vírgula para centavos.
    Ex: 1234.56 -> '1.234,56'. Retorna só o número, sem o prefixo R$."""
    return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def formatar_reais(valor):
    """
    Como formatar_moeda, mas já inclui o prefixo 'R$' com o cifrão ESCAPADO
    (\\$) para uso em st.markdown/st.write/st.caption. Sem o escape, dois
    "R$" no mesmo texto markdown formam um par de delimitadores de fórmula
    LaTeX ($...$), fazendo o Streamlit renderizar o trecho entre eles como
    equação (aparece com fundo escuro e texto verde, ilegível). Usar esta
    função em qualquer texto exibido na interface; formatar_moeda() sozinha
    continua correta para o PDF (fpdf não interpreta $ como LaTeX).
    """
    return f"R\\$ {formatar_moeda(valor)}"
