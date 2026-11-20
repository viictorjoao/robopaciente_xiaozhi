"""Provedores de IA: reconhecimento de fala (STT), modelo de linguagem (LLM) e voz (TTS)."""
import json
import logging
import re

import httpx

from . import config

log = logging.getLogger("ia")


def _ssl():
    try:
        import ssl
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return True


_cliente = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0), verify=_ssl())


class ErroIA(Exception):
    pass


def _hdr(chave):
    return {"Authorization": f"Bearer {chave}"} if chave else {}


# ---------------- STT ----------------

async def transcrever(wav: bytes) -> str:
    if not config.STT_API_KEY and "localhost" not in config.STT_BASE_URL:
        raise ErroIA("STT_API_KEY não configurada no .env")
    r = await _cliente.post(
        f"{config.STT_BASE_URL}/audio/transcriptions",
        headers=_hdr(config.STT_API_KEY),
        files={"file": ("fala.wav", wav, "audio/wav")},
        data={"model": config.STT_MODELO, "language": "pt", "response_format": "json",
              "temperature": "0"},
    )
    if r.status_code != 200:
        raise ErroIA(f"STT {r.status_code}: {r.text[:300]}")
    texto = (r.json().get("text") or "").strip()
    # Whisper às vezes "alucina" frases em silêncio
    lixo = {"obrigado.", "obrigada.", "legendas pela comunidade amara.org", "tchau.", "..."}
    if texto.lower() in lixo or len(re.sub(r"\W", "", texto)) < 2:
        return ""
    return texto


# ---------------- LLM ----------------

async def conversar(mensagens, temperatura=None, json_mode=False, max_tokens=300) -> str:
    if not config.LLM_API_KEY and "localhost" not in config.LLM_BASE_URL and "127.0.0.1" not in config.LLM_BASE_URL:
        raise ErroIA("LLM_API_KEY não configurada no .env")
    corpo = {
        "model": config.LLM_MODELO,
        "messages": mensagens,
        "temperature": config.LLM_TEMPERATURA if temperatura is None else temperatura,
        "max_tokens": max_tokens,
    }
    if json_mode:
        corpo["response_format"] = {"type": "json_object"}
    r = await _cliente.post(f"{config.LLM_BASE_URL}/chat/completions",
                            headers=_hdr(config.LLM_API_KEY), json=corpo)
    if r.status_code != 200 and json_mode:
        corpo.pop("response_format", None)  # nem todo provedor aceita
        r = await _cliente.post(f"{config.LLM_BASE_URL}/chat/completions",
                                headers=_hdr(config.LLM_API_KEY), json=corpo)
    if r.status_code != 200:
        raise ErroIA(f"LLM {r.status_code}: {r.text[:300]}")
    texto = r.json()["choices"][0]["message"].get("content") or ""
    # remove raciocínio de modelos que pensam em voz alta
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()
    return texto


def extrair_json(texto: str):
    m = re.search(r"\{.*\}", texto, flags=re.S)
    if not m:
        raise ValueError("resposta sem JSON")
    return json.loads(m.group(0))


# ---------------- TTS ----------------

def limpar_para_fala(texto: str) -> str:
    texto = re.sub(r"\*+|#+|_+|`+", "", texto)
    texto = re.sub(r"\((?:[^)]*)\)", "", texto)  # remove rubricas tipo (suspira)
    texto = re.sub(r"\[(?:[^\]]*)\]", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


async def sintetizar_mp3(texto: str, voz: str = None, velocidade: int = 0) -> bytes:
    """Devolve áudio MP3 com a fala."""
    texto = limpar_para_fala(texto)
    if not texto:
        return b""
    voz = voz or config.TTS_VOZ_PADRAO
    if config.TTS_PROVEDOR == "openai":
        vozes_openai = {"masculino": "onyx", "feminino": "nova"}
        voz_oa = vozes_openai["masculino" if ("Antonio" in voz or "Macerio" in voz) else "feminino"]
        r = await _cliente.post(f"{config.TTS_OPENAI_BASE_URL}/audio/speech",
                                headers=_hdr(config.TTS_OPENAI_API_KEY),
                                json={"model": config.TTS_OPENAI_MODELO, "voice": voz_oa,
                                      "input": texto, "response_format": "mp3"})
        if r.status_code != 200:
            raise ErroIA(f"TTS {r.status_code}: {r.text[:200]}")
        return r.content

    import edge_tts
    taxa = f"{velocidade:+d}%"
    for tentativa_voz in (voz, config.TTS_VOZ_PADRAO):
        try:
            com = edge_tts.Communicate(texto, tentativa_voz, rate=taxa)
            dados = bytearray()
            async for parte in com.stream():
                if parte["type"] == "audio":
                    dados.extend(parte["data"])
            if dados:
                return bytes(dados)
        except Exception as e:  # voz inexistente, rede etc.
            log.warning("edge-tts falhou com %s: %s", tentativa_voz, e)
    raise ErroIA("Falha na síntese de voz (edge-tts). Verifique a internet do servidor.")


def dividir_frases(texto: str):
    partes = re.split(r"(?<=[.!?…])\s+", limpar_para_fala(texto))
    frases, atual = [], ""
    for p in partes:
        atual = f"{atual} {p}".strip()
        if len(atual) >= 25:
            frases.append(atual)
            atual = ""
    if atual:
        frases.append(atual)
    return frases
