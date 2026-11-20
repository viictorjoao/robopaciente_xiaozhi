"""API da plataforma web: área do professor (/api/admin) e página do aluno (/api/aluno)."""
import base64
import csv
import hashlib
import hmac
import html
import io
import json
import socket
import time
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from . import audio, avaliacao, config, db, ia, paciente
from .catalogo import DIAG_POR_ID, DIAGNOSTICOS, NIVEIS_RISCO, VOZES, nome_diag
from .xiaozhi import CONECTADOS

router = APIRouter()

CAMPOS_PERSONA = ["nome", "idade", "genero", "profissao", "queixa_principal", "historia", "sintomas_chave",
                  "revela_se_perguntado", "estilo_fala", "abertura", "risco", "diagnostico_id",
                  "diferenciais_aceitos", "voz", "velocidade", "observacoes_professor", "ativo"]


# ------------------------------------------------------------------ util

def _token():
    return hmac.new(config.SEGREDO.encode(), config.SENHA_PROFESSOR.encode(), hashlib.sha256).hexdigest()


def admin(request: Request):
    if not hmac.compare_digest(request.cookies.get("rp_admin", ""), _token()):
        raise HTTPException(401, "Faça login como professor(a).")
    return True


def ips_locais():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if not info[4][0].startswith("127."):
                ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ips) or ["127.0.0.1"]


def _ts_dia(data_str, fim=False):
    if not data_str:
        return None
    d = datetime.strptime(data_str, "%Y-%m-%d")
    if fim:
        d = d.replace(hour=23, minute=59, second=59)
    return d.timestamp()


def fmt_data(ts):
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M") if ts else ""


def _online(d):
    return d["mac"] in CONECTADOS or (d["ultimo_contato"] or 0) > time.time() - 90


SQL_SESSAO = """
SELECT s.*, p.nome paciente_nome, p.idade paciente_idade, p.diagnostico_id,
       a.nome aluno_nome, a.matricula, t.nome turma_nome, d.nome robo_nome,
       l.hipotese_id, l.resultado, l.nota,
       (SELECT COUNT(*) FROM mensagens m WHERE m.sessao_id=s.id AND m.papel='aluno') n_perguntas
FROM sessoes s
LEFT JOIN personas p ON p.id=s.persona_id
LEFT JOIN alunos a ON a.id=s.aluno_id
LEFT JOIN turmas t ON t.id=s.turma_id
LEFT JOIN dispositivos d ON d.id=s.dispositivo_id
LEFT JOIN laudos l ON l.sessao_id=s.id
"""


def _filtros(params):
    where, args = [], []
    if params.get("turma_id"):
        where.append("s.turma_id=?"); args.append(int(params["turma_id"]))
    if params.get("persona_id"):
        where.append("s.persona_id=?"); args.append(int(params["persona_id"]))
    if params.get("status"):
        where.append("s.status=?"); args.append(params["status"])
    if params.get("de"):
        where.append("s.inicio>=?"); args.append(_ts_dia(params["de"]))
    if params.get("ate"):
        where.append("s.inicio<=?"); args.append(_ts_dia(params["ate"], True))
    if params.get("busca"):
        where.append("(a.nome LIKE ? OR a.matricula LIKE ? OR s.codigo LIKE ?)")
        args += [f"%{params['busca']}%"] * 3
    if params.get("so_alunos"):
        where.append("s.aluno_id IS NOT NULL")
    return (" WHERE " + " AND ".join(where)) if where else "", args


async def _turno_texto(sessao, texto, com_voz):
    resposta = await paciente.responder(sessao["id"], texto)
    out = {"aluno": texto, "paciente": resposta}
    if com_voz:
        p = paciente.persona_da_sessao(sessao["id"])
        try:
            mp3 = await ia.sintetizar_mp3(resposta, p.get("voz"), p.get("velocidade") or 0)
            out["audio_b64"] = base64.b64encode(mp3).decode()
        except Exception as e:
            out["erro_voz"] = str(e)
    return out


async def _turno_audio(sessao, arquivo: UploadFile, com_voz=True):
    dados = await arquivo.read()
    try:
        pcm = audio.para_pcm(dados, 16000)
    except Exception:
        raise HTTPException(400, "Não consegui ler o áudio enviado.")
    texto = await ia.transcrever(audio.pcm_para_wav(pcm))
    if not texto:
        return {"aluno": "", "paciente": "", "aviso": "Não entendi o áudio. Tente falar mais perto do microfone."}
    return await _turno_texto(sessao, texto, com_voz)


