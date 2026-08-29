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
    r"""
    Como formatar_moeda, mas já inclui o prefixo 'R$' com o cifrão ESCAPADO
    (\$) para uso em st.markdown/st.write/st.caption. Sem o escape, dois
    "R$" no mesmo texto markdown formam um par de delimitadores de fórmula
    LaTeX ($...$), fazendo o Streamlit renderizar o trecho entre eles como
    equação. Usar esta função em qualquer texto exibido na interface;
    formatar_moeda() sozinha continua correta para o PDF (fpdf não interpreta
    $ como LaTeX).
    """
    return f"R\\$ {formatar_moeda(valor)}"



def formatar_quantidade(qtd: float, unidade: str = "") -> str:
    """
    Formata quantidade no padrão brasileiro:
    - Sem casas decimais se for inteiro (ex: 1, 2, 10)
    - Com vírgula para números decimais (ex: 1,5 ou 2,75)
    - Concatena a unidade de medida com espaço caso informada (ex: '1 un.', '2,5 m')
    """
    try:
        qtd_f = float(qtd)
    except (ValueError, TypeError):
        return str(qtd)

    if qtd_f.is_integer():
        qtd_str = str(int(qtd_f))
    else:
        # Formata com até 2 casas decimais e remove zeros à direita supérfluos
        qtd_str = f"{qtd_f:.2f}".rstrip("0").rstrip(".").replace(".", ",")

    if unidade:
        return f"{qtd_str} {unidade}".strip()
    return qtd_str


def separar_descricao_unidade(descricao: str):
    """
    Se a descrição terminar com '/un.', '/m', '/h', '/kg' ou similar,
    separa em (nome_limpo, unidade).
    Ex: 'Bainha/m' -> ('Bainha', 'm')
        'Botão/un.' -> ('Botão', 'un.')
        'Zíper' -> ('Zíper', '')
    """
    if not descricao:
        return "", ""
    unidades_conhecidas = ["un.", "un", "m", "h", "kg"]
    for un in unidades_conhecidas:
        sufixo = f"/{un}"
        if descricao.endswith(sufixo):
            return descricao[:-len(sufixo)].strip(), un
    return descricao.strip(), ""

