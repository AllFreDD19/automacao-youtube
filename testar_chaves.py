"""Confere se as chaves do .env funcionam (sem mostrar as chaves)."""
import sys
import tempfile
from pathlib import Path

import requests

from automacao import config, llm, visuais

sys.stdout.reconfigure(encoding="utf-8")


def checar(nome, funcao):
    try:
        print(f"[OK]   {nome}: {funcao()}")
    except BaseException as e:
        print(f"[ERRO] {nome}: {str(e)[:300]}")


def nemotron():
    return llm.chat("Responda apenas: funcionando", max_tokens=50)


def pixabay_imagem():
    hits = visuais._pixabay("", "ancient pyramid", image_type="photo", orientation="horizontal")
    if not hits:
        raise RuntimeError("nenhum resultado (chave inválida?)")
    return f"{len(hits)} imagens encontradas"


def pixabay_video():
    hits = visuais._pixabay("videos/", "desert dunes")
    if not hits:
        raise RuntimeError("nenhum resultado")
    return f"{len(hits)} vídeos encontrados"


def nvidia_imagem():
    destino = Path(tempfile.gettempdir()) / "teste_flux.jpg"
    visuais.imagem_nvidia("a lighthouse on a cliff at sunset", destino, 1)
    return f"imagem gerada ({destino.stat().st_size // 1024} KB)"


def youtube():
    if not config.YOUTUBE_API_KEY:
        raise RuntimeError("ainda não preenchida (opcional por enquanto)")
    r = requests.get("https://www.googleapis.com/youtube/v3/videos",
                     params={"part": "id", "chart": "mostPopular", "regionCode": "BR", "maxResults": 1,
                             "key": config.YOUTUBE_API_KEY}, timeout=30)
    r.raise_for_status()
    return "respondendo"


for nome, chave in [("NVIDIA_API_KEY", config.NVIDIA_API_KEY), ("PIXABAY_API_KEY", config.PIXABAY_API_KEY),
                    ("YOUTUBE_API_KEY", config.YOUTUBE_API_KEY)]:
    print(f"{nome}: {'preenchida (' + str(len(chave)) + ' caracteres)' if chave else 'VAZIA'}")
print()
checar("Nemotron (roteiros)", nemotron)
checar("Pixabay imagens", pixabay_imagem)
checar("Pixabay vídeos", pixabay_video)
checar("NVIDIA FLUX (imagens IA)", nvidia_imagem)
checar("YouTube API (pesquisa)", youtube)
