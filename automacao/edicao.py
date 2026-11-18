"""Etapa 6b: edição final com FFmpeg — cenas, legendas, música e capítulos."""
import json
import math
import random
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

from . import apresentador, config

LARGURA, ALTURA, FPS = 1920, 1080, 30
PAUSA = 0.35  # respiro entre cenas, em segundos
# Transições no estilo da referência do usuário (canal "China Under Stress"): fusão curta entre cenas e, na virada de
# seção (ex.: do item #5 para o #4), uma transição marcada alternando zoom rápido e flash claro de luz.
# Só a imagem faz a transição; a narração segue intacta, então legendas e capítulos não mudam.
TRANSICAO = (0.4, "fade")
TRANSICOES_SECAO = [(0.6, "zoomin"), (0.6, "fadewhite")]
CENAS_EM_PARALELO = 4
CODEC_X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
CODEC_NVENC = ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "21", "-b:v", "0"]
CODEC_AUDIO = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


@lru_cache(maxsize=1)
def _tem_nvenc():
    teste = subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                            "color=c=black:s=256x256:d=0.2", *CODEC_NVENC, "-f", "null", "-"], capture_output=True)
    return teste.returncode == 0


def _codec_video(final=False):
    """Usa a placa NVIDIA (NVENC, ~2x mais rápido) se existir; senão o x264 no processador.

    No arquivo final o NVENC mira ~8 Mbps, a taxa que o YouTube recomenda para enviar 1080p30
    (o usuário prefere qualidade a arquivo pequeno); o teto de 12 Mbps evita picos sem ganho visível.
    """
    if not _tem_nvenc():
        escolhido = CODEC_X264
    elif final:
        escolhido = ["-c:v", "h264_nvenc", "-preset", "p6", "-rc", "vbr", "-cq", "21", "-b:v", "8M",
                     "-maxrate", "12M", "-bufsize", "24M"]
    else:
        escolhido = CODEC_NVENC
    return [*escolhido, "-pix_fmt", "yuv420p", "-r", str(FPS)]


