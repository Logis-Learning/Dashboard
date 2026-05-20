# =============================================================================
# config.exemplo.py — Renomeie para config.py e preencha com suas credenciais
# =============================================================================

API_TOKEN    = "seu_token_aqui"
SKORE_EMAIL  = "seu_email@empresa.com"
SKORE_SENHA  = "sua_senha_aqui"

BASE_URL_MISSION  = "https://mission.learningrocks.io"
BASE_URL_USERS    = "https://knowledge.skore.io/workspace"
BASE_URL_TEAMS    = "https://user.skore.ai/v1"
BASE_URL_CONTENT  = "https://consume.learningrocks.io"
CONTENT_TIMEOUT   = 90

HEADERS = {
    "Content-Type":  "application/json",
    "Authorization": f"Bearer {API_TOKEN}",
}
HEADERS_KNOWLEDGE = {
    "Content-Type":  "application/json",
    "Authorization": API_TOKEN,
}

OUTPUT_FOLDER = "output_powerbi"
PAGE_LIMIT    = 100
