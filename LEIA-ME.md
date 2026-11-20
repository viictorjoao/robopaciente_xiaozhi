# 🧠 Robô Paciente — sistema de IA + plataforma web

Robô com ESP32 que interpreta um **paciente simulado** para que estudantes de Psicologia treinem a entrevista inicial e o raciocínio diagnóstico. O professor configura os pacientes pela web, acompanha as conversas ao vivo e recebe relatórios com os **laudos certos e errados** de cada aluno.

```
  [ESP32 + microfone + alto-falante]  ──Wi-Fi──►  [Computador do laboratório]  ──internet──►  IA (Groq/Gemini/OpenAI)
   firmware Xiaozhi (sem programar)               servidor Python (esta pasta)                 ouvir · pensar · falar
                                                   ├─ /professor  (painel, pacientes, relatórios)
                                                   └─ /aluno      (entrevista + laudo)
```

## 1. O que tem aqui

| Pasta / arquivo | Para que serve |
|---|---|
| `servidor/` | Servidor de IA + plataforma web (Python, FastAPI, SQLite) |
| `servidor/iniciar.bat` | Liga tudo no Windows (instala na primeira vez) |
| `servidor/.env.exemplo` | Modelo de configuração (chaves de IA, senha do professor) |
| `servidor/app/xiaozhi.py` | Conversa com o robô usando o protocolo do Xiaozhi (OTA + WebSocket + Opus) |
| `servidor/app/paciente.py` | O "cérebro" do paciente: monta a personagem e responde |
| `servidor/app/avaliacao.py` | Corrige o laudo do aluno (nota 0–100 + devolutiva) |
| `servidor/app/catalogo.py` | Hipóteses diagnósticas (CID-11) e os 8 pacientes de exemplo |

## 2. Ligar o servidor (computador do laboratório)

1. Instale o **Python 3.11 ou 3.12** (marque "Add Python to PATH").
2. Crie uma chave gratuita em **https://console.groq.com/keys**.
3. Na pasta `servidor`, copie `.env.exemplo` para `.env` e preencha `LLM_API_KEY=` com a chave. Troque também `SENHA_PROFESSOR`.
4. Dê dois cliques em **`iniciar.bat`**. Na primeira vez ele instala tudo (uns 2 min).
5. A janela mostra os endereços, por exemplo:
   ```
   Professor:  http://192.168.0.15:8000/professor
   Alunos:     http://192.168.0.15:8000/aluno
   URL OTA (configure no ESP32):  http://192.168.0.15:8000/xiaozhi/ota/
   ```
   Se o Windows perguntar sobre o firewall, clique em **Permitir** (rede privada).
6. Em **/professor → Configuração**, use os botões **Testar LLM / voz / reconhecimento**.

> **Dica:** fixe o IP do computador (reserva de DHCP no roteador). A URL OTA gravada no robô usa esse IP.

Outras opções de IA estão comentadas no `.env` (Gemini, OpenAI ou **Ollama** rodando no próprio PC, sem internet para o "cérebro"). A voz padrão (edge-tts, vozes pt-BR Francisca, Thalita e Antônio) é gratuita e precisa de internet.

## 3. Preparar o robô (ESP32)

A montagem das fotos (ESP32-S3 + microfone **INMP441** + saída I2S para o amplificador e alto-falante + botão + LED) é a placa **`bread-compact-wifi`** do projeto Xiaozhi. Assim, **não é preciso programar o ESP32**: grava-se o firmware oficial e aponta-se para o nosso servidor.

### 3.1 Ligações esperadas (bread-compact-wifi)

| Módulo | Pino do módulo | GPIO do ESP32-S3 |
|---|---|---|
| Microfone INMP441 | WS | **4** |
| | SCK | **5** |
| | SD | **6** |
| | L/R | GND |
| | VDD / GND | 3V3 / GND |
| Saída de áudio I2S (MAX98357A ou PCM5102A) | DIN | **7** |
| | BCLK (BCK) | **15** |
| | LRC (LCK) | **16** |
| | (PCM5102A: SCK → GND) | — |
| Botão "conversar" (toque e solte) | — | **0** (BOOT) |
| Botão "segure para falar" (opcional) | — | **47** |
| Volume + / − (opcionais) | — | **40** / **39** |
| LED de status | — | **48** |

Confira se os jumpers da protoboard batem com esta tabela. Se algum pino for diferente, troque o fio (é mais fácil do que recompilar o firmware).

### 3.2 Gravar o firmware

1. Baixe a versão mais recente para **bread-compact-wifi** nos *Releases* de https://github.com/78/xiaozhi-esp32 (arquivo `.zip` com `merged-binary.bin`).
2. Grave com o **ESP Flash Download Tool** (Windows) ou com `esptool.py --chip esp32s3 write_flash 0x0 merged-binary.bin`.

