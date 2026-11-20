"""Áudio: Opus (protocolo Xiaozhi), conversão de formatos e detecção de fala (VAD).

Usa o PyAV (pip install av), que já traz o FFmpeg com libopus embutido —
não é preciso instalar nada no Windows.
"""
import io
import wave

import av
import numpy as np


def _resampler(rate):
    return av.AudioResampler(format="s16", layout="mono", rate=rate)


class OpusDecoder:
    """Decodifica quadros Opus vindos do ESP32 para PCM 16 bits mono."""

    def __init__(self, rate=16000):
        self.rate = rate
        self.ctx = av.CodecContext.create("opus", "r")
        self.ctx.sample_rate = 48000
        self.ctx.layout = "mono"
        self.rs = _resampler(rate)

    def decode(self, pacote: bytes) -> bytes:
        saida = []
        try:
            for fr in self.ctx.decode(av.Packet(pacote)):
                for f2 in self.rs.resample(fr):
                    saida.append(f2.to_ndarray().tobytes())
        except av.error.FFmpegError:
            return b""
        return b"".join(saida)


class OpusEncoder:
    """Codifica PCM 16 bits mono em quadros Opus de 60 ms (formato esperado pelo Xiaozhi)."""

    def __init__(self, rate=24000, frame_ms=60):
        self.rate = rate
        self.n = rate * frame_ms // 1000
        self.ctx = av.CodecContext.create("libopus", "w")
        self.ctx.sample_rate = rate
        self.ctx.layout = "mono"
        self.ctx.format = "s16"
        self.ctx.options = {"frame_duration": str(frame_ms), "application": "voip"}
        self.ctx.open()
        self.pts = 0

    def encode_pcm(self, pcm: bytes):
        """Recebe PCM (bytes) e devolve a lista de pacotes Opus."""
        arr = np.frombuffer(pcm, dtype=np.int16)
        resto = len(arr) % self.n
        if resto:
            arr = np.concatenate([arr, np.zeros(self.n - resto, dtype=np.int16)])
        pacotes = []
        for i in range(0, len(arr), self.n):
            f = av.AudioFrame.from_ndarray(arr[i:i + self.n].reshape(1, -1), format="s16", layout="mono")
            f.sample_rate = self.rate
            f.pts = self.pts
            self.pts += self.n
            pacotes.extend(bytes(p) for p in self.ctx.encode(f))
        return pacotes


def para_pcm(dados: bytes, rate: int) -> bytes:
    """Converte qualquer áudio (mp3, webm, ogg, wav...) para PCM 16 bits mono."""
    rs = _resampler(rate)
    saida = []
    with av.open(io.BytesIO(dados)) as cont:
        stream = next(s for s in cont.streams if s.type == "audio")
        for fr in cont.decode(stream):
            for f2 in rs.resample(fr):
                saida.append(f2.to_ndarray().tobytes())
    for f2 in rs.resample(None):
        saida.append(f2.to_ndarray().tobytes())
    return b"".join(saida)


def pcm_para_wav(pcm: bytes, rate=16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def rms(pcm: bytes) -> float:
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(a * a))) if len(a) else 0.0


class DetectorFala:
    """VAD simples por energia, com piso de ruído adaptativo.

    Alimente com blocos de PCM 16 kHz; `alimentar` devolve True quando
    a pessoa terminou de falar (fala seguida de silêncio).
    """

    def __init__(self, silencio_ms=900, rate=16000):
        self.rate = rate
        self.silencio_ms = silencio_ms
        self.reset()

    def reset(self):
        self.ruido = 300.0
        self.ms_fala = 0
        self.ms_silencio = 0
        self.falando = False

    def alimentar(self, pcm: bytes) -> bool:
        if not pcm:
            return False
        dur = len(pcm) // 2 * 1000 // self.rate
        e = rms(pcm)
        limiar = max(self.ruido * 2.8, 450.0)
        if e > limiar:
            self.ms_fala += dur
            self.ms_silencio = 0
            if self.ms_fala >= 180:
                self.falando = True
        else:
            # só atualiza o piso de ruído nos trechos silenciosos
            self.ruido = 0.95 * self.ruido + 0.05 * max(e, 50.0)
            if self.falando:
                self.ms_silencio += dur
            else:
                self.ms_fala = max(0, self.ms_fala - dur)
        return self.falando and self.ms_silencio >= self.silencio_ms
