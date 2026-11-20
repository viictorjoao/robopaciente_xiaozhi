"""Servidor compatível com o firmware Xiaozhi (xiaozhi-esp32).

No ESP32, configure a "URL OTA" como  http://IP-DO-COMPUTADOR:8000/xiaozhi/ota/
O robô consulta essa URL ao ligar, recebe o endereço do WebSocket e passa a
conversar com este servidor (áudio Opus nos dois sentidos).
"""
import asyncio
import json
import logging
import struct
import time
import uuid

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from . import audio, config, db, ia, paciente

log = logging.getLogger("xiaozhi")
router = APIRouter()

TAXA_ENTRADA = 16000
TAXA_SAIDA = 24000
FRAME_MS = 60

# dispositivos conectados agora: mac -> Conexao
CONECTADOS = {}


def registrar_dispositivo(mac, ip=None, firmware=None, placa=None):
    mac = (mac or "").lower()
    d = db.q1("SELECT * FROM dispositivos WHERE mac=?", (mac,))
    agora = time.time()
    if not d:
        primeira = db.q1("SELECT id FROM personas WHERE ativo=1 ORDER BY id LIMIT 1")
        n = (db.q1("SELECT COUNT(*) n FROM dispositivos")["n"] or 0) + 1
        did = db.inserir("dispositivos", dict(mac=mac, nome=f"Robô {n}", persona_id=primeira and primeira["id"],
                                              ultimo_contato=agora, ip=ip, firmware=firmware, placa=placa))
        return db.q1("SELECT * FROM dispositivos WHERE id=?", (did,))
    dados = {"ultimo_contato": agora}
    if ip:
        dados["ip"] = ip
    if firmware:
        dados["firmware"] = firmware
    if placa:
        dados["placa"] = placa
    db.atualizar("dispositivos", d["id"], dados)
    return d


@router.post("/xiaozhi/ota/")
@router.post("/xiaozhi/ota")
async def ota(request: Request):
    try:
        corpo = await request.json()
    except Exception:
        corpo = {}
    mac = request.headers.get("device-id") or corpo.get("mac_address") or "desconhecido"
    versao = (corpo.get("application") or {}).get("version") or "1.0.0"
    placa = (corpo.get("board") or {}).get("type")
    registrar_dispositivo(mac, request.client.host if request.client else None, versao, placa)
    host = request.headers.get("host") or f"127.0.0.1:{config.PORTA}"
    esquema = "wss" if request.url.scheme == "https" else "ws"
    resp = {
        "websocket": {"url": f"{esquema}://{host}/xiaozhi/v1/", "token": config.TOKEN_DISPOSITIVO or "psibot"},
        "server_time": {"timestamp": int(time.time() * 1000), "timezone_offset": -240},  # Manaus UTC-4
        "firmware": {"version": versao, "url": ""},  # nunca força atualização
    }
    log.info("OTA de %s (%s) -> %s", mac, placa, resp["websocket"]["url"])
    return resp


@router.post("/xiaozhi/ota/activate")
async def ativar():
    return {"message": "Device activated", "device_id": 1}


@router.get("/xiaozhi/ota/")
async def ota_get():
    return {"ok": True, "info": "Servidor Robô Paciente — use POST"}