### 3.3 Apontar para o nosso servidor

1. Ao ligar pela primeira vez, o robô cria a rede Wi-Fi **Xiaozhi-XXXX**. Conecte o celular nela e abra **http://192.168.4.1**.
2. Escolha o Wi-Fi do laboratório e digite a senha.
3. Na aba **Avançado** (*Advanced*), cole a **URL OTA** mostrada pelo servidor: `http://IP-DO-PC:8000/xiaozhi/ota/`.
4. Salve. O robô reinicia e aparece sozinho em **/professor → Robôs**. Ali você escolhe **qual paciente ele interpreta**.

Para voltar à tela de Wi-Fi depois, aperte o botão BOOT logo que o robô ligar, enquanto ele ainda está iniciando.

**Como falar com o robô:** aperte o botão BOOT uma vez → ele fica ouvindo; fale; quando você para de falar, ele responde e volta a ouvir. Aperte de novo para encerrar.
A palavra de ativação de fábrica é em chinês ("Nǐ hǎo Xiǎozhì"), por isso use o botão. Os avisos sonoros internos do firmware de fábrica também são em chinês; para tê-los em português é preciso compilar o firmware com o ESP-IDF escolhendo o idioma `pt-BR` no `menuconfig` (opcional, a conversa com o paciente já é toda em português).

## 4. Como usar em aula

**Professor (/professor)**
- **Pacientes:** 8 casos prontos (TAG, depressão, pânico, TEPT, luto prolongado, ansiedade social, burnout, TOC). Edite ou crie novos: história, sintomas-chave, o que o paciente só revela se perguntarem, jeito de falar, nível de abertura (1–5), nível de risco, voz, **diagnóstico correto** e **diferenciais aceitos**.
- **Simulador:** converse com qualquer paciente pelo navegador (texto ou microfone) para testar antes da aula.
- **Robôs:** veja quem está online, troque o paciente de cada robô, encerre conversas.
- **Painel / Sessões:** acompanhe as entrevistas ao vivo; abra qualquer sessão para ver a transcrição, o laudo e a nota.
- **Relatórios:** taxa de acerto por paciente (com os diagnósticos com que cada caso é **confundido**), média por aluno, média da turma em cada habilidade de entrevista, exportação para Excel (CSV) e **relatório individual para imprimir/PDF**.
- **Turmas e alunos:** cadastre turmas e cole a lista de alunos do Excel (`Nome;Matrícula`).

**Aluno (/aluno)** — pode ser no celular:
1. Informa nome, matrícula e turma e escolhe um robô disponível (ou conversa pelo computador, se não houver robô).
2. Faz a entrevista falando com o robô. A conversa aparece na tela em tempo real.
3. Clica em **Finalizar entrevista** e preenche o laudo: hipótese principal (CID-11), diferenciais, sintomas, justificativa, risco e conduta.
4. Recebe a nota e a devolutiva (desligue com `MOSTRAR_RESULTADO_ALUNO=0` se preferir que só o professor veja).

### Como a nota é calculada (0–100)
| Parte | Pontos | Regra |
|---|---|---|
| Diagnóstico | 60 | Hipótese = gabarito → 60 · hipótese entre os diferenciais aceitos, ou gabarito citado como diferencial → 30 (parcial) · outra → 0 |
| Risco | 10 | Mesmo nível do caso → 10 · nível vizinho → 5 |
| Entrevista | 30 | Rubrica feita pela IA lendo a transcrição: rapport (5), perguntas abertas (5), investigação dos sintomas-chave (10), investigação de risco (5), coerência do laudo (5) |

A correção é automática e didática. O professor pode **reavaliar** e deve revisar os casos importantes.

## 5. Observações

- **Microfone no navegador:** por segurança, o navegador só libera o microfone em `http://localhost` ou `https`. Nos celulares e PCs dos alunos, use o robô ou digite as perguntas. O simulador por voz funciona no próprio computador do servidor.
- **Dados (LGPD):** tudo fica no arquivo `servidor/dados/robo_paciente.db`, no computador do laboratório. Para o backup, basta copiar esse arquivo. O áudio dos alunos não é guardado, só o texto. O texto da conversa é enviado ao provedor de IA escolhido para gerar as respostas. Avise os alunos disso.
- **Vários robôs:** cada robô aparece com seu próprio paciente, e todos usam o mesmo servidor.
- **Latência típica:** 2 a 4 s entre o fim da pergunta e o início da resposta (Groq + edge-tts).
- **Se o robô não aparecer:** confira se o PC e o robô estão na mesma rede, se o firewall libera a porta 8000 e se a URL OTA termina com `/xiaozhi/ota/`. A janela do servidor mostra cada conexão (`OTA de ...`, `Robô conectado ...`).
