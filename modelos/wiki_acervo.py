"""2ª (e última) rodada de revisão: baixa um acervo de fotos do Commons (Ju 87, Udet, Milch, Rudel...) e o CLIP
escolhe, para cada cena com visual ruim, a melhor foto ainda não usada no vídeo. Crédito e licença vão para a cena."""
import json
import re
import sys
import time
from pathlib import Path

import requests

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA.parents[1]))
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
from automacao import relevancia, visuais  # noqa: E402

# grupo: buscas no Commons (o nome do arquivo precisa ter todas as palavras)
ACERVOS = {
    "ju87": ["Bundesarchiv Junkers Ju 87", "Junkers Ju 87", "Ju 87 Stuka", "Bundesarchiv Ju 87", "Junkers Ju87"],
    "udet": ["Ernst Udet"], "milch": ["Erhard Milch"], "rudel": ["Hans-Ulrich Rudel"], "wever": ["Walther Wever"],
}
# cena: grupo (a cena 'b' ruim é descartada e a fala fica com um visual só)
CENAS = {i: "ju87" for i in (7, 9, 16, 17, 22, 29, 31, 33, 34, 36, 37, 38, 39, 40, 41, 46, 47, 49, 50, 52, 54, 55,
                             56, 58, 61, 62, 63, 66, 67, 68, 69, 85, 86, 89, 94, 95, 102, 103, 112, 114, 118, 119,
                             129, 132, 134)}
CENAS.update({10: "udet", 11: "udet", 23: "udet", 43: "udet", 14: "milch", 27: "wever", 117: "rudel"})
SEM_EXTRA = {36, 54, 85, 117}


def buscar(termo):
    arquivos, cont = [], {}
    for _ in range(3):
        for tentativa in range(6):  # 429 = limite do Commons: espera o que ele pedir
            time.sleep(2)
            resp = requests.get(visuais.WIKI_API, headers=visuais.WIKI_HEADERS, timeout=30, params={
                "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 50,
                "gsrsearch": f"{termo} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|size|extmetadata",
                "iiurlwidth": 1920, **cont})
            if resp.status_code != 429:
                break
            time.sleep(int(resp.headers.get("retry-after", 30)) + 2)
        r = resp.json()
        arquivos += list(r.get("query", {}).get("pages", {}).values())
        if "continue" not in r:
            break
        cont = r["continue"]
    return arquivos


def acervo(termos):
    vistos, saida = set(), []
    for termo in termos:
        palavras = {p for p in re.findall(r"[a-z0-9]+", termo.lower()) if len(p) > 1}
        for p in buscar(termo):
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            licenca = visuais._limpar_html(meta.get("LicenseShortName", {}).get("value"))
            titulo = p.get("title", "").removeprefix("File:")
            prop = info.get("width", 0) / max(info.get("height", 1), 1)
            if (p["pageid"] in vistos or info.get("width", 0) < 700 or not 1.15 <= prop <= 2.1
                    or not visuais.WIKI_LICENCAS.search(licenca)
                    or not palavras <= set(re.findall(r"[a-z0-9]+", titulo.lower()))):
                continue
            vistos.add(p["pageid"])
            url = info.get("thumburl") or info["url"]
            saida.append({"pageid": p["pageid"], "url": url, "preview": re.sub(r"/1920px-", "/500px-", url),
                          "credito": {"arquivo": titulo, "licenca": licenca, "url": info.get("descriptionurl", ""),
                                      "autor": visuais._limpar_html(meta.get("Artist", {}).get("value")) or "desconhecido"}})
    return saida


r = json.loads((PASTA / "roteiro.json").read_text(encoding="utf-8"))
usados = {tuple(c["chave"]) for c in r["cenas"] if c.get("chave") and c["id"] not in CENAS}
usados |= {tuple(c["chave_extra"]) for c in r["cenas"] if c.get("chave_extra")}
for grupo in sorted(set(CENAS.values())):
    pool = acervo(ACERVOS[grupo])
    print(f"{grupo}: {len(pool)} fotos no acervo")
    if not pool:
        continue
    imagens = []
    for p in pool:  # miniaturas devagar, para não levar outro 429
        time.sleep(0.3)
        imagens.append(relevancia._baixar_imagem(p["preview"], visuais.WIKI_HEADERS))
    print(f"  {sum(i is not None for i in imagens)} miniaturas baixadas")
    for cena in [c for c in r["cenas"] if CENAS.get(c["id"]) == grupo]:
        livres = [i for i, p in enumerate(pool) if ("wiki", p["pageid"]) not in usados and imagens[i] is not None]
        if not livres:
            print(f"  cena {cena['id']}: acervo esgotado, fica como está")
            continue
        notas = relevancia.notas(relevancia.textos_da_cena(cena), [imagens[i] for i in livres])
        melhor = livres[max(range(len(livres)), key=lambda k: notas[k])]
        p = pool[melhor]
        destino = PASTA / "visuais" / f"cena_{cena['id']:03d}.jpg"
        for arq in (cena.get("visual_arquivo"),):
            if arq and not cena.get("visual_reaproveitado") and (PASTA / arq).exists():
                (PASTA / arq).unlink()
        conteudo = requests.get(p["url"], headers=visuais.WIKI_HEADERS, timeout=60).content
        destino.write_bytes(conteudo)
        for k in ("visual_reaproveitado", "visual_tipo", "nota", "chave", "credito"):
            cena.pop(k, None)
        cena.update({"visual_arquivo": str(destino.relative_to(PASTA)), "visual_tipo": "imagem",
                     "nota": round(max(notas), 3), "chave": ["wiki", p["pageid"]], "credito": p["credito"]})
        if cena["id"] in SEM_EXTRA:
            if cena.get("visual_extra") and (PASTA / cena["visual_extra"]).exists():
                (PASTA / cena["visual_extra"]).unlink()
            for k in ("visual_extra", "visual_extra_tipo", "nota_extra", "chave_extra", "credito_extra"):
                cena.pop(k, None)
        usados.add(("wiki", p["pageid"]))
        print(f"  cena {cena['id']}: {p['credito']['arquivo'][:70]} ({max(notas):.2f})")
(PASTA / "roteiro.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
