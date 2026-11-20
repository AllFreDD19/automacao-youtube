"""Etapa 6a: visuais de cada cena — vídeos de banco (Pexels) e imagens geradas por IA."""
import base64
import re
import subprocess
from collections import Counter
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests

from . import config, relevancia


def _recortar(url, destino, inicio, duracao=20):
    """Baixa só um trecho do vídeo, a partir de `inicio` segundos (o ffmpeg lê direto do endereço)."""
    r = subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", "-ss", str(inicio), "-i", url, "-t", str(duracao),
                        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(destino)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not destino.exists() or destino.stat().st_size < 50_000:
        raise RuntimeError(f"recorte falhou: {r.stderr[-300:]}")
    return destino


def _baixar(url, destino, timeout=180, headers=None):
    for tentativa in range(4):
        r = requests.get(url, stream=True, timeout=timeout, headers=headers)
        if r.status_code != 429 or tentativa == 3:
            break
        # Limite de pedidos (Wikimedia): espera o que o servidor pede, sem insistir antes
        espera = min(int(r.headers.get("retry-after") or 0) or 20 * (tentativa + 1), 120)
        r.close()
        time.sleep(espera)
    with r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for parte in r.iter_content(1 << 16):
                f.write(parte)
    return destino


# ---------- candidatos ----------
# Cada fonte devolve candidatos {"tipo", "chave", "preview", "url", "headers", "credito"}; o CLIP compara a miniatura
# ("preview") de todos com a cena e só o vencedor é baixado em alta resolução ("url").
POR_FONTE = 6  # candidatos por fonte e por busca


def _cands_pexels_videos(busca, duracao_min):
    if not config.PEXELS_API_KEY:
        return []
    try:
        r = requests.get("https://api.pexels.com/videos/search", timeout=30,
                         params={"query": busca, "orientation": "landscape", "per_page": 15, "size": "medium"},
                         headers={"Authorization": config.PEXELS_API_KEY})
        videos = r.json().get("videos", []) if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return []
    cands = []
    for video in videos:
        arquivos = [a for a in video.get("video_files", [])
                    if a.get("width") and a["width"] >= 1280 and a.get("file_type") == "video/mp4"]
        if video.get("duration", 0) < duracao_min or not arquivos:
            continue
        # O mais próximo de 1920px de largura (evita baixar 4K à toa)
        melhor = min(arquivos, key=lambda a: abs(a["width"] - 1920))
        cands.append({"tipo": "video", "chave": ("px_v", video["id"]), "preview": video.get("image"),
                      "url": melhor["link"]})
    return cands[:POR_FONTE]


def _cands_pixabay_videos(busca, duracao_min):
    if not config.PIXABAY_API_KEY:
        return []
    cands = []
    for video in _relevantes(_pixabay("videos/", busca, video_type="film"), busca):
        opcoes = [v for v in video["videos"].values() if v.get("url") and v.get("width", 0) >= 1280]
        if video.get("duration", 0) < duracao_min or not opcoes or video.get("isLowQuality"):
            continue
        melhor = min(opcoes, key=lambda v: abs(v["width"] - 1920))
        cands.append({"tipo": "video", "chave": ("pb_v", video["id"]), "preview": melhor.get("thumbnail"),
                      "url": melhor["url"]})
    return cands[:POR_FONTE]


def _cands_pixabay_imagens(busca):
    if not config.PIXABAY_API_KEY:
        return []
    # Só fotos: ilustrações e vetores vinham como desenho animado ou com fundo transparente (vira tela preta)
    hits = _pixabay("", busca, image_type="photo", orientation="horizontal", min_width=1280)
    # fullHDURL só vem para contas com acesso completo; senão usa a de 1280px
    return [{"tipo": "imagem", "chave": ("pb_i", h["id"]), "preview": h.get("webformatURL"),
             "url": h.get("fullHDURL") or h["largeImageURL"]}
            for h in _relevantes(hits, busca)[:POR_FONTE]]


_ultima_chamada_pixabay = 0.0
_trava_taxa = threading.Lock()
_trava_usados = threading.Lock()


def _reservar(usados, chave):
    """Marca uma mídia como usada; False se outra cena (talvez em outra thread) já pegou."""
    with _trava_usados:
        if chave in usados:
            return False
        usados.add(chave)
        return True