def _erro_ia(e):
    raise HTTPException(503, f"Serviço de IA indisponível: {e}")


# ------------------------------------------------------------------ público

@router.get("/api/info")
def info():
    return {
        "diagnosticos": [{"id": d[0], "nome": d[1], "cid": d[2]} for d in DIAGNOSTICOS],
        "riscos": NIVEIS_RISCO, "vozes": [{"id": v[0], "nome": v[1]} for v in VOZES],
        "ips": ips_locais(), "porta": config.PORTA,
        "mostrar_resultado_aluno": config.MOSTRAR_RESULTADO_ALUNO,
    }


@router.post("/api/login")
async def login(request: Request, response: Response):
    corpo = await request.json()
    if not hmac.compare_digest(str(corpo.get("senha", "")), config.SENHA_PROFESSOR):
        raise HTTPException(401, "Senha incorreta.")
    response.set_cookie("rp_admin", _token(), httponly=True, samesite="lax", max_age=60 * 60 * 12)
    return {"ok": True}


@router.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("rp_admin")
    return {"ok": True}


@router.get("/api/me")
def me(request: Request):
    return {"admin": hmac.compare_digest(request.cookies.get("rp_admin", ""), _token())}


# ------------------------------------------------------------------ aluno

def _sessao_codigo(codigo):
    s = db.q1("SELECT * FROM sessoes WHERE codigo=?", (codigo.upper(),))
    if not s:
        raise HTTPException(404, "Sessão não encontrada.")
    return s


@router.get("/api/aluno/opcoes")
def aluno_opcoes():
    robos = []
    for d in db.q("SELECT d.*, p.nome pnome, p.idade pidade FROM dispositivos d LEFT JOIN personas p ON p.id=d.persona_id ORDER BY d.nome"):
        ocupado = db.q1("SELECT id FROM sessoes WHERE dispositivo_id=? AND status='ativa' AND aluno_id IS NOT NULL", (d["id"],))
        robos.append({"id": d["id"], "nome": d["nome"], "online": _online(d), "ocupado": bool(ocupado),
                      "paciente": f"{d['pnome']}, {d['pidade']} anos" if d["pnome"] else "—"})
    pacientes = [{"id": p["id"], "rotulo": f"{p['nome']}, {p['idade']} anos"}
                 for p in db.q("SELECT id, nome, idade FROM personas WHERE ativo=1 ORDER BY nome")]
    return {"turmas": db.q("SELECT id, nome FROM turmas ORDER BY nome"), "robos": robos, "pacientes": pacientes}


@router.post("/api/aluno/sessao")
async def aluno_iniciar(request: Request):
    c = await request.json()
    nome, matricula = (c.get("nome") or "").strip(), (c.get("matricula") or "").strip()
    if not nome or not matricula:
        raise HTTPException(400, "Informe nome e matrícula.")
    turma_id = int(c["turma_id"]) if c.get("turma_id") else None
    a = db.q1("SELECT * FROM alunos WHERE matricula=?", (matricula,))
    if a:
        db.atualizar("alunos", a["id"], {"nome": nome, "turma_id": turma_id or a["turma_id"]})
        aluno_id = a["id"]
    else:
        aluno_id = db.inserir("alunos", {"nome": nome, "matricula": matricula, "turma_id": turma_id})
    if c.get("dispositivo_id"):
        d = db.q1("SELECT * FROM dispositivos WHERE id=?", (int(c["dispositivo_id"]),))
        if not d:
            raise HTTPException(404, "Robô não encontrado.")
        if not d["persona_id"]:
            raise HTTPException(400, "O professor ainda não escolheu o paciente deste robô.")
        s = db.criar_sessao(d["persona_id"], "robo", dispositivo_id=d["id"], aluno_id=aluno_id, turma_id=turma_id)
    elif c.get("persona_id"):
        s = db.criar_sessao(int(c["persona_id"]), "navegador", aluno_id=aluno_id, turma_id=turma_id)
    else:
        raise HTTPException(400, "Escolha um robô ou um paciente.")
    return {"codigo": s["codigo"]}


@router.get("/api/aluno/sessao/{codigo}")
def aluno_ver(codigo: str):
    s = _sessao_codigo(codigo)
    p = db.q1("SELECT nome, idade FROM personas WHERE id=?", (s["persona_id"],))
    a = db.q1("SELECT nome, matricula FROM alunos WHERE id=?", (s["aluno_id"],)) if s["aluno_id"] else None
    out = {"codigo": s["codigo"], "status": s["status"], "origem": s["origem"],
           "paciente": p, "aluno": a, "mensagens": [{"papel": m["papel"], "texto": m["texto"]} for m in db.mensagens(s["id"])],
           "laudo": None}
    l = db.q1("SELECT * FROM laudos WHERE sessao_id=?", (s["id"],))
    if l:
        out["laudo"] = {"enviado": True}
        if config.MOSTRAR_RESULTADO_ALUNO:
            pers = db.q1("SELECT diagnostico_id FROM personas WHERE id=?", (s["persona_id"],))
            out["laudo"].update(_laudo_publico(l, pers["diagnostico_id"]))
    return out