class Conexao:
    def __init__(self, ws: WebSocket, mac: str, versao_bin: int):
        self.ws = ws
        self.mac = mac
        self.versao_bin = versao_bin
        self.session_id = str(uuid.uuid4())
        self.dec = audio.OpusDecoder(TAXA_ENTRADA)
        self.vad = audio.DetectorFala(config.SILENCIO_FIM_FALA_MS)
        self.ouvindo = False
        self.modo = "auto"
        self.buffer = bytearray()
        self.tarefa = None
        self.falando = False
        self.envio_lock = asyncio.Lock()

    # ---------- envio ----------
    async def json(self, **msg):
        msg.setdefault("session_id", self.session_id)
        await self.ws.send_text(json.dumps(msg, ensure_ascii=False))

    async def bin(self, opus: bytes):
        if self.versao_bin == 2:
            dado = struct.pack(">HHIII", 2, 0, 0, 0, len(opus)) + opus
        elif self.versao_bin == 3:
            dado = struct.pack(">BBH", 0, 0, len(opus)) + opus
        else:
            dado = opus
        await self.ws.send_bytes(dado)

    def desembrulhar(self, dado: bytes) -> bytes:
        if self.versao_bin == 2 and len(dado) >= 16:
            _v, tipo, _r, _ts, tam = struct.unpack(">HHIII", dado[:16])
            return dado[16:16 + tam] if tipo == 0 else b""
        if self.versao_bin == 3 and len(dado) >= 4:
            tipo, _r, tam = struct.unpack(">BBH", dado[:4])
            return dado[4:4 + tam] if tipo == 0 else b""
        return dado

    # ---------- sessão ----------
    def sessao(self):
        disp = db.q1("SELECT * FROM dispositivos WHERE mac=?", (self.mac,))
        s = db.sessao_ativa_do_dispositivo(disp["id"])
        if not s:
            pid = disp["persona_id"] or db.q1("SELECT id FROM personas ORDER BY id LIMIT 1")["id"]
            s = db.criar_sessao(pid, "robo", dispositivo_id=disp["id"])
            log.info("Sessão avulsa %s criada para %s", s["codigo"], self.mac)
        return s

    # ---------- fluxo ----------
    async def ao_receber_audio(self, dado: bytes):
        if not self.ouvindo:
            return
        pcm = self.dec.decode(self.desembrulhar(dado))
        if not pcm:
            return
        self.buffer.extend(pcm)
        fim = self.modo != "manual" and self.vad.alimentar(pcm)
        longo = len(self.buffer) > TAXA_ENTRADA * 2 * 30  # 30 s
        if fim or longo:
            self.processar()

    def processar(self):
        if not self.ouvindo:
            return
        self.ouvindo = False
        pcm = bytes(self.buffer)
        self.buffer.clear()
        self.vad.reset()
        self.tarefa = asyncio.create_task(self.turno(pcm))

    async def turno(self, pcm: bytes):
        try:
            if len(pcm) < TAXA_ENTRADA * 2 * 0.4:  # menos de 0,4 s: ignora
                self.ouvindo = True
                return
            t0 = time.time()
            texto = await ia.transcrever(audio.pcm_para_wav(pcm, TAXA_ENTRADA))
            if not texto:
                self.ouvindo = True
                return
            await self.json(type="stt", text=texto)
            s = self.sessao()
            resposta = await paciente.responder(s["id"], texto)
            p = paciente.persona_da_sessao(s["id"])
            log.info("[%s] aluno: %s | paciente: %s (%.1fs)", s["codigo"], texto, resposta, time.time() - t0)
            await self.falar(resposta, p.get("voz"), p.get("velocidade") or 0)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("erro no turno: %s", e)
            await self.falar("Desculpa, me distraí. Pode repetir, por favor?", None, 0)

    async def falar(self, texto, voz, velocidade):
        enc = audio.OpusEncoder(TAXA_SAIDA, FRAME_MS)
        self.falando = True
        await self.json(type="llm", emotion="neutral", text="😐")
        await self.json(type="tts", state="start")
        try:
            inicio = time.monotonic()
            enviados = 0
            for frase in ia.dividir_frases(texto):
                mp3 = await ia.sintetizar_mp3(frase, voz, velocidade)
                pcm = audio.para_pcm(mp3, TAXA_SAIDA) if mp3 else b""
                await self.json(type="tts", state="sentence_start", text=frase)
                for pacote in enc.encode_pcm(pcm):
                    # envia ~em tempo real (com 5 quadros de folga) para não estourar o buffer do ESP32
                    alvo = inicio + max(0, enviados - 5) * FRAME_MS / 1000
                    espera = alvo - time.monotonic()
                    if espera > 0:
                        await asyncio.sleep(espera)
                    await self.bin(pacote)
                    enviados += 1
            resto = inicio + enviados * FRAME_MS / 1000 - time.monotonic()
            if resto > 0:
                await asyncio.sleep(resto)
        finally:
            self.falando = False
            try:
                await self.json(type="tts", state="stop")
            except Exception:
                pass

    async def ao_receber_json(self, msg: dict):
        tipo = msg.get("type")
        if tipo == "hello":
            await self.json(type="hello", transport="websocket",
                            audio_params={"format": "opus", "sample_rate": TAXA_SAIDA,
                                          "channels": 1, "frame_duration": FRAME_MS})
            self.sessao()
        elif tipo == "listen":
            estado = msg.get("state")
            if estado == "start":
                self.modo = msg.get("mode", "auto")
                self.buffer.clear()
                self.vad.reset()
                self.ouvindo = True
            elif estado == "stop":
                self.processar()
            # "detect" = palavra de ativação; ignoramos
        elif tipo == "abort":
            if self.tarefa and not self.tarefa.done():
                self.tarefa.cancel()
        # mensagens "mcp" e outras são ignoradas


@router.websocket("/xiaozhi/v1/")
async def websocket_xiaozhi(ws: WebSocket):
    if config.TOKEN_DISPOSITIVO:
        auth = ws.headers.get("authorization", "")
        if auth.replace("Bearer ", "").strip() != config.TOKEN_DISPOSITIVO:
            await ws.close(code=4001)
            return
    await ws.accept()
    mac = (ws.headers.get("device-id") or ws.query_params.get("device-id") or "desconhecido").lower()
    try:
        versao = int(ws.headers.get("protocol-version") or 1)
    except ValueError:
        versao = 1
    registrar_dispositivo(mac, ws.client.host if ws.client else None)
    con = Conexao(ws, mac, versao)
    CONECTADOS[mac] = con
    log.info("Robô conectado: %s (protocolo v%s)", mac, versao)
    try:
        while True:
            m = await ws.receive()
            if m["type"] == "websocket.disconnect":
                break
            if m.get("bytes") is not None:
                await con.ao_receber_audio(m["bytes"])
            elif m.get("text"):
                try:
                    await con.ao_receber_json(json.loads(m["text"]))
                except json.JSONDecodeError:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        if con.tarefa and not con.tarefa.done():
            con.tarefa.cancel()
        if CONECTADOS.get(mac) is con:
            CONECTADOS.pop(mac, None)
        registrar_dispositivo(mac)
        log.info("Robô desconectado: %s", mac)
