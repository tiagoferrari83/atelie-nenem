"""
Módulo de conexão com o banco de dados Supabase (PostgreSQL).
Centraliza a conexão e as funções de criação/consulta das tabelas.
"""

import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    """Cria e retorna uma conexão com o banco Postgres do Supabase."""
    conn_string = st.secrets["connections"]["supabase"]["url"]
    return psycopg2.connect(conn_string, cursor_factory=RealDictCursor)


def init_db():
    """Cria as tabelas do sistema caso ainda não existam."""
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
            tipo TEXT NOT NULL CHECK (tipo IN ('orcamento', 'ordem_servico')),
            status TEXT DEFAULT 'aberto',
            observacoes TEXT,
            criado_em TIMESTAMP DEFAULT NOW()
        );
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

    conn.commit()
    cur.close()
    conn.close()


# ---------- Funções genéricas de CRUD ----------

def fetch_all(table, order_by="id"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table} ORDER BY {order_by};")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def query(sql, params=None):
    """Executa um SELECT customizado (ex: com JOIN) e retorna as linhas."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def execute(query, params=None):
    """Executa INSERT/UPDATE/DELETE. Retorna o id gerado, se houver RETURNING."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params or ())
    result = None
    if cur.description:
        result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return result
