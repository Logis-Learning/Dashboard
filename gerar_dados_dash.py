# =============================================================================
# gerar_dados_dash.py — Gera dados.js para o dashboard_simpar.html
# =============================================================================
# Lê output_powerbi/relatorio_matriculas.xlsx e calcula KPIs e agregações.
# Gera dados.js na mesma pasta do dashboard HTML.
#
# Uso:
#   python gerar_dados_dash.py
# =============================================================================

import os
import json
import pandas as pd
import unicodedata
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_ENTRADA = os.path.join(BASE_DIR, "output_powerbi", "relatorio_matriculas.xlsx")
ARQUIVO_JS      = os.path.join(BASE_DIR, "dados.js")
ARQUIVO_ATIVOS  = os.path.join(BASE_DIR, "input", "Ativos.xlsx")
ARQUIVO_MISSOES = os.path.join(BASE_DIR, "input", "missoes_para_exportar.xlsx")
ARQUIVO_MATRIZ  = os.path.join(BASE_DIR, "input", "matriz_treinamentos.xlsx")
ARQUIVO_BIBLIO  = os.path.join(BASE_DIR, "input", "biblioteca_colaboradores.xlsx")


def _carregar_biblio_gestor_turno() -> dict:
    """Retorna {matricula: {"gestor": ..., "turno": ...}} da biblioteca_colaboradores.xlsx."""
    if not os.path.exists(ARQUIVO_BIBLIO):
        return {}
    df = pd.read_excel(ARQUIVO_BIBLIO, dtype=str).fillna("")
    cols = {str(c).strip().lower(): c for c in df.columns}
    col_mat  = cols.get("matricula")
    col_gest = cols.get("gestor")
    col_turn = cols.get("turno")
    if not col_mat:
        return {}
    biblio = {}
    for _, row in df.iterrows():
        mat = str(row.get(col_mat, "")).strip()
        if not mat:
            continue
        biblio[mat] = {
            "gestor": str(row.get(col_gest, "") if col_gest else "").strip(),
            "turno":  str(row.get(col_turn, "") if col_turn else "").strip(),
        }
    return biblio


def _sem_acento(valor) -> str:
    texto = "" if pd.isna(valor) else str(valor)
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(ch)
    )


def _chave_coluna(valor) -> str:
    return _sem_acento(valor).strip().lower()


def _status_normalizado(valor) -> str:
    status = _sem_acento(valor).strip().upper().replace("-", "_").replace(" ", "_")
    while "__" in status:
        status = status.replace("__", "_")
    aliases = {
        "": "NAO MATRICULADO",
        "NAN": "NAO MATRICULADO",
        "NAO_MATRICULADO": "NAO MATRICULADO",
        "NAO_INICIADO": "NOT_STARTED",
        "NAO_INICIADA": "NOT_STARTED",
        "NOT_STARTED": "NOT_STARTED",
        "NOTSTARTED": "NOT_STARTED",
    }
    return aliases.get(status, status)


COLUNAS_RELATORIO = {
    "id do usuario": "ID do Usuário",
    "nome": "Nome",
    "email": "Email",
    "username": "Username",
    "cpf": "CPF",
    "cargo": "Cargo",
    "departamento": "Departamento",
    "setor": "Setor",
    "turno": "Turno",
    "filial": "Filial",
    "lista de nome dos lideres": "Lista de Nome dos Lideres",
    "observacoes biblioteca": "Observacoes Biblioteca",
    "data de admissao": "Data de admissao",
    "id da missao": "ID da missao",
    "missao": "Missao",
    "missao obrigatoria?": "Missao Obrigatoria?",
    "missao pode ser cancelada?": "Missao pode ser cancelada?",
    "carga horaria (min)": "Carga horaria (min)",
    "data da matricula": "Data da Matricula",
    "prazo de conclusao": "Prazo de Conclusao",
    "status detalhado da matricula": "Status Detalhado da Matricula",
    "data de conclusao da matricula": "Data de Conclusao da Matricula",
    "data de cancelamento da matricula": "Data de Cancelamento da Matricula",
    "motivo do cancelamento da matricula": "Motivo do Cancelamento da matricula",
    "data de emissao do certificado": "Data de Emissao do Certificado",
    "progresso": "Progresso",
    "media das notas": "Media das notas",
    "tempo de treinamento (min)": "Tempo de treinamento (min)",
    "times do usuario": "Times do usuario",
}


def _normalizar_colunas_relatorio(df: pd.DataFrame) -> pd.DataFrame:
    renomear = {}
    for coluna in df.columns:
        destino = COLUNAS_RELATORIO.get(_chave_coluna(coluna))
        if destino:
            renomear[coluna] = destino
    return df.rename(columns=renomear)