def _pixabay(endpoint, busca, **params):
    # O Pixabay permite 100 requisições por minuto: mantém um intervalo mínimo entre chamadas (vale entre threads)
    global _ultima_chamada_pixabay
    with _trava_taxa:
        espera = 0.7 - (time.time() - _ultima_chamada_pixabay)
        if espera > 0:
            time.sleep(espera)
        _ultima_chamada_pixabay = time.time()
    r = requests.get(
        f"https://pixabay.com/api/{endpoint}",
        params={"key": config.PIXABAY_API_KEY, "q": busca[:100], "safesearch": "true", "per_page": 30, **params},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"    Pixabay: {r.status_code} {r.text[:120]}")
        return []
    return r.json().get("hits", [])


# Material que nunca serve como cena pronta: fundo verde para recorte, animações de botão, etc.
BLOQUEADAS = ("green screen", "greenscreen", "chroma", "alpha channel", "subscribe", "like button", "overlay")


def _relevantes(hits, busca):
    """Ordena pelo nº de palavras da busca presentes nas tags e descarta os que não batem com nada.

    A busca do Pixabay é ampla; sem esse filtro, "ancient advanced city" pode trazer um palácio qualquer.
    """
    palavras = {p for p in busca.lower().split() if len(p) > 2}
    # Palavras genéricas não contam como acerto: "luxury" sozinho trouxe um vídeo de café para uma cena de SUV
    genericas = {"luxury", "old", "new", "dark", "night", "modern", "vintage", "background", "view", "close"}
    pontuados = []
    for i, h in enumerate(hits):
        texto_tags = h.get("tags", "").lower()
        if any(b in texto_tags for b in BLOQUEADAS):
            continue
        tags = set(re.findall(r"[a-z0-9]+", texto_tags))
        acertos = sum(1 for p in palavras - genericas if p in tags or p.rstrip("s") in tags)
        if acertos:
            pontuados.append((-acertos, i, h))  # mais acertos primeiro; empate mantém ordem do Pixabay
    # Busca de 2+ palavras exige 2 acertos: com 1 só, "diesel particulate filter" aceitava uma xícara de café ("filter")
    minimo = min(2, len(palavras - genericas))
    return [h for a, _, h in sorted(pontuados, key=lambda x: x[:2]) if -a >= minimo]


def imagem_pixabay(busca, destino, usados):
    """Primeira foto livre do Pixabay para a busca (usada pela thumbnail, que não tem cena para comparar)."""
    for c in _cands_pixabay_imagens(busca):
        if _reservar(usados, c["chave"]):
            return _baixar(c["url"], destino)
    return None


# Wikimedia Commons: fotos do modelo exato (ex.: "Saab 900"), grátis e sem chave, com licença livre que exige crédito.
# A API pede um User-Agent que identifique a ferramenta.
WIKI_API = "https://commons.wikimedia.org/w/api.php"
# Desde 16/10/2026 o Wikimedia dá 403/429 para identificações sem endereço de contato do dono da ferramenta
# (o link antigo, para a página da API, não contava): ver config.USER_AGENT
WIKI_HEADERS = {"User-Agent": config.USER_AGENT}
# Só licenças que permitem uso comercial e edição; NC/ND ficam de fora
WIKI_LICENCAS = re.compile(r"^(cc0|public domain|pd\b|cc[ -]by(-sa)?( \d\.\d)?)", re.I)
_trava_wiki = threading.Lock()
_ultima_chamada_wiki = 0.0


def _limpar_html(texto):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", texto or "")).strip()


def _cands_wikimedia(busca):
    """Fotos livres do Commons para a busca (modelo, animal, lugar ou máquina exatos), com o crédito pronto."""
    global _ultima_chamada_wiki
    with _trava_wiki:  # educado com a API: uma chamada a cada meio segundo
        espera = 0.5 - (time.time() - _ultima_chamada_wiki)
        if espera > 0:
            time.sleep(espera)
        _ultima_chamada_wiki = time.time()
    try:
        for tentativa in range(3):
            r = requests.get(WIKI_API, headers=WIKI_HEADERS, timeout=30, params={
                "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 20,
                "gsrsearch": f"{busca} filetype:bitmap", "prop": "imageinfo",
                "iiprop": "url|size|extmetadata", "iiurlwidth": 1920,
            })
            if r.status_code != 429:
                break
            time.sleep(min(int(r.headers.get("retry-after") or 0) or 15, 60))
        r.raise_for_status()
        paginas = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    except (requests.RequestException, ValueError):
        return []
    palavras = {p for p in re.findall(r"[a-z0-9]+", busca.lower()) if len(p) > 1}
    cands = []
    for p in paginas:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        licenca = _limpar_html(meta.get("LicenseShortName", {}).get("value"))
        titulo = p.get("title", "").removeprefix("File:")
        # Foto grande, perto de 16:9 (panorâmica demais perde as pontas do assunto no corte),
        # licença livre e com as palavras da busca no nome do arquivo
        proporcao = info.get("width", 0) / max(info.get("height", 1), 1)
        # 780 px: fotos de arquivo (Bundesarchiv = 800 px) eram todas descartadas com o mínimo antigo de 1280 e, em
        # temas históricos, sobravam biplanos e aviões modernos (stuka-sirene, 2026-10-12). Relevância > nitidez.
        if (info.get("width", 0) < 780 or not 1.2 <= proporcao <= 2.1
                or not WIKI_LICENCAS.search(licenca)
                or not palavras <= set(re.findall(r"[a-z0-9]+", titulo.lower()))):
            continue
        url = info.get("thumburl") or info["url"]
        cands.append({
            "tipo": "imagem", "chave": ("wiki", p.get("pageid")), "url": url, "headers": WIKI_HEADERS,
            # A miniatura do Commons troca só a largura no endereço; só tamanhos padrão existem (400px dá erro 400)
            "preview": re.sub(r"/1920px-", "/500px-", url),
            "credito": {"arquivo": titulo, "autor": _limpar_html(meta.get("Artist", {}).get("value")) or "desconhecido",
                        "licenca": licenca, "url": info.get("descriptionurl", "")},
        })
    return cands[:POR_FONTE]