def _laudo_publico(l, diag_correto):
    rub = json.loads(l["rubrica_json"] or "{}")
    return {"resultado": l["resultado"], "nota": l["nota"], "nota_diagnostico": l["nota_diagnostico"],
            "nota_risco": l["nota_risco"], "nota_entrevista": l["nota_entrevista"],
            "feedback": l["feedback"], "hipotese": nome_diag(l["hipotese_id"]), "correto": nome_diag(diag_correto),
            "criterios": [{"nome": n, "max": mx, "nota": rub.get("criterios", {}).get(k, 0)} for k, n, mx in avaliacao.CRITERIOS],
            "pontos_fortes": rub.get("pontos_fortes", []), "pontos_a_melhorar": rub.get("pontos_a_melhorar", []),
            "sintomas_investigados": rub.get("sintomas_investigados", []),
            "sintomas_nao_investigados": rub.get("sintomas_nao_investigados", [])}


@router.post("/api/aluno/sessao/{codigo}/mensagem")
async def aluno_mensagem(codigo: str, request: Request):
    s = _sessao_codigo(codigo)
    if s["status"] != "ativa":
        raise HTTPException(400, "Esta entrevista já foi finalizada.")
    c = await request.json()
    texto = (c.get("texto") or "").strip()
    if not texto:
        raise HTTPException(400, "Mensagem vazia.")
    try:
        return await _turno_texto(s, texto, bool(c.get("voz")))
    except ia.ErroIA as e:
        _erro_ia(e)


@router.post("/api/aluno/sessao/{codigo}/audio")
async def aluno_audio(codigo: str, arquivo: UploadFile = File(...)):
    s = _sessao_codigo(codigo)
    if s["status"] != "ativa":
        raise HTTPException(400, "Esta entrevista já foi finalizada.")
    try:
        return await _turno_audio(s, arquivo)
    except ia.ErroIA as e:
        _erro_ia(e)


@router.post("/api/aluno/sessao/{codigo}/finalizar")
def aluno_finalizar(codigo: str):
    s = _sessao_codigo(codigo)
    if s["status"] == "ativa":
        db.ex("UPDATE sessoes SET status='aguardando_laudo', fim=? WHERE id=?", (time.time(), s["id"]))
    return {"ok": True}


@router.post("/api/aluno/sessao/{codigo}/laudo")
async def aluno_laudo(codigo: str, request: Request):
    s = _sessao_codigo(codigo)
    if db.q1("SELECT id FROM laudos WHERE sessao_id=?", (s["id"],)):
        raise HTTPException(400, "O laudo desta sessão já foi enviado.")
    c = await request.json()
    if c.get("hipotese_id") not in DIAG_POR_ID:
        raise HTTPException(400, "Escolha a hipótese diagnóstica principal.")
    if s["status"] == "ativa":
        db.ex("UPDATE sessoes SET status='aguardando_laudo', fim=? WHERE id=?", (time.time(), s["id"]))
    await avaliacao.avaliar(s["id"], c)
    return aluno_ver(codigo)


# ------------------------------------------------------------------ professor

A = APIRouter(prefix="/api/admin", dependencies=[Depends(admin)])


@A.get("/painel")
def painel():
    hoje = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
    tot = db.q1("""SELECT COUNT(*) n, SUM(resultado='correto') c, SUM(resultado='parcial') p, AVG(nota) media
                   FROM laudos""")
    disp = db.q("SELECT * FROM dispositivos")
    return {
        "sessoes_hoje": db.q1("SELECT COUNT(*) n FROM sessoes WHERE inicio>=?", (hoje,))["n"],
        "laudos": tot["n"] or 0, "corretos": tot["c"] or 0, "parciais": tot["p"] or 0,
        "media": round(tot["media"] or 0, 1),
        "taxa_acerto": round(100 * (tot["c"] or 0) / tot["n"], 1) if tot["n"] else 0,
        "robos_online": sum(1 for d in disp if _online(d)), "robos": len(disp),
        "ativas": [_fmt_sessao(s) for s in db.q(SQL_SESSAO + " WHERE s.status='ativa' ORDER BY s.id DESC")],
        "recentes": [_fmt_sessao(s) for s in db.q(SQL_SESSAO + " WHERE l.id IS NOT NULL ORDER BY l.criado_em DESC LIMIT 8")],
    }


