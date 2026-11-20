"""Cortes de LIVE (Twitch, Kick; YouTube só no Windows): baixa só o necessário e acha os melhores momentos.

Só lives do PRÓPRIO dono (ou com autorização por escrito do criador): cortar live de outra pessoa dá Content ID,
strike e "conteúdo reutilizado".

Uso:
  python main.py live info <link>                          título, se está ao vivo e duração
  python main.py live baixar <link> <projeto> [--de 1:02:00 --ate 1:20:00] [--minutos 30]
        gravação (VOD) inteira ou só um trecho; live no ar: grava os próximos N minutos (--minutos)
  python main.py live momentos <projeto> [--quantos 10] [--duracao 45]
        acha os trechos mais animados (volume, gritos, risadas e fala) e transcreve só eles -> momentos.md
Depois: escolher os momentos, pôr em roteiro_jogo.json ("curtos" e/ou "trechos") e rodar
  python main.py jogo curtos <projeto>   (verticais 1080x1920)   e/ou   jogo preparar/montar (vídeo longo).

Na nuvem: Twitch e Kick funcionam; o YouTube pede "confirme que não é robô" para este servidor (no Windows vai).
"""
import json
import shutil
import subprocess
import sys

import numpy as np

from . import config

SR = 16000


def _ytdlp():
    exe = shutil.which("yt-dlp")
    return [exe] if exe else [sys.executable, "-m", "yt_dlp"]


def _avisar_youtube(link):
    if ("youtube.com" in link or "youtu.be" in link) and not config.NO_WINDOWS:
        print("  aviso: na nuvem o YouTube recusa este servidor; se falhar, rode este comando no Windows")


def info(link):
    _avisar_youtube(link)
    r = subprocess.run([*_ytdlp(), "-J", "--no-warnings", "--no-playlist", link], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Não consegui abrir o link: {r.stderr.strip()[-400:]}")
    d = json.loads(r.stdout)
    dur = d.get("duration")
    print(f"Título: {d.get('title')}\nCanal: {d.get('uploader') or d.get('channel')}\n"
          f"Ao vivo agora: {'sim' if d.get('is_live') else 'não'}"
          + (f"\nDuração: {int(dur // 3600)}h{int(dur % 3600 // 60):02d}min" if dur else ""))
    return d


def baixar(link, pasta, de=None, ate=None, minutos=None, altura=1080):
    """Baixa para projetos/<projeto>/gameplay/. Trecho (--de/--ate) baixa só aquele pedaço da gravação."""
    _avisar_youtube(link)
    destino_pasta = pasta / "gameplay"
    destino_pasta.mkdir(parents=True, exist_ok=True)
    print("Lembrete: só lives suas ou com autorização do criador.")
    formato = f"bv*[height<={altura}]+ba/b[height<={altura}]/b"
    if minutos:
        # Live no ar: grava os próximos N minutos direto do fluxo (sem esperar a live acabar)
        r = subprocess.run([*_ytdlp(), "-g", "-f", f"b[height<={altura}]/b", "--no-warnings", link],
                           capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            sys.exit(f"A live não está no ar ou o link falhou: {r.stderr.strip()[-300:]}")
        url = r.stdout.strip().splitlines()[0]
        from datetime import datetime
        destino = destino_pasta / f"live_{datetime.now():%Y%m%d_%H%M}.mp4"
        print(f"Gravando {minutos} min da live em {destino.name}...")
        proxy = ["-http_proxy", config.PROXY] if config.PROXY else []
        subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", *proxy, "-i", url, "-t", str(int(minutos * 60)),
                        "-c", "copy", "-bsf:a", "aac_adtstoasc", str(destino)], check=True)
        print(f"Pronto: {destino}")
        return destino
    args = [*_ytdlp(), "-f", formato, "--merge-output-format", "mp4", "--no-warnings", "--no-playlist",
            "-o", str(destino_pasta / ("live_%(id)s" + (f"_{de or 'inicio'}-{ate or 'fim'}".replace(":", "")
                                                          if de or ate else "") + ".%(ext)s")),
            "--print", "after_move:filepath"]
    if de or ate:
        args += ["--download-sections", f"*{de or '0'}-{ate or 'inf'}", "--force-keyframes-at-cuts"]
        if config.PROXY:  # o trecho é lido pelo ffmpeg, que na nuvem só sai pelo proxy se ele for passado
            args += ["--downloader-args", f"ffmpeg_i:-http_proxy {config.PROXY}"]
    args.append(link)
    print("Baixando" + (f" o trecho {de or 'início'} a {ate or 'fim'}" if de or ate else " a gravação inteira") + "...")
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Falhou: {r.stderr.strip()[-500:]}")
    arquivo = r.stdout.strip().splitlines()[-1]
    print(f"Pronto: {arquivo}")
    return arquivo


