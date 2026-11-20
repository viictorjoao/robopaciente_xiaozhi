"""Catálogo de hipóteses diagnósticas (CID-11) e pacientes de exemplo.

O catálogo serve para que a correção seja objetiva: o aluno escolhe a
hipótese principal numa lista, e o sistema compara com o diagnóstico
configurado no perfil do paciente.
"""

DIAGNOSTICOS = [
    ("tag", "Transtorno de Ansiedade Generalizada", "6B00"),
    ("panico", "Transtorno de Pânico", "6B01"),
    ("agorafobia", "Agorafobia", "6B02"),
    ("fobia_especifica", "Fobia Específica", "6B03"),
    ("ansiedade_social", "Transtorno de Ansiedade Social", "6B04"),
    ("depressivo_unico", "Transtorno Depressivo de Episódio Único", "6A70"),
    ("depressivo_recorrente", "Transtorno Depressivo Recorrente", "6A71"),
    ("distimia", "Transtorno Distímico", "6A72"),
    ("bipolar_1", "Transtorno Bipolar Tipo I", "6A60"),
    ("bipolar_2", "Transtorno Bipolar Tipo II", "6A61"),
    ("toc", "Transtorno Obsessivo-Compulsivo", "6B20"),
    ("tept", "Transtorno de Estresse Pós-Traumático", "6B40"),
    ("luto_prolongado", "Transtorno de Luto Prolongado", "6B42"),
    ("adaptacao", "Transtorno de Adaptação", "6B43"),
    ("burnout", "Burnout (síndrome ocupacional)", "QD85"),
    ("insonia", "Insônia Crônica", "7A00"),
    ("tdah", "Transtorno de Déficit de Atenção e Hiperatividade", "6A05"),
    ("alcool", "Dependência de Álcool", "6C40.2"),
    ("sem_transtorno", "Sem transtorno mental (sofrimento esperado)", "—"),
]

DIAG_POR_ID = {d[0]: {"id": d[0], "nome": d[1], "cid": d[2]} for d in DIAGNOSTICOS}

NIVEIS_RISCO = ["ausente", "baixo", "moderado", "alto"]

VOZES = [
    ("pt-BR-FranciscaNeural", "Francisca (feminina)"),
    ("pt-BR-ThalitaMultilingualNeural", "Thalita (feminina)"),
    ("pt-BR-AntonioNeural", "Antônio (masculina)"),
]


def nome_diag(did):
    d = DIAG_POR_ID.get(did or "")
    return f"{d['nome']} ({d['cid']})" if d else (did or "—")


