"""
Sofia v3 - v2 + abrir pastas, arquivos e qualquer programa instalado (Windows)

Mesmas bibliotecas da v2 (nada novo pra instalar):
    pip install SpeechRecognition pyttsx3 pyaudio google-genai edge-tts pygame
"""

import os
import re
import time
import asyncio
import subprocess
import tempfile
import unicodedata
import webbrowser
import difflib
import random
import ctypes
import threading
import winsound
from datetime import datetime
from urllib.parse import quote
from pathlib import Path

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
import edge_tts
import pyttsx3
import speech_recognition as sr

# ---------- CONFIGURE AQUI ----------
NOME_USUARIO = "Pedro"
VOZ = "pt-BR-FranciscaNeural"
MODELO = "gemini-3.5-flash"          # se der erro, troque por "gemini-2.5-flash"

OPERA = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe")

APPS = {
    "visual code": ("code", "Code.exe"),
    "vs code": ("code", "Code.exe"),
    "notion": ("start notion:", "Notion.exe"),
    "spotify": ("start spotify:", "Spotify.exe"),
    "excel": ("start excel", "EXCEL.EXE"),
    "word": ("start winword", "WINWORD.EXE"),
    "navegador": (f'"{OPERA}"', "opera.exe"),
    "opera": (f'"{OPERA}"', "opera.exe"),
    "calculadora": ("calc", "CalculatorApp.exe"),
    "bloco de notas": ("notepad", "notepad.exe"),
    "paint": ("mspaint", "mspaint.exe"),
}

SITES = {
    "crunchyroll": "https://www.crunchyroll.com",
    "youtube": "https://www.youtube.com",
}

PERSONALIDADE = (
    f"Você é a Sofia, assistente pessoal e amiga do {NOME_USUARIO}. "
    "Fala português do Brasil, de um jeito caloroso, animado e descontraído, com gírias leves, como uma amiga de verdade. "
    "Gosta de bater papo: comente o que ele disse com interesse e, na maior parte das vezes, "
    "termine com uma pergunta curta pra manter a conversa viva. "
    "Responda em 2 a 4 frases curtas, sem markdown, sem listas e sem emojis, "
    "porque sua resposta será falada em voz alta. "
    f"Ajude o {NOME_USUARIO} com programação, estudos e o dia a dia, e seja honesta quando não souber algo."
)
# ------------------------------------

HOME = Path.home()

# jeitos que o microfone costuma entender no lugar de "Sofia"
VARIANTES_NOME = {"sofia", "sófia", "sofya", "sofi", "sophia", "sofie", "zofia", "filha"}


def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower())
                   if unicodedata.category(c) != "Mn")


# ---------- Pastas conhecidas ----------
def _primeira_existente(*caminhos):
    for c in caminhos:
        if c.exists():
            return c
    return caminhos[0]


PASTAS = {
    "documentos": _primeira_existente(HOME / "OneDrive" / "Documentos", HOME / "Documents", HOME / "Documentos"),
    "downloads": HOME / "Downloads",
    "desktop": _primeira_existente(HOME / "OneDrive" / "Área de Trabalho", HOME / "Desktop", HOME / "Área de Trabalho"),
    "area de trabalho": _primeira_existente(HOME / "OneDrive" / "Área de Trabalho", HOME / "Desktop", HOME / "Área de Trabalho"),
    "imagens": _primeira_existente(HOME / "OneDrive" / "Imagens", HOME / "Pictures", HOME / "Imagens"),
    "musicas": _primeira_existente(HOME / "Music", HOME / "Músicas"),
    "videos": _primeira_existente(HOME / "Videos", HOME / "Vídeos"),
    "estudos": _primeira_existente(HOME / "OneDrive" / "Documentos" / "Estudos.py"),
}

# onde ela procura pastas/arquivos por nome
BASES_BUSCA = [PASTAS["documentos"], PASTAS["desktop"], PASTAS["downloads"], PASTAS["imagens"], PASTAS["videos"]]
IGNORAR = {"appdata", "node_modules", ".git", "__pycache__", "venv", ".venv"}