# NASA (images.nasa.gov): fotos e vídeos em Full HD, em geral de domínio público, sem chave nem limite conhecido.
# Útil para espaço, ciência, engenharia, aviação e natureza vista do alto; o CLIP descarta o resto.
# O endereço do arquivo grande sai de uma segunda chamada, feita só para o vencedor (campo "resolver").
NASA_API = "https://images-api.nasa.gov"


def _nasa_arquivo(nasa_id, tipo, duracao_min):
    """Endereço do arquivo grande de um item da NASA; para vídeo, confere duração e resolução antes.

    Vídeo devolve (url, inicio): os vídeos da NASA abrem com uma tela de identificação (logo e contatos) ou com tela
    preta, então o trecho usado começa depois disso.
    """
    try:
        hrefs = [a["href"].replace("http://", "https://")
                 for a in requests.get(f"{NASA_API}/asset/{nasa_id}", timeout=30).json()["collection"]["items"]]
        if tipo == "video":
            meta = next((h for h in hrefs if h.endswith("metadata.json")), None)
            info = requests.get(meta, timeout=30).json() if meta else {}
            h, m, s = (int(x) for x in str(info.get("QuickTime:Duration", "0:00:00")).split(":")[-3:])
            total = h * 3600 + m * 60 + s
            inicio = max(8, round(total * 0.2))
            if total - inicio < duracao_min or int(info.get("QuickTime:ImageWidth") or 0) < 1280:
                return None
            # "large" é Full HD; o "orig" pode ter gigabytes
            url = next((x for suf in ("~large.mp4", "~medium.mp4") for x in hrefs if x.endswith(suf)), None)
            return (url, inicio) if url else None
        return next((x for suf in ("~large.jpg", "~medium.jpg") for x in hrefs if x.endswith(suf)), None)
    except (requests.RequestException, ValueError, KeyError, StopIteration):
        return None


def _cands_nasa(busca, tipos, duracao_min):
    try:
        itens = requests.get(f"{NASA_API}/search", timeout=30, params={
            "q": busca, "media_type": ",".join("video" if t == "video" else "image" for t in tipos), "page_size": 20,
        }).json()["collection"]["items"]
    except (requests.RequestException, ValueError, KeyError):
        return []
    cands = []
    for it in itens:
        d, preview = it["data"][0], (it.get("links") or [{}])[0].get("href")
        tipo = "video" if d.get("media_type") == "video" else "imagem"
        if not preview or tipo not in tipos:
            continue
        nid = d["nasa_id"]
        cands.append({
            "tipo": tipo, "chave": ("nasa", nid), "preview": preview.replace("http://", "https://"),
            "resolver": lambda nid=nid, tipo=tipo: _nasa_arquivo(nid, tipo, duracao_min),
            "credito": {"arquivo": d.get("title", nid), "autor": "NASA", "licenca": "Public domain (NASA)",
                        "url": f"https://images.nasa.gov/details/{nid}"},
        })
    return cands[:4]


# Openverse: reúne imagens de licença livre de vários acervos (Flickr, museus, Wikimedia). Sem chave o limite é de
# 20 buscas por minuto e 200 por dia, então só entra como reforço, quando as outras fontes não acharam nada bom.
OPENVERSE_API = "https://api.openverse.org/v1/images/"
_trava_openverse = threading.Lock()
_ultima_openverse = 0.0
_openverse_esgotado = False


