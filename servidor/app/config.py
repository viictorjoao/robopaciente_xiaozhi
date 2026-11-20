"""Configuração lida do arquivo .env (na pasta servidor/)."""
import os
from pathlib import Path

# Usa os certificados do próprio Windows/macOS (resolve "CERTIFICATE_VERIFY_FAILED"
# em redes de universidade/empresa ou com antivírus que inspecionam HTTPS).
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

BASE = Path(__file__).resolve().parent.parent
ENV_FILE = BASE / ".env"


def _carregar_env():
    if not ENV_FILE.exists():
        return
    for linha in ENV_FILE.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        k, v = linha.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_carregar_env()


def env(nome, padrao=""):
    return os.environ.get(nome, padrao)


PORTA = int(env("PORTA", "8000"))
SENHA_PROFESSOR = env("SENHA_PROFESSOR", "psicologia")
SEGREDO = env("SEGREDO", "troque-este-segredo")

# LLM (qualquer API compatível com OpenAI: Groq, OpenAI, Gemini, Ollama, LM Studio...)
LLM_BASE_URL = env("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
LLM_API_KEY = env("LLM_API_KEY")
LLM_MODELO = env("LLM_MODELO", "llama-3.3-70b-versatile")
LLM_TEMPERATURA = float(env("LLM_TEMPERATURA", "0.8"))

# Reconhecimento de fala (Whisper via API compatível com OpenAI)
STT_BASE_URL = (env("STT_BASE_URL") or LLM_BASE_URL).rstrip("/")
STT_API_KEY = env("STT_API_KEY") or LLM_API_KEY
STT_MODELO = env("STT_MODELO", "whisper-large-v3-turbo")

# Síntese de voz: "edge" (gratuito, vozes Microsoft pt-BR) ou "openai"
TTS_PROVEDOR = env("TTS_PROVEDOR", "edge")
TTS_VOZ_PADRAO = env("TTS_VOZ_PADRAO", "pt-BR-FranciscaNeural")
TTS_OPENAI_BASE_URL = env("TTS_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
TTS_OPENAI_API_KEY = env("TTS_OPENAI_API_KEY")
TTS_OPENAI_MODELO = env("TTS_OPENAI_MODELO", "gpt-4o-mini-tts")

# Robô
TOKEN_DISPOSITIVO = env("TOKEN_DISPOSITIVO")  # vazio = não exige token
SILENCIO_FIM_FALA_MS = int(env("SILENCIO_FIM_FALA_MS", "900"))
SESSAO_AVULSA_EXPIRA_MIN = int(env("SESSAO_AVULSA_EXPIRA_MIN", "20"))

# Aluno vê nota/feedback logo após enviar o laudo?
MOSTRAR_RESULTADO_ALUNO = env("MOSTRAR_RESULTADO_ALUNO", "1") == "1"

DB_PATH = BASE / env("BANCO", "dados/robo_paciente.db")