def _fmt_sessao(s):
    s = dict(s)
    s["inicio_fmt"] = fmt_data(s["inicio"])
    s["duracao_min"] = round(((s["fim"] or s["ultima_atividade"] or s["inicio"]) - s["inicio"]) / 60, 1)
    s["hipotese_nome"] = nome_diag(s.get("hipotese_id")) if s.get("hipotese_id") else None
    s["diagnostico_nome"] = nome_diag(s.get("diagnostico_id"))
    return s


# --- pacientes (personas)
@A.get("/personas")
def personas_listar():
    return db.q("SELECT * FROM personas ORDER BY ativo DESC, nome")


def _persona_dados(c):
    d = {k: c.get(k) for k in CAMPOS_PERSONA if k in c}
    for k in ("idade", "abertura", "velocidade", "ativo"):
        if k in d and d[k] not in (None, ""):
            d[k] = int(d[k])
    if isinstance(d.get("diferenciais_aceitos"), list):
        d["diferenciais_aceitos"] = ",".join(d["diferenciais_aceitos"])
    return d


@A.post("/personas")
async def personas_criar(request: Request):
    d = _persona_dados(await request.json())
    if not d.get("nome"):
        raise HTTPException(400, "Informe o nome do paciente.")
    d["criado_em"] = time.time()
    d.setdefault("ativo", 1)
    return {"id": db.inserir("personas", d)}


@A.put("/personas/{pid}")
async def personas_editar(pid: int, request: Request):
    db.atualizar("personas", pid, _persona_dados(await request.json()))
    return {"ok": True}


@A.post("/personas/{pid}/duplicar")
def personas_duplicar(pid: int):
    p = db.q1("SELECT * FROM personas WHERE id=?", (pid,))
    d = {k: p[k] for k in CAMPOS_PERSONA}
    d["nome"] = p["nome"] + " (cópia)"
    d["criado_em"] = time.time()
    return {"id": db.inserir("personas", d)}


@A.delete("/personas/{pid}")
def personas_excluir(pid: int):
    if db.q1("SELECT id FROM sessoes WHERE persona_id=? LIMIT 1", (pid,)):
        db.atualizar("personas", pid, {"ativo": 0})  # mantém histórico
        return {"ok": True, "arquivado": True}
    db.ex("DELETE FROM personas WHERE id=?", (pid,))
    return {"ok": True}


# --- turmas e alunos
@A.get("/turmas")
def turmas():
    return db.q("""SELECT t.*, (SELECT COUNT(*) FROM alunos a WHERE a.turma_id=t.id) n_alunos
                   FROM turmas t ORDER BY nome""")


@A.post("/turmas")
async def turmas_criar(request: Request):
    c = await request.json()
    return {"id": db.inserir("turmas", {k: c.get(k) for k in ("nome", "curso", "semestre")})}


@A.put("/turmas/{tid}")
async def turmas_editar(tid: int, request: Request):
    c = await request.json()
    db.atualizar("turmas", tid, {k: c[k] for k in ("nome", "curso", "semestre") if k in c})
    return {"ok": True}


@A.delete("/turmas/{tid}")
def turmas_excluir(tid: int):
    db.ex("UPDATE alunos SET turma_id=NULL WHERE turma_id=?", (tid,))
    db.ex("DELETE FROM turmas WHERE id=?", (tid,))
    return {"ok": True}


@A.get("/alunos")
def alunos(turma_id: int = None):
    sql = """SELECT a.*, t.nome turma_nome,
               (SELECT COUNT(*) FROM sessoes s WHERE s.aluno_id=a.id) n_sessoes,
               (SELECT AVG(l.nota) FROM laudos l JOIN sessoes s ON s.id=l.sessao_id WHERE s.aluno_id=a.id) media
             FROM alunos a LEFT JOIN turmas t ON t.id=a.turma_id"""
    if turma_id:
        return db.q(sql + " WHERE a.turma_id=? ORDER BY a.nome", (turma_id,))
    return db.q(sql + " ORDER BY a.nome")