def _cands_openverse(busca):
    global _ultima_openverse, _openverse_esgotado
    if _openverse_esgotado:
        return []
    with _trava_openverse:  # 20 por minuto = uma a cada 3 segundos
        espera = 3.1 - (time.time() - _ultima_openverse)
        if espera > 0:
            time.sleep(espera)
        _ultima_openverse = time.time()
    try:
        r = requests.get(OPENVERSE_API, headers=WIKI_HEADERS, timeout=30, params={
            "q": busca, "license_type": "commercial,modification", "page_size": 20, "aspect_ratio": "wide",
            "size": "large", "mature": "false",
        })
        if r.status_code == 429:
            print("    Openverse: limite diário atingido, seguindo sem ele")
            _openverse_esgotado = True
            return []
        resultados = r.json().get("results", []) if r.ok else []
    except (requests.RequestException, ValueError):
        return []
    cands = []
    for it in resultados:
        largura, altura = it.get("width") or 0, it.get("height") or 1
        if largura < 1280 or not 1.3 <= largura / altura <= 2.0 or not it.get("url"):
            continue
        licenca = f"CC {it.get('license', '').upper()} {it.get('license_version') or ''}".strip()
        if it.get("license") in ("cc0", "pdm"):
            licenca = "Public domain" if it["license"] == "pdm" else "CC0"
        cands.append({
            "tipo": "imagem", "chave": ("ov", it["id"]), "preview": it.get("thumbnail") or it["url"],
            "url": it["url"], "headers": WIKI_HEADERS,
            "credito": {"arquivo": it.get("title") or it["id"], "autor": it.get("creator") or "desconhecido",
                        "licenca": licenca, "url": it.get("foreign_landing_url") or it["url"]},
        })
    return cands[:POR_FONTE]


# Unsplash: fotos profissionais de qualquer tema. A licença permite uso comercial; as regras da API pedem o crédito
# "Photo by <nome> on Unsplash" e um aviso de download (download_location) para cada foto usada.
# A chave "Demo" permite 50 buscas por hora, então ele entra como reforço, igual ao Openverse.
_unsplash_esgotado = False


def _cands_unsplash(busca):
    global _unsplash_esgotado
    if not config.UNSPLASH_ACCESS_KEY or _unsplash_esgotado:
        return []
    try:
        r = requests.get("https://api.unsplash.com/search/photos", timeout=30,
                         headers={"Authorization": f"Client-ID {config.UNSPLASH_ACCESS_KEY}", "Accept-Version": "v1"},
                         params={"query": busca, "orientation": "landscape", "per_page": 20, "content_filter": "high"})
        if r.status_code in (401, 403, 429) or r.headers.get("X-Ratelimit-Remaining") == "0":
            print(f"    Unsplash: {'limite da hora atingido' if r.status_code != 401 else 'chave inválida'}, seguindo sem ele")
            _unsplash_esgotado = True
        fotos = r.json().get("results", []) if r.ok else []
    except (requests.RequestException, ValueError):
        return []
    cands = []
    for f in fotos:
        largura, altura = f.get("width") or 0, f.get("height") or 1
        if largura < 1280 or not 1.3 <= largura / altura <= 2.0:
            continue
        nome = (f.get("user") or {}).get("name") or "desconhecido"
        perfil = ((f.get("user") or {}).get("links") or {}).get("html", "https://unsplash.com")
        cands.append({
            "tipo": "imagem", "chave": ("us", f["id"]), "preview": f["urls"]["small"],
            # Largura 1920 já recortada pelo próprio Unsplash; o aviso de download vai junto ao baixar
            "resolver": lambda f=f: _avisar_unsplash(f) or f["urls"]["raw"] + "&w=1920&q=85&fm=jpg",
            "credito": {"arquivo": f.get("alt_description") or f["id"], "autor": f"{nome} on Unsplash",
                        "licenca": "Unsplash License",
                        "url": f"{perfil}?utm_source=automacao_youtube&utm_medium=referral"},
        })
    return cands[:POR_FONTE]


def _avisar_unsplash(foto):
    """Regra da API do Unsplash: avisar cada download usado (não conta no limite de buscas)."""
    try:
        requests.get(foto["links"]["download_location"], timeout=30,
                     headers={"Authorization": f"Client-ID {config.UNSPLASH_ACCESS_KEY}"})
    except (requests.RequestException, KeyError):
        pass


def imagem_pollinations(prompt, destino, semente):
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
           + f"?width=1920&height=1080&nologo=true&model=flux&seed={semente}")
    return _baixar(url, destino, timeout=240)


