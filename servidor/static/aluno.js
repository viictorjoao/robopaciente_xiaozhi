// Página do aluno: identificação -> entrevista -> laudo -> resultado
const T = $("#tela");
let INFO, CODIGO = new URLSearchParams(location.search).get("s") || localStorage.getItem("rp_sessao"), poll = null;

function passo(n) { for (let i = 1; i <= 4; i++) $("#p" + i).className = i < n ? "ok" : i === n ? "at" : ""; }
function guardar(c) { CODIGO = c; if (c) localStorage.setItem("rp_sessao", c); else localStorage.removeItem("rp_sessao"); history.replaceState(null, "", c ? "?s=" + c : "/aluno"); }

async function inicio() {
  INFO = await api("/api/info");
  if (CODIGO) {
    try { return mostrarSessao(await api("/api/aluno/sessao/" + CODIGO)); } catch { guardar(null); }
  }
  identificacao();
}

async function identificacao() {
  passo(1); clearInterval(poll);
  const o = await api("/api/aluno/opcoes");
  const salvo = JSON.parse(localStorage.getItem("rp_aluno") || "{}");
  T.innerHTML = `
  <div class="card">
    <h3>Quem é você?</h3>
    <form id="fi">
      <div class="grid g2"><div><label>Nome completo</label><input name="nome" required value="${esc(salvo.nome || "")}"></div>
      <div><label>Matrícula</label><input name="matricula" required value="${esc(salvo.matricula || "")}"></div></div>
      <label>Turma</label><select name="turma_id">${o.turmas.map((t) => `<option value="${t.id}" ${t.id == salvo.turma_id ? "selected" : ""}>${esc(t.nome)}</option>`).join("")}</select>
      <h3 style="margin-top:18px">Com quem você vai conversar?</h3>
      ${o.robos.map((r) => `<label class="card linha" style="margin:6px 0;cursor:pointer;font-weight:500">
        <input type="radio" name="alvo" value="r${r.id}" style="width:auto" ${!r.online || r.ocupado ? "disabled" : ""}>
        <span class="dot ${r.online ? "on" : ""}"></span><b>${esc(r.nome)}</b> — paciente: ${esc(r.paciente)}
        <span class="esp"></span>${r.ocupado ? '<span class="tag warn">em uso</span>' : r.online ? '<span class="tag ok">disponível</span>' : '<span class="tag">desligado</span>'}</label>`).join("")}
      <details style="margin-top:8px"><summary>Sem robô? Converse pelo computador</summary>
        ${o.pacientes.map((p) => `<label class="linha" style="font-weight:500;margin:6px 0"><input type="radio" name="alvo" value="p${p.id}" style="width:auto"> ${esc(p.rotulo)}</label>`).join("")}
      </details>
      <div id="err" class="erro" style="display:none;margin-top:10px"></div>
      <button class="btn pri grande" style="margin-top:16px">Começar entrevista</button>
    </form>
  </div>`;
  $("#fi").onsubmit = async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target));
    if (!d.alvo) return erro("Escolha um robô ou um paciente.");
    localStorage.setItem("rp_aluno", JSON.stringify({ nome: d.nome, matricula: d.matricula, turma_id: d.turma_id }));
    const corpo = { nome: d.nome, matricula: d.matricula, turma_id: d.turma_id };
    if (d.alvo[0] === "r") corpo.dispositivo_id = +d.alvo.slice(1); else corpo.persona_id = +d.alvo.slice(1);
    try { const r = await api("/api/aluno/sessao", { method: "POST", body: corpo }); guardar(r.codigo); mostrarSessao(await api("/api/aluno/sessao/" + r.codigo)); }
    catch (err) { erro(err.message); }
  };
}
function erro(m) { const el = $("#err"); el.textContent = m; el.style.display = "block"; }

function mostrarSessao(s) {
  if (s.laudo) return resultado(s);
  if (s.status === "ativa") return entrevista(s);
  if (s.status === "aguardando_laudo") return laudo(s);
  guardar(null); identificacao();
}

