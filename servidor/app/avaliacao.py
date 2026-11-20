"""Correção do laudo do aluno.

Nota (0-100):
  - Diagnóstico (60): hipótese principal = diagnóstico do perfil -> 60;
    hipótese entre os diferenciais aceitos, ou o diagnóstico correto listado
    como diferencial pelo aluno -> 30; caso contrário 0.
  - Avaliação de risco (10): nível igual -> 10; nível vizinho -> 5.
  - Entrevista e raciocínio (30): rubrica avaliada pela IA a partir da transcrição
    (com regra simples de reserva se a IA estiver indisponível).
"""
import json
import logging
import re
import time

from . import db, ia
from .catalogo import DIAG_POR_ID, NIVEIS_RISCO, nome_diag

log = logging.getLogger("avaliacao")

CRITERIOS = [
    ("rapport", "Acolhimento e vínculo (rapport)", 5),
    ("perguntas_abertas", "Uso de perguntas abertas", 5),
    ("investigacao_sintomas", "Investigação dos sintomas-chave", 10),
    ("avaliacao_risco", "Investigação de risco (ideação, autocuidado)", 5),
    ("coerencia_laudo", "Coerência do laudo com a entrevista", 5),
]


def _transcricao(msgs):
    nomes = {"aluno": "ESTUDANTE", "paciente": "PACIENTE"}
    return "\n".join(f"{nomes.get(m['papel'], m['papel'])}: {m['texto']}" for m in msgs if m["papel"] in nomes)


async def _rubrica_ia(persona, msgs, laudo):
    sintomas = [s.strip() for s in (persona.get("sintomas_chave") or "").splitlines() if s.strip()]
    crit = "\n".join(f'- "{k}": {nome} (0 a {mx})' for k, nome, mx in CRITERIOS)
    prompt = f"""Você é um(a) professor(a) supervisor(a) de estágio em Psicologia avaliando a entrevista inicial
de um estudante com um paciente SIMULADO. Seja justo(a), específico(a) e construtivo(a). Escreva em português do Brasil.

Diagnóstico correto do caso: {nome_diag(persona.get('diagnostico_id'))}
Nível de risco do caso: {persona.get('risco')}
Sintomas-chave que deveriam ser investigados:
{chr(10).join('- ' + s for s in sintomas)}

TRANSCRIÇÃO DA ENTREVISTA:
{_transcricao(msgs) or '(vazia)'}

LAUDO DO ESTUDANTE:
- Hipótese principal: {nome_diag(laudo.get('hipotese_id'))}
- Diferenciais: {', '.join(nome_diag(d) for d in laudo.get('diferenciais_lista', [])) or '—'}
- Sintomas observados: {laudo.get('sintomas') or '—'}
- Justificativa: {laudo.get('justificativa') or '—'}
- Risco avaliado: {laudo.get('risco') or '—'}
- Conduta/encaminhamento: {laudo.get('conduta') or '—'}

Responda SOMENTE com um JSON neste formato:
{{
  "criterios": {{ {", ".join(f'"{k}": 0' for k, _, _ in CRITERIOS)} }},
  "sintomas_investigados": ["..."],
  "sintomas_nao_investigados": ["..."],
  "pontos_fortes": ["..."],
  "pontos_a_melhorar": ["..."],
  "feedback": "um parágrafo curto dirigido ao estudante (use 'você')"
}}
Critérios e pontuação máxima:
{crit}
Use apenas os nomes da lista de sintomas-chave em sintomas_investigados / sintomas_nao_investigados."""
    txt = await ia.conversar([{"role": "user", "content": prompt}], temperatura=0.2, json_mode=True, max_tokens=900)
    r = ia.extrair_json(txt)
    crits = {}
    for k, _, mx in CRITERIOS:
        try:
            crits[k] = max(0.0, min(float(r.get("criterios", {}).get(k, 0)), mx))
        except (TypeError, ValueError):
            crits[k] = 0.0
    r["criterios"] = crits
    r["origem"] = "ia"
    return r


