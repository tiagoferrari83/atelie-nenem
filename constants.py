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
    Ex: 1234.56 -> '1.234,56'. Usado em toda a interface e no PDF, para nunca
    aparecer com ponto decimal (padrão americano) nem em cifras (R$) nem em preços."""
    return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
