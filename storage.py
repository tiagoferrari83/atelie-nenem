"""
Upload e remoção de fotos no Supabase Storage.
Guardamos só a URL no banco Postgres - o binário fica no Storage (bucket separado,
com cota própria de 1GB no plano free, fora do limite do banco).
"""

import streamlit as st
from supabase import create_client
import uuid

BUCKET_NAME = "orcamento-fotos"


def get_storage_client():
    url = st.secrets["connections"]["supabase"]["storage_url"]
    key = st.secrets["connections"]["supabase"]["storage_key"]
    return create_client(url, key)


def upload_foto(orcamento_id, file_bytes, file_extension):
    """Envia uma foto para o bucket e retorna (url_publica, storage_path)."""
    client = get_storage_client()
    storage_path = f"{orcamento_id}/{uuid.uuid4().hex}.{file_extension}"

    client.storage.from_(BUCKET_NAME).upload(
        storage_path,
        file_bytes,
        file_options={"content-type": f"image/{file_extension}"},
    )

    url_publica = client.storage.from_(BUCKET_NAME).get_public_url(storage_path)
    return url_publica, storage_path


def excluir_foto(storage_path):
    """Remove uma foto do bucket."""
    client = get_storage_client()
    client.storage.from_(BUCKET_NAME).remove([storage_path])