def top_n(series: pd.Series, n: int = 20) -> tuple:
    s = series.sort_values(ascending=False).head(n)
    return [str(x) for x in s.index], [int(x) for x in s.values]


def carregar_df() -> pd.DataFrame:
    if not os.path.exists(ARQUIVO_ENTRADA):
        raise FileNotFoundError(
            f"Arquivo não encontrado: {ARQUIVO_ENTRADA}\n"
            "Execute primeiro: python gerar_relatorio_matriculas.py"
        )

    df = _normalizar_colunas_relatorio(pd.read_excel(ARQUIVO_ENTRADA, dtype=str))

    # Remove coluna índice automática
    colunas_unnamed = [c for c in df.columns if _chave_coluna(c).startswith("unnamed")]
    if colunas_unnamed:
        df = df.drop(columns=colunas_unnamed)

    chaves = [c for c in ["ID do Usuário", "Username", "ID da missao", "Status Detalhado da Matricula"] if c in df.columns]
    if chaves:
        df = df.drop_duplicates(subset=chaves, keep="last").copy()

    # Normaliza status
    col_st = "Status Detalhado da Matricula"
    if col_st not in df.columns:
        # tenta com acento
        col_st = next((c for c in df.columns if "status" in _chave_coluna(c) and "matricula" in _chave_coluna(c)), None)
    if col_st:
        df["_status"] = df[col_st].apply(_status_normalizado)
    else:
        df["_status"] = "NAO MATRICULADO"

    df["_ok"]  = df["_status"].isin(["COMPLETED", "COMPLETED_AFTER_DUE_DATE"])
    df["_and"] = df["_status"] == "IN_PROGRESS"
    df["_ns"]  = df["_status"] == "NOT_STARTED"
    df["_can"] = df["_status"] == "CANCELLED"
    df["_nao"] = df["_status"] == "NAO MATRICULADO"
    df["_pend"] = ~df["_ok"] & ~df["_can"]

    # Progresso numérico
    col_prog = next((c for c in df.columns if "progresso" in c.lower() or "progress" in c.lower()), None)
    df["_prog"] = pd.to_numeric(df[col_prog], errors="coerce").fillna(0) if col_prog else 0

    # Turno: prefere a biblioteca; se nao existir, usa o primeiro time.
    col_turno = next((c for c in df.columns if c.strip().lower() == "turno"), None)
    col_times = next((c for c in df.columns if "times" in c.lower()), None)
    if col_turno:
        df["_turno"] = (
            df[col_turno].fillna("Não informado")
            .apply(lambda x: str(x).strip())
            .replace({"": "Não informado", "nan": "Não informado"})
        )
    elif col_times:
        df["_turno"] = (
            df[col_times].fillna("Não informado")
            .apply(lambda x: x.split("//")[0].strip() if "//" in str(x) else str(x).strip())
            .replace({"": "Não informado", "nan": "Não informado"})
        )
    else:
        df["_turno"] = "Não informado"

    return df


def _total_ativos() -> int:
    """Conta colaboradores com Status = Ativo no Ativos.xlsx."""
    if not os.path.exists(ARQUIVO_ATIVOS):
        return 0
    df = pd.read_excel(ARQUIVO_ATIVOS, dtype=str)
    col_st = None
    if len(df.columns) > 17 and df.columns[17].strip().lower() == "status":
        col_st = df.columns[17]
    else:
        col_st = next((c for c in df.columns if c.strip().lower() == "status"), None)
    if col_st:
        return int((df[col_st].str.strip().str.lower() == "ativo").sum())
    return len(df)


def _filiais_missoes() -> dict:
    """Lê input/missoes_para_exportar.xlsx e retorna mission_id -> filial."""
    if not os.path.exists(ARQUIVO_MISSOES):
        return {}
    df = pd.read_excel(ARQUIVO_MISSOES, dtype=str)
    col_id = next((c for c in df.columns if str(c).strip().lower() == "mission_id"), None)
    col_filial = next((c for c in df.columns if str(c).strip().lower() == "filial"), None)
    if not col_id or not col_filial:
        return {}
    mapa = {}
    for _, row in df.iterrows():
        mid = str(row.get(col_id, "")).strip()
        filial = str(row.get(col_filial, "")).strip().upper()
        if mid and mid.lower() not in ("nan", ""):
            mapa[mid] = filial
    return mapa


