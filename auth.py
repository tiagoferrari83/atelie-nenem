"""
Módulo de autenticação via Supabase Auth.
Reaproveita a URL e a chave anon já configuradas em [connections.supabase] no secrets.toml.
"""

import streamlit as st
from supabase import create_client


def _get_supabase_client():
    url = st.secrets["connections"]["supabase"]["storage_url"]
    key = st.secrets["connections"]["supabase"]["storage_key"]
    return create_client(url, key)


def usuario_esta_logado() -> bool:
    """Retorna True se houver um usuário autenticado na sessão atual."""
    return bool(st.session_state.get("usuario_autenticado"))


def autenticar(email: str, senha: str) -> tuple[bool, str]:
    """
    Autentica o usuário no Supabase Auth com e-mail e senha.
    Retorna (sucesso: bool, mensagem_erro: str).
    """
    email_limpo = (email or "").strip()
    if not email_limpo or not senha:
        return False, "Informe seu e-mail e sua senha."

    try:
        client = _get_supabase_client()
        resposta = client.auth.sign_in_with_password(
            {"email": email_limpo, "password": senha}
        )
        if resposta and resposta.user:
            st.session_state["usuario_autenticado"] = True
            st.session_state["usuario_email"] = resposta.user.email
            st.session_state["usuario_id"] = resposta.user.id
            return True, ""
        return False, "Não foi possível autenticar. Verifique suas credenciais."
    except Exception as e:
        msg = str(e).lower()
        if "invalid login credentials" in msg or "invalid_credentials" in msg:
            return False, "E-mail ou senha incorretos."
        if "email not confirmed" in msg:
            return (
                False,
                "E-mail ainda não confirmado no Supabase. No painel do Supabase, "
                "marque 'Auto Confirm User' ou confirme o usuário em Authentication → Users.",
            )
        return False, f"Erro ao conectar ao servidor de autenticação: {e}"


def fazer_logout():
    """Encerra a sessão do usuário atual."""
    try:
        client = _get_supabase_client()
        client.auth.sign_out()
    except Exception:
        pass

    for chave in ("usuario_autenticado", "usuario_email", "usuario_id"):
        st.session_state.pop(chave, None)


def tela_login():
    """Renderiza a tela de login centralizada."""
    st.markdown("<br>", unsafe_allow_html=True)
    col_esq, col_centro, col_dir = st.columns([1, 2, 1])

    with col_centro:
        st.markdown(
            "<h2 style='text-align: center;'>🧵 Ateliê - Gestão</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align: center; color: gray;'>Faça login para acessar o sistema</p>",
            unsafe_allow_html=True,
        )

        with st.form("form_login", clear_on_submit=False):
            email = st.text_input("E-mail", placeholder="seu@email.com")
            senha = st.text_input("Senha", type="password", placeholder="••••••••")
            entrar = st.form_submit_button("Entrar", type="primary", width="stretch")

            if entrar:
                with st.spinner("Verificando credenciais..."):
                    sucesso, erro = autenticar(email, senha)
                if sucesso:
                    st.rerun()
                else:
                    st.error(erro)
