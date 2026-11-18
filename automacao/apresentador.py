"""Apresentador de IA: um rosto fictício que fala nas cenas de interação com o público
(abertura, pedidos de inscrição, perguntas ao espectador). Usa o SadTalker localmente, grátis.

O SadTalker roda num Python 3.10 separado (apresentador/.venv310); se não estiver instalado,
o vídeo sai normalmente, só sem o apresentador.
"""
import json
import os
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from . import config

PASTA = config.RAIZ / "apresentador"
PYTHON = PASTA / ".venv310" / "Scripts" / "python.exe"
SADTALKER = PASTA / "SadTalker-main"
ROSTO = PASTA / "rosto.jpg"
DIAMETRO = 380      # janela redonda no canto, em pixels do vídeo 1920x1080
MAX_CENAS = 6       # aparições por vídeo: o suficiente para interagir sem cansar
# O SadTalker leva ~16x a duração da fala na RTX 3050 (com GFPGAN para nitidez):
# 75 s de apresentador ≈ 20 min de geração, que rodam em paralelo com a busca de visuais
MAX_SEGUNDOS = 75
# Pedido de inscrição em vários idiomas
CTA = re.compile(r"subscri|inscrev|inscri|iscriv|suscr|abonn", re.I)


def disponivel():
    return PYTHON.exists() and (SADTALKER / "checkpoints" / "SadTalker_V0.0.2_256.safetensors").exists() and ROSTO.exists()


def escolher_cenas(roteiro):
    """Abertura + pedidos de inscrição + perguntas ao público, respeitando os limites."""
    cenas = roteiro["cenas"]
    candidatas = [cenas[0]]
    candidatas += [c for c in cenas[1:] if CTA.search(c["narracao"])]
    candidatas += [c for c in cenas[1:] if c["narracao"].rstrip().endswith("?") and c not in candidatas]
    escolhidas, tempo = [], 0.0
    for c in candidatas:
        if len(escolhidas) >= MAX_CENAS or tempo + c.get("duracao", 0) > MAX_SEGUNDOS:
            continue
        escolhidas.append(c)
        tempo += c.get("duracao", 0)
    return sorted(escolhidas, key=lambda c: c["id"])


def gerar(roteiro, pasta_projeto):
    if not disponivel():
        print("  apresentador: SadTalker não instalado (rode apresentador\\instalar.ps1); seguindo sem ele")
        return roteiro
    pasta = pasta_projeto / "apresentador"
    pasta.mkdir(exist_ok=True)
    for cena in roteiro["cenas"]:
        cena.pop("apresentador_video", None)

    lista = []
    for cena in escolher_cenas(roteiro):
        audio = pasta_projeto / cena["audio"]
        saida = pasta / f"cena_{cena['id']:03d}.mp4"
        cena["apresentador_video"] = str(saida.relative_to(pasta_projeto))
        if saida.exists() and saida.stat().st_mtime > audio.stat().st_mtime:
            continue
        wav = pasta / f"cena_{cena['id']:03d}.wav"
        subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", "-i", str(audio), "-ar", "16000", "-ac", "1",
                        str(wav)], check=True)
        lista.append({"audio": str(wav), "saida": str(saida)})

    if lista:
        arquivo_lista = pasta / "_lista.json"
        arquivo_lista.write_text(json.dumps(lista), encoding="utf-8")
        print(f"  apresentador: gerando {len(lista)} fala(s) com o SadTalker...")
        # O SadTalker chama o ffmpeg pelo nome para juntar o áudio ao rosto
        ambiente = {**os.environ, "PATH": f"{Path(config.ffmpeg()).parent}{os.pathsep}{os.environ.get('PATH', '')}"}
        r = subprocess.run([str(PYTHON), "falar_lote.py", str(ROSTO), str(arquivo_lista)], cwd=SADTALKER,
                           env=ambiente, capture_output=True, text=True, encoding="utf-8", errors="replace")
        for linha in r.stdout.splitlines():
            if linha.startswith("["):
                print(f"    {linha}")
        if r.returncode != 0:
            print(f"  apresentador: o SadTalker falhou; seguindo sem ele\n{r.stderr[-800:]}")
            for cena in roteiro["cenas"]:
                cena.pop("apresentador_video", None)
            return roteiro
        for item in lista:
            (pasta / item["audio"]).unlink(missing_ok=True)
    usadas = [c["id"] for c in roteiro["cenas"] if c.get("apresentador_video")]
    print(f"  apresentador nas cenas: {usadas}")
    return roteiro


def mascaras():
    """Máscara redonda (onde o rosto aparece) e aro branco com sombra, criadas uma vez."""
    mascara, aro = PASTA / "mascara.png", PASTA / "aro.png"
    if not mascara.exists():
        m = Image.new("L", (DIAMETRO, DIAMETRO), 0)
        ImageDraw.Draw(m).ellipse([0, 0, DIAMETRO - 1, DIAMETRO - 1], fill=255)
        m.save(mascara)
    if not aro.exists():
        borda = 8
        lado = DIAMETRO + 2 * borda
        a = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        d = ImageDraw.Draw(a)
        d.ellipse([0, 0, lado - 1, lado - 1], outline=(255, 255, 255, 255), width=borda)
        a.save(aro)
    return mascara, aro