def _dados_matriz_dashboard(biblio_gt: dict | None = None) -> dict:
    """Monta dados da aba Matriz a partir de input/matriz_treinamentos.xlsx."""
    if biblio_gt is None:
        biblio_gt = {}
    if not os.path.exists(ARQUIVO_MATRIZ):
        return {"treinamentos": [], "colaboradores": []}

    df = pd.read_excel(ARQUIVO_MATRIZ, sheet_name="Matriz", dtype=str).fillna("")
    cols = {str(c).strip().lower(): c for c in df.columns}
    col_mat = cols.get("matricula")
    col_nome = cols.get("nome")
    col_cargo = cols.get("cargo")
    col_turno = cols.get("turno")
    col_gestor = cols.get("gestor")
    col_setor = cols.get("filial colaborador")
    col_mid = cols.get("id da missao") or cols.get("mission_id")
    col_missao = cols.get("missao") or cols.get("nome_missao")
    col_filial_missao = cols.get("filial missao")
    col_status = cols.get("status matriz")
    if not col_mat or not col_nome or not col_mid or not col_status:
        return {"treinamentos": [], "colaboradores": []}

    def _limpo(valor):
        texto = "" if pd.isna(valor) else str(valor).strip()
        return "" if texto.lower() == "nan" else texto

    if col_filial_missao:
        df = df[df[col_filial_missao].fillna("").astype(str).str.strip().str.upper() == "JSL/GRU"].copy()

    treinos_df = df[[col_mid, col_missao, col_filial_missao]].drop_duplicates(subset=[col_mid]).copy()
    treinamentos = []
    for _, row in treinos_df.iterrows():
        mid = _limpo(row.get(col_mid, ""))
        if not mid:
            continue
        filial = _limpo(row.get(col_filial_missao, "")).upper()
        grupo = "simpar" if filial == "SIMPAR" else "jsl"
        nome = _limpo(row.get(col_missao, ""))
        treinamentos.append({
            "c": mid,
            "n": nome or mid,
            "g": grupo,
            "grupo": filial or "MATRIZ",
        })

    ordem_missoes = [t["c"] for t in treinamentos]
    colaboradores = []
    for i, (mat, grp) in enumerate(df.groupby(col_mat, sort=False), 1):
        mat = _limpo(mat)
        if not mat:
            continue
        first = grp.iloc[0]
        status_por_missao = {
            _limpo(row.get(col_mid, "")): (_limpo(row.get(col_status, "")) or "N/A").upper()
            for _, row in grp.iterrows()
        }
        turno_matriz = _limpo(first.get(col_turno, "")) if col_turno else ""
        turno_biblio = biblio_gt.get(mat, {}).get("turno", "")
        turno_final  = turno_biblio if turno_biblio else turno_matriz
        colaboradores.append({
            "n": i,
            "mat": mat,
            "nome": _limpo(first.get(col_nome, "")),
            "cargo": _limpo(first.get(col_cargo, "")) if col_cargo else "",
            "turno": turno_final,
            "sup": _limpo(first.get(col_gestor, "")) if col_gestor else "",
            "setor": _limpo(first.get(col_setor, "")) if col_setor else "",
            "sub": "",
            "st": [status_por_missao.get(mid, "N/A") for mid in ordem_missoes],
        })

    return {"treinamentos": treinamentos, "colaboradores": colaboradores}


def _status_matriz_para_relatorio(valor: str) -> str:
    status = _sem_acento(valor).strip().upper().replace(" ", "")
    if status in {"T", "A.T", "AT", "B.T", "BT"}:
        return "COMPLETED"
    if status == "A":
        return "IN_PROGRESS"
    return "NOT_STARTED"