def flux_nvidia(corpo, modelo="flux.1-dev"):
    """Pede uma imagem ao FLUX da NVIDIA e devolve os bytes.

    Em 2026-11-18 a NVIDIA passou a recusar o campo "seed" (422 extra_forbidden). Se ela recusar algum campo, ele é
    tirado e o pedido é refeito, para a ferramenta não parar a cada mudança da API.
    """
    corpo = dict(corpo)
    for _ in range(len(corpo)):
        r = requests.post(
            f"https://ai.api.nvidia.com/v1/genai/black-forest-labs/{modelo}",
            headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}", "Accept": "application/json"},
            json=corpo, timeout=120)
        if r.status_code == 422:
            try:
                extras = [d["loc"][-1] for d in r.json().get("detail", []) if d.get("type") == "extra_forbidden"]
            except ValueError:
                extras = []
            extras = [c for c in extras if c in corpo and c != "prompt"]
            if extras:
                for c in extras:
                    corpo.pop(c)
                continue
        if not r.ok:
            raise RuntimeError(f"NVIDIA {modelo}: erro {r.status_code} {r.text[:300]}")
        return base64.b64decode(r.json()["artifacts"][0]["base64"])
    raise RuntimeError(f"NVIDIA {modelo}: pedido recusado")


def imagem_nvidia(prompt, destino, semente):
    destino.write_bytes(flux_nvidia({"prompt": prompt, "mode": "base", "cfg_scale": 3.5, "width": 1344, "height": 768,
                                     "steps": 30}))
    return destino


_provedores_falhos = set()


def imagem_ia(prompt, destino, semente):
    estilo = ", cinematic lighting, highly detailed, 16:9, no text, no watermark"
    provedores = []
    # FLUX da NVIDIA só quando escolhido: em 2026-10 o endpoint não respondia e cada tentativa custava 90 s
    if config.NVIDIA_API_KEY and config.IMAGEM_PROVEDOR == "nvidia":
        provedores.append(imagem_nvidia)
    if config.IMAGEM_PROVEDOR == "pollinations":
        # Só sob pedido: o plano grátis põe marca d'água e gera em baixa resolução
        provedores.append(imagem_pollinations)
    for provedor in provedores:
        if provedor in _provedores_falhos:
            continue
        for tentativa in range(3):
            try:
                return provedor(prompt + estilo, destino, semente)
            except requests.Timeout:
                # Serviço fora do ar ou sobrecarregado: não insiste nele no resto desta execução
                print(f"    {provedor.__name__} não respondeu, pulando ele nas próximas cenas")
                _provedores_falhos.add(provedor)
                break
            except Exception as e:
                codigo = getattr(getattr(e, "response", None), "status_code", None)
                print(f"    {provedor.__name__} falhou ({codigo or e.__class__.__name__}), tentando de novo...")
                # 402/429 = limite de uso atingido: espera mais antes de tentar de novo
                time.sleep((20 if codigo in (402, 429) else 5) * (tentativa + 1))
        destino.unlink(missing_ok=True)
    return None


def _duracao_minima(cena):
    """O vídeo repete em loop se for mais curto que a fala: pede um clipe de duração parecida (até 12 s)."""
    return max(5, min(cena.get("duracao", 8), 12))


# Notas do CLIP (semelhança média com a busca e a narração): ~0,30 = combina muito, abaixo de ~0,18 = sem relação
NOTA_BOA = 0.27     # achou algo assim: para de procurar em outras buscas
NOTA_MINIMA = 0.18  # abaixo disso o candidato é descartado (melhor reaproveitar a cena anterior ou usar IA)
MARGEM_VIDEO = 0.03  # vídeo ganha da imagem se a nota for no máximo isso abaixo (movimento vale um pouco)
# Rumo aos 50% de vídeo (meta, não obrigação: o usuário prefere menos vídeo a vídeo sem relação), uma imagem já
# escolhida vira vídeo se ele estiver até 0,04 abaixo dela e tiver nota de pelo menos 0,25
MARGEM_EQUILIBRIO, NOTA_VIDEO_EQUILIBRIO = 0.04, 0.25
# A tela muda a cada ~8 s: cada frase é uma cena, e fala mais longa que isso ganha um segundo visual na metade
SEGUNDO_VISUAL_ACIMA_DE = 9.0
QUASE_IGUAL = 0.93  # semelhança entre imagens acima disso = mesma foto ou da mesma sessão do fotógrafo


