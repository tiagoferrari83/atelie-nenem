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
    _definir_timezone(conn)
    return conn


def _definir_timezone(conn):
    """
    Define o timezone da sessão como horário de Brasília, para que NOW() e
    CURRENT_DATE já retornem no horário local em vez de UTC (padrão do
    Postgres). Isso resolve na origem, sem precisar converter na exibição.
    """
    cur = conn.cursor()
    cur.execute("SET TIME ZONE 'America/Sao_Paulo';")
    conn.commit()
    cur.close()


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
            assinatura BYTEA,
            clausulas TEXT,
            criado_em TIMESTAMP DEFAULT NOW()
        );
    """)

    # Compatibilidade: adiciona coluna assinatura em bancos já existentes (Bloco D)
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'prestador' AND column_name = 'assinatura'
            ) THEN
                ALTER TABLE prestador ADD COLUMN assinatura BYTEA;
            END IF;
        END $$;
    """)

    # Clientes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            telefone TEXT,
            email TEXT,
            endereco TEXT,
            criado_em TIMESTAMP DEFAULT NOW(),
            atualizado_em TIMESTAMP DEFAULT NOW()
        );
    """)

    # Serviços (cobrados por unidade, tempo ou metro)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS servicos (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            tipo_cobranca TEXT NOT NULL CHECK (tipo_cobranca IN ('unidade', 'tempo', 'metro')),
            valor NUMERIC(10, 2) NOT NULL,
            criado_em TIMESTAMP DEFAULT NOW(),
            atualizado_em TIMESTAMP DEFAULT NOW()
        );
    """)

    # Matéria-prima (cobrada por unidade, metro ou peso)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS materia_prima (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            tipo_medida TEXT NOT NULL CHECK (tipo_medida IN ('unidade', 'metro', 'peso')),
            tipo_material TEXT NOT NULL DEFAULT 'outros' CHECK (tipo_material IN ('tecido', 'aviamento', 'outros')),
            valor NUMERIC(10, 2) NOT NULL,
            criado_em TIMESTAMP DEFAULT NOW(),
            atualizado_em TIMESTAMP DEFAULT NOW()
        );
    """)

    # Compatibilidade: adiciona colunas novas em bancos já existentes
    cur.execute("""
        DO $$
        BEGIN
            -- atualizado_em em clientes
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'clientes' AND column_name = 'atualizado_em'
            ) THEN
                ALTER TABLE clientes ADD COLUMN atualizado_em TIMESTAMP DEFAULT NOW();
                UPDATE clientes SET atualizado_em = criado_em WHERE atualizado_em IS NULL;
            END IF;

            -- atualizado_em em servicos
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'servicos' AND column_name = 'atualizado_em'
            ) THEN
                ALTER TABLE servicos ADD COLUMN atualizado_em TIMESTAMP DEFAULT NOW();
                UPDATE servicos SET atualizado_em = criado_em WHERE atualizado_em IS NULL;
            END IF;

            -- atualizado_em em materia_prima
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'materia_prima' AND column_name = 'atualizado_em'
            ) THEN
                ALTER TABLE materia_prima ADD COLUMN atualizado_em TIMESTAMP DEFAULT NOW();
                UPDATE materia_prima SET atualizado_em = criado_em WHERE atualizado_em IS NULL;
            END IF;

            -- clausulas no prestador (Bloco E)
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'prestador' AND column_name = 'clausulas'
            ) THEN
                ALTER TABLE prestador ADD COLUMN clausulas TEXT;
            END IF;

            -- tipo_material em materia_prima (Bloco A)
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'materia_prima' AND column_name = 'tipo_material'
            ) THEN
                ALTER TABLE materia_prima ADD COLUMN tipo_material TEXT NOT NULL DEFAULT 'outros';
            END IF;
        END $$;
    """)

    # Orçamentos / Ordens de serviço
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orcamentos (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER REFERENCES clientes(id),
            tipo_operacao TEXT NOT NULL CHECK (tipo_operacao IN ('orcamento', 'ordem_servico')),
            tipo_pedido TEXT NOT NULL CHECK (tipo_pedido IN ('confeccao', 'personalizacao', 'criacao')),
            status TEXT NOT NULL DEFAULT 'nova' CHECK (
                status IN (
                    'nova', 'aguardando_aprovacao', 'em_atendimento', 'entregue', 'reaberta',
                    'aprovado', 'vencido'
                )
            ),
            observacoes TEXT,
            data_validade DATE,
            data_entrega DATE,
            orcamento_origem_id INTEGER REFERENCES orcamentos(id) ON DELETE SET NULL,
            descricao_livre TEXT,
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

    # Compatibilidade: descricao_livre em orcamentos (Bloco E)
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamentos' AND column_name = 'descricao_livre'
            ) THEN
                ALTER TABLE orcamentos ADD COLUMN descricao_livre TEXT;
            END IF;
        END $$;
    """)

    # Corrige registros antigos com status fora dos valores válidos atuais
    cur.execute("""
        UPDATE orcamentos
        SET status = 'nova'
        WHERE tipo_operacao = 'ordem_servico'
          AND (status IS NULL
               OR status NOT IN ('nova', 'aguardando_aprovacao', 'em_atendimento', 'entregue', 'reaberta'));
    """)
    cur.execute("""
        UPDATE orcamentos
        SET status = 'aguardando_aprovacao'
        WHERE tipo_operacao = 'orcamento'
          AND (status IS NULL
               OR status NOT IN ('aguardando_aprovacao', 'aprovado', 'vencido'));
    """)

    # Marca como "vencido" todo orçamento ainda aguardando aprovação cuja validade já passou
    cur.execute("""
        UPDATE orcamentos
        SET status = 'vencido'
        WHERE tipo_operacao = 'orcamento'
          AND status = 'aguardando_aprovacao'
          AND data_validade IS NOT NULL
          AND data_validade < CURRENT_DATE;
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
                CHECK (status IN (
                    'nova', 'aguardando_aprovacao', 'em_atendimento', 'entregue', 'reaberta',
                    'aprovado', 'vencido'
                ));
            ALTER TABLE orcamentos ALTER COLUMN status SET DEFAULT 'nova';
        END $$;
    """)

    # Corrige a foreign key de orcamento_origem_id para ON DELETE SET NULL
    cur.execute("""
        DO $$
        DECLARE
            nome_constraint TEXT;
        BEGIN
            SELECT tc.constraint_name INTO nome_constraint
            FROM information_schema.table_constraints tc
            WHERE tc.table_name = 'orcamentos'
              AND tc.constraint_type = 'FOREIGN KEY'
              AND tc.constraint_name LIKE '%orcamento_origem_id%'
            LIMIT 1;

            IF nome_constraint IS NOT NULL THEN
                EXECUTE format('ALTER TABLE orcamentos DROP CONSTRAINT %I', nome_constraint);
            END IF;

            ALTER TABLE orcamentos
                ADD CONSTRAINT orcamentos_orcamento_origem_id_fkey
                FOREIGN KEY (orcamento_origem_id) REFERENCES orcamentos(id) ON DELETE SET NULL;
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
            valor_total NUMERIC(10, 2) NOT NULL,
            observacao_item TEXT,
            tipo_desconto TEXT,
            valor_desconto NUMERIC(10, 2),
            motivo_desconto TEXT,
            desconto_calculado NUMERIC(10, 2),
            servico_pai_item_id INTEGER REFERENCES orcamento_itens(id) ON DELETE CASCADE
        );
    """)

    # Compatibilidade: adiciona colunas em orcamento_itens para bancos já existentes
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamento_itens' AND column_name = 'servico_pai_item_id'
            ) THEN
                ALTER TABLE orcamento_itens
                    ADD COLUMN servico_pai_item_id INTEGER REFERENCES orcamento_itens(id) ON DELETE CASCADE;
            END IF;

            -- observacao_item: observação opcional por serviço (Bloco C)
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamento_itens' AND column_name = 'observacao_item'
            ) THEN
                ALTER TABLE orcamento_itens ADD COLUMN observacao_item TEXT;
            END IF;

            -- Descontos em serviços
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamento_itens' AND column_name = 'tipo_desconto'
            ) THEN
                ALTER TABLE orcamento_itens ADD COLUMN tipo_desconto TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamento_itens' AND column_name = 'valor_desconto'
            ) THEN
                ALTER TABLE orcamento_itens ADD COLUMN valor_desconto NUMERIC(10, 2);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamento_itens' AND column_name = 'motivo_desconto'
            ) THEN
                ALTER TABLE orcamento_itens ADD COLUMN motivo_desconto TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'orcamento_itens' AND column_name = 'desconto_calculado'
            ) THEN
                ALTER TABLE orcamento_itens ADD COLUMN desconto_calculado NUMERIC(10, 2);
            END IF;
        END $$;
    """)

    # Fotos anexadas ao orçamento/OS
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
    Igual a fetch_all, mas cacheado por 30s. Retorna list[dict] puro,
    com qualquer campo memoryview convertido para bytes.
    """
    rows = fetch_all(table, order_by)
    return [
        {k: (bytes(v) if isinstance(v, memoryview) else v) for k, v in row.items()}
        for row in rows
    ]