def _visao_geral_por_matriz() -> dict | None:
    """Calcula a Visao Geral usando a matriz JSL/GRU como base."""
    matriz = _dados_matriz_dashboard()
    treinamentos = matriz.get("treinamentos", [])
    colaboradores = matriz.get("colaboradores", [])
    if not treinamentos or not colaboradores:
        return None

    registros = []
    status_por_colab = {}
    for colab in colaboradores:
        mat = str(colab.get("mat", "")).strip()
        if not mat:
            continue
        status_colab = []
        for treino, status_matriz in zip(treinamentos, colab.get("st", [])):
            status = _status_matriz_para_relatorio(status_matriz)
            if not status:
                continue
            status_colab.append(status)
            registros.append({
                "mat": mat,
                "status": status,
                "turno": str(colab.get("turno", "")),
                "setor": str(colab.get("setor", "")),
                "tipo": str(treino.get("n", "")),
                "missao": str(treino.get("n", "")),
                "filial": str(colab.get("setor", "")),
                "filial_missao": "JSL/GRU",
                "minutos": 0,
                "data_matricula": "",
                "data_conclusao": "",
            })
        status_por_colab[mat] = status_colab

    total_ativos = _total_ativos() or len(colaboradores)
    completos = 0
    em_andamento = 0
    nao_iniciado = 0
    for statuses in status_por_colab.values():
        if not statuses:
            continue
        if any(st == "IN_PROGRESS" for st in statuses):
            em_andamento += 1
        elif any(st == "NOT_STARTED" for st in statuses):
            nao_iniciado += 1
        else:
            completos += 1

    total_status = max(1, completos + em_andamento + nao_iniciado)
    status_labels = ["COMPLETED", "IN_PROGRESS", "NOT_STARTED"]
    _CONCLUIDO = {"COMPLETED", "COMPLETED_AFTER_DUE_DATE"}
    status_values = [
        sum(1 for r in registros if r["status"] in _CONCLUIDO),
        sum(1 for r in registros if r["status"] == "IN_PROGRESS"),
        sum(1 for r in registros if r["status"] == "NOT_STARTED"),
    ]

    def _pct(conc, tot):
        return round(conc / tot * 100, 1) if tot else 0

    turnos = {}
    for colab in colaboradores:
        turno = str(colab.get("turno", "")).strip() or "Nao informado"
        statuses = status_por_colab.get(str(colab.get("mat", "")).strip(), [])
        if not statuses:
            continue
        turnos.setdefault(turno, {"conc": 0, "tot": 0})
        turnos[turno]["tot"] += 1
        if all(st in {"COMPLETED", "COMPLETED_AFTER_DUE_DATE"} for st in statuses):
            turnos[turno]["conc"] += 1
    turnos_ord = sorted(turnos.items(), key=lambda item: _pct(item[1]["conc"], item[1]["tot"]), reverse=True)[:10]
    turnos_pct = {
        "labels": [k for k, _ in turnos_ord],
        "values": [_pct(v["conc"], v["tot"]) for _, v in turnos_ord],
    }

    missoes = []
    for idx, treino in enumerate(treinamentos):
        nome = str(treino.get("n", ""))
        sts = [_status_matriz_para_relatorio(c.get("st", [])[idx] if idx < len(c.get("st", [])) else "") for c in colaboradores]
        sts = [st for st in sts if st]
        conc = sum(1 for st in sts if st in {"COMPLETED", "COMPLETED_AFTER_DUE_DATE"})
        pend = sum(1 for st in sts if st not in {"COMPLETED", "COMPLETED_AFTER_DUE_DATE"})
        tot = len(sts)
        pct = _pct(conc, tot)
        cor = "#16a34a" if pct >= 80 else ("#ea580c" if pct >= 60 else "#dc2626")
        bg = "#f0fdf4" if pct >= 80 else ("#fff7ed" if pct >= 60 else "#fef2f2")
        missoes.append({"missao": nome, "total": tot, "concluidos": conc, "pendentes": pend, "pct": pct, "cor": cor, "bg": bg})
    missoes = sorted(missoes, key=lambda item: item["pct"], reverse=True)

    return {
        "total_ativos": total_ativos,
        "total": len(registros),
        "concluidos": completos,
        "em_andamento": em_andamento,
        "nao_iniciado": nao_iniciado,
        "nao_mat": nao_iniciado,
        "pendentes": sum(1 for r in registros if r["status"] not in {"COMPLETED", "COMPLETED_AFTER_DUE_DATE"}),
        "pct": round(completos / total_ativos * 100, 1) if total_ativos else 0,
        "status_labels": status_labels,
        "status_values": status_values,
        "turnos_pct": turnos_pct,
        "missoes": {
            "tabela": missoes,
            "ranking": [{"pos": i, "nome": r["missao"], "pct": r["pct"], "cor": r["cor"]} for i, r in enumerate(missoes, 1)],
            "bar_pendentes": {"labels": [r["missao"] for r in sorted(missoes, key=lambda x: x["pct"])], "values": [r["pendentes"] for r in sorted(missoes, key=lambda x: x["pct"])]},
            "donut_labels": ["Concluidos", "Em Andamento", "Nao Iniciados"],
            "donut_values": [completos, em_andamento, nao_iniciado],
            "maior_nome": missoes[0]["missao"] if missoes else "",
            "maior_pct": missoes[0]["pct"] if missoes else 0,
            "menor_nome": missoes[-1]["missao"] if missoes else "",
            "menor_pct": missoes[-1]["pct"] if missoes else 0,
            "media_pct": round(sum(r["pct"] for r in missoes) / len(missoes), 1) if missoes else 0,
            "total_missoes": len(missoes),
        },
        "registros": registros,
    }


