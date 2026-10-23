"""
Ponto de entrada FastAPI (compatível com Vercel Serverless e execução local).
Reaproveita integralmente o banco Supabase, Supabase Storage, Supabase Auth e pdf_generator.py.
"""

import os
import sys
import base64
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Depends, HTTPException, Header, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.backend_db import (
    query,
    fetch_all,
    execute,
    login_supabase,
    validar_token,
    gerar_token_biometria,
    trocar_token_biometria_por_sessao,
    upload_foto,
    excluir_foto,
    marcar_orcamentos_vencidos,
    montar_grupos_orcamento,
    montar_secoes_orcamento,
)
from pdf_generator import gerar_pdf_os, gerar_pdf_orcamento

app = FastAPI(title="Ateliê - Plataforma Universal", version="2.0.0", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = ROOT_DIR / "static"


# ════════════════════════════════════════════════════════════════════
# AUTENTICAÇÃO E HELPERS DE SERIALIZAÇÃO
# ════════════════════════════════════════════════════════════════════

def require_auth(
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> str:
    jwt_token = None
    if authorization and authorization.lower().startswith("bearer "):
        jwt_token = authorization[7:].strip()
    elif token:
        jwt_token = token.strip()

    email = validar_token(jwt_token)
    if not email:
        raise HTTPException(status_code=401, detail="Sessão expirada ou não autenticada.")
    return email


def _fmt_dt(val) -> Optional[str]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y %H:%M")
    if isinstance(val, date):
        return val.strftime("%d/%m/%Y")
    return str(val)


def _fmt_iso_date(val) -> Optional[str]:
    if not val:
        return None
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    return str(val)[:10]


def _parse_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    try:
        return datetime.strptime(val[:10], "%Y-%m-%d").date()
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════
# SCHEMAS PYDANTIC
# ════════════════════════════════════════════════════════════════════

class LoginInput(BaseModel):
    email: str
    senha: str


class BiometriaLoginInput(BaseModel):
    bio_token: str


class PrestadorInput(BaseModel):
    nome: str
    telefone: Optional[str] = ""
    email: Optional[str] = ""
    cnpj: Optional[str] = ""
    clausulas: Optional[str] = ""
    logo_base64: Optional[str] = None


class ClienteInput(BaseModel):
    nome: str
    telefone: Optional[str] = ""
    email: Optional[str] = ""
    endereco: Optional[str] = ""


class ServicoInput(BaseModel):
    nome: str
    tipo_cobranca: str
    valor: float


class MaterialInput(BaseModel):
    nome: str
    tipo_material: str = "outros"
    tipo_medida: str = "unidade"
    valor: float


class StatusInput(BaseModel):
    status: str


class DocumentoInput(BaseModel):
    tipo_operacao: str  # 'orcamento' | 'ordem_servico'
    cliente_id: int
    tipo_pedido: str = "confeccao"
    observacoes: Optional[str] = ""
    descricao_livre: Optional[str] = ""
    data_validade: Optional[str] = None
    data_entrega: Optional[str] = None
    orcamento_origem_id: Optional[int] = None
    # Para OS: lista de [{servico: {...}, materiais: [...]}]
    grupos: Optional[list] = None
    # Para Orçamento: {tecidos: [...], aviamentos: [...], outros: [...], servicos: [...]}
    secoes: Optional[dict] = None
    # Config de fotos existentes: {foto_id: bool}
    fotos_cfg: Optional[dict] = None


# ════════════════════════════════════════════════════════════════════
# ROTAS DE AUTENTICAÇÃO E BOOTSTRAP
# ════════════════════════════════════════════════════════════════════

@app.post("/api/auth/login")
def api_login(dados: LoginInput):
    if not dados.email.strip() or not dados.senha:
        raise HTTPException(status_code=400, detail="Informe seu e-mail e sua senha.")
    try:
        res = login_supabase(dados.email, dados.senha)
        return res
    except Exception as e:
        msg = str(e).lower()
        if "invalid login credentials" in msg or "invalid_credentials" in msg:
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
        raise HTTPException(status_code=400, detail=f"Erro ao autenticar: {e}")


@app.post("/api/auth/biometria/registrar")
def api_registrar_biometria(user_email: str = Depends(require_auth)):
    """Emite um token vinculado à credencial biométrica do aparelho."""
    bio_token = gerar_token_biometria(user_email)
    return {"bio_token": bio_token, "email": user_email}


@app.post("/api/auth/biometria/login")
def api_login_biometria(dados: BiometriaLoginInput):
    """Troca o token biométrico desbloqueado pela digital do aparelho por uma sessão de 30 dias."""
    try:
        return trocar_token_biometria_por_sessao(dados.bio_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro no login biométrico: {e}")


@app.get("/api/bootstrap")
def api_bootstrap(user_email: str = Depends(require_auth)):
    """Carrega em uma única requisição o Dashboard e os cadastros base."""
    marcar_orcamentos_vencidos()

    # 1. Prestador
    prestadores = fetch_all("prestador")
    prestador_raw = prestadores[0] if prestadores else None
    prestador_out = None
    if prestador_raw:
        logo_b64 = None
        if prestador_raw.get("logo"):
            raw_bytes = bytes(prestador_raw["logo"])
            logo_b64 = base64.b64encode(raw_bytes).decode("ascii")
        prestador_out = {
            "id": prestador_raw["id"],
            "nome": prestador_raw["nome"] or "",
            "telefone": prestador_raw.get("telefone") or "",
            "email": prestador_raw.get("email") or "",
            "cnpj": prestador_raw.get("cnpj") or "",
            "clausulas": prestador_raw.get("clausulas") or "",
            "logo_base64": logo_b64,
        }

    # 2. Clientes
    clientes_raw = fetch_all("clientes", order_by="nome")
    clientes_out = [
        {
            "id": c["id"],
            "nome": c["nome"],
            "telefone": c.get("telefone") or "",
            "email": c.get("email") or "",
            "endereco": c.get("endereco") or "",
            "criado_em": _fmt_dt(c.get("criado_em")),
            "atualizado_em": _fmt_dt(c.get("atualizado_em") or c.get("criado_em")),
        }
        for c in clientes_raw
    ]

    # 3. Serviços
    servicos_raw = fetch_all("servicos", order_by="nome")
    servicos_out = [
        {
            "id": s["id"],
            "nome": s["nome"],
            "tipo_cobranca": s["tipo_cobranca"],
            "valor": float(s["valor"]),
            "criado_em": _fmt_dt(s.get("criado_em")),
            "atualizado_em": _fmt_dt(s.get("atualizado_em") or s.get("criado_em")),
        }
        for s in servicos_raw
    ]

    # 4. Matéria-Prima
    materiais_raw = fetch_all("materia_prima", order_by="nome")
    materiais_out = [
        {
            "id": m["id"],
            "nome": m["nome"],
            "tipo_material": m.get("tipo_material") or "outros",
            "tipo_medida": m["tipo_medida"],
            "valor": float(m["valor"]),
            "criado_em": _fmt_dt(m.get("criado_em")),
            "atualizado_em": _fmt_dt(m.get("atualizado_em") or m.get("criado_em")),
        }
        for m in materiais_raw
    ]

    # 5. Dashboard
    hoje = date.today()
    limite_7_dias = hoje + timedelta(days=7)

    reabertas = query("""
        SELECT o.id, o.tipo_pedido, o.status, o.data_entrega, c.nome AS cliente_nome
        FROM orcamentos o
        JOIN clientes c ON c.id = o.cliente_id
        WHERE o.tipo_operacao = 'ordem_servico' AND o.status = 'reaberta'
        ORDER BY o.criado_em DESC
    """)
    ordens_abertas = query("""
        SELECT o.id, o.tipo_operacao, o.tipo_pedido, o.status, o.data_entrega, c.nome AS cliente_nome
        FROM orcamentos o
        JOIN clientes c ON c.id = o.cliente_id
        WHERE o.tipo_operacao = 'ordem_servico' AND o.status != 'entregue'
        ORDER BY
            CASE WHEN o.status = 'reaberta' THEN 0 ELSE 1 END,
            o.data_entrega ASC NULLS LAST
        LIMIT 10
    """)
    agenda_7d = query(
        """
        SELECT o.id, o.tipo_pedido, o.status, o.data_entrega, c.nome AS cliente_nome
        FROM orcamentos o
        JOIN clientes c ON c.id = o.cliente_id
        WHERE o.tipo_operacao = 'ordem_servico'
          AND o.status != 'entregue'
          AND o.data_entrega IS NOT NULL
          AND o.data_entrega BETWEEN %s AND %s
        ORDER BY o.data_entrega ASC
        """,
        (hoje, limite_7_dias),
    )

    def _fmt_os_dash(row):
        dt = row.get("data_entrega")
        dias = (dt - hoje).days if isinstance(dt, date) else None
        return {
            "id": row["id"],
            "cliente_nome": row["cliente_nome"],
            "tipo_pedido": row["tipo_pedido"],
            "status": row["status"],
            "data_entrega": _fmt_dt(dt),
            "dias_restantes": dias,
        }

    return {
        "user_email": user_email,
        "prestador": prestador_out,
        "clientes": clientes_out,
        "servicos": servicos_out,
        "materiais": materiais_out,
        "dashboard": {
            "reabertas": [_fmt_os_dash(r) for r in reabertas],
            "abertas": [_fmt_os_dash(r) for r in ordens_abertas],
            "agenda": [_fmt_os_dash(r) for r in agenda_7d],
        },
    }


# ════════════════════════════════════════════════════════════════════
# ROTAS DE CADASTROS (PRESTADOR, CLIENTES, SERVIÇOS, MATÉRIA-PRIMA)
# ════════════════════════════════════════════════════════════════════

@app.post("/api/prestador")
def api_salvar_prestador(dados: PrestadorInput, _: str = Depends(require_auth)):
    if not dados.nome.strip():
        raise HTTPException(status_code=400, detail="O nome do prestador é obrigatório.")

    prestadores = fetch_all("prestador")
    existente = prestadores[0] if prestadores else None

    if dados.logo_base64:
        b64_clean = dados.logo_base64.split(",")[-1]
        logo_bytes = base64.b64decode(b64_clean)
    elif existente and existente.get("logo"):
        logo_bytes = bytes(existente["logo"])
    else:
        logo_bytes = None

    if existente:
        execute(
            """UPDATE prestador
               SET nome=%s, telefone=%s, email=%s, cnpj=%s, logo=%s, clausulas=%s
               WHERE id=%s""",
            (
                dados.nome.strip(),
                dados.telefone,
                dados.email,
                dados.cnpj,
                logo_bytes,
                dados.clausulas or None,
                existente["id"],
            ),
        )
    else:
        execute(
            """INSERT INTO prestador (nome, telefone, email, cnpj, logo, clausulas)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                dados.nome.strip(),
                dados.telefone,
                dados.email,
                dados.cnpj,
                logo_bytes,
                dados.clausulas or None,
            ),
        )
    return {"ok": True}


@app.post("/api/clientes")
def api_criar_cliente(dados: ClienteInput, _: str = Depends(require_auth)):
    if not dados.nome.strip():
        raise HTTPException(status_code=400, detail="O nome é obrigatório.")
    res = execute(
        """INSERT INTO clientes (nome, telefone, email, endereco)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (dados.nome.strip(), dados.telefone, dados.email, dados.endereco),
    )
    return {"ok": True, "id": res["id"]}


@app.put("/api/clientes/{cliente_id}")
def api_editar_cliente(cliente_id: int, dados: ClienteInput, _: str = Depends(require_auth)):
    if not dados.nome.strip():
        raise HTTPException(status_code=400, detail="O nome é obrigatório.")
    execute(
        """UPDATE clientes
           SET nome=%s, telefone=%s, email=%s, endereco=%s, atualizado_em=NOW()
           WHERE id=%s""",
        (dados.nome.strip(), dados.telefone, dados.email, dados.endereco, cliente_id),
    )
    return {"ok": True}


@app.get("/api/clientes/{cliente_id}/vinculos")
def api_vinculos_cliente(cliente_id: int, _: str = Depends(require_auth)):
    docs = query(
        """SELECT id, tipo_operacao, tipo_pedido, criado_em
           FROM orcamentos
           WHERE cliente_id = %s
           ORDER BY criado_em DESC""",
        (cliente_id,),
    )
    return {
        "documentos": [
            {
                "id": d["id"],
                "tipo_operacao": d["tipo_operacao"],
                "criado_em": _fmt_dt(d.get("criado_em")),
            }
            for d in docs
        ]
    }


@app.delete("/api/clientes/{cliente_id}")
def api_excluir_cliente(cliente_id: int, _: str = Depends(require_auth)):
    docs = query("SELECT id FROM orcamentos WHERE cliente_id = %s", (cliente_id,))
    for doc in docs:
        fotos = query("SELECT storage_path FROM orcamento_fotos WHERE orcamento_id = %s", (doc["id"],))
        for f in fotos:
            try:
                excluir_foto(f["storage_path"])
            except Exception:
                pass
        execute("DELETE FROM orcamentos WHERE id = %s", (doc["id"],))
    execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))
    return {"ok": True}


@app.post("/api/servicos")
def api_criar_servico(dados: ServicoInput, _: str = Depends(require_auth)):
    if not dados.nome.strip():
        raise HTTPException(status_code=400, detail="O nome do serviço é obrigatório.")
    res = execute(
        """INSERT INTO servicos (nome, tipo_cobranca, valor)
           VALUES (%s, %s, %s) RETURNING id""",
        (dados.nome.strip(), dados.tipo_cobranca, dados.valor),
    )
    return {"ok": True, "id": res["id"]}


@app.put("/api/servicos/{servico_id}")
def api_editar_servico(servico_id: int, dados: ServicoInput, _: str = Depends(require_auth)):
    if not dados.nome.strip():
        raise HTTPException(status_code=400, detail="O nome do serviço é obrigatório.")
    execute(
        """UPDATE servicos
           SET nome=%s, tipo_cobranca=%s, valor=%s, atualizado_em=NOW()
           WHERE id=%s""",
        (dados.nome.strip(), dados.tipo_cobranca, dados.valor, servico_id),
    )
    return {"ok": True}


@app.delete("/api/servicos/{servico_id}")
def api_excluir_servico(servico_id: int, _: str = Depends(require_auth)):
    execute("DELETE FROM servicos WHERE id = %s", (servico_id,))
    return {"ok": True}


@app.post("/api/materiais")
def api_criar_material(dados: MaterialInput, _: str = Depends(require_auth)):
    if not dados.nome.strip():
        raise HTTPException(status_code=400, detail="O nome do material é obrigatório.")
    res = execute(
        """INSERT INTO materia_prima (nome, tipo_material, tipo_medida, valor)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (dados.nome.strip(), dados.tipo_material, dados.tipo_medida, dados.valor),
    )
    return {"ok": True, "id": res["id"]}


@app.put("/api/materiais/{material_id}")
def api_editar_material(material_id: int, dados: MaterialInput, _: str = Depends(require_auth)):
    if not dados.nome.strip():
        raise HTTPException(status_code=400, detail="O nome do material é obrigatório.")
    execute(
        """UPDATE materia_prima
           SET nome=%s, tipo_material=%s, tipo_medida=%s, valor=%s, atualizado_em=NOW()
           WHERE id=%s""",
        (dados.nome.strip(), dados.tipo_material, dados.tipo_medida, dados.valor, material_id),
    )
    return {"ok": True}


@app.delete("/api/materiais/{material_id}")
def api_excluir_material(material_id: int, _: str = Depends(require_auth)):
    execute("DELETE FROM materia_prima WHERE id = %s", (material_id,))
    return {"ok": True}


# ════════════════════════════════════════════════════════════════════
# ROTAS DE DOCUMENTOS (ORÇAMENTOS E ORDENS DE SERVIÇO)
# ════════════════════════════════════════════════════════════════════

@app.get("/api/documentos")
def api_listar_documentos(_: str = Depends(require_auth)):
    marcar_orcamentos_vencidos()

    docs = query("""
        SELECT o.id, o.cliente_id, o.tipo_operacao, o.tipo_pedido, o.status,
               o.observacoes, o.data_validade, o.data_entrega,
               o.orcamento_origem_id, o.descricao_livre, o.criado_em,
               c.nome AS cliente_nome, c.telefone AS cliente_telefone,
               c.email AS cliente_email, c.endereco AS cliente_endereco
        FROM orcamentos o
        JOIN clientes c ON c.id = o.cliente_id
        ORDER BY o.criado_em DESC
    """)

    todos_itens = query("""
        SELECT oi.*, mp.tipo_material
        FROM orcamento_itens oi
        LEFT JOIN materia_prima mp
          ON mp.id = oi.item_id AND oi.tipo_item = 'materia_prima'
        ORDER BY oi.id
    """)

    todas_fotos = query("""
        SELECT id, orcamento_id, url, storage_path, pagina_inteira
        FROM orcamento_fotos
        ORDER BY id
    """)

    itens_por_doc = {}
    for i in todos_itens:
        itens_por_doc.setdefault(i["orcamento_id"], []).append(i)

    fotos_por_doc = {}
    for f in todas_fotos:
        fotos_por_doc.setdefault(f["orcamento_id"], []).append({
            "id": f["id"],
            "url": f["url"],
            "storage_path": f["storage_path"],
            "pagina_inteira": bool(f.get("pagina_inteira", False)),
        })

    saida = []
    for d in docs:
        doc_id = d["id"]
        itens_doc = itens_por_doc.get(doc_id, [])

        # Estrutura para OS (grupos) e para Orçamento (seções)
        grupos = []
        grupos_map = {}
        secoes = {"tecidos": [], "aviamentos": [], "outros": [], "servicos": []}
        subtotal_bruto = 0.0
        total_desconto = 0.0

        for i in itens_doc:
            vt = float(i["valor_total"])
            vu = float(i["valor_unitario"])
            qtd = float(i["quantidade"])
            dc = float(i["desconto_calculado"]) if i.get("desconto_calculado") is not None else 0.0
            vd = float(i["valor_desconto"]) if i.get("valor_desconto") is not None else 0.0

            subtotal_bruto += vt
            total_desconto += dc

            if i["tipo_item"] == "servico":
                srv_obj = {
                    "item_id": i["item_id"],
                    "descricao": i["descricao"],
                    "quantidade": qtd,
                    "valor_unitario": vu,
                    "valor_total": vt,
                    "observacao_item": i.get("observacao_item") or "",
                    "tipo_desconto": i.get("tipo_desconto"),
                    "valor_desconto": vd,
                    "motivo_desconto": i.get("motivo_desconto") or "",
                    "desconto_calculado": dc,
                }
                g = {"item_id_bd": i["id"], "servico": srv_obj, "materiais": []}
                grupos.append(g)
                grupos_map[i["id"]] = g
                secoes["servicos"].append(srv_obj)

        for i in itens_doc:
            if i["tipo_item"] == "materia_prima":
                mat_obj = {
                    "item_id": i["item_id"],
                    "descricao": i["descricao"],
                    "quantidade": float(i["quantidade"]),
                    "valor_unitario": float(i["valor_unitario"]),
                    "valor_total": float(i["valor_total"]),
                    "observacao_item": i.get("observacao_item") or "",
                }
                pai_id = i.get("servico_pai_item_id")
                if pai_id in grupos_map:
                    grupos_map[pai_id]["materiais"].append(mat_obj)
                elif d["tipo_operacao"] == "ordem_servico" and grupos:
                    grupos[0]["materiais"].append(mat_obj)
                else:
                    tm = i.get("tipo_material") or "outros"
                    if tm == "tecido":
                        secoes["tecidos"].append(mat_obj)
                    elif tm == "aviamento":
                        secoes["aviamentos"].append(mat_obj)
                    else:
                        secoes["outros"].append(mat_obj)

        saida.append({
            "id": doc_id,
            "cliente_id": d["cliente_id"],
            "cliente_nome": d["cliente_nome"],
            "tipo_operacao": d["tipo_operacao"],
            "tipo_pedido": d.get("tipo_pedido") or "confeccao",
            "status": d["status"],
            "observacoes": d.get("observacoes") or "",
            "descricao_livre": d.get("descricao_livre") or "",
            "data_validade_fmt": _fmt_dt(d.get("data_validade")),
            "data_validade_iso": _fmt_iso_date(d.get("data_validade")),
            "data_entrega_fmt": _fmt_dt(d.get("data_entrega")),
            "data_entrega_iso": _fmt_iso_date(d.get("data_entrega")),
            "orcamento_origem_id": d.get("orcamento_origem_id"),
            "criado_em": _fmt_dt(d.get("criado_em")),
            "subtotal_bruto": round(subtotal_bruto, 2),
            "total_desconto": round(total_desconto, 2),
            "total_liquido": round(max(0.0, subtotal_bruto - total_desconto), 2),
            "grupos": grupos,
            "secoes": secoes,
            "fotos": fotos_por_doc.get(doc_id, []),
        })

    return {"documentos": saida}


def _salvar_itens_documento(doc_id: int, dados: DocumentoInput):
    if dados.tipo_operacao == "ordem_servico":
        for grupo in (dados.grupos or []):
            s = grupo["servico"]
            res_item = execute(
                """INSERT INTO orcamento_itens
                    (orcamento_id, tipo_item, item_id, descricao, quantidade,
                     valor_unitario, valor_total, observacao_item,
                     tipo_desconto, valor_desconto, motivo_desconto, desconto_calculado)
                   VALUES (%s,'servico',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (
                    doc_id,
                    s["item_id"],
                    s["descricao"],
                    s["quantidade"],
                    s["valor_unitario"],
                    s["valor_total"],
                    s.get("observacao_item") or None,
                    s.get("tipo_desconto") or None,
                    s.get("valor_desconto") or 0.0,
                    s.get("motivo_desconto") or None,
                    s.get("desconto_calculado") or 0.0,
                ),
            )
            srv_item_id = res_item["id"]
            for m in grupo.get("materiais", []):
                execute(
                    """INSERT INTO orcamento_itens
                        (orcamento_id, tipo_item, item_id, descricao, quantidade,
                         valor_unitario, valor_total, servico_pai_item_id)
                       VALUES (%s,'materia_prima',%s,%s,%s,%s,%s,%s)""",
                    (
                        doc_id,
                        m["item_id"],
                        m["descricao"],
                        m["quantidade"],
                        m["valor_unitario"],
                        m["valor_total"],
                        srv_item_id,
                    ),
                )
    else:
        secoes = dados.secoes or {}
        for ch in ("tecidos", "aviamentos", "outros"):
            for item in secoes.get(ch, []):
                execute(
                    """INSERT INTO orcamento_itens
                        (orcamento_id, tipo_item, item_id, descricao, quantidade,
                         valor_unitario, valor_total, observacao_item)
                       VALUES (%s,'materia_prima',%s,%s,%s,%s,%s,%s)""",
                    (
                        doc_id,
                        item["item_id"],
                        item["descricao"],
                        item["quantidade"],
                        item["valor_unitario"],
                        item["valor_total"],
                        item.get("observacao_item") or None,
                    ),
                )
        for item in secoes.get("servicos", []):
            execute(
                """INSERT INTO orcamento_itens
                    (orcamento_id, tipo_item, item_id, descricao, quantidade,
                     valor_unitario, valor_total, observacao_item,
                     tipo_desconto, valor_desconto, motivo_desconto, desconto_calculado)
                   VALUES (%s,'servico',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    doc_id,
                    item["item_id"],
                    item["descricao"],
                    item["quantidade"],
                    item["valor_unitario"],
                    item["valor_total"],
                    item.get("observacao_item") or None,
                    item.get("tipo_desconto") or None,
                    item.get("valor_desconto") or 0.0,
                    item.get("motivo_desconto") or None,
                    item.get("desconto_calculado") or 0.0,
                ),
            )


@app.post("/api/documentos")
def api_criar_documento(dados: DocumentoInput, _: str = Depends(require_auth)):
    dt_val = _parse_date(dados.data_validade)
    dt_ent = _parse_date(dados.data_entrega)

    if dados.tipo_operacao == "ordem_servico":
        res = execute(
            """INSERT INTO orcamentos
                (cliente_id, tipo_operacao, tipo_pedido, status, observacoes, data_entrega, orcamento_origem_id)
               VALUES (%s, 'ordem_servico', %s, 'nova', %s, %s, %s)
               RETURNING id""",
            (
                dados.cliente_id,
                dados.tipo_pedido or "confeccao",
                dados.observacoes or None,
                dt_ent,
                dados.orcamento_origem_id,
            ),
        )
        if dados.orcamento_origem_id:
            execute(
                "UPDATE orcamentos SET status = 'aprovado' WHERE id = %s",
                (dados.orcamento_origem_id,),
            )
    else:
        res = execute(
            """INSERT INTO orcamentos
                (cliente_id, tipo_operacao, tipo_pedido, status, data_validade, descricao_livre)
               VALUES (%s, 'orcamento', %s, 'aguardando_aprovacao', %s, %s)
               RETURNING id""",
            (
                dados.cliente_id,
                dados.tipo_pedido or "confeccao",
                dt_val,
                dados.descricao_livre or None,
            ),
        )

    doc_id = res["id"]
    _salvar_itens_documento(doc_id, dados)
    return {"ok": True, "id": doc_id}


@app.put("/api/documentos/{doc_id}")
def api_editar_documento(doc_id: int, dados: DocumentoInput, _: str = Depends(require_auth)):
    dt_val = _parse_date(dados.data_validade)
    dt_ent = _parse_date(dados.data_entrega)

    if dados.tipo_operacao == "ordem_servico":
        execute(
            """UPDATE orcamentos
               SET cliente_id=%s, observacoes=%s, data_entrega=%s
               WHERE id=%s""",
            (dados.cliente_id, dados.observacoes or None, dt_ent, doc_id),
        )
    else:
        execute(
            """UPDATE orcamentos
               SET cliente_id=%s, data_validade=%s, descricao_livre=%s
               WHERE id=%s""",
            (dados.cliente_id, dt_val, dados.descricao_livre or None, doc_id),
        )

    execute("DELETE FROM orcamento_itens WHERE orcamento_id = %s", (doc_id,))
    _salvar_itens_documento(doc_id, dados)

    if dados.fotos_cfg:
        for foto_id_str, pi in dados.fotos_cfg.items():
            execute(
                "UPDATE orcamento_fotos SET pagina_inteira = %s WHERE id = %s AND orcamento_id = %s",
                (bool(pi), int(foto_id_str), doc_id),
            )

    return {"ok": True, "id": doc_id}


@app.post("/api/documentos/{doc_id}/fotos")
async def api_upload_fotos(
    doc_id: int,
    files: list[UploadFile] = File(...),
    paginas_inteiras: str = Form(default=""),
    _: str = Depends(require_auth),
):
    flags = [x.strip() == "1" for x in paginas_inteiras.split(",")] if paginas_inteiras else []
    enviadas = []
    for idx, f in enumerate(files):
        conteudo = await f.read()
        ext = (f.filename or "foto.jpg").split(".")[-1].lower()
        pi = flags[idx] if idx < len(flags) else False
        url_pub, spath = upload_foto(doc_id, conteudo, ext)
        res = execute(
            """INSERT INTO orcamento_fotos (orcamento_id, url, storage_path, pagina_inteira)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (doc_id, url_pub, spath, pi),
        )
        enviadas.append({"id": res["id"], "url": url_pub, "pagina_inteira": pi})
    return {"ok": True, "fotos": enviadas}


@app.delete("/api/fotos/{foto_id}")
def api_excluir_foto_endpoint(foto_id: int, _: str = Depends(require_auth)):
    rows = query("SELECT storage_path FROM orcamento_fotos WHERE id = %s", (foto_id,))
    for r in rows:
        try:
            excluir_foto(r["storage_path"])
        except Exception:
            pass
    execute("DELETE FROM orcamento_fotos WHERE id = %s", (foto_id,))
    return {"ok": True}


@app.patch("/api/documentos/{doc_id}/status")
def api_atualizar_status(doc_id: int, dados: StatusInput, _: str = Depends(require_auth)):
    execute("UPDATE orcamentos SET status = %s WHERE id = %s", (dados.status, doc_id))
    return {"ok": True}


@app.delete("/api/documentos/{doc_id}")
def api_excluir_documento(doc_id: int, _: str = Depends(require_auth)):
    fotos = query("SELECT storage_path FROM orcamento_fotos WHERE orcamento_id = %s", (doc_id,))
    for f in fotos:
        try:
            excluir_foto(f["storage_path"])
        except Exception:
            pass
    execute("DELETE FROM orcamentos WHERE id = %s", (doc_id,))
    return {"ok": True}


@app.get("/api/documentos/{doc_id}/pdf")
def api_gerar_pdf(doc_id: int, _: str = Depends(require_auth)):
    """Gera o PDF idêntico ao Streamlit usando pdf_generator.py e retorna para download."""
    prestadores = fetch_all("prestador")
    if not prestadores:
        raise HTTPException(status_code=400, detail="Cadastre o Prestador de Serviço antes de gerar o PDF.")
    prestador_pdf = prestadores[0]

    docs = query(
        """SELECT o.*, c.nome AS cliente_nome, c.telefone AS cliente_telefone,
                  c.email AS cliente_email, c.endereco AS cliente_endereco
           FROM orcamentos o
           JOIN clientes c ON c.id = o.cliente_id
           WHERE o.id = %s""",
        (doc_id,),
    )
    if not docs:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    doc = docs[0]

    cliente_pdf = {
        "nome": doc["cliente_nome"],
        "telefone": doc["cliente_telefone"],
        "email": doc["cliente_email"],
        "endereco": doc["cliente_endereco"],
    }

    if doc["tipo_operacao"] == "orcamento":
        secoes_pdf = montar_secoes_orcamento(doc_id)
        fotos_bd = query(
            "SELECT url, pagina_inteira FROM orcamento_fotos WHERE orcamento_id = %s ORDER BY id",
            (doc_id,),
        )
        fotos_pdf = [
            {"url": f["url"], "pagina_inteira": bool(f.get("pagina_inteira", False))}
            for f in fotos_bd
        ]
        pdf_path = gerar_pdf_orcamento(
            prestador=prestador_pdf,
            cliente=cliente_pdf,
            secoes=secoes_pdf,
            descricao_livre=doc.get("descricao_livre") or "",
            data_validade=doc.get("data_validade"),
            fotos=fotos_pdf,
        )
    else:
        grupos = montar_grupos_orcamento(doc_id)
        grupos_pdf = [
            {
                "descricao": g["servico"]["descricao"],
                "quantidade": g["servico"]["quantidade"],
                "valor_unitario": g["servico"]["valor_unitario"],
                "valor_total": g["servico"]["valor_total"],
                "observacao_item": g["servico"].get("observacao_item", ""),
                "tipo_desconto": g["servico"].get("tipo_desconto"),
                "valor_desconto": g["servico"].get("valor_desconto", 0.0),
                "motivo_desconto": g["servico"].get("motivo_desconto", ""),
                "desconto_calculado": g["servico"].get("desconto_calculado", 0.0),
                "materiais": g["materiais"],
            }
            for g in grupos
        ]
        pdf_path = gerar_pdf_os(
            prestador=prestador_pdf,
            cliente=cliente_pdf,
            grupos=grupos_pdf,
            observacoes=doc.get("observacoes") or "",
            data_entrega=doc.get("data_entrega"),
        )

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    try:
        os.remove(pdf_path)
    except Exception:
        pass

    nome_cliente_limpo = "".join(
        c if c.isalnum() else "_" for c in (doc["cliente_nome"] or "cliente")
    )
    nome_arquivo = f"{doc['tipo_operacao']}_{nome_cliente_limpo}_{doc_id}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


# ════════════════════════════════════════════════════════════════════
# ARQUIVOS ESTÁTICOS E SPA (PWA / WEB / ANDROID)
# ════════════════════════════════════════════════════════════════════

@app.get("/manifest.json")
def serve_manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/icon.svg")
def serve_icon():
    return FileResponse(STATIC_DIR / "icon.svg", media_type="image/svg+xml")


@app.get("/static/app.js")
def serve_app_js():
    return FileResponse(STATIC_DIR / "app.js", media_type="application/javascript")


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return JSONResponse({"status": "Ateliê API online"})
