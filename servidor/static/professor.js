// Área do professor
let INFO = null, VISTA = "painel", timer = null;
const C = $("#conteudo");
const diagNome = (id) => { const d = INFO.diagnosticos.find((x) => x.id === id); return d ? `${d.nome} (${d.cid})` : (id || "—"); };
const opcoesDiag = (sel) => INFO.diagnosticos.map((d) => `<option value="${d.id}" ${d.id === sel ? "selected" : ""}>${esc(d.nome)} — ${d.cid}</option>`).join("");

function aoDeslogar() { $("#app").style.display = "none"; $("#login").style.display = "block"; }

async function iniciar() {
  INFO = await api("/api/info");
  const me = await api("/api/me");
  if (!me.admin) return aoDeslogar();
  $("#login").style.display = "none"; $("#app").style.display = "grid";
  ir(location.hash.slice(1) || "painel");
}

$("#formLogin").onsubmit = async (e) => {
  e.preventDefault();
  try { await api("/api/login", { method: "POST", body: { senha: $("#senha").value } }); iniciar(); }
  catch (err) { const el = $("#erroLogin"); el.textContent = err.message; el.style.display = "block"; }
};
$("#sair").onclick = async () => { await api("/api/logout", { method: "POST" }); aoDeslogar(); };
document.querySelectorAll("nav.lado button[data-v]").forEach((b) => (b.onclick = () => ir(b.dataset.v)));

function ir(v) {
  VISTA = v; location.hash = v;
  clearInterval(timer); timer = null;
  document.querySelectorAll("nav.lado button[data-v]").forEach((b) => b.classList.toggle("ativo", b.dataset.v === v));
  C.innerHTML = '<div class="vazio">Carregando…</div>';
  ({ painel, sessoes, relatorios, pacientes, robos, turmas, simulador, config: configuracao }[v] || painel)()
    .catch((e) => (C.innerHTML = `<div class="erro">${esc(e.message)}</div>`));
}

function abrirModal(html) {
  $("#modal").innerHTML = `<div class="modal-fundo"><div class="modal"><button class="fechar">×</button>${html}</div></div>`;
  $("#modal .fechar").onclick = fecharModal;
  $("#modal .modal-fundo").onclick = (e) => { if (e.target.classList.contains("modal-fundo")) fecharModal(); };
  return $("#modal .modal");
}
function fecharModal() { $("#modal").innerHTML = ""; if (window._modalTimer) clearInterval(window._modalTimer); }

// ------------------------------------------------------------------ PAINEL
async function painel() {
  const d = await api("/api/admin/painel");
  C.innerHTML = `
  <div class="topo"><h2>Painel</h2><span class="muted small">Atualiza sozinho a cada 5 s</span></div>
  <div class="grid g4">
    <div class="kpi"><span>Sessões hoje</span><b>${d.sessoes_hoje}</b></div>
    <div class="kpi"><span>Laudos avaliados</span><b>${d.laudos}</b></div>
    <div class="kpi"><span>Taxa de acerto do diagnóstico</span><b>${d.taxa_acerto}%</b><div class="small muted">${d.corretos} corretos · ${d.parciais} parciais</div></div>
    <div class="kpi"><span>Robôs online</span><b>${d.robos_online} / ${d.robos}</b></div>
  </div>
  <div class="grid g2" style="margin-top:16px">
    <div class="card"><h3>Entrevistas em andamento</h3>${tabelaSessoes(d.ativas, true)}</div>
    <div class="card"><h3>Últimos laudos</h3>${tabelaSessoes(d.recentes, true)}</div>
  </div>`;
  ligarLinhas();
  if (!timer) timer = setInterval(() => VISTA === "painel" && !$("#modal").innerHTML && painel(), 5000);
}