PACIENTES_EXEMPLO = [
    dict(
        nome="Ana Clara", idade=28, genero="feminino", profissao="Analista financeira",
        queixa_principal="Vivo preocupada com tudo e não consigo desligar a cabeça.",
        historia="Mora sozinha em Manaus há 3 anos. Foi promovida há 8 meses e desde então "
        "as preocupações aumentaram, mas diz que 'sempre foi ansiosa'. Preocupa-se com o "
        "trabalho, com a saúde dos pais no interior, com dinheiro e com coisas pequenas, "
        "como chegar atrasada. Os sintomas duram bem mais de 6 meses, quase todos os dias.",
        sintomas_chave="Preocupação excessiva e difícil de controlar\nInquietação / sensação de nervos à flor da pele\n"
        "Tensão muscular (ombros e mandíbula)\nDificuldade para dormir (demora a pegar no sono)\n"
        "Cansaço fácil\nDificuldade de concentração\nDuração maior que 6 meses",
        revela_se_perguntado="Range os dentes à noite (o dentista notou). Já foi ao cardiologista por "
        "palpitações e os exames deram normais. Toma chá de camomila e às vezes um remédio para "
        "dormir da mãe, sem receita. Nunca teve crises súbitas de pânico.",
        estilo_fala="Fala rápido, se justifica bastante, pede desculpas por 'falar demais'. Educada.",
        abertura=4, risco="ausente", diagnostico_id="tag",
        diferenciais_aceitos="insonia,burnout,panico", voz="pt-BR-FranciscaNeural",
        observacoes_professor="Caso didático de TAG. Diferenciar de pânico (não há crises súbitas) e burnout "
        "(preocupações não se limitam ao trabalho).",
    ),
    dict(
        nome="Roberto", idade=45, genero="masculino", profissao="Motorista de aplicativo",
        queixa_principal="Minha esposa insistiu que eu viesse. Ando sem vontade de nada.",
        historia="Casado, dois filhos adolescentes. Era mecânico, perdeu a oficina há 1 ano. "
        "Há cerca de 4 meses está desanimado quase todos os dias, deixou de jogar futebol com os "
        "amigos, perdeu uns 6 kg sem fazer dieta, acorda às 4h e não volta a dormir. Sente-se um "
        "fracasso como pai e marido. Nunca teve um período em que ficou eufórico ou acelerado.",
        sintomas_chave="Humor deprimido na maior parte do dia\nPerda de interesse e prazer (anedonia)\n"
        "Perda de peso e de apetite\nDespertar precoce\nFadiga / falta de energia\n"
        "Sentimento de inutilidade e culpa\nDificuldade de concentração\nPensamentos passivos de morte",
        revela_se_perguntado="Às vezes pensa que 'seria melhor dormir e não acordar mais', mas não tem plano "
        "e diz que não faria isso pelos filhos. Bebe 2 a 3 cervejas no fim de semana, como sempre bebeu. "
        "O pai teve 'depressão' e se isolou muito na velhice.",
        estilo_fala="Fala pouco, frases curtas, pausado, voz cansada. Minimiza ('é coisa de cabeça fraca').",
        abertura=2, risco="baixo", diagnostico_id="depressivo_unico",
        diferenciais_aceitos="adaptacao,distimia,depressivo_recorrente", voz="pt-BR-AntonioNeural", velocidade=-12,
        observacoes_professor="Exige que o aluno investigue ideação (passiva, sem plano). Avaliar se o aluno "
        "pergunta sobre risco de forma direta e acolhedora. Descartar bipolaridade (sem episódios de euforia).",
    ),
    dict(
        nome="Juliana", idade=22, genero="feminino", profissao="Estudante de Enfermagem",
        queixa_principal="Tive umas crises do nada e achei que ia morrer.",
        historia="Há 5 meses teve a primeira crise no ônibus: coração disparado, falta de ar, formigamento, "
        "tontura e medo de morrer, durando uns 10 minutos. Já foi duas vezes ao pronto-socorro e os exames "
        "estavam normais. Desde então teve outras 6 crises, algumas em casa, sem motivo. Agora vive com "
        "medo de ter outra crise e passou a evitar ônibus lotado.",
        sintomas_chave="Ataques de pânico recorrentes e inesperados\nPalpitações e falta de ar\nMedo de morrer ou de enlouquecer\n"
        "Preocupação persistente com novas crises (ansiedade antecipatória)\nMudança de comportamento / evitação",
        revela_se_perguntado="Toma muito café e energético em época de provas. Não usa outras substâncias. "
        "A mãe tem 'problema de ansiedade'. Entre as crises fica relativamente bem, não se preocupa com tudo.",
        estilo_fala="Fala com emoção, descreve sensações corporais com detalhes, um pouco assustada.",
        abertura=4, risco="ausente", diagnostico_id="panico",
        diferenciais_aceitos="agorafobia,tag", voz="pt-BR-ThalitaMultilingualNeural",
        observacoes_professor="Diferenciar de TAG (preocupação não é generalizada) e investigar uso de cafeína.",
    ),
    dict(
        nome="Marcos", idade=34, genero="masculino", profissao="Bombeiro militar",
        queixa_principal="Não consigo tirar umas cenas da cabeça. O comandante me mandou procurar ajuda.",
        historia="Há 7 meses participou do resgate de um desabamento em que uma criança morreu nos braços dele. "
        "Desde então tem pesadelos com a cena, 'flashes' durante o dia, se assusta com barulhos fortes e evita "
        "passar pela rua do acidente. Anda irritado com a esposa e se sente distante das pessoas.",
        sintomas_chave="Exposição a evento traumático\nRevivescência: pesadelos e flashbacks\nEvitação de lembranças do evento\n"
        "Hipervigilância / sobressalto exagerado\nIrritabilidade\nDuração maior que 1 mês com prejuízo",
        revela_se_perguntado="Tem bebido mais para conseguir dormir (quase todo dia, 'umas doses'). "
        "Sente culpa por não ter chegado antes. Evita falar do caso com colegas. Não tem pensamentos de suicídio.",
        estilo_fala="Firme, contido, evita detalhes da cena no começo; se o aluno for acolhedor, se emociona.",
        abertura=2, risco="baixo", diagnostico_id="tept",
        diferenciais_aceitos="adaptacao,depressivo_unico,alcool", voz="pt-BR-AntonioNeural",
        observacoes_professor="Avaliar se o aluno investiga o evento com cuidado e pergunta sobre uso de álcool.",
    ),
    dict(
        nome="Helena", idade=67, genero="feminino", profissao="Professora aposentada",
        queixa_principal="Desde que meu marido partiu, parece que a vida parou.",
        historia="Viúva há 1 ano e 3 meses, após 40 anos de casamento. Ainda fala com o marido como se ele estivesse "
        "presente, mantém o quarto e as roupas intactos, não aceita a morte e sente um vazio intenso todos os dias. "
        "Deixou de ir à igreja e ao grupo de dança. Os filhos dizem que 'ela precisa seguir em frente'.",
        sintomas_chave="Perda de pessoa próxima há mais de 6 meses\nSaudade intensa e preocupação persistente com o falecido\n"
        "Dificuldade em aceitar a morte\nSensação de que parte de si morreu / vazio\nDificuldade de retomar atividades\n"
        "Sofrimento acima do esperado no contexto cultural",
        revela_se_perguntado="Dorme mal, mas come razoavelmente. Às vezes 'queria ir junto com ele', mas diz que "
        "não faria nada contra a própria vida por causa da fé e dos netos. Não tinha histórico de depressão.",
        estilo_fala="Fala devagar, carinhosa, conta histórias do marido, usa expressões regionais do Amazonas.",
        abertura=5, risco="baixo", diagnostico_id="luto_prolongado",
        diferenciais_aceitos="depressivo_unico,adaptacao", voz="pt-BR-FranciscaNeural",
        observacoes_professor="Diferenciar luto prolongado de episódio depressivo. Investigar o desejo de 'ir junto'.",
    ),
    dict(
        nome="Pedro", idade=19, genero="masculino", profissao="Estudante de Engenharia",
        queixa_principal="Eu travo quando tenho que falar na frente dos outros. Vou reprovar por causa disso.",
        historia="Desde o ensino médio sente medo intenso de ser julgado. Evita apresentar seminários, não pergunta "
        "nada em sala, almoça sozinho para não ter que conversar. Fica vermelho, sua e a voz treme. Sabe que o medo "
        "é exagerado, mas não consegue evitar. Com os amigos de infância fica tranquilo.",
        sintomas_chave="Medo intenso de situações sociais e de avaliação\nMedo de ser humilhado ou julgado\n"
        "Evitação de situações sociais\nSintomas físicos: rubor, sudorese, tremor\nPrejuízo acadêmico\nDuração de vários meses",
        revela_se_perguntado="Já faltou a duas provas orais. Passa horas jogando online, onde se sente à vontade. "
        "Nunca teve crises de pânico fora dessas situações. Não usa álcool para se 'soltar'.",
        estilo_fala="Tímido, respostas curtas no início, hesita ('é... tipo...'), vai se soltando se o aluno for gentil.",
        abertura=2, risco="ausente", diagnostico_id="ansiedade_social",
        diferenciais_aceitos="tag,fobia_especifica", voz="pt-BR-AntonioNeural",
        observacoes_professor="Paciente fechado: avalia rapport e uso de perguntas abertas.",
    ),
    dict(
        nome="Carla", idade=38, genero="feminino", profissao="Enfermeira de UTI",
        queixa_principal="Estou esgotada. Não aguento mais o plantão.",
        historia="Trabalha há 12 anos em UTI, faz plantões extras por necessidade. No último ano sente exaustão "
        "extrema, ficou fria e impaciente com pacientes e familiares ('virei uma pessoa que eu não gosto') e sente que "
        "nada do que faz adianta. Nas férias melhorou bastante, mas piorou ao voltar. Fora do trabalho ainda sente "
        "prazer com a filha e com a igreja.",
        sintomas_chave="Exaustão relacionada ao trabalho\nDistanciamento mental / cinismo em relação ao trabalho\n"
        "Sensação de ineficácia profissional\nMelhora fora do contexto de trabalho (férias)\nContexto de estresse crônico no trabalho",
        revela_se_perguntado="Tem dor de cabeça frequente e acorda cansada. Pensou em largar a profissão. "
        "Não tem pensamentos de morte. O humor em casa é razoável, aproveita o tempo com a filha.",
        estilo_fala="Objetiva, um pouco irônica, cansada; usa termos do hospital.",
        abertura=3, risco="ausente", diagnostico_id="burnout",
        diferenciais_aceitos="depressivo_unico,adaptacao,insonia", voz="pt-BR-ThalitaMultilingualNeural",
        observacoes_professor="Burnout na CID-11 é fenômeno ocupacional (QD85), não transtorno mental. Aceitar "
        "depressão/adaptação como diferencial; o aluno deve notar que o prazer fora do trabalho está preservado.",
    ),
    dict(
        nome="Lucas", idade=26, genero="masculino", profissao="Programador",
        queixa_principal="Perco muito tempo conferindo as coisas e lavando as mãos. Sei que é bobagem, mas não consigo parar.",
        historia="Há uns 2 anos, piorou depois da pandemia. Tem pensamentos intrusivos de que vai contaminar a família "
        "ou de que deixou o fogão ligado. Lava as mãos até machucar e confere portas e fogão várias vezes, numa "
        "sequência certa. Gasta mais de 1 hora por dia nisso e chega atrasado ao trabalho.",
        sintomas_chave="Obsessões (pensamentos intrusivos de contaminação e de dano)\nCompulsões (lavar as mãos, verificar)\n"
        "Rituais para aliviar a ansiedade\nReconhece que é exagerado (insight)\nMais de 1 hora por dia / prejuízo",
        revela_se_perguntado="Tem vergonha e esconde dos colegas. Tem números 'certos' (conta até 8). "
        "Não tem tiques. Não tem pensamentos de morte.",
        estilo_fala="Detalhista, educado, um pouco envergonhado; às vezes se corrige para ser exato.",
        abertura=3, risco="ausente", diagnostico_id="toc",
        diferenciais_aceitos="tag", voz="pt-BR-AntonioNeural", velocidade=8,
        observacoes_professor="Avaliar se o aluno diferencia obsessões de preocupações (TAG).",
    ),
]
