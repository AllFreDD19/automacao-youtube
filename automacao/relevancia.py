"""Nota de relevância imagem x texto com o CLIP (grátis e local).

Usado para escolher, entre os candidatos de todas as fontes (Wikimedia, Pixabay, Pexels), a imagem ou o vídeo que
mais combina com a cena. Roda na placa de vídeo (RTX 3050, PyTorch cu130 desde 2026-10-12, pedido do usuário) e volta
sozinho para o processador se não houver CUDA. Antes rodava na CPU para deixar a placa ao apresentador, que saiu.
"""
import io
import logging
import os
import threading

import requests
from PIL import Image

# O Windows sem modo desenvolvedor não cria links simbólicos no cache do modelo: só um aviso, funciona igual
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")  # o aviso de "requisição sem token" também é só ruído
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

MODELO, PESOS = "ViT-B-32", "laion2b_s34b_b79k"  # ~600 MB, baixado uma vez na primeira execução

_trava = threading.Lock()
_carregado = None  # (modelo, preprocessamento, tokenizador)
_textos = {}  # cache das codificações de texto
_dispositivo = "cpu"


def _carregar():
    global _carregado, _dispositivo
    if _carregado is None:
        import open_clip
        import torch
        _dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
        modelo, _, prep = open_clip.create_model_and_transforms(MODELO, pretrained=PESOS, device=_dispositivo)
        modelo.eval()
        _carregado = (modelo, prep, open_clip.get_tokenizer(MODELO))
    return _carregado


def disponivel():
    try:
        import open_clip  # noqa: F401
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


def _baixar_imagem(url, headers=None):
    try:
        r = requests.get(url, timeout=30, headers=headers)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def notas(textos, urls, headers=None):
    """Nota de 0 a ~0,4 para cada imagem (url ou PIL.Image): média da semelhança com cada texto.

    Imagem que não baixou recebe -1, para nunca ganhar.
    """
    import torch
    imagens = [u if isinstance(u, Image.Image) else _baixar_imagem(u, headers) for u in urls]
    validas = [i for i, img in enumerate(imagens) if img is not None]
    resultado = [-1.0] * len(urls)
    if not validas or not textos:
        return resultado
    with _trava:  # um modelo para todas as threads de busca
        modelo, prep, tokenizador = _carregar()
        with torch.no_grad():
            faltando = [t for t in textos if t not in _textos]
            if faltando:
                emb = modelo.encode_text(tokenizador(faltando).to(_dispositivo))
                for t, e in zip(faltando, emb / emb.norm(dim=-1, keepdim=True)):
                    _textos[t] = e
            emb_txt = torch.stack([_textos[t] for t in textos])
            lote = torch.stack([prep(imagens[i]) for i in validas]).to(_dispositivo)
            emb_img = modelo.encode_image(lote)
            emb_img = emb_img / emb_img.norm(dim=-1, keepdim=True)
            semelhanca = (emb_img @ emb_txt.T).mean(dim=1)
    for i, s in zip(validas, semelhanca.tolist()):
        resultado[i] = s
    return resultado


def _abrir(img, headers=None):
    if isinstance(img, Image.Image):
        return img
    if str(img).startswith("http"):
        return _baixar_imagem(str(img), headers)
    try:
        return Image.open(img).convert("RGB")
    except Exception:
        return None


def semelhanca_visual(a, b, headers=None):
    """Quão parecidas são duas imagens (0 a 1). Acima de ~0,93 é a mesma foto ou da mesma sessão."""
    import torch
    imgs = [_abrir(a, headers), _abrir(b, headers)]
    if None in imgs:
        return 0.0
    with _trava:
        modelo, prep, _ = _carregar()
        with torch.no_grad():
            emb = modelo.encode_image(torch.stack([prep(i) for i in imgs]).to(_dispositivo))
            emb = emb / emb.norm(dim=-1, keepdim=True)
    return float(emb[0] @ emb[1])


def textos_da_cena(cena):
    """Frases que descrevem a cena para o CLIP: a busca específica e o começo da narração (em inglês, no canal)."""
    busca = cena.get("busca_wiki") or cena.get("busca_stock") or cena.get("busca_segura") or ""
    textos = [f"a photo of {busca}"] if busca else []
    narracao = (cena.get("narracao") or "")[:300]
    if narracao:
        textos.append(narracao)
    return textos
