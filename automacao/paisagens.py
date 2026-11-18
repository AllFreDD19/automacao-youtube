"""Biblioteca FIXA de vídeos de paisagem (drone) para os vídeos de HISTÓRIA (fundo contínuo, trazido da Fábrica de
Vídeos do usuário em 24/10/2026). Fica em biblioteca/paisagens/, fora de projetos/, e não some na limpeza.

    .venv\\Scripts\\python.exe -m automacao.paisagens restaurar     → baixa os clipes do lista.json que faltam
    .venv\\Scripts\\python.exe -m automacao.paisagens resumo
    .venv\\Scripts\\python.exe -m automacao.paisagens excluir 012 015   → nunca usar (cidade, estrada, gente...)

Cada clipe vem do Pixabay (licença livre, sem crédito obrigatório) e é convertido UMA vez para 1920x1080, 30 fps,
sem som, com quadro-chave a cada 1 s (corte rápido e exato).
"""
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests

from . import config

PASTA = config.RAIZ / "biblioteca" / "paisagens"
CLIPES = PASTA / "clipes"
INDICE = PASTA / "lista.json"


def carregar():
    return json.loads(INDICE.read_text(encoding="utf-8")) if INDICE.exists() else {"clipes": {}}


def salvar(ind):
    INDICE.write_text(json.dumps(ind, ensure_ascii=False, indent=1), encoding="utf-8")


def _normalizar(origem, destino):
    r = subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-i", str(origem), "-an",
                        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=30,"
                               "format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "30", "-movflags", "+faststart",
                        str(destino)], capture_output=True, text=True)
    return r.returncode == 0 and destino.exists()


def _baixar_um(nome, clipe):
    bruto = CLIPES / f"_{nome}.mp4"
    try:
        r = requests.get(clipe["url"], timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        bruto.write_bytes(r.content)
        return _normalizar(bruto, CLIPES / f"{nome}.mp4")
    except Exception as e:
        print(f"   {nome}: {e}", flush=True)
        return False
    finally:
        bruto.unlink(missing_ok=True)


def restaurar():
    CLIPES.mkdir(parents=True, exist_ok=True)
    faltam = [(n, c) for n, c in carregar()["clipes"].items()
              if not c.get("excluido") and not (CLIPES / f"{n}.mp4").exists()]
    print(f"{len(faltam)} clipes para baixar", flush=True)
    with ThreadPoolExecutor(4) as ex:
        resultados = list(ex.map(lambda nc: _baixar_um(*nc), faltam))
    falhas = [n for (n, _), ok in zip(faltam, resultados) if not ok]
    print("pronto" + (f"; falharam (rode de novo): {' '.join(falhas)}" if falhas else ""), flush=True)


def disponiveis(temas=None):
    ok = {n: c for n, c in carregar()["clipes"].items() if not c.get("excluido") and (CLIPES / f"{n}.mp4").exists()}
    if temas:
        ok = {n: c for n, c in ok.items() if c["tema"] in temas} or ok
    if not ok:
        raise RuntimeError("biblioteca de paisagens vazia: rodar  python -m automacao.paisagens restaurar")
    return ok


def resumo():
    ok = disponiveis()
    print(f"{len(ok)} clipes ({sum(c['segundos'] for c in ok.values()) / 60:.0f} min de imagens)")
    print("por tema:", dict(Counter(c["tema"] for c in ok.values())))


def excluir(nomes):
    ind = carregar()
    for n in nomes:
        if n in ind["clipes"]:
            ind["clipes"][n]["excluido"] = True
    salvar(ind)
    print("excluídos:", " ".join(nomes))


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "resumo"
    {"restaurar": restaurar, "resumo": resumo}.get(acao, lambda: excluir(sys.argv[2:]))()