def _energia(video):
    """Volume (dB) a cada segundo, lendo só o áudio."""
    bruto = subprocess.run([config.ffmpeg(), "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(SR),
                            "-f", "f32le", "-"], capture_output=True, check=True).stdout
    som = np.frombuffer(bruto, dtype=np.float32)
    n = len(som) // SR
    blocos = som[:n * SR].reshape(n, SR)
    return 20 * np.log10(np.sqrt((blocos ** 2).mean(axis=1)) + 1e-6)


def _relogio(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def momentos(pasta, quantos=10, duracao=45, idioma="pt"):
    """Ranqueia janelas de `duracao` s pela animação do áudio (picos acima do normal da própria live) e transcreve
    só as escolhidas (Whisper no processador é ~1,5x o tempo do áudio: transcrever a live inteira levaria horas)."""
    from . import jogos
    videos = jogos.gameplays(pasta)
    if not videos:
        sys.exit(f"Nenhum vídeo em {pasta / 'gameplay'} (rode antes: live baixar)")
    achados = []
    for video in videos:
        print(f"{video.name}: medindo o áudio...")
        e = _energia(video)
        if len(e) < duracao:
            continue
        base, desvio = np.median(e), max(np.std(e), 1.0)
        z = (e - base) / desvio
        # Nota da janela: picos (gritos, risadas, explosões) pesam mais que o volume médio
        picos = np.convolve((z > 1.5).astype(float), np.ones(duracao), "valid")
        media = np.convolve(z, np.ones(duracao) / duracao, "valid")
        nota = picos * 1.0 + media * 4.0
        usados = np.zeros(len(e), bool)
        for ini in np.argsort(-nota):
            if len([a for a in achados if a["video"] == video.name]) >= quantos:
                break
            if usados[max(0, ini - 5):ini + duracao + 5].any():
                continue
            usados[ini:ini + duracao] = True
            achados.append({"video": video.name, "de": int(ini), "ate": int(ini + duracao), "nota": round(float(nota[ini]), 1)})
    achados.sort(key=lambda a: -a["nota"])
    achados = achados[:quantos]

    print(f"Transcrevendo os {len(achados)} melhores trechos (de uma vez só)...")
    tmp = pasta / "fala_jogo"
    tmp.mkdir(exist_ok=True)
    # Junta os trechos num áudio só, com 1 s de silêncio entre eles: o Whisper carrega uma vez só
    partes, inicio = [], 0.0
    for i, a in enumerate(achados, 1):
        wav = tmp / f"_momento_{i}.wav"
        subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-ss", str(a["de"]), "-t", str(duracao),
                        "-i", str(pasta / "gameplay" / a["video"]), "-vn", "-ac", "1", "-ar", str(SR), str(wav)],
                       check=True)
        a["_ini"], inicio = inicio, inicio + duracao + 1.0
        partes.append(wav)
    lista = tmp / "_momentos.txt"
    silencio = tmp / "_silencio.wav"
    subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", "1",
                    str(silencio)], check=True)
    lista.write_text("".join(f"file '{p.resolve().as_posix()}'\nfile '{silencio.resolve().as_posix()}'\n"
                             for p in partes), encoding="utf-8")
    junto, js = tmp / "_momentos.wav", tmp / "_momentos.json"
    subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista), str(junto)],
                   check=True)
    try:
        subprocess.run([sys.executable, "-u", "-m", "automacao.transcrever", str(junto), str(js), idioma],
                       check=True, cwd=config.RAIZ)
        palavras = json.loads(js.read_text(encoding="utf-8"))
    except (subprocess.CalledProcessError, OSError, ValueError) as e:
        print(f"  transcrição falhou ({e.__class__.__name__}); momentos saem sem a fala")
        palavras = []
    for p in [*partes, lista, silencio, junto, js]:
        p.unlink(missing_ok=True)
    for i, a in enumerate(achados, 1):
        ini = a.pop("_ini")
        a["fala"] = " ".join(p["w"] for p in palavras if ini <= p["s"] < ini + duracao).strip()
        # Quadro do meio do trecho para ver o que acontece
        quadro = pasta / "folhas" / f"momento_{i:02d}.jpg"
        quadro.parent.mkdir(exist_ok=True)
        subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-ss", str(a["de"] + duracao / 2),
                        "-i", str(pasta / "gameplay" / a["video"]), "-frames:v", "1", "-vf", "scale=640:-1",
                        str(quadro)], check=True)
        a["quadro"] = f"folhas/{quadro.name}"
        print(f"  {i}. {a['video']} {_relogio(a['de'])}-{_relogio(a['ate'])} nota {a['nota']}")

    (pasta / "momentos.json").write_text(json.dumps(achados, ensure_ascii=False, indent=2), encoding="utf-8")
    linhas = [f"# Melhores momentos: {pasta.name}", "",
              "Ordenados pela animação do áudio. CONFIRA o quadro e a fala antes de cortar: volume alto também pode ser "
              "só música ou barulho do jogo.", ""]
    for i, a in enumerate(achados, 1):
        linhas += [f"## {i}. {a['video']}  {_relogio(a['de'])} a {_relogio(a['ate'])}  (nota {a['nota']})", "",
                   f"![quadro]({a['quadro']})", "", f"Fala: {a.get('fala') or '—'}", "",
                   "Para curto (roteiro_jogo.json, campo \"curtos\"): "
                   f'{{"nome": "curto_{i}", "arquivo": "{a["video"]}", "de": "{_relogio(a["de"])}", '
                   f'"ate": "{_relogio(a["ate"])}", "textos": [{{"de": 0, "ate": 3, "texto": "GANCHO"}}]}}', ""]
    (pasta / "momentos.md").write_text("\n".join(linhas), encoding="utf-8")
    print(f"\nMomentos: {pasta / 'momentos.md'}\nPróximo passo: copiar os escolhidos para roteiro_jogo.json "
          "e rodar: python main.py jogo curtos " + pasta.name)
    return achados