def _pontuar(cena, cands):
    """Dá nota a cada candidato; sem o CLIP instalado, mantém a ordem das fontes (como antes)."""
    if not cands:
        return []
    if not relevancia.disponivel():
        return [(0.5 - i * 0.001, c) for i, c in enumerate(cands)]
    notas = relevancia.notas(relevancia.textos_da_cena(cena), [c["preview"] for c in cands],
                             headers=WIKI_HEADERS)
    return sorted(zip(notas, cands), key=lambda x: -x[0])


def _candidatos(cena, buscas, quer):
    """Junta candidatos de todas as fontes para as buscas; quer = {"video", "imagem"}. Para cedo se achar nota boa."""
    pontuados = []
    if "imagem" in quer and cena.get("busca_wiki"):
        pontuados += _pontuar(cena, _cands_wikimedia(cena["busca_wiki"]))
    for b in buscas:
        if pontuados and pontuados[0][0] >= NOTA_BOA:
            break
        novos = _cands_nasa(b, quer, _duracao_minima(cena))
        if "video" in quer:
            novos += _cands_pexels_videos(b, _duracao_minima(cena)) + _cands_pixabay_videos(b, _duracao_minima(cena))
        if "imagem" in quer:
            novos += _cands_pixabay_imagens(b)
        pontuados = sorted(pontuados + _pontuar(cena, novos), key=lambda x: -x[0])
    # Reforços com cota pequena (Unsplash: 50/hora; Openverse: 200/dia): só quando nada chegou a uma nota boa,
    # e com a busca principal da cena
    for reforco in (_cands_unsplash, _cands_openverse):
        if "imagem" in quer and buscas and not (pontuados and pontuados[0][0] >= NOTA_BOA):
            pontuados = sorted(pontuados + _pontuar(cena, reforco(buscas[0])), key=lambda x: -x[0])
    return [(n, c) for n, c in pontuados if n >= NOTA_MINIMA]


def _baixar_melhor(pontuados, destino_base, usados, diferente_de=None):
    """Baixa o candidato de maior nota ainda livre; devolve (arquivo, tipo, nota, credito, chave) ou None.

    diferente_de: miniatura/arquivo que o vencedor não pode repetir (segundo visual de uma fala longa).
    """
    for nota, c in pontuados:
        if diferente_de and relevancia.disponivel() and \
                relevancia.semelhanca_visual(diferente_de, c["preview"], WIKI_HEADERS) > QUASE_IGUAL:
            continue
        if not _reservar(usados, c["chave"]):
            continue
        destino = destino_base.with_suffix(".mp4" if c["tipo"] == "video" else ".jpg")
        # Algumas fontes (NASA) só dizem o endereço do arquivo grande, e se ele serve, numa segunda chamada;
        # vídeo pode vir como (url, segundo de início) para pular a abertura
        url = c["resolver"]() if c.get("resolver") else c["url"]
        url, inicio = url if isinstance(url, tuple) else (url, 0)
        if not url:
            continue
        try:
            if inicio:
                _recortar(url, destino, inicio)
            else:
                _baixar(url, destino, headers=c.get("headers"))
            return destino, c["tipo"], round(nota, 3), c.get("credito"), list(c["chave"])
        except (requests.RequestException, RuntimeError):
            destino.unlink(missing_ok=True)
            continue
    return None


