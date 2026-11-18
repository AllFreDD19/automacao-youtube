"""Canal de jogos (Fora da Missão): vídeos de missão, easter egg e react a partir da gameplay do dono.

Fluxo (comandos em `.\\rodar.bat jogo <ação> <projeto>`):
  preparar  quadros a cada 2,5 s + nas trocas de cena, folhas de contato com o horário e a fala do jogo
            (Whisper) para "ver" a gameplay; cria o modelo roteiro_jogo.json
  (roteiro) escrever roteiro_jogo.json olhando as folhas (Claude Code ou à mão); nunca inventar o que não aparece
  gravar    para_gravar.txt: o texto para colar no Clipchamp; o áudio volta como narracao_usuario.mp3
  montar    vídeo longo 1920x1080: trechos da gameplay no ritmo da narração, som do jogo baixo, legenda palavra a
            palavra, texto na tela, música, capítulos e descrição
  curtos    vídeos verticais 1080x1920 (Shorts/Reels/TikTok): gameplay no centro, fundo desfocado, texto grande
  thumb     thumbnails 1280x720 com um quadro do jogo + 2 linhas grandes (mesmo estilo "cinema" dos outros canais)
  mascote   4 opções do mascote ORIGINAL do canal (FLUX da NVIDIA), para a foto de perfil

Pastas do projeto (projetos/<nome>/): gameplay/ (vídeos do dono), quadros/, folhas/, fala_jogo/, trechos/, curtos/.
Tempos no roteiro: "mm:ss", "hh:mm:ss" ou segundos (ex.: "01:23.5").
"""
import base64
import json
import random
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config, edicao, historia

FPS = edicao.FPS
LARGURA, ALTURA = 1920, 1080
CURTO_L, CURTO_A = 1080, 1920
INTERVALO = 2.5          # um quadro a cada 2,5 s
LIMIAR_CENA = 0.35       # sensibilidade da troca de cena (0 a 1; menor = mais quadros)
MUSICA_VOLUME = 0.125    # -18 dB (decisão do canal)
SOM_JOGO_NARRADO = 0.30  # som do jogo por baixo da narração
SOM_JOGO_SEM_NARRACAO = 0.9
TELA_SEGUNDOS = 5.0      # quanto tempo o texto na tela fica no começo do trecho
CURTO_MAX = 60.0
EXTENSOES = (".mp4", ".mkv", ".mov", ".webm", ".avi")
ESTILOS_ASS = {
    "longo": ["Style: Default,Arial,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,1,2,"
              "80,80,60,1",
              "Style: Tela,Impact,84,&H0000D7FF,&H0000D7FF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,6,2,8,"
              "60,60,50,1"],
    "curto": ["Style: Default,Arial,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,5,1,2,"
              "60,60,330,1",
              "Style: Tela,Impact,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,8,3,8,"
              "50,50,230,1"],
}
MASCOTE = ("original cartoon mascot character for a Brazilian gaming YouTube channel, anime-inspired but ORIGINAL design "
           "(not any existing character), tall muscular man in his 30s, short messy dark hair with a white streak, "
           "small scar over the left eyebrow, sharp confident half-smile, toothpick in the mouth, black open jacket "
           "over a dark red shirt, fingerless gloves, holding a game controller, relaxed cool leader attitude, bold "
           "clean line art, cel shading, vibrant colors, centered head and shoulders, plain solid teal background, "
           "profile picture composition, no text, no logo, no watermark")


# ---------------------------------------------------------------- utilidades