def _rodar(args, cwd=None):
    r = subprocess.run([config.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", *args],
                       cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {r.stderr[-1500:]}")


def _fundo(visual, tipo, dur, semente):
    """Entrada do FFmpeg e filtro de um visual que ocupa `dur` segundos."""
    ajuste = f"scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,crop={LARGURA}:{ALTURA}"
    if visual and visual.exists() and tipo == "video":
        return ["-stream_loop", "-1", "-i", str(visual)], f"{ajuste},fps={FPS},format=yuv420p"
    if visual and visual.exists():
        # Efeito Ken Burns: zoom lento alternando aproximar/afastar
        quadros = int(dur * FPS) + 1
        zoom = "min(1.0+0.0007*on,1.25)" if semente % 2 else "max(1.25-0.0007*on,1.0)"
        return ["-i", str(visual)], (
            f"scale={LARGURA * 2}:{ALTURA * 2}:force_original_aspect_ratio=increase,crop={LARGURA * 2}:{ALTURA * 2},"
            f"zoompan=z='{zoom}':d={quadros}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={LARGURA}x{ALTURA}:fps={FPS},format=yuv420p")
    return ["-f", "lavfi", "-i", f"color=c=0x101018:s={LARGURA}x{ALTURA}:r={FPS}"], "format=yuv420p"


def _clipe_cena(cena, pasta_projeto, destino, cauda=0.0):
    """Renderiza a cena. `cauda` = segundos extras de imagem no fim (com áudio em silêncio), consumidos pela
    transição com a cena seguinte."""
    dur = cena["duracao"] + PAUSA + cauda
    audio = pasta_projeto / cena["audio"]
    # Fala longa ganha uma segunda imagem/vídeo na metade, para a tela mudar a cada ~8 segundos
    # sem cortar a frase da narração no meio
    partes = [(cena.get("visual_arquivo"), cena.get("visual_tipo"))]
    if cena.get("visual_extra") and (pasta_projeto / cena["visual_extra"]).exists():
        partes.append((cena["visual_extra"], cena.get("visual_extra_tipo")))
    # Com dois visuais, o primeiro ganha a sobra da fusão (TRANSICAO) para trocar com a mesma suavidade das cenas
    metade = dur / len(partes)
    fusao = TRANSICAO[0] if len(partes) > 1 else 0.0
    duracoes = [metade + fusao, dur - metade][:len(partes)] if len(partes) > 1 else [dur]

    entradas, grafo = [], []
    for i, ((arquivo, tipo), d) in enumerate(zip(partes, duracoes)):
        entrada, filtro = _fundo(pasta_projeto / arquivo if arquivo else None, tipo, d, cena["id"] + i)
        entradas += entrada
        grafo.append(f"[{i}:v]{filtro},trim=duration={d:.3f},setpts=PTS-STARTPTS,settb=AVTB[p{i}]")
    if len(partes) > 1:
        grafo.append(f"[p0][p1]xfade=transition={TRANSICAO[1]}:duration={fusao:.3f}:offset={metade:.3f}[fundo]")
    else:
        grafo.append("[p0]null[fundo]")
    ia = len(partes)  # índice da entrada de áudio
    entradas += ["-i", str(audio)]

    rosto = pasta_projeto / cena["apresentador_video"] if cena.get("apresentador_video") else None
    if rosto and rosto.exists():
        # Apresentador numa janela redonda no canto direito, acima da área da legenda
        mascara, aro = apresentador.mascaras()
        d = apresentador.DIAMETRO
        # Base do círculo em y≈800: a legenda ocupa ~840-1035 e linhas longas chegavam por baixo da janela
        x, y = LARGURA - d - 70, ALTURA - d - 280
        entradas += ["-i", str(rosto), "-loop", "1", "-i", str(mascara), "-loop", "1", "-i", str(aro)]
        grafo += [f"[{ia + 1}:v]scale={d}:{d}:force_original_aspect_ratio=increase,crop={d}:{d},fps={FPS},"
                  f"tpad=stop_mode=clone:stop_duration=3,format=rgba[rosto]",
                  f"[{ia + 2}:v]format=gray,scale={d}:{d}[mascara]",
                  "[rosto][mascara]alphamerge[circulo]",
                  f"[fundo][circulo]overlay={x}:{y}[v1]",
                  f"[v1][{ia + 3}:v]overlay={x - 8}:{y - 8},format=yuv420p[v]"]
    else:
        grafo.append("[fundo]format=yuv420p[v]")

    _rodar([*entradas, "-t", f"{dur:.3f}", "-filter_complex", ";".join(grafo), "-af", "apad",
            "-map", "[v]", "-map", f"{ia}:a", *_codec_video(), *CODEC_AUDIO, str(destino)])


def _transicoes(roteiro):
    """(cauda, tipo) da transição depois de cada cena; a última cena não tem."""
    resultado, viradas = [], 0
    cenas = roteiro["cenas"]
    for i, cena in enumerate(cenas):
        if i == len(cenas) - 1:
            resultado.append((0.0, "fade"))
        elif cenas[i + 1].get("secao") != cena.get("secao"):
            resultado.append(TRANSICOES_SECAO[viradas % len(TRANSICOES_SECAO)])
            viradas += 1
        else:
            resultado.append(TRANSICAO)
    return resultado


def _juntar(itens, destino):
    """Junta clipes com transição de imagem (xfade) e áudio emendado sem sobreposição.

    Cada item: {"arquivo", "d" (duração útil), "cauda" (sobra de imagem no fim), "transicao" (tipo, para o próximo)}.
    O resultado tem imagem de d total + a cauda do último item, e áudio de d total; serve de item para outra junção.
    """
    if len(itens) == 1:
        return itens[0]
    entradas, grafo = [], []
    for i, it in enumerate(itens):
        entradas += ["-i", str(it["arquivo"])]
        grafo.append(f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps={FPS},format=yuv420p[v{i}]")
        grafo.append(f"[{i}:a]atrim=0:{it['d']:.3f},asetpts=PTS-STARTPTS[a{i}]")
    atual, acumulado = "v0", 0.0
    for k in range(1, len(itens)):
        anterior = itens[k - 1]
        acumulado += anterior["d"]
        grafo.append(f"[{atual}][v{k}]xfade=transition={anterior['transicao']}:duration={anterior['cauda']:.3f}"
                     f":offset={acumulado:.3f}[x{k}]")
        atual = f"x{k}"
    grafo.append("".join(f"[a{i}]" for i in range(len(itens))) + f"concat=n={len(itens)}:v=0:a=1[a]")
    _rodar([*entradas, "-filter_complex", ";".join(grafo), "-map", f"[{atual}]", "-map", "[a]",
            *_codec_video(final=True), *CODEC_AUDIO, str(destino)])
    return {"arquivo": destino, "d": sum(it["d"] for it in itens), "cauda": itens[-1]["cauda"],
            "transicao": itens[-1]["transicao"]}


def _tempo_srt(seg):
    ms = int(round(seg * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def gerar_legendas(roteiro, destino, palavras_por_bloco=6):
    """Divide a narração em blocos curtos e distribui o tempo pelo tamanho de cada bloco."""
    blocos, inicio_cena = [], 0.0
    for cena in roteiro["cenas"]:
        palavras = cena["narracao"].split()
        partes = [" ".join(palavras[i:i + palavras_por_bloco]) for i in range(0, len(palavras), palavras_por_bloco)]
        total_chars = sum(len(p) for p in partes) or 1
        t = inicio_cena
        for p in partes:
            dur = cena["duracao"] * len(p) / total_chars
            blocos.append((t, t + dur, p))
            t += dur
        inicio_cena += cena["duracao"] + PAUSA
    linhas = []
    for i, (ini, fim, texto) in enumerate(blocos, 1):
        linhas += [str(i), f"{_tempo_srt(ini)} --> {_tempo_srt(fim)}", texto, ""]
    destino.write_text("\n".join(linhas), encoding="utf-8")


def capitulos(roteiro):
    """Timestamps das seções para colar na descrição do YouTube."""
    linhas, t, secao = [], 0.0, None
    for cena in roteiro["cenas"]:
        if cena.get("secao") != secao:
            secao = cena.get("secao")
            m, s = divmod(int(t), 60)
            linhas.append(f"{m:02d}:{s:02d} {secao}")
        t += cena["duracao"] + PAUSA
    return linhas


def _escolher_musica():
    musicas = [p for p in config.PASTA_MUSICAS.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")]
    return random.choice(musicas) if musicas else None


def editar(roteiro, pasta_projeto, nome_saida="video_final.mp4"):
    pasta_cenas = pasta_projeto / "cenas"
    pasta_cenas.mkdir(exist_ok=True)

    # Cenas de encoders diferentes não podem ser juntadas sem recodificar: se o encoder mudou, refaz todas
    marcador = pasta_cenas / ".encoder"
    encoder = _codec_video()[1]
    refazer_todas = marcador.exists() is False or marcador.read_text() != encoder

    # A sobra de imagem de cada cena depende da transição seguinte: se ela mudou, a cena é refeita
    transicoes = _transicoes(roteiro)
    arquivo_caudas = pasta_cenas / ".caudas.json"
    try:
        caudas_antes = json.loads(arquivo_caudas.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        caudas_antes = {}

    itens, pendentes = [], []
    for cena, (cauda, tipo) in zip(roteiro["cenas"], transicoes):
        destino = pasta_cenas / f"cena_{cena['id']:03d}.mp4"
        fontes = [pasta_projeto / cena["audio"]]
        for campo in ("visual_arquivo", "visual_extra"):
            if cena.get(campo) and (pasta_projeto / cena[campo]).exists():
                fontes.append(pasta_projeto / cena[campo])
        if cena.get("apresentador_video"):
            fontes.append(pasta_projeto / cena["apresentador_video"])
        desatualizado = destino.exists() and any(f.stat().st_mtime > destino.stat().st_mtime for f in fontes)
        if (refazer_todas or not destino.exists() or desatualizado
                or caudas_antes.get(str(cena["id"])) != cauda):
            pendentes.append((cena, destino, cauda))
        itens.append({"arquivo": destino, "d": cena["duracao"] + PAUSA, "cauda": cauda, "transicao": tipo})

    if pendentes:
        print(f"  renderizando {len(pendentes)} cena(s), {CENAS_EM_PARALELO} por vez ({encoder})...")
        with ThreadPoolExecutor(CENAS_EM_PARALELO) as pool:
            futuros = [pool.submit(_clipe_cena, cena, pasta_projeto, destino, cauda)
                       for cena, destino, cauda in pendentes]
            for feitos, futuro in enumerate(as_completed(futuros), 1):
                futuro.result()
                if feitos % 20 == 0 or feitos == len(futuros):
                    print(f"    {feitos}/{len(futuros)}")
        marcador.write_text(encoder)
        arquivo_caudas.write_text(json.dumps({str(c["id"]): t[0] for c, t in zip(roteiro["cenas"], transicoes)}),
                                  encoding="utf-8")

    # Junta em grupos de ~raiz(n) cenas e depois os grupos: só duas recodificações, qualquer que seja o tamanho
    print("  juntando cenas com transições...")
    tamanho = max(2, math.ceil(math.sqrt(len(itens))))
    grupos = [_juntar(itens[i:i + tamanho], pasta_cenas / f"_grupo_{i // tamanho:03d}.mp4")
              for i in range(0, len(itens), tamanho)]
    final = _juntar(grupos, pasta_cenas / "_todos.mp4")
    (pasta_projeto / "montado.mp4").unlink(missing_ok=True)
    if final["arquivo"].name.startswith("_"):
        final["arquivo"].replace(pasta_projeto / "montado.mp4")
    else:  # vídeo de uma cena só: o clipe da cena fica no lugar (é cache para a próxima edição)
        shutil.copy(final["arquivo"], pasta_projeto / "montado.mp4")
    for g in pasta_cenas.glob("_grupo_*.mp4"):
        g.unlink()

    gerar_legendas(roteiro, pasta_projeto / "legendas.srt")
    musica = _escolher_musica()

    entradas = ["-i", "montado.mp4"]
    filtros, mapa_audio = [], "0:a"
    if config.LEGENDAS:
        estilo = ("FontName=Arial,FontSize=20,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                  "BorderStyle=1,Outline=2,Shadow=1,MarginV=45")
        filtros.append(f"[0:v]subtitles=legendas.srt:force_style='{estilo}'[v]")
        mapa_video = "[v]"
    else:
        mapa_video = "0:v"
    if musica:
        print(f"  música de fundo: {musica.name}")
        entradas += ["-stream_loop", "-1", "-i", str(musica)]
        filtros.append(f"[1:a]volume={config.MUSICA_VOLUME},afade=t=in:d=2[m];"
                       "[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
        mapa_audio = "[a]"

    print("  renderizando vídeo final (legendas + música)...")
    args = [*entradas]
    if filtros:
        args += ["-filter_complex", ";".join(filtros)]
    args += ["-map", mapa_video, "-map", mapa_audio, *_codec_video(final=True), *CODEC_AUDIO, "-movflags", "+faststart", nome_saida]
    _rodar(args, cwd=pasta_projeto)
    (pasta_projeto / "montado.mp4").unlink(missing_ok=True)
    return pasta_projeto / nome_saida