function entrevista(s) {
  passo(2);
  const robo = s.origem === "robo";
  T.innerHTML = `
  <div class="card">
    <div class="linha"><div><h3 style="margin:0">Paciente: ${esc(s.paciente.nome)}, ${s.paciente.idade} anos</h3>
    <div class="small muted">Sessão ${s.codigo} · ${esc(s.aluno?.nome || "")}</div></div></div>
    ${robo ? `<div class="aviso" style="margin-top:12px">🤖 Converse com o robô: <b>aperte o botão</b> do robô e fale normalmente. Espere ele terminar de responder antes de perguntar de novo. A conversa aparece abaixo.</div>` : ""}
    <div class="chat" id="chat" style="margin-top:14px;min-height:260px"></div>
    ${robo ? "" : `<form id="fm" class="linha" style="margin-top:12px"><button type="button" class="mic" id="mic" title="Segure para falar">🎤</button>
      <input id="txt" placeholder="Digite sua pergunta ao paciente…" style="flex:1"><button class="btn pri">Enviar</button></form>
      <label class="linha small" style="font-weight:500"><input type="checkbox" id="voz" style="width:auto" checked> Ouvir a voz do paciente</label>`}
    <div id="st" class="small muted"></div>
  </div>
  <div class="linha"><span class="esp"></span><button class="btn pri grande" id="fim">Finalizar entrevista e escrever o laudo →</button></div>`;
  let msgs = s.mensagens;
  renderChat($("#chat"), msgs, s.paciente.nome);
  clearInterval(poll);
  poll = setInterval(async () => {
    const n = await api("/api/aluno/sessao/" + s.codigo);
    if (n.status !== "ativa") { clearInterval(poll); return mostrarSessao(n); }
    if (n.mensagens.length !== msgs.length) { msgs = n.mensagens; renderChat($("#chat"), msgs, s.paciente.nome); }
  }, robo ? 2000 : 6000);
  $("#fim").onclick = async () => {
    if (!confirm("Finalizar a entrevista? Depois disso não dá para fazer mais perguntas.")) return;
    clearInterval(poll);
    await api(`/api/aluno/sessao/${s.codigo}/finalizar`, { method: "POST" });
    mostrarSessao(await api("/api/aluno/sessao/" + s.codigo));
  };
  if (robo) return;
  const st = (on) => ($("#st").textContent = on ? `${s.paciente.nome} está respondendo…` : "");
  const resp = (r) => {
    if (r.aviso) return toast(r.aviso);
    msgs = [...msgs, { papel: "aluno", texto: r.aluno }, { papel: "paciente", texto: r.paciente }];
    renderChat($("#chat"), msgs, s.paciente.nome);
    if ($("#voz").checked) tocarB64(r.audio_b64);
  };
  $("#fm").onsubmit = async (e) => {
    e.preventDefault(); const t = $("#txt").value.trim(); if (!t) return;
    $("#txt").value = ""; st(true);
    try { resp(await api(`/api/aluno/sessao/${s.codigo}/mensagem`, { method: "POST", body: { texto: t, voz: $("#voz").checked } })); }
    catch (err) { toast(err.message, 6000); } finally { st(false); }
  };
  ligarMicrofone($("#mic"), async (blob) => {
    const fd = new FormData(); fd.append("arquivo", blob, "fala.webm"); st(true);
    try { resp(await api(`/api/aluno/sessao/${s.codigo}/audio`, { method: "POST", body: fd })); }
    catch (err) { toast(err.message, 6000); } finally { st(false); }
  });
}