def calcular_dados(df: pd.DataFrame) -> dict:
    # Coluna de username/matrícula para deduplicação
    col_user = next((c for c in df.columns if c.lower() in ("username", "matricula")), None)
    col_id_missao = next((c for c in df.columns if "id da missao" in c.lower() or "id da missão" in c.lower()), None)
    mapa_filiais_missoes = _filiais_missoes()
    if col_id_missao and mapa_filiais_missoes:
        df["_filial_missao"] = df[col_id_missao].fillna("").astype(str).str.strip().map(mapa_filiais_missoes).fillna("")
    else:
        df["_filial_missao"] = ""

    # ── KPIs principais ────────────────────────────────────────────────────────
    # Visão Geral: somente JSL/GRU quando disponível; fallback para tudo.
    df_jsl = df[df["_filial_missao"].str.upper() == "JSL/GRU"].copy()
    df_vg  = df_jsl if not df_jsl.empty else df

    # ── Enriquece turno e gestor via biblioteca_colaboradores.xlsx ────────────
    biblio_gt = _carregar_biblio_gestor_turno()
    if biblio_gt and col_user:
        col_gest_df = next((c for c in df_vg.columns if "lider" in c.lower() or "gestor" in c.lower()), None)
        col_turn_df = next((c for c in df_vg.columns if c.strip().lower() == "turno"), None)

        def _aplicar_biblio(row):
            mat  = str(row.get(col_user, "")).strip()
            info = biblio_gt.get(mat, {})
            if col_gest_df:
                # Gestor SEMPRE da biblioteca — zera quem não está lá
                # (evita que valores do Skore como "CREDENCIAMENTO" apareçam)
                row[col_gest_df] = info.get("gestor", "")
            if col_turn_df and info.get("turno"):
                row[col_turn_df] = info["turno"]
                row["_turno"]    = info["turno"]
            return row

        df_vg = df_vg.apply(_aplicar_biblio, axis=1)
        print(f"Biblioteca aplicada: {len(biblio_gt)} registros de gestor/turno.")

    # ── KPIs por USUÁRIO (não por linha de matrícula) ─────────────────────────
    col_min = next((c for c in df.columns if "carga" in c.lower()), None)
    minutos = int(pd.to_numeric(df_vg[col_min], errors="coerce").fillna(0).sum()) if col_min else 0

    if col_user:
        # Agrupa por username e consolida status de todas as missões daquele colaborador
        ug = df_vg.groupby(col_user).agg(
            _ok_all  = ("_ok",  "all"),   # concluiu TODAS as missões
            _and_any = ("_and", "any"),   # tem pelo menos 1 em andamento
            _ns_any  = ("_ns",  "any"),   # tem pelo menos 1 não iniciada
            _nao_any = ("_nao", "any"),   # tem pelo menos 1 não matriculada
            _can_any = ("_can", "any"),   # tem pelo menos 1 cancelada
        )
        # Categorias exclusivas (hierarquia: concluído > em andamento > não iniciado > outros)
        concluidos   = int(ug["_ok_all"].sum())
        em_and       = int((~ug["_ok_all"] &  ug["_and_any"]).sum())
        nao_iniciado = int((~ug["_ok_all"] & ~ug["_and_any"] &  ug["_ns_any"]).sum())
        nao_mat      = int((~ug["_ok_all"] & ~ug["_and_any"] & ~ug["_ns_any"] & ug["_nao_any"]).sum())
        cancelados   = int(ug["_can_any"].sum())
        total        = len(ug)          # pessoas únicas no escopo JSL/GRU
        pendentes    = total - concluidos
    else:
        # Fallback sem coluna de username (não deve ocorrer)
        total        = len(df_vg)
        concluidos   = int(df_vg["_ok"].sum())
        em_and       = int(df_vg["_and"].sum())
        nao_iniciado = int(df_vg["_ns"].sum())
        nao_mat      = int(df_vg["_nao"].sum())
        cancelados   = int(df_vg["_can"].sum())
        pendentes    = int(df_vg["_pend"].sum())

    # Total de colaboradores = usernames únicos em TODO o arquivo (Lista completa)
    total_ativos = int(df[col_user].nunique()) if col_user else total
    pct = round(concluidos / total_ativos * 100, 1) if total_ativos > 0 else 0

    # Distribuição de status por pessoa (categorias exclusivas, sem dupla contagem)
    status_labels = ["COMPLETED", "IN_PROGRESS", "NOT_STARTED", "NAO MATRICULADO"]
    status_values = [concluidos, em_and, nao_iniciado, nao_mat]
    # Remove categorias zeradas do gráfico
    pares = [(l, v) for l, v in zip(status_labels, status_values) if v > 0]
    if pares:
        status_labels, status_values = map(list, zip(*pares))
    else:
        status_labels, status_values = [], []

    # Coluna missão
    col_miss = next((c for c in df.columns if c.lower() in ("missao", "missão", "mission")), None)
    # Coluna filial
    col_fil  = next((c for c in df.columns if "filial" in c.lower()), None)
    # Coluna gestor/lider
    col_gest = next((c for c in df.columns if "lider" in c.lower() or "gestor" in c.lower()), None)
    # Coluna cargo
    col_carg = next((c for c in df.columns if "cargo" in c.lower()), None)
    # Coluna setor/departamento
    col_dept = next((c for c in df.columns if c.strip().lower() == "setor"), None)
    if not col_dept:
        col_dept = next((c for c in df.columns if "departamento" in c.lower()), None)
    # Coluna nome
    col_nome = next((c for c in df.columns if c.lower() == "nome"), None)
    # Coluna username/matrícula
    col_user = next((c for c in df.columns if c.lower() in ("username", "matricula")), None)

    # ── Por Turno (% conclusão) ──────────────────────────────────────────────
    grp_tp = df_vg.groupby("_turno").agg(conc=("_ok","sum"), tot=("_status","count"))
    grp_tp["pct"] = (grp_tp["conc"] / grp_tp["tot"] * 100).round(1)
    grp_tp = grp_tp.sort_values("pct", ascending=False).head(10)
    turnos_pct = {
        "labels": [str(l) for l in grp_tp.index],
        "values": [float(v) for v in grp_tp["pct"]],
    }

    # ── Por Filial ───────────────────────────────────────────────────────────
    filiais_data = {}
    if col_fil:
        grp = df_vg.groupby(col_fil).agg(conc=("_ok","sum"), tot=("_status","count"))
        grp["pend"] = grp["tot"] - grp["conc"]
        grp = grp.sort_values("tot", ascending=False).head(20)
        filiais_data = {
            "labels":     [str(l) for l in grp.index],
            "concluidos": [int(v) for v in grp["conc"]],
            "pendentes":  [int(v) for v in grp["pend"]],
        }

    # ── Por Gestor (colaboradores únicos com pendência, top 20) ─────────────
    gestores_data = {"labels": [], "values": []}
    if col_gest and col_user:
        grp = df_vg[df_vg["_pend"]].groupby(col_gest)[col_user].nunique()
        lb, vl = top_n(grp, 20)
        gestores_data = {"labels": lb, "values": vl}

    # ── Por Turno (pendentes, top 20) ────────────────────────────────────────
    grp_tp2 = df_vg[df_vg["_pend"]].groupby("_turno").size()
    lb_t, vl_t = top_n(grp_tp2, 20)
    turnos_pend = {"labels": lb_t, "values": vl_t}

    # ── Por Missão ───────────────────────────────────────────────────────────
    missoes_data = {}
    if col_miss:
        grp = df_vg.groupby(col_miss).agg(conc=("_ok","sum"), tot=("_status","count")).reset_index()
        grp["pend"] = grp["tot"] - grp["conc"]
        grp["pct"]  = (grp["conc"] / grp["tot"] * 100).round(1)
        grp = grp.sort_values("pct", ascending=False)

        ranking = []
        for i, row in enumerate(grp.itertuples(), 1):
            pct_m = float(row.pct)
            cor = "#16a34a" if pct_m >= 80 else ("#ea580c" if pct_m >= 60 else "#dc2626")
            ranking.append({"pos": i, "nome": str(row[1]), "pct": pct_m, "cor": cor})

        tabela = []
        for row in grp.itertuples():
            pct_m = float(row.pct)
            bg  = "#f0fdf4" if pct_m >= 80 else ("#fff7ed" if pct_m >= 60 else "#fef2f2")
            cor = "#16a34a" if pct_m >= 80 else ("#ea580c" if pct_m >= 60 else "#dc2626")
            tabela.append({"missao": str(row[1]), "total": int(row.tot),
                           "concluidos": int(row.conc), "pendentes": int(row.pend),
                           "pct": pct_m, "bg": bg, "cor": cor})

        grp_asc = grp.sort_values("pct")
        bar_pend = {
            "labels": [str(n) for n in grp_asc[col_miss].tolist()],
            "values": [int(v) for v in grp_asc["pend"].tolist()],
        }

        maior = grp.iloc[0] if not grp.empty else None
        menor = grp.iloc[-1] if not grp.empty else None
        media_m = round(float(grp["pct"].mean()), 1) if not grp.empty else 0

        missoes_data = {
            "ranking":       ranking,
            "tabela":        tabela,
            "bar_pendentes": bar_pend,
            "donut_labels":  ["Concluídos", "Em Andamento", "Não Matriculados"],
            "donut_values":  [concluidos, em_and, nao_mat],
            "maior_nome":    str(maior[col_miss]) if maior is not None else "",
            "maior_pct":     float(maior["pct"]) if maior is not None else 0,
            "menor_nome":    str(menor[col_miss]) if menor is not None else "",
            "menor_pct":     float(menor["pct"]) if menor is not None else 0,
            "media_pct":     media_m,
            "total_missoes": int(len(grp)),
        }

    # ── Colaboradores pendentes (p5 + clique no ranking p4/p7) ──────────────
    df_pend = df_vg[df_vg["_pend"]]  # sem limite: necessário para filtro por missão
    colaboradores_pend = []
    for _, row in df_pend.iterrows():
        colaboradores_pend.append({
            "nome":   str(row.get(col_nome, "")) if col_nome else "",
            "mat":    str(row.get(col_user, "")) if col_user else "",
            "cargo":  str(row.get(col_carg, "")) if col_carg else "",
            "depto":  str(row.get(col_dept, "")) if col_dept else "",
            "filial": str(row.get(col_fil,  "")) if col_fil  else "",
            "turno":  str(row.get("_turno", "")),
            "gestor": str(row.get(col_gest, "")) if col_gest else "",
            "missao": str(row.get(col_miss, "")) if col_miss else "",
            "status": str(row.get("_status", "")),
            "prog":   str(row.get(col_prog if (col_prog := next((c for c in df.columns if "progresso" in c.lower()), None)) else "_prog", "")),
        })

    # Donut por departamento (pendentes)
    setor_donut = {"labels": [], "values": []}
    if col_dept:
        grp_s = df_vg[df_vg["_pend"]].groupby(col_dept).size().sort_values(ascending=False).head(8)
        setor_donut = {"labels": [str(l) for l in grp_s.index], "values": [int(v) for v in grp_s.values]}

    # Top 5 por cargo (pendentes)
    cargo_bar = {"labels": [], "values": []}
    if col_carg:
        grp_c = df_vg[df_vg["_pend"]].groupby(col_carg).size().sort_values(ascending=False).head(5)
        cargo_bar = {"labels": [str(l) for l in grp_c.index], "values": [int(v) for v in grp_c.values]}

    # Linhas compactas para filtros interativos no dashboard HTML.
    col_status = next((c for c in df.columns if "status" in c.lower() and "matricula" in c.lower()), None)
    col_dt_mat = next((c for c in df.columns if "data da matricula" in c.lower()), None)
    col_dt_conc = next((c for c in df.columns if "conclusao" in c.lower() and "matricula" in c.lower()), None)
    def _num(row, col):
        if not col:
            return 0
        valor = pd.to_numeric(row.get(col, 0), errors="coerce")
        return 0 if pd.isna(valor) else float(valor)

    registros = []
    for _, row in df_vg.iterrows():
        registros.append({
            "mat": str(row.get(col_user, "")) if col_user else "",
            "status": str(row.get(col_status, row.get("_status", ""))) if col_status else str(row.get("_status", "")),
            "turno": str(row.get("_turno", "")),
            "setor": str(row.get(col_dept, "")) if col_dept else "",
            "tipo": str(row.get(col_miss, "")) if col_miss else "",
            "missao": str(row.get(col_miss, "")) if col_miss else "",
            "filial": str(row.get(col_fil, "")) if col_fil else "",
            "filial_missao": str(row.get("_filial_missao", "")),
            "minutos": _num(row, col_min),
            "data_matricula": str(row.get(col_dt_mat, "")) if col_dt_mat else "",
            "data_conclusao": str(row.get(col_dt_conc, "")) if col_dt_conc else "",
        })

    def _criar_missoes_data(df_base: pd.DataFrame) -> dict:
        if not col_miss or df_base.empty:
            return {
                "ranking": [], "tabela": [], "bar_pendentes": {"labels": [], "values": []},
                "donut_labels": ["Concluídos", "Em Andamento", "Não Iniciados"],
                "donut_values": [0, 0, 0],
                "maior_nome": "", "maior_pct": 0, "menor_nome": "", "menor_pct": 0,
                "media_pct": 0, "total_missoes": 0,
                "total": 0, "concluidos": 0, "em_andamento": 0, "nao_iniciado": 0, "pct": 0,
            }

        grp = df_base.groupby(col_miss).agg(conc=("_ok", "sum"), tot=("_status", "count")).reset_index()
        grp["pend"] = grp["tot"] - grp["conc"]
        grp["pct"] = (grp["conc"] / grp["tot"] * 100).round(1)
        grp = grp.sort_values("pct", ascending=False)

        ranking = []
        tabela = []
        for i, row in enumerate(grp.itertuples(), 1):
            pct_m = float(row.pct)
            cor = "#16a34a" if pct_m >= 80 else ("#ea580c" if pct_m >= 60 else "#dc2626")
            ranking.append({"pos": i, "nome": str(row[1]), "pct": pct_m, "cor": cor})
            bg = "#f0fdf4" if pct_m >= 80 else ("#fff7ed" if pct_m >= 60 else "#fef2f2")
            tabela.append({
                "missao": str(row[1]), "total": int(row.tot),
                "concluidos": int(row.conc), "pendentes": int(row.pend),
                "pct": pct_m, "bg": bg, "cor": cor,
            })

        grp_asc = grp.sort_values("pct")
        maior = grp.iloc[0] if not grp.empty else None
        menor = grp.iloc[-1] if not grp.empty else None
        total_base = len(df_base)
        concluidos_base = int(df_base["_ok"].sum())
        andamento_base = int(df_base["_and"].sum())
        nao_iniciado_base = int(df_base["_ns"].sum() + df_base["_nao"].sum())

        return {
            "ranking": ranking,
            "tabela": tabela,
            "bar_pendentes": {
                "labels": [str(n) for n in grp_asc[col_miss].tolist()],
                "values": [int(v) for v in grp_asc["pend"].tolist()],
            },
            "donut_labels": ["Concluídos", "Em Andamento", "Não Iniciados"],
            "donut_values": [concluidos_base, andamento_base, nao_iniciado_base],
            "maior_nome": str(maior[col_miss]) if maior is not None else "",
            "maior_pct": float(maior["pct"]) if maior is not None else 0,
            "menor_nome": str(menor[col_miss]) if menor is not None else "",
            "menor_pct": float(menor["pct"]) if menor is not None else 0,
            "media_pct": round(float(grp["pct"].mean()), 1) if not grp.empty else 0,
            "total_missoes": int(len(grp)),
            "total": int(total_base),
            "concluidos": int(concluidos_base),
            "em_andamento": int(andamento_base),
            "nao_iniciado": int(nao_iniciado_base),
            "pct": round(concluidos_base / total_base * 100, 1) if total_base else 0,
        }

    missoes_jsl = _criar_missoes_data(df[df["_filial_missao"].str.upper() == "JSL/GRU"].copy())
    missoes_simpar = _criar_missoes_data(df[df["_filial_missao"].str.upper() == "SIMPAR"].copy())

    # Mantém a aba Matriz intacta, mas NÃO sobrescreve a Visão Geral com dados
    # sintéticos do produto cartesiano. Os KPIs vêm do arquivo real (df_vg).
    matriz_dashboard = _dados_matriz_dashboard(biblio_gt)

    dados = {
        "updated_at":     datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_ativos":   total_ativos,
        "total":          total,
        "concluidos":     concluidos,
        "em_andamento":   em_and,
        "nao_iniciado":   nao_iniciado,
        "nao_mat":        nao_mat,
        "cancelados":     cancelados,
        "pendentes":      pendentes,
        "pct":            pct,
        "minutos":        minutos,
        "status_labels": status_labels,
        "status_values": status_values,
        "filiais":       filiais_data,
        "turnos_pct":    turnos_pct,
        "gestores":      gestores_data,
        "turnos_pend":   turnos_pend,
        "missoes":       missoes_data,
        "missoes_jsl":   missoes_jsl,
        "missoes_simpar": missoes_simpar,
        "colaboradores_pendentes": colaboradores_pend,
        "setor_donut":   setor_donut,
        "cargo_bar":     cargo_bar,
        "registros":     registros,
        "matriz":        matriz_dashboard,
    }
    return dados