def _equilibrar_videos(roteiro, pasta, usados, em_paralelo):
    """Troca imagens por vídeos até chegar em PROPORCAO_VIDEO, intercalando para não juntar blocos iguais.

    Fotos do Wikimedia (modelo exato) ficam: acertar o carro vale mais que o movimento.
    """
    cenas = roteiro["cenas"]
    meta = round(config.PROPORCAO_VIDEO * len(cenas))
    videos = sum(1 for c in cenas if c.get("visual_tipo") == "video")
    if videos >= meta:
        return
    # Animações (estilo motion design) foram escolhidas de propósito: não viram vídeo de banco
    trocaveis = [c for c in cenas if c.get("visual_tipo") not in ("video", "animacao") and not c.get("credito")]
    # Primeiro as cenas cuja anterior também é imagem: assim os vídeos ficam espalhados pelo vídeo todo
    por_id = {c["id"]: c for c in cenas}
    def anterior_imagem(c):
        ant = por_id.get(c["id"] - 1)
        return ant is None or ant.get("visual_tipo") != "video"
    trocaveis = [c for c in trocaveis if anterior_imagem(c)][::2] + [c for c in trocaveis if anterior_imagem(c)][1::2] \
        + [c for c in trocaveis if not anterior_imagem(c)]
    print(f"  equilibrando: {videos} de {len(cenas)} cenas em vídeo, meta {meta}")
    # O canal tem temas variados (de animais a engenharia): as buscas de reserva saem do próprio roteiro,
    # com os termos seguros mais usados nas cenas deste vídeo, nunca de uma lista fixa
    tema = [b for b, _ in Counter(c.get("busca_segura", "") for c in cenas if c.get("busca_segura")).most_common(6)]

    def tentar(cena):
        segura = cena.get("busca_segura", "")
        busca = cena.get("busca_stock", "")
        buscas = list(dict.fromkeys(b for b in [busca, " ".join(busca.split()[-2:]), segura, *tema] if b))
        # Só troca se o vídeo combinar quase tão bem quanto a imagem atual: relevância antes de movimento
        piso = max(NOTA_VIDEO_EQUILIBRIO, cena.get("nota", 0) - MARGEM_EQUILIBRIO)
        pontuados = [(n, c) for n, c in _candidatos(cena, buscas, {"video"}) if n >= piso]
        return cena, _baixar_melhor(pontuados, pasta / f"cena_{cena['id']:03d}", usados)

    faltam = meta - videos
    for i in range(0, len(trocaveis), em_paralelo):
        if faltam <= 0:
            break
        with ThreadPoolExecutor(em_paralelo) as pool:
            for cena, achado in pool.map(tentar, trocaveis[i:i + min(em_paralelo, faltam)]):
                if not achado:
                    continue
                arquivo, _, nota, _, chave = achado
                if cena.get("visual_arquivo") and not cena.get("visual_reaproveitado"):
                    (pasta.parent / cena["visual_arquivo"]).unlink(missing_ok=True)
                cena["visual_arquivo"] = str(arquivo.relative_to(pasta.parent))
                cena["visual_tipo"] = "video"
                cena["visual"] = "stock"
                cena["nota"] = nota
                cena["chave"] = chave
                cena.pop("credito", None)
                cena.pop("visual_reaproveitado", None)
                faltam -= 1
    total = sum(1 for c in cenas if c.get("visual_tipo") == "video")
    print(f"  vídeo em {total} de {len(cenas)} cenas ({total / len(cenas):.0%})")


def _segundos_visuais(roteiro, pasta, usados, em_paralelo):
    """Falas longas (mais de SEGUNDO_VISUAL_ACIMA_DE segundos) ganham um segundo visual, mostrado na metade."""
    longas = [c for c in roteiro["cenas"] if c.get("duracao", 0) > SEGUNDO_VISUAL_ACIMA_DE
              and c.get("visual_tipo") != "animacao"  # a animação já se move a fala inteira
              and not (c.get("visual_extra") and (pasta.parent / c["visual_extra"]).exists())]
    if not longas:
        return
    print(f"  {len(longas)} fala(s) longa(s): buscando um segundo visual para cada")

    def tentar(cena):
        busca, segura = cena.get("busca_stock", ""), cena.get("busca_segura", "")
        buscas = list(dict.fromkeys(b for b in [busca, " ".join(busca.split()[-2:]), segura] if b))
        # Não pode ser a mesma foto nem uma quase igual à primeira (fotos em série do mesmo fotógrafo)
        primeiro = pasta.parent / cena["visual_arquivo"] if cena.get("visual_arquivo") else None
        diferente_de = primeiro if primeiro and primeiro.exists() and cena.get("visual_tipo") != "video" else None
        return cena, _baixar_melhor(_candidatos(cena, buscas, {"video", "imagem"}),
                                    pasta / f"cena_{cena['id']:03d}_b", usados, diferente_de)

    with ThreadPoolExecutor(em_paralelo) as pool:
        for cena, achado in pool.map(tentar, longas):
            if achado:
                arquivo, tipo, nota, credito, chave = achado
                cena["visual_extra"] = str(arquivo.relative_to(pasta.parent))
                cena["visual_extra_tipo"] = tipo
                cena["nota_extra"] = nota
                cena["chave_extra"] = chave
                cena.pop("credito_extra", None)
                if credito:
                    cena["credito_extra"] = credito