def segundos(valor):
    """"01:23.5" / "1:02:03" / 83 → segundos."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    partes = [float(p) for p in str(valor).strip().split(":")]
    total = 0.0
    for p in partes:
        total = total * 60 + p
    return total


def relogio(s):
    s = max(0.0, s)
    h, m, r = int(s // 3600), int(s // 60 % 60), s % 60
    return f"{h}:{m:02d}:{r:04.1f}" if h else f"{m:02d}:{r:04.1f}"


def duracao(arquivo):
    saida = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                            str(arquivo)], capture_output=True, text=True).stdout.strip()
    return float(saida)


def tem_audio(arquivo):
    saida = subprocess.run([config.ffprobe(), "-v", "error", "-select_streams", "a", "-show_entries",
                            "stream=index", "-of", "csv=p=0", str(arquivo)], capture_output=True, text=True).stdout
    return bool(saida.strip())


def gameplays(pasta):
    origem = pasta / "gameplay"
    arquivos = sorted(p for p in origem.glob("*") if p.suffix.lower() in EXTENSOES) if origem.exists() else []
    if not arquivos:
        sys.exit(f"Ponha os vídeos da gameplay em {origem} (mp4, mkv, mov...)")
    return arquivos


def _video(pasta, nome):
    p = pasta / "gameplay" / nome
    if not p.exists():
        sys.exit(f'Vídeo "{nome}" não está em {pasta / "gameplay"}')
    return p


def _fonte(tamanho):
    for nome in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    return ImageFont.load_default(size=tamanho)


def ler_roteiro(pasta):
    arq = pasta / "roteiro_jogo.json"
    if not arq.exists():
        sys.exit(f"Falta {arq}. Rode antes: .\\rodar.bat jogo preparar {pasta.name}")
    r = json.loads(arq.read_text(encoding="utf-8"))
    if any("ESCREVA" in json.dumps(t, ensure_ascii=False) for t in r.get("trechos", [])):
        sys.exit("roteiro_jogo.json ainda é o modelo: preencha os trechos (olhando as folhas/) antes")
    return r


def _ass(estilo, largura, altura, eventos):
    cab = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {largura}", f"PlayResY: {altura}", "WrapStyle: 0", "",
           "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
           "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding", *ESTILOS_ASS[estilo], "", "[Events]",
           "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    return "\n".join(cab + eventos) + "\n"


def _evento(ini, fim, texto, estilo="Tela"):
    texto = str(texto).replace("\n", "\\N")
    return (f"Dialogue: 1,{historia._ass_tempo(ini)},{historia._ass_tempo(max(fim, ini + 0.3))},{estilo},,0,0,0,,"
            f"{{\\fad(150,150)}}{texto}")


def _musica(volume_padrao):
    musica = edicao._escolher_musica()
    if not musica:
        return None, None, volume_padrao
    credito = musica.with_suffix(".txt")
    texto = credito.read_text(encoding="utf-8").strip() if credito.exists() else ""
    if not texto:
        print(f"  ATENÇÃO: sem crédito da música. Crie {credito.name} na pasta musicas com o crédito exigido pela licença")
        texto = f"Música: {musica.stem} [completar crédito]"
    return musica, texto, volume_padrao


# ---------------------------------------------------------------- preparar (ver a gameplay)

def _quadros_intervalo(video, destino, intervalo):
    edicao._rodar(["-i", str(video), "-vf", f"fps=1/{intervalo},scale=480:-2", "-q:v", "4",
                   str(destino / "i_%05d.jpg")])
    quadros = []
    for p in sorted(destino.glob("i_*.jpg")):
        t = (int(p.stem[2:]) - 1) * intervalo
        novo = destino / f"t{t:08.1f}.jpg"
        p.replace(novo)
        quadros.append((t, novo, False))
    return quadros


def _quadros_troca(video, destino, limiar):
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-i", str(video), "-vf",
                        f"select='gt(scene,{limiar})',showinfo,scale=480:-2", "-fps_mode", "vfr", "-q:v", "4",
                        str(destino / "c_%05d.jpg")], capture_output=True, text=True)
    tempos = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    quadros = []
    for p, t in zip(sorted(destino.glob("c_*.jpg")), tempos):
        novo = destino / f"t{t:08.1f}c.jpg"
        p.replace(novo)
        quadros.append((t, novo, True))
    return quadros


def folhas_contato(quadros, nome, destino, por_folha=20, colunas=4):
    """Grades de quadros com o horário de cada um (troca de cena marcada em amarelo)."""
    arquivos = []
    fonte = _fonte(22)
    for n in range(0, len(quadros), por_folha):
        lote = quadros[n:n + por_folha]
        amostra = Image.open(lote[0][1])
        w, h = amostra.size
        linhas = (len(lote) + colunas - 1) // colunas
        folha = Image.new("RGB", (colunas * w, linhas * (h + 30)), (20, 20, 20))
        desenho = ImageDraw.Draw(folha)
        for k, (t, arq, troca) in enumerate(lote):
            x, y = k % colunas * w, k // colunas * (h + 30)
            folha.paste(Image.open(arq).convert("RGB").resize((w, h)), (x, y + 30))
            desenho.text((x + 6, y + 3), relogio(t) + ("  troca de cena" if troca else ""), font=fonte,
                         fill=(255, 214, 0) if troca else (255, 255, 255))
        arq_folha = destino / f"{nome}_{n // por_folha + 1:03d}.jpg"
        folha.save(arq_folha, quality=85)
        arquivos.append(arq_folha)
    return arquivos


def _fala_por_trecho(palavras, ini, fim):
    return " ".join(p["w"] for p in palavras if ini <= p["s"] < fim)


MODELO_ROTEIRO = {
    "tipo": "missao | easter_egg | react | sem_narracao",
    "jogo": "GTA VI",
    "titulo": "ESCREVA o título principal",
    "titulos_alternativos": ["alternativa 1", "alternativa 2", "alternativa 3"],
    "descricao": "ESCREVA 2 a 4 frases sobre o vídeo, sem prometer o que ele não mostra",
    "tags": ["gta 6", "gta vi"],
    "som_jogo": SOM_JOGO_NARRADO,
    "trechos": [
        {"arquivo": "NOME_DO_VIDEO.mp4", "de": "00:00", "ate": "00:20", "capitulo": "Intro",
         "narracao": "ESCREVA o que o narrador fala enquanto este trecho aparece",
         "tela": "texto grande opcional no topo (ou apague este campo)"},
    ],
    "thumb": {"arquivo": "NOME_DO_VIDEO.mp4", "tempo": "00:10", "lado": "esquerda",
              "textos": [["LINHA 1", "LINHA 2", "amarelo"], ["OUTRA", "OPÇÃO", "vermelho"]]},
    "curtos": [
        {"nome": "curto_1", "arquivo": "NOME_DO_VIDEO.mp4", "de": "00:00", "ate": "00:40",
         "textos": [{"de": 0, "ate": 4, "texto": "GANCHO NOS 2 PRIMEIROS SEGUNDOS"},
                    {"de": 30, "ate": 40, "texto": "SEGUE PRA PARTE 2"}],
         "musica": True, "som_jogo": 0.8, "legenda": "texto do post + hashtags"},
    ],
}


def preparar(pasta, intervalo=INTERVALO, limiar=LIMIAR_CENA, fala=True):
    (pasta / "folhas").mkdir(exist_ok=True)
    (pasta / "fala_jogo").mkdir(exist_ok=True)
    mapa = [f"# Mapa da gameplay: {pasta.name}", "",
            "Quadros a cada {:.1f} s e nas trocas de cena (amarelo). Use as folhas para escrever o roteiro: "
            "só descreva o que aparece nelas ou na fala do jogo.".format(intervalo), ""]
    for video in gameplays(pasta):
        total = duracao(video)
        print(f"{video.name}: {relogio(total)}")
        destino = pasta / "quadros" / video.stem
        destino.mkdir(parents=True, exist_ok=True)
        for velho in destino.glob("*.jpg"):
            velho.unlink()
        quadros = _quadros_intervalo(video, destino, intervalo) + _quadros_troca(video, destino, limiar)
        quadros.sort(key=lambda q: q[0])
        # tira trocas de cena que caem quase em cima de um quadro do intervalo
        limpos = []
        for q in quadros:
            if limpos and q[2] and q[0] - limpos[-1][0] < 0.8:
                q[1].unlink(missing_ok=True)
                limpos[-1] = (limpos[-1][0], limpos[-1][1], True)  # o quadro vizinho já mostra a cena nova
                continue
            limpos.append(q)
        folhas = folhas_contato(limpos, video.stem, pasta / "folhas")
        trocas = sum(q[2] for q in limpos)
        print(f"  {len(limpos)} quadros ({trocas} trocas de cena) em {len(folhas)} folhas")

        palavras = []
        arq_fala = pasta / "fala_jogo" / f"{video.stem}.json"
        if fala and tem_audio(video):
            if not arq_fala.exists():
                audio = pasta / "fala_jogo" / f"{video.stem}.wav"
                edicao._rodar(["-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(audio)])
                print("  transcrevendo a fala do jogo (Whisper)...")
                subprocess.run([sys.executable, "-u", "-m", "automacao.transcrever", str(audio), str(arq_fala), "pt"],
                               check=True, cwd=config.RAIZ)
                audio.unlink(missing_ok=True)
            palavras = json.loads(arq_fala.read_text(encoding="utf-8"))

        mapa += [f"## {video.name} ({relogio(total)})", "", "Folhas: " + ", ".join(f"folhas/{f.name}" for f in folhas),
                 "", "| Início | Fim | Fala do jogo |", "|---|---|---|"]
        passo = 15.0
        t = 0.0
        while t < total:
            texto = _fala_por_trecho(palavras, t, t + passo)
            mapa.append(f"| {relogio(t)} | {relogio(min(t + passo, total))} | {texto or '—'} |")
            t += passo
        mapa.append("")
    (pasta / "mapa.md").write_text("\n".join(mapa), encoding="utf-8")
    roteiro = pasta / "roteiro_jogo.json"
    if not roteiro.exists():
        modelo = json.loads(json.dumps(MODELO_ROTEIRO))
        primeiro = gameplays(pasta)[0].name
        for item in [*modelo["trechos"], modelo["thumb"], *modelo["curtos"]]:
            item["arquivo"] = primeiro
        roteiro.write_text(json.dumps(modelo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nMapa: {pasta / 'mapa.md'}\nFolhas: {pasta / 'folhas'}\nRoteiro (preencher): {roteiro}")


# ---------------------------------------------------------------- gravar

def para_gravar(pasta):
    r = ler_roteiro(pasta)
    if r.get("tipo") == "sem_narracao":
        sys.exit("Vídeo sem narração: não há o que gravar. Rode direto: .\\rodar.bat jogo montar " + pasta.name)
    texto = "\n\n".join(t["narracao"].strip() for t in r["trechos"] if t.get("narracao", "").strip())
    destino = pasta / "para_gravar.txt"
    destino.write_text(texto + "\n", encoding="utf-8")
    print(f"{len(texto):,} caracteres (≈ {len(texto) / 735:.1f} min). Cole no Clipchamp e salve o áudio como "
          f"{pasta / 'narracao_usuario.mp3'}\n{destino}")


# ---------------------------------------------------------------- montar (vídeo longo)

def _palavras_roteiro(trechos):
    """[(palavra, capítulo ou None)] e o índice da primeira palavra de cada trecho."""
    palavras, inicios = [], []
    for t in trechos:
        inicios.append(len(palavras))
        cap = t.get("capitulo")
        for w in t.get("narracao", "").split():
            palavras.append((w, cap))
            cap = None
    return palavras, inicios


def _render_trecho(video, ini, dur, volume, destino, tela, vertical=False):
    """Um pedaço da gameplay já no formato final (vídeo + som do jogo com o volume pedido)."""
    if vertical:
        filtro_v = (f"[0:v]setpts=PTS-STARTPTS,fps={FPS},split[a][b];"
                    f"[a]scale={CURTO_L}:{CURTO_A}:force_original_aspect_ratio=increase,crop={CURTO_L}:{CURTO_A},"
                    f"boxblur=24:2,eq=brightness=-0.12[fundo];"
                    f"[b]scale={CURTO_L}:-2[frente];[fundo][frente]overlay=(W-w)/2:(H-h)/2")
    else:
        filtro_v = (f"[0:v]setpts=PTS-STARTPTS,fps={FPS},scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=decrease,"
                    f"pad={LARGURA}:{ALTURA}:(ow-iw)/2:(oh-ih)/2")
    # segura o último quadro se o vídeo acabar antes (narração mais longa que o fim da gameplay)
    filtro_v += f",format=yuv420p,tpad=stop_mode=clone:stop_duration={dur:.3f},trim=duration={dur:.3f}"
    if tela:
        filtro_v += f",subtitles={tela.name}"
    filtro_v += "[v]"
    entradas = ["-ss", f"{ini:.3f}", "-t", f"{dur + 0.2:.3f}", "-i", str(video.resolve())]
    if tem_audio(video):
        filtro_a = (f"[0:a]asetpts=PTS-STARTPTS,aresample=48000,volume={volume},apad,"
                    f"atrim=duration={dur:.3f}[a]")
    else:
        entradas += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        filtro_a = "[1:a]anull[a]"
    edicao._rodar([*entradas, "-filter_complex", f"{filtro_v};{filtro_a}", "-map", "[v]", "-map", "[a]",
                   "-t", f"{dur:.3f}", *edicao._codec_video(final=True), *edicao.CODEC_AUDIO,
                   str(destino.resolve())], cwd=destino.parent)
    return destino


def _planejar(pasta, r):
    """Duração de cada trecho: com narração, o tempo da fala dele; sem narração, de 'de' até 'ate'."""
    trechos = r["trechos"]
    narrado = r.get("tipo") != "sem_narracao"
    if not narrado:
        for t in trechos:
            if segundos(t.get("ate")) is None:
                sys.exit(f"Trecho sem 'ate' em vídeo sem narração: {t}")
            t["_dur"] = segundos(t["ate"]) - segundos(t["de"])
        return None, None, None
    audio = next((pasta / n for n in ("narracao_usuario.mp3", "narracao_usuario.wav", "narracao_usuario.m4a")
                  if (pasta / n).exists()), None)
    if not audio:
        sys.exit(f"Falta a narração: rode .\\rodar.bat jogo gravar {pasta.name}, grave no Clipchamp e salve como "
                 f"narracao_usuario.mp3 em {pasta}")
    if not (pasta / "palavras.json").exists():
        subprocess.run([sys.executable, "-u", "-m", "automacao.transcrever", str(audio), str(pasta / "palavras.json"),
                        "pt"], check=True, cwd=config.RAIZ)
    total = duracao(audio)
    palavras, inicios = _palavras_roteiro(trechos)
    tempo = historia.alinhar(palavras, json.loads((pasta / "palavras.json").read_text(encoding="utf-8")), total)
    cortes = [0.0] + [tempo[i][0] - 0.15 for i in inicios[1:]] + [total]
    for k, t in enumerate(trechos):
        t["_dur"] = max(cortes[k + 1] - cortes[k], 0.5)
        ate = segundos(t.get("ate"))
        if ate is not None:
            jogo = ate - segundos(t["de"])
            if t["_dur"] > jogo + 3:
                print(f"  aviso: trecho {k + 1} tem {t['_dur']:.0f} s de fala e {jogo:.0f} s de jogo marcados; "
                      f"o vídeo segue além do 'ate' ({t['ate']})")
            elif jogo > t["_dur"] + 5:
                print(f"  aviso: trecho {k + 1} tem {jogo:.0f} s de jogo e só {t['_dur']:.0f} s de fala; "
                      f"o fim do trecho fica de fora (encurte o 'ate' ou escreva mais)")
    return audio, palavras, tempo


def montar(pasta):
    r = ler_roteiro(pasta)
    narrado = r.get("tipo") != "sem_narracao"
    audio, palavras, tempo = _planejar(pasta, r)
    pasta_trechos = pasta / "trechos"
    pasta_trechos.mkdir(exist_ok=True)
    volume_padrao = r.get("som_jogo", SOM_JOGO_NARRADO if narrado else SOM_JOGO_SEM_NARRACAO)
    arquivos, inicio = [], 0.0
    for k, t in enumerate(r["trechos"], 1):
        dur = t["_dur"]
        tela = None
        if t.get("tela"):
            tela = pasta_trechos / f"tela_{k:03d}.ass"
            fim = dur if not narrado else min(TELA_SEGUNDOS, dur)
            tela.write_text(_ass("longo", LARGURA, ALTURA, [_evento(0.2, fim - 0.2, t["tela"])]), encoding="utf-8")
        destino = pasta_trechos / f"trecho_{k:03d}.mp4"
        print(f"  trecho {k}/{len(r['trechos'])}: {t['arquivo']} {t['de']} + {dur:.1f} s")
        _render_trecho(_video(pasta, t["arquivo"]), segundos(t["de"]), dur, t.get("som_jogo", volume_padrao),
                       destino, tela)
        arquivos.append(destino)
        t["_ini"] = inicio
        inicio += dur
    total = inicio
    lista = pasta_trechos / "lista.txt"
    lista.write_text("".join(f"file '{a.resolve().as_posix()}'\n" for a in arquivos), encoding="utf-8")
    edicao._rodar(["-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(pasta / "trilha_jogo.mp4")])

    # legenda palavra a palavra da narração (o mesmo sistema dos vídeos de história)
    filtro_v = "[0:v]null[v]"
    if narrado:
        historia.gerar_legendas(palavras, tempo, pasta / "legendas.ass")
        texto = (pasta / "legendas.ass").read_text(encoding="utf-8").replace(historia.ESTILO_ASS, ESTILOS_ASS["longo"][0])
        (pasta / "legendas.ass").write_text(texto, encoding="utf-8")
        filtro_v = "[0:v]subtitles=legendas.ass[v]"
    musica, credito, volume_musica = _musica(r.get("musica_volume", MUSICA_VOLUME))
    entradas, mix, filtros = ["-i", "trilha_jogo.mp4"], ["[0:a]"], [filtro_v]
    if narrado:
        entradas += ["-i", str(audio.resolve())]
        mix.append("[1:a]")
    if musica:
        idx = entradas.count("-i")
        entradas += ["-stream_loop", "-1", "-i", str(musica.resolve())]
        filtros.append(f"[{idx}:a]volume={volume_musica},afade=t=out:st={max(total - 2, 0):.2f}:d=2[m]")
        mix.append("[m]")
    filtros.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:dropout_transition=0:normalize=0,"
                   f"afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5[a]")
    edicao._rodar([*entradas, "-filter_complex", ";".join(filtros), "-map", "[v]", "-map", "[a]",
                   "-t", f"{total:.3f}", *edicao._codec_video(final=True), *edicao.CODEC_AUDIO,
                   "-movflags", "+faststart", "video_final.mp4"], cwd=pasta)
    (pasta / "trilha_jogo.mp4").unlink(missing_ok=True)

    if narrado:
        caps = historia.capitulos(palavras, tempo)
    else:
        caps = []
        for t in r["trechos"]:
            if t.get("capitulo"):
                s = int(t["_ini"])
                caps.append(f"{s // 60:02d}:{s % 60:02d} {t['capitulo']}")
        if caps and not caps[0].startswith("00:00"):
            caps.insert(0, "00:00 Intro")
    escrever_descricao(pasta, r, caps, credito)
    print(f"\nPRONTO {pasta / 'video_final.mp4'} ({int(total // 60)} min {int(total % 60)} s)")


def escrever_descricao(pasta, r, caps, credito):
    texto = [r.get("titulo", ""), "", r.get("descricao", ""), ""]
    if len(caps) >= 3 and caps[0].startswith("00:00"):  # o YouTube só mostra capítulos com 3 ou mais
        texto += ["Capítulos:", *caps, ""]
    texto += [f"Gameplay gravada pelo canal ({r.get('jogo', 'jogo')})."]
    if credito:
        texto += ["", credito]
    texto += ["", "Tags: " + ", ".join(r.get("tags", []))]
    (pasta / "descricao_youtube.txt").write_text("\n".join(texto) + "\n", encoding="utf-8")
    titulos = [r.get("titulo", ""), *r.get("titulos_alternativos", [])]
    (pasta / "titulos.txt").write_text("\n".join(f"{i}. {t}" for i, t in enumerate(titulos, 1)) + "\n",
                                       encoding="utf-8")
    print(f"Descrição: {pasta / 'descricao_youtube.txt'}\nTítulos: {pasta / 'titulos.txt'}")


# ---------------------------------------------------------------- curtos (vertical)

def curtos(pasta, so=None):
    r = ler_roteiro(pasta)
    lista = [c for c in r.get("curtos", []) if not so or c["nome"] == so]
    if not lista:
        sys.exit("Nenhum curto em roteiro_jogo.json (campo \"curtos\")")
    destino_pasta = pasta / "curtos"
    destino_pasta.mkdir(exist_ok=True)
    for c in lista:
        ini, fim = segundos(c["de"]), segundos(c["ate"])
        dur = fim - ini
        if dur > CURTO_MAX:
            print(f"  aviso: {c['nome']} tem {dur:.0f} s (o canal usa até {CURTO_MAX:.0f} s)")
        eventos = []
        for tx in c.get("textos", []):
            eventos.append(_evento(segundos(tx.get("de", 0)), min(segundos(tx.get("ate", dur)), dur), tx["texto"]))
        if isinstance(c.get("texto"), str):
            eventos.append(_evento(0.1, dur - 0.1, c["texto"]))
        tela = None
        if eventos:
            tela = destino_pasta / f"{c['nome']}.ass"
            tela.write_text(_ass("curto", CURTO_L, CURTO_A, eventos), encoding="utf-8")
        bruto = destino_pasta / f"_{c['nome']}.mp4"
        print(f"  {c['nome']}: {c['arquivo']} {c['de']} a {c['ate']} ({dur:.0f} s)")
        _render_trecho(_video(pasta, c["arquivo"]), ini, dur, c.get("som_jogo", 0.8), bruto, tela, vertical=True)
        final = destino_pasta / f"{c['nome']}.mp4"
        musica = edicao._escolher_musica() if c.get("musica", True) else None
        if musica:
            edicao._rodar(["-i", str(bruto.resolve()), "-stream_loop", "-1", "-i", str(musica.resolve()),
                           "-filter_complex",
                           f"[1:a]volume={c.get('musica_volume', 0.25)},afade=t=out:st={max(dur - 1.5, 0):.2f}:d=1.5[m];"
                           "[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                           "-map", "0:v", "-map", "[a]", "-c:v", "copy", *edicao.CODEC_AUDIO, "-t", f"{dur:.3f}",
                           "-movflags", "+faststart", str(final.resolve())])
            bruto.unlink()
        else:
            bruto.replace(final)
        info = [c.get("legenda", "")]
        if musica:
            cred = musica.with_suffix(".txt")
            info += ["", cred.read_text(encoding="utf-8").strip() if cred.exists() else f"Música: {musica.stem}",
                     "(No Instagram/TikTok, confira se a licença da música vale lá; senão, use a música do app.)"]
        (destino_pasta / f"{c['nome']}.txt").write_text("\n".join(info) + "\n", encoding="utf-8")
        print(f"    {final}")


# ---------------------------------------------------------------- thumbnail

def thumbs(pasta):
    from . import thumb_ia
    r = ler_roteiro(pasta)
    t = r.get("thumb") or sys.exit("Falta o campo \"thumb\" no roteiro_jogo.json")
    quadro = pasta / "quadro_thumb.png"
    edicao._rodar(["-ss", f"{segundos(t['tempo']):.3f}", "-i", str(_video(pasta, t["arquivo"]).resolve()),
                   "-frames:v", "1", "-vf", "scale=1920:-2", str(quadro.resolve())])
    gerados = []
    for n, (l1, l2, *cor) in enumerate(t.get("textos", []), 1):
        destino = pasta / f"thumbnail_{n}.jpg"
        thumb_ia.montar_cinema(quadro, l1, l2, (cor or ["amarelo"])[0], destino, t.get("lado", "esquerda"))
        gerados.append(destino)
        print(f"  {destino.name}: {l1} / {l2}")
    print(f"{len(gerados)} thumbnail(s) em {pasta}")


# ---------------------------------------------------------------- mascote

def _flux_nvidia(modelo, prompt, semente):
    from . import visuais
    corpo = {"prompt": prompt, "width": 1024, "height": 1024}
    corpo.update({"mode": "base", "cfg_scale": 3.5, "steps": 30} if modelo == "flux.1-dev" else {"steps": 4})
    return visuais.flux_nvidia(corpo, modelo)


def _pollinations(prompt, semente):
    import urllib.parse
    import requests
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
           + f"?width=1024&height=1024&nologo=true&model=flux&seed={semente}")
    import time
    # o plano grátis aceita um pedido por vez: 429/503 logo depois de outra imagem é só esperar
    for espera in (20, 40, 60, None):
        resp = requests.get(url, timeout=240)
        if resp.ok and resp.headers.get("content-type", "").startswith("image/"):
            return resp.content
        if resp.status_code not in (429, 502, 503, 504) or espera is None:
            raise RuntimeError(f"Pollinations: erro {resp.status_code}")
        print(f"    Pollinations ocupado ({resp.status_code}), esperando {espera} s...")
        time.sleep(espera)


def mascote(variacoes=4, descricao=None):
    """Tenta o FLUX da NVIDIA (dev, depois schnell); se a chave não tiver acesso, usa o Pollinations (grátis, sem
    chave). O FLUX não aceita mais semente (seed): as variações saem diferentes a cada pedido."""
    destino = config.RAIZ / "canal_jogos"
    destino.mkdir(exist_ok=True)
    prompt = descricao or MASCOTE
    (destino / "prompt_mascote.txt").write_text(prompt + "\n", encoding="utf-8")
    fontes = []
    if config.NVIDIA_API_KEY:
        fontes += [("NVIDIA flux.1-dev", lambda s: _flux_nvidia("flux.1-dev", prompt, s)),
                   ("NVIDIA flux.1-schnell", lambda s: _flux_nvidia("flux.1-schnell", prompt, s))]
    fontes.append(("Pollinations", lambda s: _pollinations(prompt, s)))
    feitas = 0
    for n in range(1, variacoes + 1):
        semente = random.randint(1, 999999)
        while fontes:
            nome, gerar = fontes[0]
            try:
                dados = gerar(semente)
                break
            except Exception as e:  # noqa: BLE001 - qualquer falha passa para a próxima fonte
                print(f"  {nome} falhou ({e}); tentando a próxima")
                fontes.pop(0)
        else:
            sys.exit("Nenhuma fonte de imagem respondeu. Tente mais tarde ou gere fora com o texto de "
                     f"{destino / 'prompt_mascote.txt'}")
        arq = destino / f"mascote_{n}_semente{semente}.jpg"
        arq.write_bytes(dados)
        feitas += 1
        print(f"  {arq}  ({nome})")
    print(f"{feitas} opções. Escolha uma; para refazer parecida, use a mesma semente (está no nome do arquivo).")


# ---------------------------------------------------------------- comando

def comando(a):
    if a.acao == "mascote":
        return mascote(a.variacoes, a.descricao)
    if not a.projeto:
        sys.exit(f"Informe o projeto: .\\rodar.bat jogo {a.acao} <projeto>")
    pasta = config.PASTA_PROJETOS / a.projeto
    if a.acao == "preparar":
        (pasta / "gameplay").mkdir(parents=True, exist_ok=True)
        return preparar(pasta, a.intervalo, a.limiar, not a.sem_fala)
    if not pasta.exists():
        sys.exit(f'Projeto "{a.projeto}" não existe em {config.PASTA_PROJETOS}')
    {"gravar": para_gravar, "montar": montar, "thumb": thumbs}.get(a.acao, lambda p: curtos(p, a.so))(pasta)


def opcoes(s):
    s.add_argument("acao", choices=["preparar", "gravar", "montar", "curtos", "thumb", "mascote"])
    s.add_argument("projeto", nargs="?")
    s.add_argument("--intervalo", type=float, default=INTERVALO, help="preparar: segundos entre quadros (padrão 2.5)")
    s.add_argument("--limiar", type=float, default=LIMIAR_CENA, help="preparar: troca de cena, 0 a 1 (padrão 0.35)")
    s.add_argument("--sem-fala", action="store_true", help="preparar: não transcrever a fala do jogo")
    s.add_argument("--so", help="curtos: só o curto com este nome")
    s.add_argument("--variacoes", type=int, default=4, help="mascote: quantas opções")
    s.add_argument("--descricao", help="mascote: descrição em inglês no lugar da padrão")
    s.set_defaults(func=comando)