def buscar(nome, quer_pasta, profundidade=4, limite_seg=6):
    """Procura uma pasta ou arquivo pelo nome nas pastas principais."""
    alvo = sem_acento(nome).strip()
    inicio = time.time()
    for base in BASES_BUSCA:
        if not base.exists():
            continue
        base_prof = len(base.parts)
        for raiz, pastas, arquivos in os.walk(base):
            if time.time() - inicio > limite_seg:
                return None
            if len(Path(raiz).parts) - base_prof >= profundidade:
                pastas[:] = []
            pastas[:] = [p for p in pastas if p.lower() not in IGNORAR and not p.startswith(".")]
            lista = pastas if quer_pasta else arquivos
            for item in lista:
                if alvo in sem_acento(item):
                    return Path(raiz) / item
    return None


def buscar_programa(nome):
    """Procura um atalho no Menu Iniciar (qualquer programa instalado)."""
    alvo = sem_acento(nome).strip()
    locais = [
        Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    for local in locais:
        if not local.exists():
            continue
        for raiz, _, arquivos in os.walk(local):
            for a in arquivos:
                if a.lower().endswith(".lnk") and alvo in sem_acento(a):
                    return Path(raiz) / a
    return None


# ---------- Gemini (conversa) ----------
chat = None
if os.environ.get("GEMINI_API_KEY"):
    try:
        from google import genai
        from google.genai import types

        cliente = genai.Client()
        chat = cliente.chats.create(
            model=MODELO,
            config=types.GenerateContentConfig(system_instruction=PERSONALIDADE, max_output_tokens=260),
        )
    except Exception as e:
        print("Não consegui iniciar o Gemini:", e)


def conversar(texto):
    if chat is None:
        return "Ainda não estou conectada ao Gemini. Confira a chave da API."
    try:
        return chat.send_message(texto).text.strip()
    except Exception as e:
        print("Erro no Gemini:", e)
        return "Tive um problema pra pensar nisso agora. Tenta de novo?"


# ---------- Voz (fala) ----------
voz_offline = pyttsx3.init()
voz_offline.setProperty("rate", 190)
for v in voz_offline.getProperty("voices"):
    if "maria" in v.name.lower() or "brazil" in v.name.lower():
        voz_offline.setProperty("voice", v.id)
        break


def falar(texto, natural=False):
    """natural=True usa a voz neural (mais bonita, mais lenta).
    Padrao e a voz do Windows (instantanea) pra confirmacoes curtas."""
    print(f"Sofia: {texto}")
    if not natural:
        voz_offline.say(texto)
        voz_offline.runAndWait()
        return
    try:
        arquivo = os.path.join(tempfile.gettempdir(), "sofia_fala.mp3")
        asyncio.run(edge_tts.Communicate(texto, VOZ).save(arquivo))
        pygame.mixer.init()
        pygame.mixer.music.load(arquivo)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
        pygame.mixer.music.unload()
    except Exception:
        voz_offline.say(texto)
        voz_offline.runAndWait()


# ---------- Voz (escuta) ----------
reconhecedor = sr.Recognizer()
reconhecedor.pause_threshold = 0.6          # termina a frase mais rapido
reconhecedor.dynamic_energy_threshold = True
microfone = sr.Microphone()
with microfone as _fonte:                    # calibra o ruido UMA vez so
    reconhecedor.adjust_for_ambient_noise(_fonte, duration=1)


def normalizar_nome(texto):
    """Troca 'filha', 'sofi' etc. no comeco da frase por 'sofia'."""
    palavras = texto.split()
    if palavras and palavras[0].strip(",.!?") in VARIANTES_NOME:
        palavras[0] = "sofia"
    return " ".join(palavras)


def ouvir(limite=8, espera=10):
    with microfone as fonte:
        print("Ouvindo...")
        try:
            audio = reconhecedor.listen(fonte, timeout=espera, phrase_time_limit=limite)
        except sr.WaitTimeoutError:
            return ""
    try:
        resp = reconhecedor.recognize_google(audio, language="pt-BR", show_all=True)
    except (sr.UnknownValueError, sr.RequestError):
        return ""            # não entendeu nada ou sem internet: só escuta de novo
    if not resp or "alternative" not in resp:
        return ""
    alternativas = [a["transcript"].lower() for a in resp["alternative"] if "transcript" in a]
    if not alternativas:
        return ""
    texto = alternativas[0]
    for a in alternativas:               # se alguma alternativa ouviu "sofia", usa ela
        if "sofia" in a:
            texto = a
            break
    texto = normalizar_nome(texto)
    print(f"Você: {texto}")
    return texto


# ---------- Ações básicas ----------
def abrir(nome):
    if nome in SITES:
        webbrowser.open(SITES[nome])
    elif nome in APPS:
        subprocess.Popen(APPS[nome][0], shell=True)


def fechar(nome):
    if nome in APPS:
        subprocess.run(f"taskkill /IM {APPS[nome][1]} /F", shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    return False


# jeitos que o microfone costuma entender (o que ela ouve -> o nome certo)
APELIDOS = {
    "cru": "crunchyroll", "crunchy": "crunchyroll", "crunch": "crunchyroll",
    "cranchi": "crunchyroll", "crânchi": "crunchyroll", "crunchiroll": "crunchyroll",
    "yotube": "youtube", "youtubi": "youtube", "iutube": "youtube", "iutubi": "youtube",
    "espotify": "spotify", "espotifai": "spotify", "spotifai": "spotify",
    "vscode": "vs code", "visual": "visual code", "opera gx": "opera",
    "excell": "excel", "ecxel": "excel",
}


def achar_alvo(comando):
    for nome in list(APPS) + list(SITES):
        if nome in comando:
            return nome
    for palavra in comando.split():
        palavra = palavra.strip(",.!?")
        if palavra in APELIDOS:
            return APELIDOS[palavra]
    # ultimo recurso: parecido com algum nome (ex: "crunchirol")
    unicos = [n for n in list(APPS) + list(SITES) if " " not in n]
    for palavra in comando.split():
        parecido = difflib.get_close_matches(palavra.strip(",.!?"), unicos, n=1, cutoff=0.75)
        if parecido:
            return parecido[0]
    return None


def extrair_nome(comando, palavra_chave):
    """Pega o que vem depois de 'pasta' / 'arquivo' / 'abrir' etc."""
    depois = comando.split(palavra_chave, 1)[-1].strip()
    depois = re.sub(r"^(o|a|os|as|do|da|de|chamada?|chamado)\s+", "", depois).strip()
    return depois


# ---------- Comandos de pastas e arquivos ----------
def cmd_pasta(comando):
    nome = extrair_nome(comando, "pasta")
    if not nome:
        falar("Qual pasta você quer?")
        return True
    chave = sem_acento(nome)
    caminho = PASTAS.get(chave) or buscar(nome, quer_pasta=True)
    if caminho and Path(caminho).exists():
        falar(f"Abrindo a pasta {nome}")
        os.startfile(caminho)
    else:
        falar(f"Não achei a pasta {nome}.")
    return True


def cmd_arquivo(comando):
    nome = extrair_nome(comando, "arquivo")
    if not nome:
        falar("Qual arquivo você quer?")
        return True
    caminho = buscar(nome, quer_pasta=False)
    if caminho:
        falar(f"Abrindo {caminho.name}")
        os.startfile(caminho)
    else:
        falar(f"Não achei nenhum arquivo com o nome {nome}.")
    return True


def cmd_listar(comando):
    nome = extrair_nome(comando, "pasta") if "pasta" in comando else "documentos"
    caminho = PASTAS.get(sem_acento(nome)) or buscar(nome, quer_pasta=True)
    if not caminho or not Path(caminho).exists():
        falar(f"Não achei a pasta {nome}.")
        return True
    itens = sorted(os.listdir(caminho))[:8]
    if itens:
        falar(f"Na pasta {nome} tem: " + ", ".join(itens))
    else:
        falar("Essa pasta está vazia.")
    return True


def cmd_criar_pasta(comando):
    nome = extrair_nome(comando, "pasta")
    nome = re.sub(r'[\\/:*?"<>|]', "", nome).strip()
    if not nome:
        falar("Qual nome você quer dar pra pasta?")
        return True
    destino = PASTAS["documentos"] / nome
    destino.mkdir(exist_ok=True)
    falar(f"Criei a pasta {nome} em Documentos.")
    os.startfile(destino)
    return True


def cmd_abrir_programa(comando):
    achou = re.search(r"abr\w*\s+(?:o |a |os |as )?(.+)", comando)  # abrir/abre/abra + nome
    if not achou:
        return False
    nome = achou.group(1).strip()
    atalho = buscar_programa(nome)
    if atalho:
        falar(f"Abrindo {nome}")
        os.startfile(atalho)
        return True
    return False


# ---------- Calculadora por voz ----------
import ast
import operator

OPERADORES = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
}


def _avaliar(no):
    """Avalia só contas simples (números e + - * / ** %). Nada de código."""
    if isinstance(no, ast.Expression):
        return _avaliar(no.body)
    if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
        return no.value
    if isinstance(no, ast.UnaryOp) and isinstance(no.op, (ast.USub, ast.UAdd)):
        v = _avaliar(no.operand)
        return -v if isinstance(no.op, ast.USub) else v
    if isinstance(no, ast.BinOp) and type(no.op) in OPERADORES:
        a, b = _avaliar(no.left), _avaliar(no.right)
        if isinstance(no.op, ast.Pow) and abs(b) > 100:
            raise ValueError("expoente grande demais")
        return OPERADORES[type(no.op)](a, b)
    raise ValueError("expressão não permitida")


def texto_para_conta(comando):
    t = sem_acento(comando)
    t = re.sub(r"(\d+)\s*por cento de\s*(\d+)", r"(\1/100)*\2", t)
    t = re.sub(r"raiz quadrada de\s*(\d+(?:[.,]\d+)?)", r"(\1)**0.5", t)
    trocas = [
        ("elevado a", "**"), ("ao quadrado", "**2"), ("ao cubo", "**3"),
        ("multiplicado por", "*"), ("vezes", "*"), ("dividido por", "/"),
        ("dividido", "/"), ("mais", "+"), ("menos", "-"), ("resto", "%"),
    ]
    for falado, simbolo in trocas:
        t = t.replace(falado, simbolo)
    t = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "*", t)       # "5 x 3"
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)              # 2,5 -> 2.5
    t = re.sub(r"(?<=\d)\s*virgula\s*(?=\d)", ".", t)
    t = "".join(c for c in t if c in "0123456789+-*/()%. ")
    return t.strip()


