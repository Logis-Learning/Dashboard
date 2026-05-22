"""
Skore — Emissor de Certificados em Lote
Recebe uma lista de IDs via JSON, abre cada certificado no Skore
e clica em Baixar. Salva os PDFs em output_certificados/.

Uso direto:
    python emitir_certificados.py ids.json

Uso via servidor (stdin JSON):
    echo '[{"id":"14092_abc_123","nome":"João","missao":"Conformidade"}]' | python emitir_certificados.py -
"""

import json, sys, os, time, re
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────
SKORE_URL = "https://universidadesimpar.skore.io"
CERT_URL  = f"{SKORE_URL}/plugins/certificates?page=preview&id={{id}}"

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
OUT_DIR   = os.path.join(BASE_DIR, "output_certificados")

try:
    sys.path.insert(0, BASE_DIR)
    import config as cfg
    EMAIL = cfg.SKORE_EMAIL
    SENHA = cfg.SKORE_SENHA
except Exception:
    EMAIL = "felipe.pianelli@jsl.com.br"
    SENHA = "199003Fg?"
# ─────────────────────────────────────────────────────────────

def _emit(msg: dict):
    """Imprime linha JSON de progresso — o servidor lê via stdout."""
    print(json.dumps(msg, ensure_ascii=False), flush=True)

def _nome_arquivo(nome: str, missao: str, id_cert: str) -> str:
    def _limpar(s):
        s = re.sub(r"[\\/:*?\"<>|]", "", str(s))
        return s.strip()[:60]
    return f"{_limpar(nome)} — {_limpar(missao)}.pdf"

def emitir(lista: list[dict]):
    """
    lista: [{id, nome, missao, mat?}, ...]
    Emite cada certificado e salva o PDF em output_certificados/
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    total = len(lista)

    if total == 0:
        _emit({"tipo": "erro", "msg": "Lista vazia"})
        return

    _emit({"tipo": "inicio", "total": total})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        # ── Login ────────────────────────────────────────────
        _emit({"tipo": "status", "msg": "Fazendo login no Skore..."})
        page.goto(f"{SKORE_URL}/login", wait_until="networkidle")
        page.fill("#username", EMAIL)
        page.fill("#password", SENHA)
        page.wait_for_timeout(2000)
        page.wait_for_selector("#login-button:not([disabled])", timeout=10000)
        page.click("#login-button")
        page.wait_for_timeout(3000)

        if "/login" in page.url:
            _emit({"tipo": "erro", "msg": "Falha no login — verifique config.py"})
            browser.close()
            return

        _emit({"tipo": "status", "msg": "Login OK. Iniciando emissão..."})

        erros = []

        for i, item in enumerate(lista, 1):
            id_cert = str(item.get("id", "")).strip()
            nome    = str(item.get("nome", "Colaborador")).strip()
            missao  = str(item.get("missao", "Missao")).strip()
            mat     = str(item.get("mat", "")).strip()

            if not id_cert:
                _emit({"tipo": "item", "idx": i, "total": total,
                       "nome": nome, "status": "erro", "msg": "ID vazio"})
                erros.append(nome)
                continue

            _emit({"tipo": "item", "idx": i, "total": total,
                   "nome": nome, "missao": missao, "status": "processando"})

            try:
                url_cert = CERT_URL.format(id=id_cert)

                # Abre página do certificado
                page.goto(url_cert, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Pasta de destino: output_certificados/<missao_limpa>/
                pasta_missao = os.path.join(OUT_DIR,
                    re.sub(r"[\\/:*?\"<>|]", "", missao)[:50].strip())
                os.makedirs(pasta_missao, exist_ok=True)

                arquivo = os.path.join(pasta_missao, _nome_arquivo(nome, missao, id_cert))

                # Clica em Baixar e aguarda download
                with page.expect_download(timeout=30000) as dl_info:
                    # Tenta pelo texto "Baixar" primeiro
                    btn = page.locator("text=Baixar").first
                    if btn.count() == 0:
                        # Fallback: qualquer botão com ícone de download
                        btn = page.locator("button:has-text('Baix'), a:has-text('Baix')").first
                    btn.click()

                download = dl_info.value
                download.save_as(arquivo)

                _emit({"tipo": "item", "idx": i, "total": total,
                       "nome": nome, "missao": missao, "status": "ok",
                       "arquivo": arquivo})

            except Exception as e:
                msg_erro = str(e)[:120]
                _emit({"tipo": "item", "idx": i, "total": total,
                       "nome": nome, "missao": missao,
                       "status": "erro", "msg": msg_erro})
                erros.append(nome)
                # Pequena pausa antes de continuar
                time.sleep(1)

        browser.close()

    ok_count = total - len(erros)
    _emit({
        "tipo":   "fim",
        "total":  total,
        "ok":     ok_count,
        "erros":  len(erros),
        "pasta":  OUT_DIR,
    })


# ── Entrada ───────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python emitir_certificados.py <arquivo.json>")
        print("  ou: echo '[...]' | python emitir_certificados.py -")
        sys.exit(1)

    arg = sys.argv[1]
    if arg == "-":
        dados = json.load(sys.stdin)
    else:
        if not os.path.exists(arg):
            print(f"Arquivo não encontrado: {arg}")
            sys.exit(1)
        with open(arg, encoding="utf-8") as f:
            dados = json.load(f)

    emitir(dados)
