"""Gera para_gravar.txt (só o texto lido em voz alta) a partir da seção "## Roteiro" de um roteiro.md escrito à mão
(capítulos marcados com "### 1", "### 2"...) e confere tamanho e algarismos esquecidos.
Uso: python modelos/para_gravar.py projetos/<pasta>"""
import re
import sys
from pathlib import Path

pasta = Path(sys.argv[1])
md = (pasta / "roteiro.md").read_text(encoding="utf-8")
corpo = md.split("## Roteiro", 1)[1].split("## Abertura alternativa", 1)[0]
caps = [c.strip() for c in re.split(r"^### \d+\s*$", corpo, flags=re.M) if c.strip()]
texto = "\n\n".join(caps)
(pasta / "para_gravar.txt").write_text(texto + "\n", encoding="utf-8")
for i, c in enumerate(caps, 1):
    print(f"capitulo {i}: {len(c)} caracteres")
print("total:", len(texto), "| estimativa:", round(len(texto) / 900, 1), "min a 900 car/min")
digitos = re.findall(r"[^\n]{0,30}\d[^\n]{0,30}", texto)
print("algarismos no texto:", digitos or "nenhum")
