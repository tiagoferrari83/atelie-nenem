"""
Constantes compartilhadas entre as páginas: tipos de pedido, status, labels.
"""

TIPO_PEDIDO_LABELS = {
    "confeccao": "Orçamento de Confecção",
    "personalizacao": "Personalização",
    "criacao": "Criação",
}

TIPO_OPERACAO_LABELS = {
    "orcamento": "Orçamento",
    "ordem_servico": "Ordem de Serviço",
}

STATUS_LABELS = {
    "nova": "Nova",
    "aguardando_aprovacao": "Aguardando aprovação",
    "em_atendimento": "Em atendimento",
    "entregue": "Entregue",
    "reaberta": "Reaberta",
}

# Ordem em que os status aparecem em selects
STATUS_ORDEM = ["nova", "aguardando_aprovacao", "em_atendimento", "entregue", "reaberta"]

STATUS_CORES = {
    "nova": "🔵",
    "aguardando_aprovacao": "🟡",
    "em_atendimento": "🟠",
    "entregue": "🟢",
    "reaberta": "🔴",
}

TIPO_LABELS_SERVICO = {"unidade": "un.", "tempo": "h", "metro": "m"}
TIPO_LABELS_MATERIAL = {"unidade": "un.", "metro": "m", "peso": "kg"}