def query(sql, params=None):
    """Executa um SELECT customizado e retorna as linhas."""
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


def montar_grupos_orcamento(orcamento_id):
    """
    Busca os itens de um orçamento e monta a estrutura de grupos:
    cada serviço com sua lista de materiais (subitens) aninhada.
    Retorna list[dict]: [{item_id_bd, servico: {...}, materiais: [...]}, ...]
    """
    itens = query(
        "SELECT * FROM orcamento_itens WHERE orcamento_id = %s ORDER BY id",
        (orcamento_id,),
    )

    grupos = []
    grupos_por_item_id = {}

    for i in itens:
        if i["tipo_item"] == "servico":
            grupo = {
                "item_id_bd": i["id"],
                "servico": {
                    "item_id": i["item_id"],
                    "descricao": i["descricao"],
                    "quantidade": float(i["quantidade"]),
                    "valor_unitario": float(i["valor_unitario"]),
                    "valor_total": float(i["valor_total"]),
                    "observacao_item": i.get("observacao_item") or "",
                    "tipo_desconto": i.get("tipo_desconto"),
                    "valor_desconto": float(i["valor_desconto"]) if i.get("valor_desconto") is not None else 0.0,
                    "motivo_desconto": i.get("motivo_desconto") or "",
                    "desconto_calculado": float(i["desconto_calculado"]) if i.get("desconto_calculado") is not None else 0.0,
                },
                "materiais": [],
            }
            grupos.append(grupo)
            grupos_por_item_id[i["id"]] = grupo

    for i in itens:
        if i["tipo_item"] == "materia_prima":
            material = {
                "item_id": i["item_id"],
                "descricao": i["descricao"],
                "quantidade": float(i["quantidade"]),
                "valor_unitario": float(i["valor_unitario"]),
                "valor_total": float(i["valor_total"]),
            }
            pai_id = i["servico_pai_item_id"]
            if pai_id in grupos_por_item_id:
                grupos_por_item_id[pai_id]["materiais"].append(material)
            elif grupos:
                grupos[0]["materiais"].append(material)

    return grupos


def marcar_orcamentos_vencidos():
    """
    Atualiza para 'vencido' todo orçamento ainda aguardando aprovação
    cuja data_validade já passou.
    """
    execute("""
        UPDATE orcamentos
        SET status = 'vencido'
        WHERE tipo_operacao = 'orcamento'
          AND status = 'aguardando_aprovacao'
          AND data_validade IS NOT NULL
          AND data_validade < CURRENT_DATE
    """)
