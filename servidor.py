# =============================================================================
# servidor.py — Servidor do Dashboard Universidade SIMPAR
# =============================================================================
# Uso local:
#   python servidor.py
#
# Servidor Windows (24/7):
#   Configurar no Task Scheduler para rodar no boot
#   Acesso pela rede: http://<IP-do-servidor>:8050
# =============================================================================

import os
import sys
import socket
import subprocess
import threading
import logging
import time
from flask import Flask, send_file, jsonify, Response, stream_with_context, request, make_response
from matriz_api import atualizar_status_matriz

# Suprime logs do Flask (mantém só erros)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

BASE  = os.path.dirname(os.path.abspath(__file__))
PORTA = 8050

app = Flask(__name__, static_folder=BASE)

# Estado do processo em execução
_estado = {"rodando": False, "log": [], "erro": None}

NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma":        "no-cache",
    "Expires":       "0",
}


# =============================================================================
# UTILITÁRIOS
# =============================================================================

def _ip_local():
    """Retorna o IP da máquina na rede local."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# =============================================================================
# ROTAS — ARQUIVOS ESTÁTICOS
# =============================================================================

@app.route("/")
def index():
    caminho = os.path.join(BASE, "dashboard_simpar.html")
    with open(caminho, encoding="utf-8") as f:
        html = f.read()
    # Injeta timestamp para forçar reload do dados.js
    ts = str(int(time.time()))
    html = html.replace('src="dados.js"', f'src="dados.js?v={ts}"')
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers.update(NO_CACHE)
    return resp


@app.route("/dados.js")
def dados_js():
    caminho = os.path.join(BASE, "dados.js")
    if not os.path.exists(caminho):
        return "const DADOS = null;", 200, {"Content-Type": "application/javascript", **NO_CACHE}
    resp = send_file(caminho, mimetype="application/javascript", conditional=False)
    resp.headers.update(NO_CACHE)
    return resp


# =============================================================================
# ROTA — STATUS DO SERVIDOR
# =============================================================================

@app.route("/status")
def status():
    return jsonify({
        "rodando": _estado["rodando"],
        "log":     _estado["log"],
        "erro":    _estado["erro"],
    })


# =============================================================================
# ROTA — ATUALIZAR MATRIZ (edição de status via dashboard)
# =============================================================================

@app.route("/matriz/update", methods=["POST"])
def matriz_update():
    try:
        dados = request.get_json(force=True) or {}
        resultado = atualizar_status_matriz(
            dados.get("matricula"),
            dados.get("mission_id"),
            dados.get("status"),
        )
        # Regenera dados.js após atualização
        subprocess.run(
            [sys.executable, os.path.join(BASE, "gerar_dados_dash.py")],
            cwd=BASE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return jsonify({"ok": True, "resultado": resultado})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 400


# =============================================================================
# ROTA — DISPARAR PIPELINE (botão Recarregar do dashboard)
# =============================================================================

@app.route("/atualizar", methods=["POST"])
def atualizar():
    if _estado["rodando"]:
        return jsonify({"ok": False, "msg": "Atualização já em andamento."}), 409

    _estado["rodando"] = True
    _estado["log"]     = []
    _estado["erro"]    = None

    def _rodar():
        def _executar(script):
            _estado["log"].append(f"▶ {script}")
            proc = subprocess.Popen(
                [sys.executable, "-u", os.path.join(BASE, script)],
                cwd=BASE,
                env=os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for linha in proc.stdout:
                _estado["log"].append(linha.rstrip())
            proc.wait()
            return proc.returncode

        try:
            # Passo 1: extrai dados da Skore
            if _executar("skore_not_started_20.py") != 0:
                _estado["erro"] = "Erro ao extrair dados da Skore. Veja o log."
                return
            # Passo 2: gera dados.js para o dashboard
            if _executar("gerar_dados_dash.py") != 0:
                _estado["erro"] = "Erro ao gerar dados.js. Veja o log."
                return
            _estado["log"].append("✅ Concluído!")
        except Exception as e:
            _estado["erro"] = str(e)
        finally:
            _estado["rodando"] = False

    threading.Thread(target=_rodar, daemon=True).start()
    return jsonify({"ok": True, "msg": "Atualização iniciada."})


# =============================================================================
# ROTA — LOG EM TEMPO REAL (SSE)
# =============================================================================

@app.route("/log")
def log_stream():
    def _gerar():
        ultimo = 0
        while True:
            linhas = _estado["log"]
            if len(linhas) > ultimo:
                for linha in linhas[ultimo:]:
                    yield f"data: {linha}\n\n"
                ultimo = len(linhas)
            if not _estado["rodando"] and ultimo >= len(_estado["log"]):
                yield "data: __DONE__\n\n"
                break
            time.sleep(0.3)

    return Response(
        stream_with_context(_gerar()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# =============================================================================
# INICIALIZAÇÃO
# =============================================================================

if __name__ == "__main__":
    ip = _ip_local()

    print("=" * 55)
    print("  Dashboard Universidade SIMPAR")
    print(f"  Local:  http://localhost:{PORTA}")
    print(f"  Rede:   http://{ip}:{PORTA}")
    print("  Ctrl+C para encerrar")
    print("=" * 55)

    app.run(host="0.0.0.0", port=PORTA, debug=False, threaded=True)