function tabelaSessoes(lista, compacta) {
  if (!lista.length) return '<div class="vazio">Nada por aqui ainda.</div>';
  return `<table class="t"><tr><th>Código</th><th>Estudante</th><th>Paciente</th>${compacta ? "" : "<th>Turma</th><th>Data</th><th>Perg.</th>"}<th>Status</th><th>Resultado</th><th>Nota</th></tr>
  ${lista.map((s) => `<tr class="clic" data-sid="${s.id}">
    <td><b>${s.codigo}</b></td><td>${esc(s.aluno_nome || "avulsa")}</td><td>${esc(s.paciente_nome)}</td>
    ${compacta ? "" : `<td>${esc(s.turma_nome || "—")}</td><td class="small">${s.inicio_fmt}</td><td>${s.n_perguntas}</td>`}
    <td>${tagStatus(s.status)}</td><td>${tagResultado(s.resultado)}</td><td>${s.nota ?? "—"}</td></tr>`).join("")}</table>`;
}
function ligarLinhas() { C.querySelectorAll("tr[data-sid]").forEach((tr) => (tr.onclick = () => detalheSessao(+tr.dataset.sid))); }

// ------------------------------------------------------------------ SESSÃO (detalhe)
async function detalheSessao(sid) {
  const d = await api(`/api/admin/sessoes/${sid}`);
  const s = d.sessao, l = d.laudo, p = d.persona;
  const m = abrirModal(`
    <div class="linha"><h2 style="margin:0">Sessão ${s.codigo}</h2>${tagStatus(s.status)}${tagResultado(l?.resultado)}</div>
    <p class="muted">${esc(s.aluno_nome || "Sessão avulsa")} ${s.matricula ? "· " + esc(s.matricula) : ""} · ${esc(s.turma_nome || "")} · ${s.inicio_fmt} · ${s.duracao_min} min · ${s.origem}${s.robo_nome ? " (" + esc(s.robo_nome) + ")" : ""}</p>
    <div class="grid g2">
      <div><h3>Conversa com ${esc(p.nome)}</h3><div class="chat card" id="chatDet" style="max-height:420px"></div></div>
      <div>${l ? blocoLaudo(l, p) : `<div class="card"><h3>Laudo</h3><p class="muted">Ainda não enviado.</p><p class="small">Diagnóstico do caso: <b>${esc(diagNome(p.diagnostico_id))}</b></p></div>`}</div>
    </div>
    <div class="linha" style="margin-top:12px">
      <a class="btn" href="/relatorio/${s.id}" target="_blank">🖨️ Relatório para imprimir/PDF</a>
      ${s.status === "ativa" ? '<button class="btn" id="btEnc">⏹ Encerrar entrevista</button>' : ""}
      ${l ? '<button class="btn" id="btReav">↻ Reavaliar com IA</button>' : ""}
      <span class="esp"></span><button class="btn perigo" id="btDel">Excluir sessão</button>
    </div>`);
  renderChat($("#chatDet", m), d.mensagens, p.nome);
  $("#btDel", m).onclick = async () => { if (confirm("Excluir esta sessão e a conversa?")) { await api(`/api/admin/sessoes/${sid}`, { method: "DELETE" }); fecharModal(); ir(VISTA); } };
  if ($("#btEnc", m)) $("#btEnc", m).onclick = async () => { await api(`/api/admin/sessoes/${sid}/encerrar`, { method: "POST" }); detalheSessao(sid); };
  if ($("#btReav", m)) $("#btReav", m).onclick = async (e) => { e.target.disabled = true; e.target.textContent = "Avaliando…"; await api(`/api/admin/sessoes/${sid}/reavaliar`, { method: "POST" }); detalheSessao(sid); };
  if (s.status === "ativa") {
    window._modalTimer = setInterval(async () => {
      if (!$("#chatDet")) return clearInterval(window._modalTimer);
      const n = await api(`/api/admin/sessoes/${sid}`);
      renderChat($("#chatDet"), n.mensagens, p.nome);
    }, 2500);
  }
}

