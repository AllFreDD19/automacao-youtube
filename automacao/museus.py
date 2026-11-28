"""Imagens de acervos de museus em domínio público (CC0), sem chave: Metropolitan Museum (Met) e Cleveland Museum of
Art. Úteis quando o Wikimedia está limitando (429): pinturas, esculturas, objetos antigos e gravuras.

Uso:  python -m automacao.museus <pasta_projeto> '{"12": "Diogenes", "40": "Inca khipu"}' saida.json
Para cada cena, baixa a 1a obra de domínio público com imagem e grava visuais/cena_XXX_m.jpg (1920x1080, a obra
inteira sobre um fundo desfocado dela mesma). saida.json = {cena: crédito}. Revisar a folha antes de usar.
"""
import io
import json
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automacao import config  # noqa: E402

H = {"User-Agent": config.USER_AGENT}
MET = "https://collectionapi.metmuseum.org/public/collection/v1.1"
CMA = "https://openaccess-api.clevelandart.org/api/artworks/"


def _met(q, maximo=8):
    r = requests.get(f"{MET}/search", params={"q": q, "hasImages": "true"}, headers=H, timeout=60)
    for oid in (r.json().get("objectIDs") or [])[:maximo]:
        o = requests.get(f"{MET}/objects/{oid}", headers=H, timeout=60).json()
        if o.get("isPublicDomain") and o.get("primaryImage"):
            return o["primaryImage"], {"arquivo": o.get("title", "")[:90], "autor": o.get("artistDisplayName") or "Unknown",
                                       "licenca": "CC0 (The Metropolitan Museum of Art)", "url": o.get("objectURL", "")}
        time.sleep(0.5)
    return None, None


def _cma(q):
    r = requests.get(CMA, params={"q": q, "has_image": 1, "cc0": 1, "limit": 5}, headers=H, timeout=60)
    for a in r.json().get("data", []):
        img = ((a.get("images") or {}).get("print") or (a.get("images") or {}).get("web") or {}).get("url")
        if img:
            autor = ", ".join(c.get("description", "").split("(")[0].strip() for c in a.get("creators", [])) or "Unknown"
            return img, {"arquivo": a.get("title", "")[:90], "autor": autor,
                         "licenca": "CC0 (Cleveland Museum of Art)", "url": a.get("url", "")}
    return None, None


def preparar(conteudo, destino):
    im = Image.open(io.BytesIO(conteudo)).convert("RGB")
    fundo = im.resize((1920, 1080)).filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.45))
    im.thumbnail((1920, 1080))
    if im.height < 1080 and im.width < 1920:  # obra pequena: amplia até caber
        f = min(1920 / im.width, 1080 / im.height)
        im = im.resize((int(im.width * f), int(im.height * f)), Image.LANCZOS)
    fundo.paste(im, ((1920 - im.width) // 2, (1080 - im.height) // 2))
    fundo.save(destino, quality=92)


def buscar(pasta, pedidos):
    res = {}
    for cena, q in pedidos.items():
        url, cred = None, None
        for fonte in (_cma, _met):
            try:
                url, cred = fonte(q)
            except (requests.RequestException, ValueError):
                url = None
            if url:
                break
        if not url:
            print(cena, "sem resultado:", q, flush=True)
            continue
        try:
            dados = requests.get(url, headers=H, timeout=120).content
            preparar(dados, Path(pasta) / "visuais" / f"cena_{int(cena):03d}_m.jpg")
            res[cena] = cred
            print(cena, cred["arquivo"], "|", cred["licenca"], flush=True)
        except Exception as e:  # noqa: BLE001
            print(cena, "erro:", e, flush=True)
    return res


if __name__ == "__main__":
    pasta, pedidos, saida = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3]
    json.dump(buscar(pasta, pedidos), open(saida, "w"), ensure_ascii=False)
    print("FIM")
