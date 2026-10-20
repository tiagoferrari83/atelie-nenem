"""
Script de Keep-Alive para manter o projeto Supabase ativo no plano gratuito.
Evita que o banco de dados e o Storage entrem em modo de pausa após 7 dias sem uso.
"""

import os
import sys
from pathlib import Path
from supabase import create_client


def _carregar_credenciais_locais():
    """Tenta ler .streamlit/secrets.toml caso as variáveis de ambiente não estejam definidas."""
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return "", "", ""

    try:
        import tomllib
        with open(secrets_path, "rb") as f:
            data = tomllib.load(f)
        supa = data.get("connections", {}).get("supabase", {})
        return (
            supa.get("storage_url", ""),
            supa.get("storage_key", ""),
            supa.get("url", ""),
        )
    except Exception:
        return "", "", ""


def main():
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_KEY", "").strip()
    database_url = os.environ.get("DATABASE_URL", "").strip()

    if not supabase_url and not database_url:
        local_url, local_key, local_db = _carregar_credenciais_locais()
        supabase_url = supabase_url or local_url
        supabase_key = supabase_key or local_key
        database_url = database_url or local_db

    sucesso = False

    # 1. Ping via API HTTPS do Supabase (Storage + consulta interna ao PostgreSQL)
    if supabase_url and supabase_key:
        try:
            client = create_client(supabase_url, supabase_key)
            res = client.storage.from_("orcamento-fotos").list(options={"limit": 1})
            print(
                f"[OK] Supabase API/Storage respondeu com sucesso "
                f"({len(res)} item(ns) verificado(s) no bucket 'orcamento-fotos')."
            )
            sucesso = True
        except Exception as e:
            print(f"[AVISO] Erro ao consultar Supabase API/Storage: {e}")

    # 2. Ping opcional via conexão direta/pooler PostgreSQL (psycopg2)
    if database_url:
        try:
            import psycopg2

            conn = psycopg2.connect(database_url, connect_timeout=10)
            cur = conn.cursor()
            cur.execute("SELECT NOW();")
            data_atual = cur.fetchone()[0]
            cur.close()
            conn.close()
            print(f"[OK] PostgreSQL respondeu diretamente: {data_atual}")
            sucesso = True
        except Exception as e:
            print(
                f"[AVISO] Conexão direta PostgreSQL não realizada "
                f"(normal no GitHub Actions se não for URL Pooler IPv4): {e}"
            )

    if not sucesso:
        print(
            "[ERRO] Nenhuma verificação conseguiu se comunicar com o Supabase. "
            "Verifique se SUPABASE_URL e SUPABASE_KEY estão configurados nos Secrets do GitHub."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