@A.post("/alunos")
async def alunos_criar(request: Request):
    c = await request.json()
    linhas = c.get("lista")
    turma_id = c.get("turma_id") or None
    n = 0
    itens = []
    if linhas:  # importação: "Nome;Matrícula" por linha
        for ln in linhas.splitlines():
            partes = [x.strip() for x in ln.replace("\t", ";").replace(",", ";").split(";")]
            if len(partes) >= 2 and partes[0] and partes[1]:
                itens.append((partes[0], partes[1]))
    elif c.get("nome") and c.get("matricula"):
        itens.append((c["nome"].strip(), c["matricula"].strip()))
    for nome, mat in itens:
        a = db.q1("SELECT id FROM alunos WHERE matricula=?", (mat,))
        if a:
            db.atualizar("alunos", a["id"], {"nome": nome, "turma_id": turma_id})
        else:
            db.inserir("alunos", {"nome": nome, "matricula": mat, "turma_id": turma_id})
        n += 1
    return {"importados": n}


@A.delete("/alunos/{aid}")
def alunos_excluir(aid: int):
    db.ex("UPDATE sessoes SET aluno_id=NULL WHERE aluno_id=?", (aid,))
    db.ex("DELETE FROM alunos WHERE id=?", (aid,))
    return {"ok": True}


# --- robôs
@A.get("/dispositivos")
def dispositivos():
    out = []
    for d in db.q("SELECT d.*, p.nome persona_nome FROM dispositivos d LEFT JOIN personas p ON p.id=d.persona_id ORDER BY d.nome"):
        s = db.q1(SQL_SESSAO + " WHERE s.dispositivo_id=? AND s.status='ativa' ORDER BY s.id DESC LIMIT 1", (d["id"],))
        d["online"] = _online(d)
        d["conectado_ws"] = d["mac"] in CONECTADOS
        d["ultimo_contato_fmt"] = fmt_data(d["ultimo_contato"])
        d["sessao"] = _fmt_sessao(s) if s else None
        out.append(d)
    return out


@A.put("/dispositivos/{did}")
async def dispositivos_editar(did: int, request: Request):
    c = await request.json()
    dados = {k: c[k] for k in ("nome", "persona_id") if k in c}
    antigo = db.q1("SELECT persona_id FROM dispositivos WHERE id=?", (did,))
    db.atualizar("dispositivos", did, dados)
    if "persona_id" in dados and antigo and antigo["persona_id"] != dados["persona_id"]:
        db.encerrar_sessoes_do_dispositivo(did)  # troca de paciente encerra a conversa atual
    return {"ok": True}


@A.delete("/dispositivos/{did}")
def dispositivos_excluir(did: int):
    db.ex("DELETE FROM dispositivos WHERE id=?", (did,))
    return {"ok": True}


# --- sessões
@A.get("/sessoes")
def sessoes(request: Request):
    w, args = _filtros(dict(request.query_params))
    return [_fmt_sessao(s) for s in db.q(SQL_SESSAO + w + " ORDER BY s.id DESC LIMIT 500", args)]


@A.get("/sessoes/{sid}")
def sessao_detalhe(sid: int):
    s = db.q1(SQL_SESSAO + " WHERE s.id=?", (sid,))
    if not s:
        raise HTTPException(404)
    l = db.q1("SELECT * FROM laudos WHERE sessao_id=?", (sid,))
    p = db.q1("SELECT * FROM personas WHERE id=?", (s["persona_id"],))
    laudo = None
    if l:
        laudo = dict(l)
        laudo.update(_laudo_publico(l, p["diagnostico_id"]))
        laudo["diferenciais_nomes"] = [nome_diag(d) for d in (l["diferenciais"] or "").split(",") if d]
    return {"sessao": _fmt_sessao(s), "persona": p, "mensagens": db.mensagens(sid), "laudo": laudo}


@A.post("/sessoes")
async def sessao_criar_admin(request: Request):
    c = await request.json()
    s = db.criar_sessao(int(c["persona_id"]), "simulador")
    return {"id": s["id"], "codigo": s["codigo"]}


@A.post("/sessoes/{sid}/mensagem")
async def sessao_mensagem_admin(sid: int, request: Request):
    s = db.q1("SELECT * FROM sessoes WHERE id=?", (sid,))
    c = await request.json()
    try:
        return await _turno_texto(s, c["texto"], bool(c.get("voz")))
    except ia.ErroIA as e:
        _erro_ia(e)


@A.post("/sessoes/{sid}/audio")
async def sessao_audio_admin(sid: int, arquivo: UploadFile = File(...)):
    s = db.q1("SELECT * FROM sessoes WHERE id=?", (sid,))
    try:
        return await _turno_audio(s, arquivo)
    except ia.ErroIA as e:
        _erro_ia(e)