function laudo(s) {
  passo(3); clearInterval(poll);
  const ops = INFO.diagnosticos.map((d) => `<option value="${d.id}">${esc(d.nome)} — ${d.cid}</option>`).join("");
  T.innerHTML = `
  <div class="card">
    <h3>Laudo / parecer — paciente ${esc(s.paciente.nome)}</h3>
    <details><summary>Rever a conversa</summary><div class="chat" id="chat" style="max-height:300px"></div></details>
    <form id="fl">
      <label>Hipótese diagnóstica principal (CID-11)</label><select name="hipotese_id" required><option value="">Escolha…</option>${ops}</select>
      <label>Diagnósticos diferenciais considerados (Ctrl+clique para vários)</label><select name="diferenciais" multiple size="5">${ops}</select>
      <label>Sintomas e sinais observados na entrevista</label><textarea name="sintomas" required placeholder="Ex.: preocupação excessiva há mais de 6 meses, insônia inicial…"></textarea>
      <label>Justificativa da hipótese</label><textarea name="justificativa" required rows="4" placeholder="Explique por que os sintomas sustentam a hipótese e por que descartou os diferenciais."></textarea>
      <div class="grid g2">
        <div><label>Avaliação de risco (ideação suicida / autolesão)</label><select name="risco" required><option value="">Escolha…</option>${INFO.riscos.map((r) => `<option>${r}</option>`).join("")}</select></div>
        <div><label>Conduta / encaminhamento</label><input name="conduta" placeholder="Ex.: psicoterapia TCC, avaliação psiquiátrica…"></div>
      </div>
      <div id="err" class="erro" style="display:none;margin-top:10px"></div>
      <button class="btn pri grande" id="env" style="margin-top:16px">Enviar laudo</button>
    </form>
  </div>`;
  renderChat($("#chat"), s.mensagens, s.paciente.nome);
  $("#fl").onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target), d = Object.fromEntries(f);
    d.diferenciais = f.getAll("diferenciais");
    $("#env").disabled = true; $("#env").textContent = "Avaliando… (pode levar alguns segundos)";
    try { resultado(await api(`/api/aluno/sessao/${s.codigo}/laudo`, { method: "POST", body: d })); }
    catch (err) { erro(err.message); $("#env").disabled = false; $("#env").textContent = "Enviar laudo"; }
  };
}

function resultado(s) {
  passo(4); clearInterval(poll);
  const l = s.laudo;
  const novo = '<button class="btn pri grande" id="nova">Nova entrevista</button>';
  if (!l.resultado) {
    T.innerHTML = `<div class="card"><h3>Laudo enviado ✔</h3><p>Seu professor vai analisar a entrevista e o laudo.</p>${novo}</div>`;
  } else {
    const cor = { correto: "var(--ok)", parcial: "var(--warn)", incorreto: "var(--bad)" }[l.resultado];
    const lista = (xs) => (xs?.length ? `<ul>${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : '<p class="muted small">—</p>');
    T.innerHTML = `
    <div class="card">
      <div class="resultado"><div class="num" style="color:${cor}">${l.nota}</div>
      <div><div>${tagResultado(l.resultado)}</div><div class="small muted">Diagnóstico ${l.nota_diagnostico}/60 · Risco ${l.nota_risco}/10 · Entrevista ${l.nota_entrevista}/30</div></div></div>
      <p>Sua hipótese: <b>${esc(l.hipotese)}</b><br>Diagnóstico do caso: <b>${esc(l.correto)}</b></p>
      <h3>Sua entrevista</h3>
      ${l.criterios.map((c) => `<div class="small linha" style="margin-top:6px"><span class="esp">${esc(c.nome)}</span><b>${c.nota}/${c.max}</b></div><div class="barra"><i style="width:${(100 * c.nota) / c.max}%"></i></div>`).join("")}
      <div class="grid g2" style="margin-top:12px"><div><h3>Pontos fortes</h3>${lista(l.pontos_fortes)}</div><div><h3>Para melhorar</h3>${lista(l.pontos_a_melhorar)}</div></div>
      ${l.sintomas_nao_investigados?.length ? `<h3>Sintomas que você não investigou</h3>${lista(l.sintomas_nao_investigados)}` : ""}
      <p style="background:#faf9fe;padding:12px;border-radius:10px">${esc(l.feedback)}</p>
      <p class="small muted">Correção automática para fins didáticos — seu professor pode revisar.</p>
      ${novo}
    </div>`;
  }
  $("#nova").onclick = () => { guardar(null); identificacao(); };
}

inicio();