def cmd_calcular(comando):
    conta = texto_para_conta(comando)
    if not re.search(r"\d", conta) or not re.search(r"[+\-*/%]", conta):
        return False
    try:
        r = _avaliar(ast.parse(conta, mode="eval"))
    except Exception:
        return False  # não entendi a conta -> deixa o Gemini responder
    if isinstance(r, float) and r.is_integer():
        r = int(r)
    elif isinstance(r, float):
        r = round(r, 4)
    falar(f"O resultado é {str(r).replace('.', ' vírgula ')}")
    return True


# ---------- Novas habilidades ----------
AVISOS = []   # avisos de timer (a Sofia fala no proximo ciclo)
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
NOTAS = PASTAS["documentos"] / "Notas da Sofia.txt"


def apertar(*teclas, vezes=1):
    """Simula teclas do Windows (volume, midia, atalhos)."""
    for _ in range(vezes):
        for t in teclas:
            ctypes.windll.user32.keybd_event(t, 0, 0, 0)
        for t in reversed(teclas):
            ctypes.windll.user32.keybd_event(t, 0, 2, 0)


def cmd_hora_data(comando):
    agora = datetime.now()
    if "que horas" in comando or "hora é" in comando or "horas são" in comando or "me diz as horas" in comando:
        falar(f"São {agora.hour} e {agora.minute:02d}." if agora.minute else f"São {agora.hour} horas em ponto.")
        return True
    if "data de hoje" in comando or "dia é hoje" in comando or "que dia" in comando:
        falar(f"Hoje é {DIAS[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]} de {agora.year}.")
        return True
    return False