def _buscar_visual(cena, pasta, usados):
    """Acha o visual de uma cena comparando candidatos de todas as fontes; devolve (arquivo, tipo) ou (None, None)."""
    base = pasta / f"cena_{cena['id']:03d}"
    busca = cena.get("busca_stock") or " ".join((cena.get("prompt_imagem") or "").split()[:4])

    # Busca específica, depois as duas últimas palavras (costumam ser o núcleo) e por fim a busca segura
    # (concreta, escolhida pelo roteiro). Cortar para uma palavra solta trazia imagens sem relação.
    segura = cena.get("busca_segura", "")
    buscas = list(dict.fromkeys(b for b in [busca, " ".join(busca.split()[-2:]), segura] if b))

    cena.pop("credito", None)
    cena.pop("nota", None)
    if cena["visual"] == "animacao":
        # Ilustração plana para animar na edição (automacao/animacao.py); sem crédito: gerada por IA
        from . import animacao
        jpg = base.with_suffix(".jpg")
        arquivo = animacao.gerar_imagem(cena.get("prompt_animacao") or cena.get("prompt_imagem") or busca,
                                        jpg, semente=cena["id"])
        return (arquivo, "animacao") if arquivo else (None, None)
    if config.IMAGEM_PROVEDOR == "pixabay" or cena["visual"] == "stock":
        # Wikimedia (foto exata), Pixabay e Pexels concorrem juntos; cena "stock" prefere vídeo se ele combinar
        # quase tão bem quanto a melhor imagem
        pontuados = _candidatos(cena, buscas, {"video", "imagem"} if cena["visual"] == "stock" else {"imagem"})
        if cena["visual"] == "stock" and pontuados:
            melhor = pontuados[0][0]
            pontuados = sorted(pontuados, key=lambda x: -(x[0] + (MARGEM_VIDEO if x[1]["tipo"] == "video" else 0)))
            pontuados = [(n, c) for n, c in pontuados if n >= melhor - MARGEM_VIDEO] or pontuados
        achado = _baixar_melhor(pontuados, base, usados)
        if achado:
            arquivo, tipo, nota, credito, chave = achado
            cena["nota"] = nota
            cena["chave"] = chave
            if credito:
                cena["credito"] = credito
            return arquivo, tipo
    # Nada combinou (ou provedor de IA escolhido): gera imagem com IA
    jpg = base.with_suffix(".jpg")
    prompt = cena.get("prompt_imagem") or busca or cena["narracao"][:200]
    arquivo = imagem_ia(prompt, jpg, semente=cena["id"])
    return (arquivo, "imagem") if arquivo else (None, None)


def gerar_visuais(roteiro, pasta_projeto, em_paralelo=3):  # Wikimedia pede no máximo 3 pedidos simultâneos
    pasta = pasta_projeto / "visuais"
    pasta.mkdir(exist_ok=True)

    def pronta(c):
        return c.get("visual_arquivo") and (pasta_projeto / c["visual_arquivo"]).exists() and not c.get("visual_reaproveitado")

    # O que as cenas já prontas usam fica bloqueado: sem isso, rodar "visuais" de novo (ex.: depois de trocar
    # buscas) escolhia o mesmo arquivo para outra cena
    usados = {tuple(c[campo]) for c in roteiro["cenas"] if pronta(c)
              for campo in ("chave", "chave_extra") if c.get(campo)}

    # Busca em paralelo (downloads simultâneos); o limite de requisições do Pixabay continua valendo
    pendentes = [c for c in roteiro["cenas"] if not pronta(c)]
    print(f"  {len(pendentes)} cena(s) para buscar, {em_paralelo} por vez")
    with ThreadPoolExecutor(em_paralelo) as pool:
        achados = dict(zip((c["id"] for c in pendentes), pool.map(lambda c: _buscar_visual(c, pasta, usados), pendentes)))

    # Aplica em ordem, porque a falha de uma cena reaproveita o visual da anterior
    anterior = None
    for cena in roteiro["cenas"]:
        if cena["id"] not in achados:
            anterior = cena
            continue
        arquivo, tipo = achados[cena["id"]]
        if arquivo:
            cena["visual_arquivo"] = str(arquivo.relative_to(pasta_projeto))
            cena["visual_tipo"] = tipo
            cena.pop("visual_reaproveitado", None)
            anterior = cena
            print(f"  cena {cena['id']:03d}: {tipo}")
        elif anterior:
            # Sem visual: repete o da cena anterior (rode "visuais" de novo depois para tentar substituir)
            cena["visual_arquivo"] = anterior["visual_arquivo"]
            cena["visual_tipo"] = anterior["visual_tipo"]
            cena["visual_reaproveitado"] = True
            if anterior.get("credito"):
                cena["credito"] = anterior["credito"]
            print(f"  cena {cena['id']:03d}: falhou, reaproveitando visual da cena {anterior['id']:03d}")
        else:
            print(f"  cena {cena['id']:03d}: SEM VISUAL (usará fundo escuro)")
    _equilibrar_videos(roteiro, pasta, usados, em_paralelo)
    _segundos_visuais(roteiro, pasta, usados, em_paralelo)
    return roteiro