def _rubrica_simples(persona, msgs, laudo):
    perguntas = [m["texto"].lower() for m in msgs if m["papel"] == "aluno"]
    n = len(perguntas)
    abertas = sum(1 for p in perguntas if re.match(r"^(como|o que|por que|porque|me (conta|fala)|fale|conte|descreva|qual|quais)", p))
    risco_palavras = ("morte", "morrer", "suic", "se machucar", "tirar a (sua|própria) vida", "vontade de viver")
    perguntou_risco = any(re.search(w, p) for p in perguntas for w in risco_palavras)
    acolhe = any(re.search(r"(entendo|imagino|deve ser difícil|obrigad|fique à vontade|estou aqui)", p) for p in perguntas)
    crits = {
        "rapport": 4.0 if acolhe else 2.0,
        "perguntas_abertas": round(5 * min(1.0, abertas / max(1, n) * 2), 1),
        "investigacao_sintomas": float(min(10, n)),
        "avaliacao_risco": 5.0 if perguntou_risco else 0.0,
        "coerencia_laudo": 3.0 if (laudo.get("justificativa") or "").strip() else 0.0,
    }
    return {"criterios": crits, "sintomas_investigados": [], "sintomas_nao_investigados": [],
            "pontos_fortes": [], "pontos_a_melhorar": [],
            "feedback": "Avaliação automática simplificada (a IA estava indisponível). "
                        f"Você fez {n} perguntas, {abertas} delas abertas"
                        + ("; investigou risco." if perguntou_risco else "; não investigou risco de forma explícita."),
            "origem": "regras"}


async def avaliar(sessao_id: int, laudo: dict) -> dict:
    sessao = db.q1("SELECT * FROM sessoes WHERE id=?", (sessao_id,))
    persona = db.q1("SELECT * FROM personas WHERE id=?", (sessao["persona_id"],))
    msgs = db.mensagens(sessao_id)

    dif = [d for d in (laudo.get("diferenciais") or []) if d in DIAG_POR_ID]
    laudo["diferenciais_lista"] = dif
    correto = persona.get("diagnostico_id")
    aceitos = [d.strip() for d in (persona.get("diferenciais_aceitos") or "").split(",") if d.strip()]
    h = laudo.get("hipotese_id")
    if h == correto:
        resultado, nd = "correto", 60.0
    elif h in aceitos or correto in dif:
        resultado, nd = "parcial", 30.0
    else:
        resultado, nd = "incorreto", 0.0

    nr = 0.0
    if laudo.get("risco") in NIVEIS_RISCO and persona.get("risco") in NIVEIS_RISCO:
        dist = abs(NIVEIS_RISCO.index(laudo["risco"]) - NIVEIS_RISCO.index(persona["risco"]))
        nr = 10.0 if dist == 0 else (5.0 if dist == 1 else 0.0)

    try:
        rub = await _rubrica_ia(persona, msgs, laudo)
    except Exception as e:  # sem internet / sem chave / JSON inválido
        log.warning("rubrica IA falhou: %s", e)
        rub = _rubrica_simples(persona, msgs, laudo)
    ne = round(sum(rub["criterios"].values()), 1)
    nota = round(nd + nr + ne, 1)

    dados = dict(
        sessao_id=sessao_id, hipotese_id=h, diferenciais=",".join(dif),
        sintomas=laudo.get("sintomas"), justificativa=laudo.get("justificativa"),
        risco=laudo.get("risco"), conduta=laudo.get("conduta"),
        resultado=resultado, nota=nota, nota_diagnostico=nd, nota_risco=nr, nota_entrevista=ne,
        feedback=rub.get("feedback", ""), rubrica_json=json.dumps(rub, ensure_ascii=False),
        criado_em=time.time())
    db.ex("DELETE FROM laudos WHERE sessao_id=?", (sessao_id,))
    db.inserir("laudos", dados)
    db.ex("UPDATE sessoes SET status='avaliada', fim=COALESCE(fim, ?) WHERE id=?", (time.time(), sessao_id))
    return dados
