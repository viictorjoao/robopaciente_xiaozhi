"""Banco SQLite (arquivo único em dados/). Sem ORM, para ficar fácil de ler."""
import sqlite3
import threading
import time
import secrets

from . import config
from .catalogo import PACIENTES_EXEMPLO

_lock = threading.RLock()
_conn = None

ESQUEMA = """
CREATE TABLE IF NOT EXISTS personas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL, idade INTEGER, genero TEXT, profissao TEXT,
  queixa_principal TEXT, historia TEXT, sintomas_chave TEXT, revela_se_perguntado TEXT,
  estilo_fala TEXT, abertura INTEGER DEFAULT 3, risco TEXT DEFAULT 'ausente',
  diagnostico_id TEXT, diferenciais_aceitos TEXT, voz TEXT, velocidade INTEGER DEFAULT 0,
  observacoes_professor TEXT, ativo INTEGER DEFAULT 1, criado_em REAL
);
CREATE TABLE IF NOT EXISTS turmas (
  id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, curso TEXT, semestre TEXT
);
CREATE TABLE IF NOT EXISTS alunos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, matricula TEXT UNIQUE,
  turma_id INTEGER REFERENCES turmas(id)
);
CREATE TABLE IF NOT EXISTS dispositivos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, mac TEXT UNIQUE, nome TEXT, persona_id INTEGER,
  ultimo_contato REAL, ip TEXT, firmware TEXT, placa TEXT
);
CREATE TABLE IF NOT EXISTS sessoes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE,
  dispositivo_id INTEGER, persona_id INTEGER, aluno_id INTEGER, turma_id INTEGER,
  origem TEXT, status TEXT DEFAULT 'ativa', inicio REAL, fim REAL, ultima_atividade REAL
);
CREATE TABLE IF NOT EXISTS mensagens (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sessao_id INTEGER, papel TEXT, texto TEXT,
  ts REAL, latencia_ms INTEGER
);
CREATE TABLE IF NOT EXISTS laudos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sessao_id INTEGER UNIQUE,
  hipotese_id TEXT, diferenciais TEXT, sintomas TEXT, justificativa TEXT, risco TEXT, conduta TEXT,
  resultado TEXT, nota REAL, nota_diagnostico REAL, nota_risco REAL, nota_entrevista REAL,
  feedback TEXT, rubrica_json TEXT, criado_em REAL
);
CREATE INDEX IF NOT EXISTS ix_msg_sessao ON mensagens(sessao_id);
CREATE INDEX IF NOT EXISTS ix_sessao_disp ON sessoes(dispositivo_id, status);
"""


def conn():
    global _conn
    if _conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(ESQUEMA)
    return _conn


def q(sql, params=()):
    with _lock:
        return [dict(r) for r in conn().execute(sql, params).fetchall()]


def q1(sql, params=()):
    r = q(sql, params)
    return r[0] if r else None


def ex(sql, params=()):
    with _lock:
        c = conn()
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid


def inserir(tabela, dados: dict):
    cols = ", ".join(dados)
    marks = ", ".join("?" for _ in dados)
    return ex(f"INSERT INTO {tabela} ({cols}) VALUES ({marks})", tuple(dados.values()))


def atualizar(tabela, id_, dados: dict):
    if not dados:
        return
    sets = ", ".join(f"{k}=?" for k in dados)
    ex(f"UPDATE {tabela} SET {sets} WHERE id=?", (*dados.values(), id_))


def iniciar():
    conn()
    if not q1("SELECT id FROM personas LIMIT 1"):
        for p in PACIENTES_EXEMPLO:
            inserir("personas", {**p, "criado_em": time.time()})
    if not q1("SELECT id FROM turmas LIMIT 1"):
        inserir("turmas", {"nome": "Turma de demonstração", "curso": "Psicologia", "semestre": "2026.2"})


# ---------- sessões ----------

def novo_codigo():
    while True:
        c = secrets.token_hex(3).upper()
        if not q1("SELECT id FROM sessoes WHERE codigo=?", (c,)):
            return c


def criar_sessao(persona_id, origem, dispositivo_id=None, aluno_id=None, turma_id=None):
    agora = time.time()
    if dispositivo_id:
        encerrar_sessoes_do_dispositivo(dispositivo_id)
    sid = inserir("sessoes", dict(
        codigo=novo_codigo(), dispositivo_id=dispositivo_id, persona_id=persona_id,
        aluno_id=aluno_id, turma_id=turma_id, origem=origem, status="ativa",
        inicio=agora, ultima_atividade=agora))
    return q1("SELECT * FROM sessoes WHERE id=?", (sid,))


def encerrar_sessoes_do_dispositivo(dispositivo_id):
    """Fecha sessões abertas desse robô (as que têm aluno ficam aguardando laudo)."""
    agora = time.time()
    ex("UPDATE sessoes SET status='aguardando_laudo', fim=? WHERE dispositivo_id=? AND status='ativa' AND aluno_id IS NOT NULL",
       (agora, dispositivo_id))
    ex("UPDATE sessoes SET status='encerrada', fim=? WHERE dispositivo_id=? AND status='ativa'",
       (agora, dispositivo_id))


def sessao_ativa_do_dispositivo(dispositivo_id):
    s = q1("SELECT * FROM sessoes WHERE dispositivo_id=? AND status='ativa' ORDER BY id DESC LIMIT 1",
           (dispositivo_id,))
    if s and s["aluno_id"] is None and s["ultima_atividade"] and \
            time.time() - s["ultima_atividade"] > config.SESSAO_AVULSA_EXPIRA_MIN * 60:
        ex("UPDATE sessoes SET status='encerrada', fim=? WHERE id=?", (time.time(), s["id"]))
        return None
    return s


def add_mensagem(sessao_id, papel, texto, latencia_ms=None):
    agora = time.time()
    ex("INSERT INTO mensagens (sessao_id, papel, texto, ts, latencia_ms) VALUES (?,?,?,?,?)",
       (sessao_id, papel, texto, agora, latencia_ms))
    ex("UPDATE sessoes SET ultima_atividade=? WHERE id=?", (agora, sessao_id))


def mensagens(sessao_id):
    return q("SELECT * FROM mensagens WHERE sessao_id=? ORDER BY id", (sessao_id,))
