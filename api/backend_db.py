"""
Camada de banco de dados (PostgreSQL), Storage e Auth (Supabase) para a API FastAPI.
Independente do Streamlit, podendo rodar na Vercel (via variáveis de ambiente)
ou localmente (lendo .streamlit/secrets.toml automaticamente).
"""

import os
import time
import uuid
import json
import hmac
import base64
import hashlib
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from supabase import create_client

BUCKET_NAME = "orcamento-fotos"

_conn = None
_db_initialized = False
_token_cache = {}  # {token: (email, exp_timestamp)}


def get_config() -> dict:
    """Retorna as credenciais do banco e Supabase de variáveis de ambiente ou secrets.toml."""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    supa_url = os.environ.get("SUPABASE_URL", "").strip()
    supa_key = os.environ.get("SUPABASE_KEY", "").strip()

    if not (db_url and supa_url and supa_key):
        secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
        if secrets_path.exists():
            try:
                import tomllib
                with open(secrets_path, "rb") as f:
                    data = tomllib.load(f)
                supa = data.get("connections", {}).get("supabase", {})
                db_url = db_url or supa.get("url", "")
                supa_url = supa_url or supa.get("storage_url", "")
                supa_key = supa_key or supa.get("storage_key", "")
            except Exception:
                pass

    return {
        "database_url": db_url,
        "supabase_url": supa_url,
        "supabase_key": supa_key,
    }


def _criar_conexao():
    cfg = get_config()
    if not cfg["database_url"]:
        raise RuntimeError("DATABASE_URL não configurada.")
    conn = psycopg2.connect(cfg["database_url"], cursor_factory=RealDictCursor, connect_timeout=10)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SET TIME ZONE 'America/Sao_Paulo';")
    conn.commit()
    cur.close()
    return conn


def get_connection():
    global _conn
    if _conn is None or _conn.closed != 0:
        _conn = _criar_conexao()
    return _conn


def _reconectar():
    global _conn
    try:
        if _conn and _conn.closed == 0:
            _conn.close()
    except Exception:
        pass
    _conn = _criar_conexao()
    return _conn


def query(sql: str, params=None) -> list[dict]:
    """Executa SELECT e retorna lista de dicionários."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        conn = _reconectar()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]


def fetch_all(table: str, order_by: str = "id") -> list[dict]:
    return query(f"SELECT * FROM {table} ORDER BY {order_by};")


def execute(sql: str, params=None):
    """Executa INSERT/UPDATE/DELETE e retorna linha do RETURNING se houver."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        result = dict(cur.fetchone()) if cur.description else None
        conn.commit()
        cur.close()
        return result
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        conn = _reconectar()
        cur = conn.cursor()
        cur.execute(sql, params or ())
        result = dict(cur.fetchone()) if cur.description else None
        conn.commit()
        cur.close()
        return result
    except Exception:
        try:
            conn = get_connection()
            conn.rollback()
        except Exception:
            pass
        raise


def get_supabase_client():
    cfg = get_config()
    if not cfg["supabase_url"] or not cfg["supabase_key"]:
        raise RuntimeError("SUPABASE_URL e SUPABASE_KEY não configuradas.")
    return create_client(cfg["supabase_url"], cfg["supabase_key"])


