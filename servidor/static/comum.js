// Funções compartilhadas entre a área do professor e a página do aluno
const $ = (s, el = document) => el.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(url, opts = {}) {
  const o = { headers: {}, ...opts };
  if (o.body && !(o.body instanceof FormData)) {
    o.headers["Content-Type"] = "application/json";
    o.body = JSON.stringify(o.body);
  }
  const r = await fetch(url, o);
  if (r.status === 401 && typeof aoDeslogar === "function") { aoDeslogar(); throw new Error("Sessão expirada"); }
  const dados = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(dados?.detail || dados || `Erro ${r.status}`);
  return dados;
}

function toast(msg, ms = 3000) {
  const d = document.createElement("div");
  d.className = "toast"; d.textContent = msg;
  document.body.appendChild(d);
  setTimeout(() => d.remove(), ms);
}

function tagResultado(r) {
  if (!r) return '<span class="tag">sem laudo</span>';
  const c = { correto: "ok", parcial: "warn", incorreto: "bad" }[r];
  return `<span class="tag ${c}">${r}</span>`;
}

function tagStatus(s) {
  const m = { ativa: ["pri", "em andamento"], aguardando_laudo: ["warn", "aguardando laudo"], avaliada: ["ok", "avaliada"], encerrada: ["", "encerrada"] };
  const [c, t] = m[s] || ["", s];
  return `<span class="tag ${c}">${t}</span>`;
}

function renderChat(el, msgs, nomePaciente) {
  const perto = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  el.innerHTML = msgs.length ? msgs.filter((m) => m.papel !== "sistema").map((m) =>
    `<div class="bolha ${m.papel}"><small>${m.papel === "aluno" ? "Estudante" : esc(nomePaciente || "Paciente")}</small>${esc(m.texto)}</div>`).join("")
    : '<div class="vazio">A conversa aparecerá aqui.</div>';
  if (perto) el.scrollTop = el.scrollHeight;
}

function tocarB64(b64) {
  if (!b64) return;
  const a = new Audio("data:audio/mpeg;base64," + b64);
  a.play().catch(() => {});
  return a;
}

// Gravação pelo microfone do navegador (segure o botão para falar)
function ligarMicrofone(botao, aoTerminar) {
  let rec, partes = [], stream;
  const iniciar = async (e) => {
    e.preventDefault();
    if (rec?.state === "recording") return;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      toast("Permita o uso do microfone. (Em rede local, o navegador só libera o microfone em http://localhost ou https.)", 6000);
      return;
    }
    partes = [];
    rec = new MediaRecorder(stream);
    rec.ondataavailable = (ev) => partes.push(ev.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      botao.classList.remove("gravando");
      const blob = new Blob(partes, { type: rec.mimeType || "audio/webm" });
      if (blob.size > 2000) aoTerminar(blob);
    };
    rec.start();
    botao.classList.add("gravando");
  };
  const parar = (e) => { e.preventDefault(); if (rec?.state === "recording") rec.stop(); };
  botao.addEventListener("mousedown", iniciar);
  botao.addEventListener("touchstart", iniciar);
  ["mouseup", "mouseleave", "touchend"].forEach((ev) => botao.addEventListener(ev, parar));
}