@A.post("/sessoes/{sid}/encerrar")
def sessao_encerrar(sid: int):
    s = db.q1("SELECT * FROM sessoes WHERE id=?", (sid,))
    if s and s["status"] == "ativa":
        novo = "aguardando_laudo" if s["aluno_id"] else "encerrada"
        db.ex("UPDATE sessoes SET status=?, fim=? WHERE id=?", (novo, time.time(), sid))
    return {"ok": True}


@A.post("/sessoes/{sid}/reavaliar")
async def sessao_reavaliar(sid: int):
    l = db.q1("SELECT * FROM laudos WHERE sessao_id=?", (sid,))
    if not l:
        raise HTTPException(400, "Sessão sem laudo.")
    await avaliacao.avaliar(sid, {**l, "diferenciais": (l["diferenciais"] or "").split(",")})
    return {"ok": True}


@A.delete("/sessoes/{sid}")
def sessao_excluir(sid: int):
    db.ex("DELETE FROM mensagens WHERE sessao_id=?", (sid,))
    db.ex("DELETE FROM laudos WHERE sessao_id=?", (sid,))
    db.ex("DELETE FROM sessoes WHERE id=?", (sid,))
    return {"ok": True}


# --- relatórios
@A.get("/relatorios")
def relatorios(request: Request):
    params = dict(request.query_params)
    w, args = _filtros(params)
    base = f"FROM sessoes s LEFT JOIN alunos a ON a.id=s.aluno_id LEFT JOIN laudos l ON l.sessao_id=s.id {w}"
    w2 = (w + " AND " if w else " WHERE ") + "l.id IS NOT NULL"
    base_l = f"FROM sessoes s LEFT JOIN alunos a ON a.id=s.aluno_id JOIN laudos l ON l.sessao_id=s.id {w2}"
    geral = db.q1(f"""SELECT COUNT(DISTINCT s.id) sessoes, COUNT(l.id) laudos, SUM(l.resultado='correto') corretos,
                      SUM(l.resultado='parcial') parciais, AVG(l.nota) media, COUNT(DISTINCT s.aluno_id) alunos {base}""", args)
    por_paciente = db.q(f"""SELECT p.id, p.nome, p.diagnostico_id, COUNT(l.id) laudos,
                               SUM(l.resultado='correto') corretos, SUM(l.resultado='parcial') parciais, AVG(l.nota) media
                            {base_l.replace('JOIN laudos', 'JOIN personas p ON p.id=s.persona_id JOIN laudos')}
                            GROUP BY p.id ORDER BY p.nome""", args)
    for r in por_paciente:
        r["diagnostico_nome"] = nome_diag(r["diagnostico_id"])
        erros = db.q(f"""SELECT l.hipotese_id, COUNT(*) n {base_l} AND s.persona_id=? AND l.resultado!='correto'
                         GROUP BY l.hipotese_id ORDER BY n DESC LIMIT 3""", (*args, r["id"]))
        r["confusoes"] = [{"hipotese": nome_diag(e["hipotese_id"]), "n": e["n"]} for e in erros]
    por_aluno = db.q(f"""SELECT a.id, a.nome, a.matricula, COUNT(l.id) laudos, SUM(l.resultado='correto') corretos,
                            AVG(l.nota) media, MAX(l.nota) melhor
                         {base_l} AND a.id IS NOT NULL GROUP BY a.id ORDER BY a.nome""", args)
    rub = db.q(f"SELECT l.rubrica_json {base_l}", args)
    crit_soma = {k: 0.0 for k, _, _ in avaliacao.CRITERIOS}
    n = 0
    for r in rub:
        try:
            cr = json.loads(r["rubrica_json"] or "{}").get("criterios", {})
            for k in crit_soma:
                crit_soma[k] += float(cr.get(k, 0))
            n += 1
        except ValueError:
            pass
    criterios = [{"nome": nm, "max": mx, "media": round(crit_soma[k] / n, 2) if n else 0}
                 for k, nm, mx in avaliacao.CRITERIOS]
    for lst in (por_paciente, por_aluno):
        for r in lst:
            r["media"] = round(r["media"] or 0, 1)
            r["taxa"] = round(100 * (r["corretos"] or 0) / r["laudos"], 1) if r["laudos"] else 0
    geral["media"] = round(geral["media"] or 0, 1)
    geral["taxa"] = round(100 * (geral["corretos"] or 0) / geral["laudos"], 1) if geral["laudos"] else 0
    return {"geral": geral, "por_paciente": por_paciente, "por_aluno": por_aluno, "criterios": criterios}