def _get_signing_secret() -> bytes:
    cfg = get_config()
    raw = f"{cfg.get('supabase_key', '')}:{cfg.get('database_url', '')}:atelie-auth-v1"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def gerar_token_assinado(email: str, dias_validade: int = 30, escopo: str = "sessao") -> str:
    payload = {
        "email": email.strip(),
        "exp": int(time.time()) + int(dias_validade * 86400),
        "escopo": escopo,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    sig = hmac.new(_get_signing_secret(), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"at1.{payload_b64}.{sig}"


def validar_token_assinado(token: str, escopo_esperado: str = "sessao") -> str | None:
    if not token or not token.startswith("at1."):
        return None
    partes = token.split(".")
    if len(partes) != 3:
        return None
    _, payload_b64, sig = partes
    expected_sig = hmac.new(_get_signing_secret(), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        return None
    try:
        pad = "=" * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload_b64 + pad).decode("utf-8"))
        if data.get("escopo") != escopo_esperado:
            return None
        if int(data.get("exp", 0)) <= int(time.time()):
            return None
        return data.get("email")
    except Exception:
        return None


def gerar_token_biometria(email: str) -> str:
    """Gera token de longa duração (180 dias) vinculado ao leitor biométrico do aparelho."""
    return gerar_token_assinado(email, dias_validade=180, escopo="biometria")


def trocar_token_biometria_por_sessao(bio_token: str) -> dict:
    """Valida o token biométrico após confirmação da digital e emite sessão de 30 dias."""
    email = validar_token_assinado(bio_token, escopo_esperado="biometria")
    if not email:
        raise ValueError("Credencial biométrica expirada ou inválida. Faça login com senha para reativar.")
    novo_access = gerar_token_assinado(email, dias_validade=30, escopo="sessao")
    novo_bio = gerar_token_biometria(email)
    return {
        "access_token": novo_access,
        "bio_token": novo_bio,
        "email": email,
    }


def login_supabase(email: str, senha: str) -> dict:
    """Autentica via Supabase Auth e retorna token de sessão de 30 dias + dados do usuário."""
    client = get_supabase_client()
    res = client.auth.sign_in_with_password({"email": email.strip(), "password": senha})
    if not res or not res.user or not res.session:
        raise ValueError("Credenciais inválidas.")
    token = gerar_token_assinado(res.user.email, dias_validade=30, escopo="sessao")
    return {
        "access_token": token,
        "email": res.user.email,
        "user_id": res.user.id,
    }


def validar_token(token: str) -> str | None:
    """Valida o token de sessão assinado (30 dias) ou JWT do Supabase Auth. Retorna o email se válido."""
    if not token:
        return None
    email_assinado = validar_token_assinado(token, escopo_esperado="sessao")
    if email_assinado:
        return email_assinado

    cached = _token_cache.get(token)
    if cached and cached[1] > time.time():
        return cached[0]

    try:
        client = get_supabase_client()
        res = client.auth.get_user(token)
        if res and res.user:
            _token_cache[token] = (res.user.email, time.time() + 900)
            return res.user.email
    except Exception:
        pass
    return None


def upload_foto(orcamento_id: int, file_bytes: bytes, file_extension: str) -> tuple[str, str]:
    """Envia foto para o bucket orcamento-fotos e retorna (url_publica, storage_path)."""
    ext = file_extension.lower().lstrip(".")
    if ext == "jpg":
        content_type = "image/jpeg"
    else:
        content_type = f"image/{ext}"

    client = get_supabase_client()
    storage_path = f"{orcamento_id}/{uuid.uuid4().hex}.{ext}"
    client.storage.from_(BUCKET_NAME).upload(
        storage_path,
        file_bytes,
        file_options={"content-type": content_type},
    )
    url_publica = client.storage.from_(BUCKET_NAME).get_public_url(storage_path)
    return url_publica, storage_path


def excluir_foto(storage_path: str):
    client = get_supabase_client()
    client.storage.from_(BUCKET_NAME).remove([storage_path])


def marcar_orcamentos_vencidos():
    execute("""
        UPDATE orcamentos
        SET status = 'vencido'
        WHERE tipo_operacao = 'orcamento'
          AND status = 'aguardando_aprovacao'
          AND data_validade IS NOT NULL
          AND data_validade < CURRENT_DATE
    """)


def montar_grupos_orcamento(orcamento_id: int) -> list[dict]:
    """Monta a estrutura de grupos (serviço + lista de materiais filhos) para Ordem de Serviço."""
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
            pai_id = i.get("servico_pai_item_id")
            if pai_id in grupos_por_item_id:
                grupos_por_item_id[pai_id]["materiais"].append(material)
            elif grupos:
                grupos[0]["materiais"].append(material)

    return grupos


def montar_secoes_orcamento(orcamento_id: int) -> dict:
    """Monta a estrutura de 4 seções (tecidos, aviamentos, outros, servicos) de um Orçamento."""
    itens = query(
        """SELECT oi.*, mp.tipo_material
           FROM orcamento_itens oi
           LEFT JOIN materia_prima mp
             ON mp.id = oi.item_id AND oi.tipo_item = 'materia_prima'
           WHERE oi.orcamento_id = %s
             AND oi.servico_pai_item_id IS NULL
           ORDER BY oi.id""",
        (orcamento_id,),
    )
    secoes = {"tecidos": [], "aviamentos": [], "outros": [], "servicos": []}
    for i in itens:
        entry = {
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
        }
        if i["tipo_item"] == "servico":
            secoes["servicos"].append(entry)
        else:
            tm = i.get("tipo_material") or "outros"
            if tm == "tecido":
                secoes["tecidos"].append(entry)
            elif tm == "aviamento":
                secoes["aviamentos"].append(entry)
            else:
                secoes["outros"].append(entry)
    return secoes
