"""
Skore — Extrator de Certificados
Navega em /reports/1206, intercepta a chamada Looker e extrai
ID do Certificado + dados do usuário/missão.

Saída: output_powerbi/certificados.xlsx
"""

import json, sys, os, re
from datetime import datetime
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────
SKORE_URL  = "https://universidadesimpar.skore.io"
LOOKER_URL = "https://skoreio.sa.looker.com"

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output_powerbi")
SAIDA      = os.path.join(OUTPUT_DIR, "certificados.xlsx")

# Credenciais via config.py
try:
    sys.path.insert(0, BASE_DIR)
    import config as cfg
    EMAIL = cfg.SKORE_EMAIL
    SENHA = cfg.SKORE_SENHA
except Exception:
    EMAIL = "felipe.pianelli@jsl.com.br"
    SENHA = "199003Fg?"

LOTE_SIZE = 200
# ─────────────────────────────────────────────────────────────

os.makedirs(OUTPUT_DIR, exist_ok=True)

def progresso(passo, total, label, largura=40):
    p = int(largura * passo / total)
    bar = "█" * p + "░" * (largura - p)
    sys.stdout.write(f"\r  [{bar}] {int(100*passo/total):3d}%  {label}")
    sys.stdout.flush()
    if passo == total:
        print()

print("\n🎓 Skore — Extrator de Certificados")
print("=" * 50)

captured = {"url": None, "fields": None, "explore": None}

all_rows = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page    = context.new_page()

    # ── Login ────────────────────────────────────────────────
    print("  [1/4] Fazendo login...")
    page.goto(f"{SKORE_URL}/login", wait_until="networkidle")
    page.fill("#username", EMAIL)
    page.fill("#password", SENHA)
    page.wait_for_timeout(2000)
    page.wait_for_selector("#login-button:not([disabled])", timeout=10000)
    page.click("#login-button")
    page.wait_for_timeout(3000)

    if "/login" in page.url:
        print("\n❌ Falha no login — verifique email e senha em config.py")
        browser.close()
        sys.exit(1)

    # ── Captura a chamada Looker do reports/1206 ─────────────
    print("  [2/4] Carregando relatório de certificados...")

    def on_request(request):
        url = request.url
        if LOOKER_URL in url and "/explore/" in url and ".json" in url:
            if not captured["url"]:
                captured["url"] = url
                # extrai explore path e fields
                m = re.search(r"/explore/([^?]+)", url)
                if m:
                    captured["explore"] = m.group(1)
                fq = re.search(r"fields=([^&]+)", url)
                if fq:
                    captured["fields"] = fq.group(1)

    page.on("request", on_request)

    # Navega para o relatório de certificados
    page.goto(f"{SKORE_URL}/reports/1206", wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(12000)

    if not captured["url"]:
        # Tenta rolar para forçar o carregamento dos dados
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(5000)

    # ── Monta URL para busca em lote ─────────────────────────
    print("  [3/4] Extraindo dados...")

    # Sempre usa mission_definitions (explore confiável) com certificates.id
    # Filtra só quem tem certificado emitido (completed)
    print("  Usando explore mission_definitions com certificates.id...")
    fields = ",".join([
        "users.id", "users.name", "users.email", "users.username",
        "metadata.cpf", "metadata.cargo", "metadata.filial",
        "metadata.departamento", "leaders.name_list",
        "mission_definitions.name",
        "mission_definitions.workload_minutes",
        "certificates.created_date",
        "certificates.id",
        "enrollments.detailed_status",
    ])
    base_url = (
        f"{LOOKER_URL}/explore/skore/mission_definitions.json"
        f"?fields={fields}"
        f"&f[users.isDeleted]=No"
        f"&f[users.active]=Yes"
        f"&f[enrollments.detailed_status]=COMPLETED,COMPLETED_AFTER_DUE_DATE"
        f"&f[certificates.id]=-NULL"
        f"&limit=5000&sorts=users.name"
    )

    # Garante sessão Looker ativa
    page.goto(f"{LOOKER_URL}/embed/dashboards/2122",
              wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    # Faz a requisição via fetch com credenciais da sessão
    def fetch_looker(url):
        return page.evaluate("""
            async (url) => {
                const r = await fetch(url, {
                    credentials: "include",
                    headers: {
                        "Accept": "application/json",
                        "x-csrf-token": document.cookie.match(/CSRF-TOKEN=([^;]+)/)?.[1] || ""
                    }
                });
                return await r.text();
            }
        """, url)

    texto = fetch_looker(base_url)

    if not texto or texto.strip() in ("[]", ""):
        print("  ⚠ Resultado vazio — verifique credenciais em config.py")

    browser.close()

try:
    dados = json.loads(texto)
except Exception as e:
    print(f"\n❌ Erro ao parsear resposta: {e}")
    print(f"   Primeiros 200 chars: {texto[:200]}")
    sys.exit(1)

if not dados:
    print("\n❌ Nenhum certificado retornado")
    sys.exit(1)

print(f"  ✓ {len(dados)} certificados encontrados")

# ── Processar e salvar ────────────────────────────────────────
print("  [4/4] Salvando certificados.xlsx...")

import pandas as pd

# Detecta campos automaticamente
sample = dados[0]
keys   = list(sample.keys())
print(f"  Campos disponíveis: {', '.join(keys[:10])}...")

# Mapeamento flexível — tenta vários nomes possíveis
def _campo(row, *candidatos, default=""):
    for c in candidatos:
        if c in row and row[c] is not None:
            return str(row[c]).strip()
    return default

rows_out = []
for row in dados:
    id_cert = _campo(row, "certificates.id")
    if not id_cert:
        continue  # pula quem não tem certificado
    rows_out.append({
        "ID do Usuário":       _campo(row, "users.id"),
        "Nome":                _campo(row, "users.name"),
        "Email":               _campo(row, "users.email"),
        "CPF":                 _campo(row, "metadata.cpf"),
        "Cargo":               _campo(row, "metadata.cargo"),
        "Filial":              _campo(row, "metadata.filial"),
        "Departamento":        _campo(row, "metadata.departamento"),
        "Gestor":              _campo(row, "leaders.name_list"),
        "Missao":              _campo(row, "mission_definitions.name"),
        "Carga Horaria (min)": _campo(row, "mission_definitions.workload_minutes"),
        "Status":              _campo(row, "enrollments.detailed_status"),
        "Data Emissao":        _campo(row, "certificates.created_date"),
        "ID do Certificado":   id_cert,
    })

df = pd.DataFrame(rows_out)

# Filtra linhas sem ID de certificado
sem_id = df[df["ID do Certificado"] == ""]
com_id = df[df["ID do Certificado"] != ""]
print(f"  ✓ {len(com_id)} com ID de certificado | {len(sem_id)} sem ID")

df.to_excel(SAIDA, index=False)

print(f"\n{'='*50}")
print(f"✅ {len(df)} certificados salvos em:")
print(f"   {SAIDA}")
print(f"\nPróximo passo: python emitir_certificados.py")