def main():
    print("=" * 60)
    print(f"Gerando dados.js — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    df = carregar_df()
    print(f"Linhas carregadas: {len(df)}")

    dados = calcular_dados(df)

    js = f"""// =============================================================
// dados.js — Gerado por gerar_dados_dash.py
// Atualizado em: {dados['updated_at']}
// NÃO EDITE — execute: python gerar_dados_dash.py
// =============================================================

const DADOS = {json.dumps(dados, ensure_ascii=False, indent=2, default=str)};
"""

    with open(ARQUIVO_JS, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"Salvo: {ARQUIVO_JS}")

    print(f"\nResumo:")
    print(f"  Colaboradores únicos: {dados['total_ativos']:,}")
    print(f"  Total de matrículas:  {dados['total']:,}")
    print(f"  Concluídos:           {dados['concluidos']:,} ({dados['pct']}%)")
    print(f"  Em andamento: {dados['em_andamento']:,}")
    print(f"  Não mat.:     {dados['nao_mat']:,}")
    print(f"  Cancelados:   {dados['cancelados']:,}")
    print(f"  Pendentes:    {dados['pendentes']:,}")
    if dados["missoes"]:
        print(f"  Missões:      {dados['missoes']['total_missoes']}")
    print("\ndados.js gerado! Abra o dashboard_simpar.html no navegador.")


if __name__ == "__main__":
    main()