def cmd_volume_midia(comando):
    if "volume" in comando and ("aument" in comando or "sobe" in comando or "mais alto" in comando):
        apertar(0xAF, vezes=5); falar("Aumentei o volume."); return True
    if "volume" in comando and ("diminu" in comando or "abaix" in comando or "baixa" in comando):
        apertar(0xAE, vezes=5); falar("Baixei o volume."); return True
    if "silenci" in comando or "mudo" in comando:
        apertar(0xAD); falar("Pronto."); return True
    if "pausar" in comando or "pausa" in comando or "continuar música" in comando or "continuar a música" in comando:
        apertar(0xB3); return True
    if "próxima" in comando or "proxima" in comando or "pular" in comando:
        apertar(0xB0); return True
    if "música anterior" in comando or "voltar música" in comando:
        apertar(0xB1); return True
    return False


def cmd_tocar(comando):
    m = re.search(r"(?:toque|tocar|toca|coloca|colocar)\s+(?:a |o |as |os )?(.+)", comando)
    if not m:
        return False
    musica = m.group(1).replace("no spotify", "").replace("no youtube", "").strip()
    if "youtube" in comando:
        falar(f"Procurando {musica} no YouTube")
        webbrowser.open("https://www.youtube.com/results?search_query=" + quote(musica))
    else:
        falar(f"Procurando {musica} no Spotify")
        os.startfile("spotify:search:" + quote(musica))
    return True


