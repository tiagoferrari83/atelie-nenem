import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from database import init_db

st.set_page_config(
    page_title="Ateliê - Gestão",
    page_icon="🧵",
    layout="centered",
)

# Cria/atualiza as tabelas no banco - roda só uma vez (cacheado), não a cada clique
@st.cache_resource(show_spinner=False)
def _init_db_once():
    init_db()
    return True

try:
    _init_db_once()
except Exception as e:
    st.error(f"Erro ao conectar/preparar o banco de dados: {e}")
    st.stop()

# Todas as páginas precisam estar aqui para serem navegáveis (inclusive via
# st.switch_page) - mas usamos position="hidden" para esconder o menu padrão
# e desenhar o nosso próprio abaixo, deixando de fora só os links de
# pages/51_Orcamento.py e pages/52_Ordem_Servico.py (acessíveis pelos botões
# em "Novo" e em "Consultar", mas não devem aparecer como opção direta no menu).
pagina_dashboard = st.Page("pages/0_Dashboard.py", title="Dashboard", icon="🧵", default=True)
pagina_prestador = st.Page("pages/1_Prestador.py", title="Prestador")
pagina_clientes = st.Page("pages/2_Clientes.py", title="Clientes")
pagina_servicos = st.Page("pages/3_Servicos.py", title="Serviços")
pagina_materia_prima = st.Page("pages/4_Materia_Prima.py", title="Matéria-Prima")
pagina_novo = st.Page("pages/50_Novo.py", title="Novo")
pagina_orcamento = st.Page("pages/51_Orcamento.py", title="Orçamento")
pagina_ordem_servico = st.Page("pages/52_Ordem_Servico.py", title="Ordem de Serviço")
pagina_consultar = st.Page("pages/6_Consultar.py", title="Consultar")

pg = st.navigation(
    [
        pagina_dashboard, pagina_prestador, pagina_clientes, pagina_servicos,
        pagina_materia_prima, pagina_novo, pagina_orcamento, pagina_ordem_servico,
        pagina_consultar,
    ],
    position="hidden",
)

# Menu lateral customizado - só os links que devem aparecer
with st.sidebar:
    st.page_link(pagina_dashboard, label="Dashboard", icon="🧵")
    st.page_link(pagina_prestador, label="Prestador")
    st.page_link(pagina_clientes, label="Clientes")
    st.page_link(pagina_servicos, label="Serviços")
    st.page_link(pagina_materia_prima, label="Matéria-Prima")
    st.page_link(pagina_novo, label="Novo")
    st.page_link(pagina_consultar, label="Consultar")

pg.run()
