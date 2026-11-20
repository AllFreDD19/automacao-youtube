"""Vídeo de HISTÓRIA com a voz do usuário (padrão desde 23/10/2026, trazido da Fábrica de Vídeos em 24/10/2026):
fundo contínuo de paisagens da biblioteca (sem som), a narração gravada pelo usuário por cima e a legenda casada
palavra por palavra com o roteiro.

    .venv\\Scripts\\python.exe -m automacao.historia <pasta do projeto> [temas...]

Na pasta: roteiro_completo.txt ("## Título" = capítulo do YouTube) e narracao_usuario.mp3 (ou .wav/.m4a).
Faz palavras.json (Whisper) se faltar, legendas.ass, capitulos.txt e video_final.mp4. O vídeo é feito em blocos de
~1 min que começam e terminam no meio de uma tomada (emenda invisível); rodar de novo reaproveita os blocos prontos.
"""
import difflib
import json
import random
import re
import subprocess
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import musica as musica_lib
from . import config, edicao, paisagens

FPS = edicao.FPS
BLOCO = 60.0       # segundos por bloco
TROCA = (10.0, 15.0)  # segundos de cada paisagem
TRANSICAO = 1.2    # fusão entre paisagens
CARACTERES_LEGENDA = 42
ESTILO_ASS = ("Style: Default,Arial,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,1,2,"
              "80,80,70,1")


# ---------------------------------------------------------------- texto e áudio

def ler_roteiro(pasta):
    """[(palavra, capítulo que começa nela ou None)] do roteiro_completo.txt."""
    palavras, capitulo = [], None
    for ln in (pasta / "roteiro_completo.txt").read_text(encoding="utf-8-sig").splitlines():
        s = ln.strip()
        if s.startswith("# ") or not s:
            continue
        if s.startswith("##"):
            capitulo = s.lstrip("#").strip()
            continue
        for w in s.split():
            palavras.append((w, capitulo))
            capitulo = None
    return palavras


def _pedacos(palavra):
    """"dell'abito" → ["dell", "abito"] (o Whisper separa os apóstrofos de jeitos diferentes)."""
    pedacos = []
    for x in re.split(r"[’'`]", palavra):
        x = unicodedata.normalize("NFKD", x.lower()).encode("ascii", "ignore").decode()
        x = re.sub(r"[^a-z0-9]", "", x)
        if x:
            pedacos.append(x)
    return pedacos


def alinhar(roteiro, whisper, total):
    """(início, fim) de cada palavra do roteiro, casando com as palavras do Whisper; as que não casam são
    distribuídas entre as vizinhas."""
    a, dono_a = [], []
    for k, (w, _) in enumerate(roteiro):
        for t in _pedacos(w):
            a.append(t)
            dono_a.append(k)
    b, dono_b = [], []
    for k, x in enumerate(whisper):
        for t in _pedacos(x["w"]):
            b.append(t)
            dono_b.append(k)
    tempo = [None] * len(roteiro)
    for bl in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(bl.size):
            x = whisper[dono_b[bl.b + k]]
            w = dono_a[bl.a + k]
            tempo[w] = (min(tempo[w][0], x["s"]), max(tempo[w][1], x["e"])) if tempo[w] else (x["s"], x["e"])
    casadas = sum(t is not None for t in tempo)
    print(f"palavras do roteiro: {len(roteiro)} | casadas com o áudio: {casadas} ({casadas * 100 // max(len(roteiro), 1)}%)")
    conhecidas = [i for i, t in enumerate(tempo) if t]
    j = 0
    for i in range(len(tempo)):
        while j < len(conhecidas) and conhecidas[j] < i:
            j += 1
        if tempo[i] is None:
            ant = conhecidas[j - 1] if j > 0 else None
            pos = conhecidas[j] if j < len(conhecidas) else None
            t0 = tempo[ant][1] if ant is not None else 0.0
            t1 = tempo[pos][0] if pos is not None else total
            n_ant = i - (ant if ant is not None else -1)
            n_tot = (pos if pos is not None else len(tempo)) - (ant if ant is not None else -1)
            s = t0 + (t1 - t0) * (n_ant - 0.5) / n_tot
            tempo[i] = (s, s + 0.25)
    return tempo