def cmd_screenshot(comando):
    if "print" in comando or "captura" in comando or "screenshot" in comando:
        apertar(0x5B, 0x2C)   # Win + PrintScreen (salva em Imagens\Capturas de tela)
        falar("Tirei um print da tela.")
        return True
    return False


def cmd_sistema(comando):
    if "bloque" in comando:
        falar("Bloqueando o computador.")
        ctypes.windll.user32.LockWorkStation()
        return True
    if "minimiz" in comando or "mostrar a área de trabalho" in comando or "mostrar desktop" in comando:
        apertar(0x5B, 0x44)   # Win + D
        return True
    return False


def _disparar_timer(minutos_txt, segundos):
    def acabou():
        for _ in range(3):
            winsound.Beep(1000, 300)
        AVISOS.append(f"{NOME_USUARIO}, seu timer de {minutos_txt} acabou!")
    threading.Timer(segundos, acabou).start()


def cmd_timer(comando):
    if not any(p in comando for p in ("timer", "cronômetro", "me avisa", "me avise", "me lembra", "me lembre", "daqui a")):
        return False
    m = re.search(r"(\d+)\s*(segundo|minuto|hora)", comando)
    if not m:
        return False
    n, unidade = int(m.group(1)), m.group(2)
    mult = {"segundo": 1, "minuto": 60, "hora": 3600}[unidade]
    plural = "s" if n != 1 else ""
    txt = f"{n} {unidade}{plural}"
    _disparar_timer(txt, n * mult)
    falar(f"Combinado, te aviso em {txt}.")
    return True


def cmd_notas(comando):
    if "minhas notas" in comando or "ler notas" in comando or "ler as notas" in comando:
        if NOTAS.exists():
            linhas = [l.strip() for l in NOTAS.read_text(encoding="utf-8").splitlines() if l.strip()][-3:]
            falar("Suas últimas notas: " + ". ".join(l.split("] ", 1)[-1] for l in linhas))
        else:
            falar("Você ainda não tem notas.")
        return True
    m = re.search(r"(?:anota|anotar|anote)\s+(?:que |aí |ai )?(.+)", comando)
    if m:
        with open(NOTAS, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%d/%m/%Y %H:%M}] {m.group(1).strip()}\n")
        falar("Anotado!")
        return True
    return False


def cmd_site(comando):
    m = re.search(r"abr\w*\s+(?:o |a )?site\s+(?:do |da |de )?(.+)", comando)
    if not m:
        return False
    nome = re.sub(r"\s+", "", sem_acento(m.group(1)))
    falar(f"Abrindo {m.group(1)}")
    webbrowser.open(f"https://www.{nome}.com")
    return True


def cmd_clima(comando):
    if "clima" in comando or "previsão do tempo" in comando or "vai chover" in comando:
        falar("Abrindo a previsão do tempo.")
        webbrowser.open("https://www.google.com/search?q=previsao+do+tempo")
        return True
    return False


