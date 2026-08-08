"""
Módulo de conexão com o banco de dados Supabase (PostgreSQL).
A conexão é cacheada com st.cache_resource: fica aberta e é reaproveitada
entre as chamadas, em vez de abrir uma conexão TCP+SSL nova a cada operação
(essa era a principal causa de lentidão - cada operação levava ~3s).
"""

import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor


@st.cache_resource(show_spinner=False)
def _get_cached_connection():
    """Cria a conexão uma única vez por sessão de servidor e a mantém em cache."""
    conn_string = st.secrets["connections"]["supabase"]["url"]
    conn = psycopg2.connect(conn_string, cursor_factory=RealDictCursor)
    conn.autocommit = False
    return conn


def get_connection():
    """Retorna a conexão cacheada."""
    return _get_cached_connection()


def _reconectar():
    """Força a criação de uma nova conexão (usado quando a conexão cacheada caiu)."""
    _get_cached_connection.clear()
    return _get_cached_connection()


def init_db():
    """Cria/atualiza as tabelas do sistema caso ainda não existam."""
    conn = get_connection()
    cur = conn.cursor()

    # Prestador de serviço (dados da empresa/costureira - geralmente um único registro)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prestador (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            telefone TEXT,
            email TEXT,
            cnpj TEXT,
            logo BYTEA,
            criado_em TIMESTAMP DEFAULT NOW()
        );
    """)

    # Clientes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            telefone TEXT,
            email TEXT,
            endereco TEXT,
            criado_em TIMESTAMP DEFAULT NOW()
        );
    """)

    # Serviços (cobrados por unidade, tempo ou metro)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS servicos (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            tipo_cobranca TEXT NOT NULL CHECK (tipo_cobranca IN ('unidade', 'tempo', 'metro')),
            valor NUMERIC(10, 2) NOT NULL,
            criado_em TIMESTAMP DEFAULT NOW()
        );
    """)

    # Matéria-prima (cobrada por unidade, metro ou peso)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS materia_prima (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            tipo_medida TEXT NOT NULL CHECK (tipo_medida IN ('unidade', 'metro', 'peso')),
            valor NUMERIC(10, 2) NOT NULL,
            criado_em TIMESTAMP DEFAULT NOW()
        );
    """)

    # Orçamentos / Ordens de serviço
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orcamentos (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER REFERENCES clientes(id),
            tipo_operacao TEXT NOT NULL CHECK (tipo_operacao IN ('orcamento', 'ordem_servico')),
            tipo_pedido TEXT NOT NULL CHECK (tipo_pedido IN ('confeccao', 'personalizacao', 'criacao')),
            status TEXT NOT NULL DEFAULT 'nova' CHECK (
                status IN ('nova', 'aguardando_aprovacao', 'em_atendimento', 'entregue', 'reaberta')
            ),
            observacoes TEXT,
            data_validade DATE,
            data_entrega DATE,
            orcamento_origem_id INTEGER REFERENCES orcamentos(id),
            criado_em TIMESTAMP DEFAULT NOW()
        );
    """)

    # Compatibilidade: bancos criados antes desta versão tinham a coluna "tipo" e não tinham as demais.
    cur.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamentos' AND column_name = 'tipo'
            ) THEN
                EXECUTE 'ALTER TABLE orcamentos RENAME COLUMN tipo TO tipo_operacao';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamentos' AND column_name = 'tipo_pedido'
            ) THEN
                ALTER TABLE orcamentos ADD COLUMN tipo_pedido TEXT NOT NULL DEFAULT 'confeccao';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamentos' AND column_name = 'data_validade'
            ) THEN
                ALTER TABLE orcamentos ADD COLUMN data_validade DATE;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamentos' AND column_name = 'data_entrega'
            ) THEN
                ALTER TABLE orcamentos ADD COLUMN data_entrega DATE;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamentos' AND column_name = 'orcamento_origem_id'
            ) THEN
                ALTER TABLE orcamentos ADD COLUMN orcamento_origem_id INTEGER REFERENCES orcamentos(id);
            END IF;
        END $$;
    """)

    # Corrige registros antigos com status fora dos valores válidos atuais
    cur.execute("""
        UPDATE orcamentos
        SET status = 'nova'
        WHERE status IS NULL
           OR status NOT IN ('nova', 'aguardando_aprovacao', 'em_atendimento', 'entregue', 'reaberta');
    """)

    # Garante que a constraint de status reflete os valores atuais
    cur.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'orcamentos' AND constraint_name = 'orcamentos_status_check'
            ) THEN
                ALTER TABLE orcamentos DROP CONSTRAINT orcamentos_status_check;
            END IF;
            ALTER TABLE orcamentos ADD CONSTRAINT orcamentos_status_check
                CHECK (status IN ('nova', 'aguardando_aprovacao', 'em_atendimento', 'entregue', 'reaberta'));
            ALTER TABLE orcamentos ALTER COLUMN status SET DEFAULT 'nova';
        END $$;
    """)

    # Itens do orçamento (serviços e materiais usados)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orcamento_itens (
            id SERIAL PRIMARY KEY,
            orcamento_id INTEGER REFERENCES orcamentos(id) ON DELETE CASCADE,
            tipo_item TEXT NOT NULL CHECK (tipo_item IN ('servico', 'materia_prima')),
            item_id INTEGER NOT NULL,
            descricao TEXT NOT NULL,
            quantidade NUMERIC(10, 2) NOT NULL,
            valor_unitario NUMERIC(10, 2) NOT NULL,
            valor_total NUMERIC(10, 2) NOT NULL
        );
    """)

    # Fotos anexadas ao orçamento/OS - guarda só a URL do Supabase Storage, não o binário
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orcamento_fotos (
            id SERIAL PRIMARY KEY,
            orcamento_id INTEGER REFERENCES orcamentos(id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()


# ---------- Funções genéricas de CRUD ----------

def fetch_all(table, order_by="id"):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table} ORDER BY {order_by};")
        rows = cur.fetchall()
        cur.close()
        return rows
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        conn = _reconectar()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table} ORDER BY {order_by};")
        rows = cur.fetchall()
        cur.close()
        return rows


@st.cache_data(ttl=30, show_spinner=False)
def fetch_all_cached(table, order_by="id"):
    """
    Igual a fetch_all, mas cacheado por 30s. Usar em telas com muitos widgets
    (selects, number_inputs) onde o Streamlit reexecuta o script inteiro a
    cada clique/tecla - sem isso, cada interação refaz a mesma query no banco
    à toa, o que é a maior causa de lentidão em telas como a de Orçamento.
    Não usar para dados que precisam refletir uma escrita feita no mesmo rerun
    (ex: logo após um INSERT, quando a tela precisa mostrar o registro novo).
    """
    return fetch_all(table, order_by)


def query(sql, params=None):
    """Executa um SELECT customizado (ex: com JOIN) e retorna as linhas."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.close()
        return rows
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        conn = _reconectar()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.close()
        return rows


def execute(sql, params=None):
    """Executa INSERT/UPDATE/DELETE. Retorna o id gerado, se houver RETURNING."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        result = None
        if cur.description:
            result = cur.fetchone()
        conn.commit()
        cur.close()
        return result
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        conn = _reconectar()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        result = None
        if cur.description:
            result = cur.fetchone()
        conn.commit()
        cur.close()
        return result
    except Exception:
        conn.rollback()
        raise
