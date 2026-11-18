"""Troca as buscas das cenas com imagem sem relação ou repetida (vistas na folha_cenas.jpg) e apaga os visuais delas.
Valor: (busca_stock, busca_wiki, parte). busca_wiki "" = só bancos de imagem/vídeo. parte: "main" = visual principal,
"extra" = só o segundo visual da fala longa (o "b" da folha), "ambos" = os dois.
A origem (chave) de cada visual trocado vai para _bloqueados.json, e _visuais.py nunca mais a escolhe: sem isso o
mesmo avião errado voltava em outra cena. Depois rodar: python _visuais.py (no máximo 2 rodadas por vídeo)."""
import json
from pathlib import Path

PASTA = Path(__file__).resolve().parent
TROCAS = {
    18: ("old car", "", "main"),
    66: ("car production line", "Saab 900", "ambos"),
    68: ("red hatchback", "", "extra"),
}

arq_bloq = PASTA / "_bloqueados.json"
bloqueados = json.loads(arq_bloq.read_text(encoding="utf-8")) if arq_bloq.exists() else []
r = json.loads((PASTA / "roteiro.json").read_text(encoding="utf-8"))
for cena in r["cenas"]:
    if cena["id"] not in TROCAS:
        continue
    stock, wiki, parte = TROCAS[cena["id"]]
    if parte in ("extra", "ambos"):
        if cena.get("chave_extra"):
            bloqueados.append(cena["chave_extra"])
        if cena.get("visual_extra"):
            (PASTA / cena["visual_extra"]).unlink(missing_ok=True)
        for chave in ("visual_extra", "visual_extra_tipo", "nota_extra", "chave_extra", "credito_extra"):
            cena.pop(chave, None)
    if parte in ("main", "ambos"):
        if cena.get("chave") and not cena.get("visual_reaproveitado"):
            bloqueados.append(cena["chave"])
        if cena.get("visual_arquivo") and not cena.get("visual_reaproveitado"):
            (PASTA / cena["visual_arquivo"]).unlink(missing_ok=True)
        for chave in ("visual_arquivo", "visual_tipo", "visual_reaproveitado", "nota", "chave", "credito"):
            cena.pop(chave, None)
        cena["busca_wiki"] = wiki
        cena["visual"] = "ia" if wiki else "stock"
    cena["busca_stock"] = stock
    cena["prompt_imagem"] = f"{wiki or stock}, photorealistic"
(PASTA / "roteiro.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
arq_bloq.write_text(json.dumps(bloqueados), encoding="utf-8")
print(f"{len(TROCAS)} cenas para buscar de novo, {len(bloqueados)} visuais bloqueados")