class _EstadoBateria(ctypes.Structure):
    _fields_ = [("ligada_na_tomada", ctypes.c_byte), ("flag", ctypes.c_byte),
                ("percentual", ctypes.c_byte), ("flag2", ctypes.c_byte),
                ("segundos_restantes", ctypes.c_ulong), ("segundos_total", ctypes.c_ulong)]


def cmd_bateria(comando):
    if "bateria" not in comando:
        return False
    est = _EstadoBateria()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(est))
    if est.percentual == 255 or est.percentual > 100:
        falar("Não consegui ler a bateria.")
    else:
        tomada = "e está carregando" if est.ligada_na_tomada == 1 else "e não está na tomada"
        falar(f"A bateria está em {est.percentual} por cento {tomada}.")
    return True


TAREFAS = PASTAS["documentos"] / "Tarefas da Sofia.txt"


def cmd_tarefas(comando):
    m = re.search(r"(?:adicion\w+|nova|criar|cria|anota\w*)\s+(?:uma\s+)?tarefa\s+(?:de |para |pra |que )?(.+)", comando)
    if m:
        with open(TAREFAS, "a", encoding="utf-8") as f:
            f.write(m.group(1).strip() + "\n")
        falar("Tarefa adicionada!")
        return True
    if "minhas tarefas" in comando or "ler tarefas" in comando or "o que tenho pra fazer" in comando or "o que eu tenho pra fazer" in comando:
        itens = [l.strip() for l in TAREFAS.read_text(encoding="utf-8").splitlines() if l.strip()] if TAREFAS.exists() else []
        if itens:
            falar(f"Você tem {len(itens)} tarefas: " + ". ".join(itens[:6]))
        else:
            falar("Você não tem tarefas. Aproveita!")
        return True
    if "limpar tarefas" in comando or "apagar tarefas" in comando:
        TAREFAS.write_text("", encoding="utf-8")
        falar("Limpei a lista de tarefas.")
        return True
    return False


def cmd_pomodoro(comando):
    if "pomodoro" not in comando and "modo foco" not in comando and "sessão de foco" not in comando:
        return False
    def fim_foco():
        for _ in range(3):
            winsound.Beep(1200, 300)
        AVISOS.append(f"{NOME_USUARIO}, acabou o foco! Descansa uns 5 minutos.")
    threading.Timer(25 * 60, fim_foco).start()
    falar("Bora focar! Te aviso daqui a 25 minutos.")
    return True


def cmd_extras(comando):
    if "cara ou coroa" in comando:
        falar("Deu " + random.choice(["cara", "coroa"]))
        return True
    if "dado" in comando and ("joga" in comando or "rola" in comando or "jogar" in comando):
        falar(f"Caiu {random.randint(1, 6)}")
        return True
    m = re.search(r"número (?:aleatório )?(?:entre )?(\d+) e (\d+)", comando)
    if m:
        a, b = sorted((int(m.group(1)), int(m.group(2))))
        falar(f"Sorteei o {random.randint(a, b)}")
        return True
    if "configura" in comando and "abr" in comando:
        falar("Abrindo as configurações.")
        os.startfile("ms-settings:")
        return True
    if "notícia" in comando or "noticia" in comando:
        falar("Abrindo as notícias.")
        webbrowser.open("https://g1.globo.com")
        return True
    if "cotação" in comando or "cotacao" in comando or "dólar" in comando:
        falar("Abrindo a cotação.")
        webbrowser.open("https://www.google.com/search?q=cotacao+dolar+hoje")
        return True
    return False


HABILIDADES = [cmd_hora_data, cmd_volume_midia, cmd_tocar, cmd_screenshot,
               cmd_sistema, cmd_timer, cmd_notas, cmd_site, cmd_clima,
               cmd_bateria, cmd_tarefas, cmd_pomodoro, cmd_extras]