# ---------------------------------------------------------------- legendas e capítulos

def _ass_tempo(s):
    cs = int(round(max(s, 0) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _ass_seg(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def gerar_legendas(roteiro, tempo, destino):
    """Linhas curtas (até ~42 caracteres), quebrando de preferência no fim de frase."""
    linhas, atual = [], []
    for i, (w, _) in enumerate(roteiro):
        if atual and len(" ".join(roteiro[k][0] for k in atual + [i])) > CARACTERES_LEGENDA:
            linhas.append(atual)
            atual = []
        atual.append(i)
        if re.search(r"[.?!»…]$", w) and len(" ".join(roteiro[k][0] for k in atual)) > 18:
            linhas.append(atual)
            atual = []
    if atual:
        linhas.append(atual)
    eventos = []
    for n, idx in enumerate(linhas):
        ini = tempo[idx[0]][0]
        fim = tempo[idx[-1]][1] + 0.35
        if n + 1 < len(linhas):
            fim = min(fim, tempo[linhas[n + 1][0]][0])
        texto = " ".join(roteiro[k][0] for k in idx).replace("«", "").replace("»", "")
        eventos.append(f"Dialogue: 0,{_ass_tempo(ini)},{_ass_tempo(max(fim, ini + 0.3))},Default,,0,0,0,,{texto}")
    cab = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 0", "",
           "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
           "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding", ESTILO_ASS, "", "[Events]",
           "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    destino.write_text("\n".join(cab + eventos) + "\n", encoding="utf-8")
    return destino


def capitulos(roteiro, tempo, intro="Intro"):
    linhas = []
    for i, (_, cap) in enumerate(roteiro):
        if cap:
            t = 0 if not linhas else int(tempo[i][0])
            linhas.append(f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d} {cap}" if t >= 3600
                          else f"{t // 60:02d}:{t % 60:02d} {cap}")
    if linhas and not linhas[0].startswith("00:00"):
        linhas.insert(0, f"00:00 {intro}")
    return linhas


def recortar_legendas(ass, inicio, segundos, destino):
    """Só as falas deste bloco, com o horário contado a partir do início do bloco."""
    cabecalho, falas = [], []
    for ln in ass.read_text(encoding="utf-8").splitlines():
        if not ln.startswith("Dialogue:"):
            cabecalho.append(ln)
            continue
        campos = ln.split(",", 9)
        s, e = max(_ass_seg(campos[1]) - inicio, 0.0), min(_ass_seg(campos[2]) - inicio, segundos)
        if e - s >= 0.05:
            campos[1], campos[2] = _ass_tempo(s), _ass_tempo(e)
            falas.append(",".join(campos))
    if not falas:
        return None
    destino.write_text("\n".join(cabecalho + falas) + "\n", encoding="utf-8")
    return destino


# ---------------------------------------------------------------- fundo de paisagens

def _quadro(t):
    return round(t * FPS) / FPS


def planejar(total, clipes, semente):
    """Tomadas {clipe, fonte_ini, s, e} cobrindo [0, total]; vizinhas se sobrepõem TRANSICAO s. A ordem muda a
    cada vídeo (semente = nome da pasta) e um clipe repetido usa o trecho mais distante do já usado."""
    rnd = random.Random(semente)
    fila, usados, tomadas, s, anterior = [], {}, [], 0.0, None
    while s < total:
        if not fila:
            fila = list(clipes)
            rnd.shuffle(fila)
            if fila[0] == anterior and len(fila) > 1:
                fila.append(fila.pop(0))
        nome = fila.pop(0)
        dur = clipes[nome]["segundos"]
        L = min(rnd.uniform(*TROCA), dur - 0.2)
        opcoes = [rnd.uniform(0, max(dur - L, 0)) for _ in range(6)]
        ja = usados.setdefault(nome, [])
        ini = max(opcoes, key=lambda o: min(abs(o - u) for u in ja)) if ja else opcoes[0]
        ja.append(ini)
        tomadas.append({"clipe": nome, "fonte_ini": ini, "s": s, "e": s + L})
        anterior = nome
        s += L - TRANSICAO
    tomadas[-1]["e"] = total
    if len(tomadas) > 1 and tomadas[-1]["e"] - tomadas[-1]["s"] < 4:
        tomadas.pop()
        ult = tomadas[-1]
        ult["e"] = total
        ult["fonte_ini"] = max(0.0, min(ult["fonte_ini"], clipes[ult["clipe"]]["segundos"] - (total - ult["s"]) - 0.05))
    return tomadas


def blocos(tomadas, total):
    cortes, ultimo = [0.0], 0.0
    for t in tomadas:
        meio = _quadro((t["s"] + t["e"]) / 2)
        if meio - ultimo >= BLOCO and total - meio >= 10 and t["e"] - t["s"] > 2 * TRANSICAO + 1:
            cortes.append(meio)
            ultimo = meio
    cortes.append(total)
    return list(zip(cortes, cortes[1:]))


def render_bloco(k, a, b, tomadas, total, legendas, pasta_blocos):
    destino = (pasta_blocos / f"bloco_{k:03d}.mp4").resolve()
    pecas = [t for t in tomadas if t["e"] > a + 1e-6 and t["s"] < b - 1e-6]
    entradas, filtros = [], []
    for i, t in enumerate(pecas):
        ini, fim = max(t["s"], a), min(t["e"], b)
        entradas += ["-ss", f"{t['fonte_ini'] + ini - t['s']:.3f}", "-t", f"{fim - ini + 0.1:.3f}",
                     "-i", str((paisagens.CLIPES / f"{t['clipe']}.mp4").resolve())]
        # tpad: se o clipe acabar um pouco antes, segura o último quadro (o tempo nunca fica curto)
        filtros.append(f"[{i}:v]setpts=PTS-STARTPTS,fps={FPS},format=yuv420p,tpad=stop_mode=clone:stop_duration=3,"
                       f"trim=duration={fim - ini + 0.1:.3f},settb=AVTB[v{i}]")
    atual = "v0"
    for i in range(1, len(pecas)):
        filtros.append(f"[{atual}][v{i}]xfade=transition=fade:duration={TRANSICAO}:offset={max(pecas[i]['s'], a) - a:.3f}[x{i}]")
        atual = f"x{i}"
    acab = []
    if a == 0:
        acab.append("fade=t=in:st=0:d=1")
    if b >= total - 1e-6:
        acab.append(f"fade=t=out:st={max(b - a - 1.5, 0):.2f}:d=1.5")
    leg = recortar_legendas(legendas, a, b - a, destino.with_suffix(".ass"))
    if leg:
        acab.append(f"subtitles={leg.name}")
    filtros.append(f"[{atual}]{','.join(acab) or 'null'}[vout]")
    edicao._rodar([*entradas, "-filter_complex", ";".join(filtros), "-map", "[vout]", "-t", f"{b - a:.3f}",
                   *edicao._codec_video(final=True), "-an", str(destino)], cwd=destino.parent)
    return destino


def renderizar(pasta, audio, total, legendas, temas, semente=None):
    t0 = time.time()
    clipes = paisagens.disponiveis(temas)
    # semente igual = mesma sequência de paisagens (a mesma história em dois idiomas, pedido de 26/10/2026)
    tomadas = planejar(total, clipes, semente or pasta.name)
    partes = blocos(tomadas, total)
    pasta_blocos = pasta / "blocos"
    pasta_blocos.mkdir(exist_ok=True)
    print(f"fundo: {len(tomadas)} tomadas de {len(set(t['clipe'] for t in tomadas))} clipes, {len(partes)} blocos",
          flush=True)
    reg = pasta_blocos / "feitos.json"
    feitos = json.loads(reg.read_text(encoding="utf-8")) if reg.exists() else {}
    prontos, trava = [0], threading.Lock()

    def fazer(k):
        a, b = partes[k]
        destino = pasta_blocos / f"bloco_{k + 1:03d}.mp4"
        tmp = recortar_legendas(legendas, a, b - a, pasta_blocos / f"_chave_{k + 1:03d}.ass")
        falas = tmp.read_text(encoding="utf-8") if tmp else ""
        if tmp:
            tmp.unlink()
        chave = json.dumps([a, b, [t for t in tomadas if t["e"] > a and t["s"] < b], falas])
        if not (destino.exists() and feitos.get(destino.name) == chave):
            render_bloco(k + 1, a, b, tomadas, total, legendas, pasta_blocos)
            with trava:
                feitos[destino.name] = chave
                # O antivírus/indexador do Windows às vezes trava o arquivo por um instante (PermissionError em
                # 27/10/2026, duca-ballo-serva): tenta de novo em vez de derrubar o vídeo inteiro
                for tentativa in range(20):
                    try:
                        reg.write_text(json.dumps(feitos), encoding="utf-8")
                        break
                    except PermissionError:
                        if tentativa == 19:
                            raise
                        time.sleep(0.5)
        with trava:
            prontos[0] += 1
            if prontos[0] % 5 == 0 or prontos[0] == len(partes):
                print(f"   {prontos[0]}/{len(partes)} blocos ({(time.time() - t0) / 60:.1f} min)", flush=True)
        return destino

    with ThreadPoolExecutor(3) as ex:
        arquivos = list(ex.map(fazer, range(len(partes))))

    lista = pasta_blocos / "lista.txt"
    lista.write_text("".join(f"file '{a.resolve().as_posix()}'\n" for a in arquivos), encoding="utf-8")
    edicao._rodar(["-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(pasta / "trilha_video.mp4")])
    musica = musica_lib.faixa_solta()
    entradas = ["-i", "trilha_video.mp4", "-i", str(audio.resolve())]
    if musica:
        entradas += ["-stream_loop", "-1", "-i", str(musica)]
        filtro_a = (f"[2:a]volume={config.MUSICA_VOLUME},afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5[m];"
                    "[1:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
    else:
        filtro_a = "[1:a]anull[a]"
    edicao._rodar([*entradas, "-filter_complex", filtro_a, "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
                   "-c:v", "copy", *edicao.CODEC_AUDIO, "-movflags", "+faststart", "video_final.mp4"], cwd=pasta)
    (pasta / "trilha_video.mp4").unlink(missing_ok=True)
    return pasta / "video_final.mp4"


def fazer_video(pasta, temas=None, idioma="it", semente=None):
    t0 = time.time()
    audio = next((pasta / n for n in ("narracao_usuario.mp3", "narracao_usuario.wav", "narracao_usuario.m4a")
                  if (pasta / n).exists()), None)
    if not audio:
        sys.exit("Faltou narracao_usuario.mp3 na pasta")
    if not (pasta / "palavras.json").exists():
        subprocess.run([sys.executable, "-u", "-m", "automacao.transcrever", str(audio), str(pasta / "palavras.json"),
                        idioma], check=True, cwd=config.RAIZ)
    total = float(subprocess.run([config.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of",
                                  "csv=p=0", str(audio)], capture_output=True, text=True).stdout)
    roteiro = ler_roteiro(pasta)
    tempo = alinhar(roteiro, json.loads((pasta / "palavras.json").read_text(encoding="utf-8")), total)
    legendas = gerar_legendas(roteiro, tempo, pasta / "legendas.ass")
    caps = capitulos(roteiro, tempo)
    (pasta / "capitulos.txt").write_text("\n".join(caps) + "\n", encoding="utf-8")
    print("capítulos:\n" + "\n".join(caps))
    final = renderizar(pasta, audio, total, legendas, temas, semente)
    print(f"PRONTO {final} ({int(total // 60)} min {int(total % 60)} s de vídeo, em {(time.time() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    # python -m automacao.historia <pasta> [temas...] [--idioma fr] [--semente nome]
    # Antes o idioma ficava sempre "it": uma gravação em francês seria transcrita como italiano.
    args, opcoes = sys.argv[2:], {"--idioma": "it", "--semente": None}
    for chave in opcoes:
        if chave in args:
            i = args.index(chave)
            opcoes[chave] = args[i + 1]
            del args[i:i + 2]
    fazer_video(Path(sys.argv[1]).resolve(), args or None, opcoes["--idioma"], opcoes["--semente"])