@A.get("/relatorios.csv")
def relatorios_csv(request: Request):
    w, args = _filtros(dict(request.query_params))
    linhas = db.q(SQL_SESSAO + w + " ORDER BY s.inicio", args)
    buf = io.StringIO()
    wr = csv.writer(buf, delimiter=";")
    wr.writerow(["Código", "Data", "Turma", "Aluno", "Matrícula", "Paciente", "Diagnóstico correto",
                 "Hipótese do aluno", "Resultado", "Nota", "Perguntas", "Duração (min)", "Origem", "Status"])
    for s in linhas:
        s = _fmt_sessao(s)
        wr.writerow([s["codigo"], s["inicio_fmt"], s["turma_nome"] or "", s["aluno_nome"] or "", s["matricula"] or "",
                     s["paciente_nome"], s["diagnostico_nome"], s["hipotese_nome"] or "", s["resultado"] or "",
                     str(s["nota"]).replace(".", ",") if s["nota"] is not None else "", s["n_perguntas"],
                     str(s["duracao_min"]).replace(".", ","), s["origem"], s["status"]])
    dados = "﻿" + buf.getvalue()  # BOM para o Excel abrir acentos corretamente
    return StreamingResponse(iter([dados]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=relatorio_robo_paciente.csv"})


# --- testes de configuração
@A.get("/teste/{servico}")
async def teste(servico: str):
    t0 = time.time()
    try:
        if servico == "llm":
            r = await ia.conversar([{"role": "user", "content": "Responda só: ok"}], max_tokens=10)
            det = r
        elif servico == "tts":
            mp3 = await ia.sintetizar_mp3("Olá, eu sou o paciente simulado.")
            det = f"{len(mp3)} bytes de áudio"
            return {"ok": True, "detalhe": det, "ms": int((time.time() - t0) * 1000),
                    "audio_b64": base64.b64encode(mp3).decode()}
        elif servico == "stt":
            mp3 = await ia.sintetizar_mp3("Bom dia, como você está se sentindo hoje?")
            det = await ia.transcrever(audio.pcm_para_wav(audio.para_pcm(mp3, 16000)))
        else:
            raise HTTPException(404)
        return {"ok": True, "detalhe": det, "ms": int((time.time() - t0) * 1000)}
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "detalhe": str(e) or repr(e), "ms": int((time.time() - t0) * 1000)}


@A.get("/config")
def ver_config():
    def mask(v):
        return (v[:4] + "…" + v[-4:]) if v and len(v) > 10 else ("(definida)" if v else "(vazia)")
    return {"LLM_BASE_URL": config.LLM_BASE_URL, "LLM_MODELO": config.LLM_MODELO, "LLM_API_KEY": mask(config.LLM_API_KEY),
            "STT_BASE_URL": config.STT_BASE_URL, "STT_MODELO": config.STT_MODELO, "STT_API_KEY": mask(config.STT_API_KEY),
            "TTS_PROVEDOR": config.TTS_PROVEDOR, "TTS_VOZ_PADRAO": config.TTS_VOZ_PADRAO,
            "MOSTRAR_RESULTADO_ALUNO": config.MOSTRAR_RESULTADO_ALUNO, "BANCO": str(config.DB_PATH),
            "url_ota": [f"http://{ip}:{config.PORTA}/xiaozhi/ota/" for ip in ips_locais()]}


# --- relatório imprimível (vira PDF pelo navegador)
@router.get("/relatorio/{sid}", response_class=HTMLResponse, dependencies=[Depends(admin)])
def relatorio_html(sid: int):
    d = sessao_detalhe(sid)
    s, p, l = d["sessao"], d["persona"], d["laudo"]
    e = html.escape
    msgs = "".join(
        f'<div class="m {m["papel"]}"><b>{"Estudante" if m["papel"] == "aluno" else p["nome"]}</b> '
        f'<span>{datetime.fromtimestamp(m["ts"]).strftime("%H:%M:%S")}</span><p>{e(m["texto"])}</p></div>'
        for m in d["mensagens"])
    if l:
        cor = {"correto": "#15803d", "parcial": "#b45309", "incorreto": "#b91c1c"}[l["resultado"]]
        crits = "".join(f"<tr><td>{e(c['nome'])}</td><td>{c['nota']:g} / {c['max']}</td></tr>" for c in l["criterios"])
        lista = lambda xs: "".join(f"<li>{e(x)}</li>" for x in xs) or "<li>—</li>"
        bloco_laudo = f"""
        <h2>Laudo do estudante</h2>
        <table class="kv">
          <tr><th>Hipótese principal</th><td>{e(nome_diag(l['hipotese_id']))}</td></tr>
          <tr><th>Diferenciais</th><td>{e(', '.join(l['diferenciais_nomes']) or '—')}</td></tr>
          <tr><th>Sintomas observados</th><td>{e(l['sintomas'] or '—')}</td></tr>
          <tr><th>Justificativa</th><td>{e(l['justificativa'] or '—')}</td></tr>
          <tr><th>Risco avaliado</th><td>{e(l['risco'] or '—')} (caso: {e(p['risco'])})</td></tr>
          <tr><th>Conduta</th><td>{e(l['conduta'] or '—')}</td></tr>
        </table>
        <h2>Avaliação</h2>
        <div class="nota" style="border-color:{cor}"><span style="color:{cor}">{l['resultado'].upper()}</span>
          <strong>{l['nota']:g}</strong>/100</div>
        <p>Diagnóstico correto: <b>{e(nome_diag(p['diagnostico_id']))}</b></p>
        <table class="kv"><tr><th>Diagnóstico</th><td>{l['nota_diagnostico']:g} / 60</td></tr>
          <tr><th>Risco</th><td>{l['nota_risco']:g} / 10</td></tr>
          <tr><th>Entrevista</th><td>{l['nota_entrevista']:g} / 30</td></tr>{crits}</table>
        <div class="cols"><div><h3>Pontos fortes</h3><ul>{lista(l['pontos_fortes'])}</ul></div>
        <div><h3>A melhorar</h3><ul>{lista(l['pontos_a_melhorar'])}</ul></div></div>
        <div class="cols"><div><h3>Sintomas investigados</h3><ul>{lista(l['sintomas_investigados'])}</ul></div>
        <div><h3>Sintomas não investigados</h3><ul>{lista(l['sintomas_nao_investigados'])}</ul></div></div>
        <h3>Devolutiva</h3><p>{e(l['feedback'] or '')}</p>"""
    else:
        bloco_laudo = "<h2>Laudo</h2><p>O estudante ainda não enviou o laudo.</p>"
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Relatório {s['codigo']}</title>
<style>body{{font-family:system-ui,Segoe UI,Arial;max-width:820px;margin:24px auto;color:#1f2937;font-size:14px}}
h1{{font-size:22px;margin:0}} h2{{font-size:17px;border-bottom:2px solid #7c3aed;padding-bottom:4px;margin-top:28px}}
.kv{{width:100%;border-collapse:collapse}} .kv th,.kv td{{text-align:left;border-bottom:1px solid #e5e7eb;padding:6px;vertical-align:top}}
.kv th{{width:190px;color:#6b7280;font-weight:600}} .m{{padding:6px 10px;margin:6px 0;border-radius:8px;break-inside:avoid}}
.m.aluno{{background:#eef2ff}} .m.paciente{{background:#f5f3ff}} .m span{{color:#9ca3af;font-size:11px}} .m p{{margin:2px 0 0}}
.nota{{display:inline-flex;gap:16px;align-items:baseline;border:2px solid;border-radius:10px;padding:8px 16px;font-size:16px}}
.nota strong{{font-size:28px}} .cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} .top{{display:flex;justify-content:space-between}}
button{{padding:8px 14px}} @media print{{button{{display:none}}}}</style></head><body>
<div class="top"><div><h1>Relatório de entrevista simulada</h1><div>Sessão {s['codigo']} · {s['inicio_fmt']} · {s['duracao_min']} min</div></div>
<button onclick="print()">Imprimir / salvar PDF</button></div>
<h2>Identificação</h2><table class="kv">
<tr><th>Estudante</th><td>{e(s['aluno_nome'] or 'Sessão avulsa')} {('· ' + e(s['matricula'])) if s['matricula'] else ''}</td></tr>
<tr><th>Turma</th><td>{e(s['turma_nome'] or '—')}</td></tr>
<tr><th>Paciente simulado</th><td>{e(p['nome'])}, {p['idade']} anos — {e(p['profissao'] or '')}</td></tr>
<tr><th>Origem</th><td>{e(s['origem'])} {('· ' + e(s['robo_nome'])) if s['robo_nome'] else ''}</td></tr>
<tr><th>Perguntas feitas</th><td>{s['n_perguntas']}</td></tr></table>
{bloco_laudo}
<h2>Transcrição</h2>{msgs or '<p>Sem mensagens.</p>'}
<p style="color:#9ca3af;font-size:11px;margin-top:30px">Avaliação gerada automaticamente para fins didáticos; deve ser revisada pelo(a) docente.</p>
</body></html>"""