# ---------- Roteador de comandos ----------
def tentar_comando(comando):
    """Retorna 'sair', True (era um comando) ou False (não é comando -> conversar)."""
    if "tchau" in comando or "encerrar" in comando:
        falar(f"Até mais, {NOME_USUARIO}!")
        return "sair"

    if "desligar" in comando and "pc" in comando:
        falar("Desligando o computador em 10 segundos.")
        os.system("shutdown /s /t 10")
        return True

    if "youtube" in comando and "canal" in comando:
        canal = comando.split("canal")[-1].strip()
        falar(f"Abrindo o canal {canal} no YouTube")
        webbrowser.open("https://www.youtube.com/results?search_query=" + canal.replace(" ", "+"))
        return True

    if "pesquis" in comando:
        assunto = comando.split("sobre")[-1].strip() if "sobre" in comando else comando.split("pesquis")[-1].strip()
        falar(f"Pesquisando {assunto}")
        webbrowser.open("https://www.google.com/search?q=" + assunto.replace(" ", "+"))
        return True

    # --- habilidades extras ---
    for habilidade in HABILIDADES:
        if habilidade(comando):
            return True

    # --- calculadora (ex: "quanto é 25 vezes 4") ---
    if "abr" not in comando and re.search(r"\d", comando):
        if cmd_calcular(comando):
            return True

    # --- pastas e arquivos ---
    if ("criar" in comando or "crie" in comando or "cria" in comando) and "pasta" in comando:
        return cmd_criar_pasta(comando)
    if ("lista" in comando or "listar" in comando or "o que tem" in comando):
        return cmd_listar(comando)
    if "pasta" in comando and ("abr" in comando or "entrar" in comando or "mostr" in comando):
        return cmd_pasta(comando)
    if "arquivo" in comando and ("abr" in comando):
        return cmd_arquivo(comando)

    # --- apps e sites conhecidos ---
    alvo = achar_alvo(comando)
    if alvo and ("abr" in comando or "entrar" in comando):
        falar(f"Abrindo {alvo}")
        abrir(alvo)
        return True
    if alvo and "fech" in comando:
        if fechar(alvo):
            falar(f"Fechando {alvo}")
        else:
            falar(f"Não consigo fechar {alvo} sozinha. Feche a aba manualmente.")
        return True

    # --- qualquer outro programa instalado ---
    if "abr" in comando:
        if cmd_abrir_programa(comando):
            return True

    return False


def main():
    falar(f"E aí {NOME_USUARIO}, como foi seu dia?", natural=True)
    modo_conversa = True
    dormindo = False

    while True:
        while AVISOS:
            falar(AVISOS.pop(0), natural=True)

        texto = ouvir(espera=7 if modo_conversa else 15)

        if not texto:
            modo_conversa = False      # silêncio: encerra o papo e espera o nome
            continue

        t = sem_acento(texto)
        chamou = "sofia" in t

        # --- modo dormir: só acorda com "Sofia, acorda" ---
        if dormindo:
            if chamou and any(p in t for p in ("acorda", "acorde", "volta", "desperta", "pode voltar", "ativar")):
                dormindo = False
                modo_conversa = True
                falar("Voltei! Pode falar.", natural=True)
            continue

        if not chamou and not modo_conversa:
            continue
        # frase muito longa sem o nome = você provavelmente falando com outra pessoa
        if not chamou and len(texto.split()) > 20:
            modo_conversa = False
            continue

        texto = texto.replace("sofia", "").strip(" ,")
        t = sem_acento(texto)

        if not texto:
            falar("Oi, estou aqui!")
            modo_conversa = True
            continue

        if any(p in t for p in ("fica quieta", "fique quieta", "silencio", "modo silencioso", "dorme",
                                "nao e com voce", "descansa", "pode parar")):
            dormindo = True
            modo_conversa = False
            falar("Beleza, fico quietinha. Pra me chamar de volta, fala: Sofia, acorda.")
            continue

        if modo_conversa and len(texto.split()) <= 5 and any(
                p in t for p in ("valeu", "obrigad", "so isso", "era isso", "por enquanto")):
            falar("Por nada! Qualquer coisa é só chamar.")
            modo_conversa = False
            continue

        resultado = tentar_comando(texto)
        if resultado == "sair":
            break
        if resultado is False:
            falar(conversar(texto), natural=True)
            modo_conversa = True       # bate-papo: continua ouvindo por alguns segundos
        else:
            modo_conversa = False      # comando executado: volta a esperar o nome


if __name__ == "__main__":
    main()