def comando(a):
    if a.acao == "info":
        return info(a.alvo)
    if a.acao == "baixar":
        if not a.projeto:
            sys.exit("Diga o projeto: live baixar <link> <projeto>")
        return baixar(a.alvo, config.RAIZ / "projetos" / a.projeto, a.de, a.ate, a.minutos)
    return momentos(config.RAIZ / "projetos" / a.alvo, a.quantos, a.duracao, a.idioma)


def opcoes(s):
    s.add_argument("acao", choices=["info", "baixar", "momentos"])
    s.add_argument("alvo", help="info/baixar: link da live ou da gravação; momentos: nome do projeto")
    s.add_argument("projeto", nargs="?", help="baixar: nome do projeto (pasta em projetos/)")
    s.add_argument("--de", help="baixar só a partir de (ex.: 1:02:00)")
    s.add_argument("--ate", help="baixar só até (ex.: 1:20:00)")
    s.add_argument("--minutos", type=float, help="live no ar: gravar os próximos N minutos")
    s.add_argument("--quantos", type=int, default=10, help="momentos: quantos trechos sugerir")
    s.add_argument("--duracao", type=int, default=45, help="momentos: segundos de cada trecho (curtos: 30 a 60)")
    s.add_argument("--idioma", default="pt", help="momentos: idioma da fala (pt, es, en...)")
    s.set_defaults(func=comando)
