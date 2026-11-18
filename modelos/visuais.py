"""Roda `visuais` deste projeto sem nunca escolher os visuais de _bloqueados.json (rejeitados na folha_cenas.jpg)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA.parents[1]))
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
import main  # noqa: E402
from automacao import visuais  # noqa: E402

arq = PASTA / "_bloqueados.json"
bloqueados = {tuple(c) for c in json.loads(arq.read_text(encoding="utf-8"))} if arq.exists() else set()
original = visuais._buscar_visual


def _buscar_sem_bloqueados(cena, pasta, usados):
    usados |= bloqueados  # `usados` é o mesmo conjunto para todas as cenas: o bloqueio vale para a busca inteira
    return original(cena, pasta, usados)


visuais._buscar_visual = _buscar_sem_bloqueados
main.cmd_visuais(SimpleNamespace(projeto=PASTA.name))
