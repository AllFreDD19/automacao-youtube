"""Produção completa a partir de um roteiro já montado (_montar.py): narrar, visuais, editar, thumb.
(O apresentador só entra se APRESENTADOR=sim no .env; hoje está desligado.)
Não usa o comando `tudo` porque ele escreveria um roteiro novo por cima. Copiar para projetos/<novo>/_produzir.py.
Uso: python _produzir.py [narrar] [visuais] [editar] [thumb]   (sem argumentos faz tudo)"""
import sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
import main  # noqa: E402
from automacao import config  # noqa: E402

a = SimpleNamespace(projeto=Path(__file__).resolve().parent.name, voz=None)
etapas = sys.argv[1:] or ["narrar", "visuais", "editar", "thumb"]
if "narrar" in etapas:
    main.cmd_narrar(a)
if "visuais" in etapas:
    main.cmd_visuais(a, com_apresentador=config.APRESENTADOR)
if "editar" in etapas:
    main.cmd_editar(a)
if "thumb" in etapas:
    main.cmd_thumb(a)