function blocoLaudo(l, p) {
  const lista = (xs) => (xs?.length ? `<ul class="small">${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : '<p class="small muted">—</p>');
  return `<div class="card">
    <div class="resultado"><div class="num">${l.nota}</div><div>${tagResultado(l.resultado)}<div class="small muted">Diag. ${l.nota_diagnostico}/60 · Risco ${l.nota_risco}/10 · Entrevista ${l.nota_entrevista}/30</div></div></div>
    <p class="small"><b>Hipótese do aluno:</b> ${esc(diagNome(l.hipotese_id))}<br><b>Correto:</b> ${esc(diagNome(p.diagnostico_id))}<br>
    <b>Diferenciais:</b> ${esc(l.diferenciais_nomes.join(", ") || "—")}<br><b>Risco:</b> ${esc(l.risco || "—")} (caso: ${esc(p.risco)})</p>
    <details><summary>Justificativa e conduta do aluno</summary><p class="small"><b>Sintomas:</b> ${esc(l.sintomas || "—")}</p><p class="small"><b>Justificativa:</b> ${esc(l.justificativa || "—")}</p><p class="small"><b>Conduta:</b> ${esc(l.conduta || "—")}</p></details>
    <details open><summary>Rubrica da entrevista</summary>${l.criterios.map((c) => `<div class="small linha"><span class="esp">${esc(c.nome)}</span><b>${c.nota}/${c.max}</b></div><div class="barra"><i style="width:${(100 * c.nota) / c.max}%"></i></div>`).join("")}</details>
    <details><summary>Sintomas investigados / não investigados</summary><div class="grid g2"><div>${lista(l.sintomas_investigados)}</div><div>${lista(l.sintomas_nao_investigados)}</div></div></details>
    <details><summary>Pontos fortes e a melhorar</summary>${lista(l.pontos_fortes)}${lista(l.pontos_a_melhorar)}</details>
    <p class="small" style="background:#faf9fe;padding:10px;border-radius:8px">${esc(l.feedback || "")}</p>
  </div>`;
}

// ------------------------------------------------------------------ SESSÕES
async function sessoes() {
  const turmas = await api("/api/admin/turmas");
  const personas = await api("/api/admin/personas");
  C.innerHTML = `
  <div class="topo"><h2>Sessões</h2></div>
  <div class="card linha">
    <div><label>Turma</label><select id="fT"><option value="">Todas</option>${turmas.map((t) => `<option value="${t.id}">${esc(t.nome)}</option>`).join("")}</select></div>
    <div><label>Paciente</label><select id="fP"><option value="">Todos</option>${personas.map((p) => `<option value="${p.id}">${esc(p.nome)}</option>`).join("")}</select></div>
    <div><label>Status</label><select id="fS"><option value="">Todos</option><option value="ativa">Em andamento</option><option value="aguardando_laudo">Aguardando laudo</option><option value="avaliada">Avaliada</option><option value="encerrada">Encerrada</option></select></div>
    <div><label>De</label><input type="date" id="fDe"></div><div><label>Até</label><input type="date" id="fAte"></div>
    <div class="esp"><label>Buscar</label><input id="fB" placeholder="nome, matrícula ou código"></div>
  </div>
  <div class="card" id="lista"></div>`;
  const carregar = async () => {
    const q = new URLSearchParams({ turma_id: $("#fT").value, persona_id: $("#fP").value, status: $("#fS").value, de: $("#fDe").value, ate: $("#fAte").value, busca: $("#fB").value });
    const l = await api("/api/admin/sessoes?" + q);
    $("#lista").innerHTML = tabelaSessoes(l, false);
    ligarLinhas();
  };
  C.querySelectorAll(".card select, .card input").forEach((el) => (el.oninput = carregar));
  carregar();
}

// ------------------------------------------------------------------ RELATÓRIOS
async function relatorios() {
  const turmas = await api("/api/admin/turmas");
  C.innerHTML = `
  <div class="topo"><h2>Relatórios</h2><a class="btn" id="csv">⬇ Exportar planilha (CSV)</a></div>
  <div class="card linha">
    <div><label>Turma</label><select id="rT"><option value="">Todas</option>${turmas.map((t) => `<option value="${t.id}">${esc(t.nome)}</option>`).join("")}</select></div>
    <div><label>De</label><input type="date" id="rDe"></div><div><label>Até</label><input type="date" id="rAte"></div>
  </div><div id="rel"></div>`;
  const carregar = async () => {
    const q = new URLSearchParams({ turma_id: $("#rT").value, de: $("#rDe").value, ate: $("#rAte").value });
    $("#csv").href = "/api/admin/relatorios.csv?" + q;
    const r = await api("/api/admin/relatorios?" + q);
    const g = r.geral;
    $("#rel").innerHTML = `
    <div class="grid g4">
      <div class="kpi"><span>Sessões</span><b>${g.sessoes}</b><div class="small muted">${g.alunos} estudantes</div></div>
      <div class="kpi"><span>Laudos</span><b>${g.laudos}</b></div>
      <div class="kpi"><span>Diagnósticos corretos</span><b>${g.taxa}%</b><div class="small muted">${g.corretos || 0} corretos · ${g.parciais || 0} parciais</div></div>
      <div class="kpi"><span>Nota média</span><b>${g.media}</b></div>
    </div>
    <div class="grid g2" style="margin-top:16px">
      <div class="card"><h3>Acertos por paciente</h3>${r.por_paciente.length ? `<table class="t"><tr><th>Paciente / caso</th><th>Laudos</th><th>Acerto</th><th>Média</th></tr>
        ${r.por_paciente.map((p) => `<tr><td><b>${esc(p.nome)}</b><div class="small muted">${esc(p.diagnostico_nome)}</div>
        ${p.confusoes.length ? `<div class="small" style="color:var(--warn)">Confundido com: ${p.confusoes.map((c) => `${esc(c.hipotese)} (${c.n})`).join("; ")}</div>` : ""}</td>
        <td>${p.laudos}</td><td><div class="barra" style="width:90px"><i style="width:${p.taxa}%"></i></div><span class="small">${p.taxa}%</span></td><td>${p.media}</td></tr>`).join("")}</table>` : '<div class="vazio">Sem laudos no período.</div>'}</div>
      <div class="card"><h3>Habilidades de entrevista (média da turma)</h3>
        ${r.criterios.map((c) => `<div class="small linha" style="margin-top:8px"><span class="esp">${esc(c.nome)}</span><b>${c.media} / ${c.max}</b></div><div class="barra"><i style="width:${(100 * c.media) / c.max}%"></i></div>`).join("")}
      </div>
    </div>
    <div class="card"><h3>Desempenho por estudante</h3>${r.por_aluno.length ? `<table class="t"><tr><th>Estudante</th><th>Matrícula</th><th>Laudos</th><th>Corretos</th><th>Taxa</th><th>Média</th><th>Melhor</th></tr>
      ${r.por_aluno.map((a) => `<tr><td>${esc(a.nome)}</td><td>${esc(a.matricula)}</td><td>${a.laudos}</td><td>${a.corretos || 0}</td><td>${a.taxa}%</td><td>${a.media}</td><td>${a.melhor ?? "—"}</td></tr>`).join("")}</table>` : '<div class="vazio">Sem dados.</div>'}</div>`;
  };
  C.querySelectorAll(".card select, .card input").forEach((el) => (el.oninput = carregar));
  carregar();
}

// ------------------------------------------------------------------ PACIENTES
async function pacientes() {
  const lista = await api("/api/admin/personas");
  C.innerHTML = `
  <div class="topo"><h2>Pacientes simulados</h2><button class="btn pri" id="novo">+ Novo paciente</button></div>
  <p class="muted">Cada perfil define quem o robô interpreta: história, sintomas, jeito de falar e o diagnóstico correto usado para corrigir os laudos.</p>
  <div class="grid g3">${lista.map((p) => `
    <div class="card persona-card" style="${p.ativo ? "" : "opacity:.55"}">
      <div class="linha"><div class="av">${esc(p.nome[0])}</div><div><b>${esc(p.nome)}</b>, ${p.idade}<div class="small muted">${esc(p.profissao || "")}</div></div></div>
      <div class="small">“${esc(p.queixa_principal || "")}”</div>
      <div class="linha"><span class="tag pri">${esc(diagNome(p.diagnostico_id))}</span><span class="tag">risco ${esc(p.risco)}</span><span class="tag">abertura ${p.abertura}/5</span>${p.ativo ? "" : '<span class="tag">arquivado</span>'}</div>
      <div class="linha" style="margin-top:6px"><button class="btn peq" data-ed="${p.id}">Editar</button><button class="btn peq" data-dup="${p.id}">Duplicar</button><button class="btn peq" data-sim="${p.id}">Testar</button></div>
    </div>`).join("")}</div>`;
  $("#novo").onclick = () => editarPersona(null);
  C.querySelectorAll("[data-ed]").forEach((b) => (b.onclick = () => editarPersona(lista.find((p) => p.id == b.dataset.ed))));
  C.querySelectorAll("[data-dup]").forEach((b) => (b.onclick = async () => { await api(`/api/admin/personas/${b.dataset.dup}/duplicar`, { method: "POST" }); pacientes(); }));
  C.querySelectorAll("[data-sim]").forEach((b) => (b.onclick = () => { window._simPersona = +b.dataset.sim; ir("simulador"); }));
}

function editarPersona(p) {
  p = p || { nome: "", idade: 30, genero: "feminino", abertura: 3, risco: "ausente", voz: INFO.vozes[0].id, velocidade: 0, ativo: 1, diferenciais_aceitos: "" };
  const dif = (p.diferenciais_aceitos || "").split(",");
  const m = abrirModal(`
  <h2>${p.id ? "Editar" : "Novo"} paciente</h2>
  <form id="fp">
  <div class="grid g4">
    <div><label>Nome</label><input name="nome" value="${esc(p.nome)}" required></div>
    <div><label>Idade</label><input name="idade" type="number" value="${p.idade ?? ""}"></div>
    <div><label>Gênero</label><select name="genero">${["feminino", "masculino", "não-binário"].map((g) => `<option ${g === p.genero ? "selected" : ""}>${g}</option>`).join("")}</select></div>
    <div><label>Profissão</label><input name="profissao" value="${esc(p.profissao || "")}"></div>
  </div>
  <label>Queixa principal (como o paciente diz)</label><input name="queixa_principal" value="${esc(p.queixa_principal || "")}">
  <label>História / contexto de vida</label><textarea name="historia" rows="4">${esc(p.historia || "")}</textarea>
  <div class="grid g2">
    <div><label>Sintomas-chave (um por linha — usados também na correção)</label><textarea name="sintomas_chave" rows="7">${esc(p.sintomas_chave || "")}</textarea></div>
    <div><label>Só revela se perguntarem diretamente</label><textarea name="revela_se_perguntado" rows="7">${esc(p.revela_se_perguntado || "")}</textarea></div>
  </div>
  <label>Jeito de falar / personalidade</label><input name="estilo_fala" value="${esc(p.estilo_fala || "")}">
  <div class="grid g4">
    <div><label>Abertura (1 fechado – 5 falante)</label><input name="abertura" type="range" min="1" max="5" value="${p.abertura}"></div>
    <div><label>Nível de risco do caso</label><select name="risco">${INFO.riscos.map((r) => `<option ${r === p.risco ? "selected" : ""}>${r}</option>`).join("")}</select></div>
    <div><label>Voz do robô</label><select name="voz">${INFO.vozes.map((v) => `<option value="${v.id}" ${v.id === p.voz ? "selected" : ""}>${esc(v.nome)}</option>`).join("")}</select></div>
    <div><label>Velocidade da fala (%)</label><input name="velocidade" type="number" min="-50" max="50" step="5" value="${p.velocidade || 0}"></div>
  </div>
  <div class="grid g2">
    <div><label>Diagnóstico correto (gabarito)</label><select name="diagnostico_id">${opcoesDiag(p.diagnostico_id)}</select></div>
    <div><label>Diferenciais aceitos como acerto parcial (Ctrl+clique)</label><select name="diferenciais_aceitos" multiple size="5">${INFO.diagnosticos.map((d) => `<option value="${d.id}" ${dif.includes(d.id) ? "selected" : ""}>${esc(d.nome)}</option>`).join("")}</select></div>
  </div>
  <label>Observações para o professor (não vão para a IA)</label><textarea name="observacoes_professor" rows="2">${esc(p.observacoes_professor || "")}</textarea>
  <label class="linha" style="font-weight:500"><input type="checkbox" name="ativo" style="width:auto" ${p.ativo ? "checked" : ""}> Ativo (aparece para os alunos)</label>
  <div class="linha" style="margin-top:14px"><button class="btn pri">Salvar</button>${p.id ? '<span class="esp"></span><button type="button" class="btn perigo" id="exc">Excluir/arquivar</button>' : ""}</div>
  </form>`);
  $("#fp", m).onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target), d = Object.fromEntries(f);
    d.diferenciais_aceitos = f.getAll("diferenciais_aceitos");
    d.ativo = f.get("ativo") ? 1 : 0;
    if (p.id) await api(`/api/admin/personas/${p.id}`, { method: "PUT", body: d });
    else await api("/api/admin/personas", { method: "POST", body: d });
    fecharModal(); toast("Paciente salvo"); pacientes();
  };
  if ($("#exc", m)) $("#exc", m).onclick = async () => {
    if (!confirm("Excluir este paciente? (Se já tiver sessões, ele será apenas arquivado.)")) return;
    await api(`/api/admin/personas/${p.id}`, { method: "DELETE" }); fecharModal(); pacientes();
  };
}

// ------------------------------------------------------------------ ROBÔS
async function robos() {
  const [lista, personas, cfg] = await Promise.all([api("/api/admin/dispositivos"), api("/api/admin/personas"), api("/api/admin/config")]);
  C.innerHTML = `
  <div class="topo"><h2>Robôs (ESP32)</h2></div>
  <div class="card"><h3>Como conectar um robô</h3>
    <p class="small">No modo de configuração de Wi-Fi do robô (rede <b>Xiaozhi-XXXX</b>, página <b>192.168.4.1</b>), abra a aba <b>Avançado</b> e cole a URL OTA abaixo. O robô aparece aqui sozinho depois de reiniciar.</p>
    ${cfg.url_ota.map((u) => `<code class="url">${u}</code> `).join("")}
  </div>
  ${lista.length ? `<div class="grid g2">${lista.map((d) => `
    <div class="card">
      <div class="linha"><span class="dot ${d.online ? "on" : ""}"></span><b>${esc(d.nome)}</b><span class="small muted">${esc(d.mac)}</span><span class="esp"></span><span class="small muted">${d.online ? "online" : "visto " + d.ultimo_contato_fmt}</span></div>
      <div class="grid g2">
        <div><label>Nome</label><input data-nome="${d.id}" value="${esc(d.nome)}"></div>
        <div><label>Paciente que este robô interpreta</label><select data-pers="${d.id}">${personas.filter((p) => p.ativo).map((p) => `<option value="${p.id}" ${p.id === d.persona_id ? "selected" : ""}>${esc(p.nome)} — ${esc(diagNome(p.diagnostico_id))}</option>`).join("")}</select></div>
      </div>
      <p class="small">${d.sessao ? `Em conversa: <a href="#" data-sid="${d.sessao.id}">sessão ${d.sessao.codigo}</a> — ${esc(d.sessao.aluno_nome || "avulsa")} (${d.sessao.n_perguntas} perguntas)` : '<span class="muted">Sem entrevista em andamento.</span>'}</p>
      <div class="small muted">Firmware ${esc(d.firmware || "?")} · ${esc(d.placa || "")} · IP ${esc(d.ip || "?")}</div>
      <div class="linha" style="margin-top:8px">${d.sessao ? `<button class="btn peq" data-enc="${d.sessao.id}">⏹ Encerrar conversa</button>` : ""}<span class="esp"></span><button class="btn peq perigo" data-del="${d.id}">Remover</button></div>
    </div>`).join("")}</div>` : '<div class="card vazio">Nenhum robô conectou ainda. Configure a URL OTA no ESP32 e ligue-o.</div>'}`;
  C.querySelectorAll("[data-nome]").forEach((i) => (i.onchange = async () => { await api(`/api/admin/dispositivos/${i.dataset.nome}`, { method: "PUT", body: { nome: i.value } }); toast("Nome salvo"); }));
  C.querySelectorAll("[data-pers]").forEach((s) => (s.onchange = async () => { await api(`/api/admin/dispositivos/${s.dataset.pers}`, { method: "PUT", body: { persona_id: +s.value } }); toast("Paciente do robô alterado"); robos(); }));
  C.querySelectorAll("[data-enc]").forEach((b) => (b.onclick = async () => { await api(`/api/admin/sessoes/${b.dataset.enc}/encerrar`, { method: "POST" }); robos(); }));
  C.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => { if (confirm("Remover este robô da lista?")) { await api(`/api/admin/dispositivos/${b.dataset.del}`, { method: "DELETE" }); robos(); } }));
  C.querySelectorAll("a[data-sid]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); detalheSessao(+a.dataset.sid); }));
  if (!timer) timer = setInterval(() => VISTA === "robos" && !$("#modal").innerHTML && document.activeElement.tagName !== "SELECT" && document.activeElement.tagName !== "INPUT" && robos(), 8000);
}

// ------------------------------------------------------------------ TURMAS
async function turmas() {
  const [ts, als] = await Promise.all([api("/api/admin/turmas"), api("/api/admin/alunos")]);
  C.innerHTML = `
  <div class="topo"><h2>Turmas e alunos</h2></div>
  <div class="grid g2">
    <div class="card"><h3>Turmas</h3>
      <table class="t"><tr><th>Turma</th><th>Curso</th><th>Semestre</th><th>Alunos</th><th></th></tr>
      ${ts.map((t) => `<tr><td>${esc(t.nome)}</td><td>${esc(t.curso || "")}</td><td>${esc(t.semestre || "")}</td><td>${t.n_alunos}</td><td><button class="btn peq perigo" data-dt="${t.id}">×</button></td></tr>`).join("")}</table>
      <form id="ft" class="linha" style="margin-top:10px"><input name="nome" placeholder="Nome da turma" required style="flex:2"><input name="curso" placeholder="Curso" value="Psicologia" style="flex:1"><input name="semestre" placeholder="2026.2" style="flex:1"><button class="btn pri">Adicionar</button></form>
    </div>
    <div class="card"><h3>Importar alunos</h3>
      <p class="small muted">Cole uma linha por aluno: <b>Nome;Matrícula</b> (pode colar direto do Excel). Os alunos também se cadastram sozinhos ao iniciar a primeira entrevista.</p>
      <form id="fi"><select name="turma_id">${ts.map((t) => `<option value="${t.id}">${esc(t.nome)}</option>`).join("")}</select>
      <textarea name="lista" rows="5" placeholder="Maria Souza;2023001&#10;João Lima;2023002" style="margin-top:8px"></textarea>
      <button class="btn pri" style="margin-top:8px">Importar</button></form>
    </div>
  </div>
  <div class="card"><h3>Alunos (${als.length})</h3>${als.length ? `<table class="t"><tr><th>Nome</th><th>Matrícula</th><th>Turma</th><th>Sessões</th><th>Média</th><th></th></tr>
  ${als.map((a) => `<tr><td>${esc(a.nome)}</td><td>${esc(a.matricula)}</td><td>${esc(a.turma_nome || "—")}</td><td>${a.n_sessoes}</td><td>${a.media ? a.media.toFixed(1) : "—"}</td><td><button class="btn peq perigo" data-da="${a.id}">×</button></td></tr>`).join("")}</table>` : '<div class="vazio">Nenhum aluno ainda.</div>'}</div>`;
  $("#ft").onsubmit = async (e) => { e.preventDefault(); await api("/api/admin/turmas", { method: "POST", body: Object.fromEntries(new FormData(e.target)) }); turmas(); };
  $("#fi").onsubmit = async (e) => { e.preventDefault(); const r = await api("/api/admin/alunos", { method: "POST", body: Object.fromEntries(new FormData(e.target)) }); toast(`${r.importados} aluno(s) importado(s)`); turmas(); };
  C.querySelectorAll("[data-dt]").forEach((b) => (b.onclick = async () => { if (confirm("Excluir turma? Os alunos ficam sem turma.")) { await api(`/api/admin/turmas/${b.dataset.dt}`, { method: "DELETE" }); turmas(); } }));
  C.querySelectorAll("[data-da]").forEach((b) => (b.onclick = async () => { if (confirm("Excluir aluno? As sessões dele ficam como avulsas.")) { await api(`/api/admin/alunos/${b.dataset.da}`, { method: "DELETE" }); turmas(); } }));
}

// ------------------------------------------------------------------ SIMULADOR
async function simulador() {
  const personas = (await api("/api/admin/personas")).filter((p) => p.ativo);
  const sel = window._simPersona || personas[0]?.id;
  C.innerHTML = `
  <div class="topo"><h2>Simulador</h2></div>
  <p class="muted">Converse com um paciente pelo navegador para testar o perfil antes de usar com o robô.</p>
  <div class="card">
    <div class="linha"><div style="flex:1"><label>Paciente</label><select id="sp">${personas.map((p) => `<option value="${p.id}" ${p.id === sel ? "selected" : ""}>${esc(p.nome)} — ${esc(diagNome(p.diagnostico_id))}</option>`).join("")}</select></div>
    <label class="linha" style="margin-top:28px;font-weight:500"><input type="checkbox" id="sv" style="width:auto" checked> Ouvir a voz</label>
    <button class="btn" id="snova" style="margin-top:24px">↺ Nova conversa</button></div>
    <div class="chat" id="schat" style="margin-top:14px;min-height:240px"></div>
    <form id="sf" class="linha" style="margin-top:12px"><button type="button" class="mic" id="smic" title="Segure para falar">🎤</button><input id="st" placeholder="Digite uma pergunta ao paciente…" style="flex:1"><button class="btn pri">Enviar</button></form>
    <div id="sstatus" class="small muted" style="margin-top:6px"></div>
  </div>`;
  let sid = null, msgs = [];
  const nome = () => personas.find((p) => p.id == $("#sp").value)?.nome;
  const nova = async () => { const r = await api("/api/admin/sessoes", { method: "POST", body: { persona_id: +$("#sp").value } }); sid = r.id; msgs = []; renderChat($("#schat"), msgs, nome()); };
  const resp = (r) => {
    if (r.aviso) return toast(r.aviso);
    msgs.push({ papel: "aluno", texto: r.aluno }, { papel: "paciente", texto: r.paciente });
    renderChat($("#schat"), msgs, nome()); tocarB64(r.audio_b64);
    if (r.erro_voz) toast("Voz indisponível: " + r.erro_voz, 5000);
  };
  const espera = (on) => ($("#sstatus").textContent = on ? `${nome()} está pensando…` : "");
  $("#sp").onchange = nova; $("#snova").onclick = nova;
  $("#sf").onsubmit = async (e) => {
    e.preventDefault(); const t = $("#st").value.trim(); if (!t) return;
    $("#st").value = ""; espera(true);
    try { resp(await api(`/api/admin/sessoes/${sid}/mensagem`, { method: "POST", body: { texto: t, voz: $("#sv").checked } })); }
    catch (err) { toast(err.message, 6000); } finally { espera(false); }
  };
  ligarMicrofone($("#smic"), async (blob) => {
    const fd = new FormData(); fd.append("arquivo", blob, "fala.webm"); espera(true);
    try { resp(await api(`/api/admin/sessoes/${sid}/audio`, { method: "POST", body: fd })); }
    catch (err) { toast(err.message, 6000); } finally { espera(false); }
  });
  window._simPersona = null;
  await nova();
}

// ------------------------------------------------------------------ CONFIGURAÇÃO
async function configuracao() {
  const c = await api("/api/admin/config");
  C.innerHTML = `
  <div class="topo"><h2>Configuração</h2></div>
  <div class="card"><h3>Serviços de IA</h3>
    <p class="small muted">As chaves e modelos ficam no arquivo <b>servidor/.env</b>. Depois de alterar, reinicie o servidor.</p>
    <table class="t">${Object.entries(c).filter(([k]) => k !== "url_ota").map(([k, v]) => `<tr><td><b>${k}</b></td><td>${esc(String(v))}</td></tr>`).join("")}</table>
    <div class="linha" style="margin-top:12px">
      <button class="btn" data-t="llm">Testar LLM (cérebro)</button><button class="btn" data-t="tts">Testar voz (TTS)</button><button class="btn" data-t="stt">Testar reconhecimento (STT)</button>
    </div><div id="tres" style="margin-top:10px"></div>
  </div>
  <div class="card"><h3>Endereços</h3>
    <p class="small">URL OTA para o robô:</p>${c.url_ota.map((u) => `<code class="url">${u}</code> `).join("")}
    <p class="small" style="margin-top:12px">Página dos alunos: ${c.url_ota.map((u) => `<code class="url">${u.replace("/xiaozhi/ota/", "/aluno")}</code>`).join(" ")}</p>
  </div>`;
  C.querySelectorAll("[data-t]").forEach((b) => (b.onclick = async () => {
    $("#tres").innerHTML = '<div class="muted small">Testando…</div>';
    const r = await api(`/api/admin/teste/${b.dataset.t}`);
    $("#tres").innerHTML = `<div class="${r.ok ? "aviso" : "erro"}" style="${r.ok ? "background:var(--okbg);color:#14532d" : ""}">${r.ok ? "✔" : "✖"} ${esc(b.textContent)}: ${esc(r.detalhe)} (${r.ms} ms)</div>`;
    tocarB64(r.audio_b64);
  }));
}

iniciar();
