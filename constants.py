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

STATUS_ORDEM = ["nova", "aguardando_aprovacao", "em_atendimento", "entregue", "reaberta"]

STATUS_CORES = {
    "nova": "🔵",
    "aguardando_aprovacao": "🟡",
    "em_atendimento": "🟠",
    "entregue": "🟢",
    "reaberta": "🔴",
}

# Status de Orçamento
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

# Tipo de material (Bloco A) — detectado na hora de montar o orçamento
TIPO_MATERIAL_LABELS = {
    "tecido": "Tecido",
    "aviamento": "Aviamento",
    "outros": "Outros",
}

# Complexidade do serviço (Bloco A)
# Nível 1 = sem acréscimo, 2 = +10%, 3 = +20%
COMPLEXIDADE_LABELS = {
    1: "1 — Simples (sem acréscimo)",
    2: "2 — Médio (+10%)",
    3: "3 — Complexo (+20%)",
}

COMPLEXIDADE_ACRESCIMO = {1: 0.0, 2: 0.10, 3: 0.20}


def valor_com_complexidade(valor_base: float, complexidade: int) -> float:
    """Retorna o valor do serviço já aplicado o acréscimo de complexidade."""
    acrescimo = COMPLEXIDADE_ACRESCIMO.get(complexidade, 0.0)
    return round(valor_base * (1 + acrescimo), 2)


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
    equação. Usar esta função em qualquer texto exibido na interface;
    formatar_moeda() sozinha continua correta para o PDF (fpdf não interpreta
    $ como LaTeX).
    """
    return f"R\\$ {formatar_moeda(valor)}"
