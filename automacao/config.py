"""Configurações lidas do arquivo .env na raiz do projeto."""
import glob
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

PASTA_PROJETOS = RAIZ / "projetos"
PASTA_MUSICAS = RAIZ / "musicas"
PASTA_FONTES = RAIZ / "fontes"

# A ferramenta roda no Windows do dono e no Linux do Claude Code na nuvem (desde 2026-11-18).
NO_WINDOWS = os.name == "nt"
_IMPACT = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "impact.ttf"
# Fonte grossa das thumbnails e do texto na tela: Impact no Windows; no Linux, Anton (parecida, licença livre OFL,
# guardada em fontes/)
FONTE_TITULO = str(_IMPACT) if NO_WINDOWS and _IMPACT.exists() else str(PASTA_FONTES / "Anton-Regular.ttf")
FONTE_TITULO_NOME = "Impact" if NO_WINDOWS and _IMPACT.exists() else "Anton"
# A Anton é mais estreita que a Impact: no texto das legendas (libass) ela precisa de letra ~30% maior
FONTE_TITULO_ESCALA = 1.0 if FONTE_TITULO_NOME == "Impact" else 1.3
# Na nuvem a internet passa por um proxy; o Edge TTS (aiohttp) não lê HTTPS_PROXY sozinho
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None


def fonte_texto(tamanho, negrito=False):
    """Fonte comum (Arial no Windows; Liberation Sans ou DejaVu no Linux) para folhas de contato e rótulos."""
    from PIL import ImageFont
    nomes = (["arialbd.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"] if negrito
             else ["arial.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf"])
    for nome in nomes:
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    return ImageFont.load_default(size=tamanho)


def _registrar_fontes_linux():
    """As legendas (libass) acham fontes pelo fontconfig: copia as de fontes/ para a pasta de fontes do usuário."""
    if NO_WINDOWS or not PASTA_FONTES.exists():
        return
    destino = Path.home() / ".local" / "share" / "fonts"
    novas = [f for f in PASTA_FONTES.glob("*.ttf") if not (destino / f.name).exists()]
    if novas:
        destino.mkdir(parents=True, exist_ok=True)
        for f in novas:
            shutil.copy(f, destino / f.name)
        import subprocess
        subprocess.run(["fc-cache", "-f", str(destino)], capture_output=True)


_registrar_fontes_linux()


def _env(nome, padrao=""):
    return os.getenv(nome, padrao).strip()


# IA de texto (NVIDIA build / NIM, compatível com a API da OpenAI)
NVIDIA_API_KEY = _env("NVIDIA_API_KEY")
NVIDIA_BASE_URL = _env("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = _env("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")

# Pesquisa e visuais
YOUTUBE_API_KEY = _env("YOUTUBE_API_KEY")
PEXELS_API_KEY = _env("PEXELS_API_KEY")
PIXABAY_API_KEY = _env("PIXABAY_API_KEY")
UNSPLASH_ACCESS_KEY = _env("UNSPLASH_ACCESS_KEY")  # fotos de alta qualidade; chave "Demo" = 50 buscas por hora
IMAGEM_PROVEDOR = _env("IMAGEM_PROVEDOR", "pixabay").lower()  # pixabay | ia
# Parte das cenas que deve ser vídeo (o resto é imagem com zoom lento); 0.5 = metade, deixa o vídeo mais dinâmico
PROPORCAO_VIDEO = float(_env("PROPORCAO_VIDEO", "0.5"))

# Narração. Padrão desde 2026-10-12 (escolha do usuário): Kokoro local, voz am_michael, para roteiros em inglês
# (o Edge TTS passou a dar 403 por limite de IP). Outros idiomas continuam no Edge TTS (VOZ / VOZ_VELOCIDADE).
VOZ_PROVEDOR = _env("VOZ_PROVEDOR", "kokoro").lower()  # kokoro | edge
VOZ_KOKORO = _env("VOZ_KOKORO", "am_michael")
VOZ_KOKORO_VELOCIDADE = float(_env("VOZ_KOKORO_VELOCIDADE", "1.05"))
# Alemão: Piper local (o Edge segue com 403). Voz "piper:<modelo>#<locutor>", modelos em vozes_piper/.
# length_scale < 1 acelera (0,95 escolhido pelo usuário em 2026-10-12 nas amostras do marder-auto).
VOZ_PIPER_ALEMAO = _env("VOZ_PIPER_ALEMAO", "piper:de_DE-thorsten_emotional-medium#neutral")
VOZ_PIPER_LENGTH_SCALE = float(_env("VOZ_PIPER_LENGTH_SCALE", "0.95"))
# Espanhol: Piper local, voz davefx (sotaque da Espanha), padrão desde 2026-10-17 (submarino-s80): o Edge segue com
# 403 e o espanhol do Kokoro é fraco. Fixa a voz para não gerar amostras a cada vídeo.
VOZ_PIPER_ESPANHOL = _env("VOZ_PIPER_ESPANHOL", "piper:es_ES-davefx-medium")
# Francês: Piper Tom (voz masculina grave), escolhida pelo usuário em 2026-10-17 (sable-marin-chine). A voz Gilles não
# tem o fonema nasal e lê "en/on/Chine" errado; não usar.
VOZ_PIPER_FRANCES = _env("VOZ_PIPER_FRANCES", "piper:fr_FR-tom-medium")
VOZ = _env("VOZ", "pt-BR-AntonioNeural")
# Voz de cada canal no lugar do Clipchamp (escolha do dono em 2026-11-19, depois de comparar com os áudios dos canais):
# Remy Multilingual nos dois, com a velocidade medida nas narrações originais. Comando: rodar voz <canal> <texto.txt>
VOZES_CANAIS = {
    "le-disciple": {"voz": "fr-FR-RemyMultilingualNeural", "velocidade": "+8%"},
    "imperios": {"voz": "fr-FR-RemyMultilingualNeural", "velocidade": "-9%"},
    # provisória até o dono escolher a voz grave do canal
    "jogos": {"voz": "pt-BR-AntonioNeural", "velocidade": "+0%"},
}
VOZ_VELOCIDADE = _env("VOZ_VELOCIDADE", "+5%")

# Roteiro (padrões do Prompt Mestre; cada um pode ser trocado por opção no comando)
IDIOMA_ROTEIRO = _env("IDIOMA_ROTEIRO", "português")
CAPITULOS = int(_env("CAPITULOS", "4"))
CARACTERES = int(_env("CARACTERES", "11000"))  # ≈ 15 min; 22000 ≈ 30 min (vídeos do canal: 15 ou 30 min)
META_CANAL = _env("META_CANAL")

# Vídeo
MUSICA_VOLUME = float(_env("MUSICA_VOLUME", "0.10"))
LEGENDAS = _env("LEGENDAS", "sim").lower() in ("sim", "s", "true", "1")
# Desligado por padrão desde 2026-10 (decisão do usuário); o código fica para quem quiser ligar com APRESENTADOR=sim
APRESENTADOR = _env("APRESENTADOR", "nao").lower() in ("sim", "s", "true", "1")
REGIAO = _env("REGIAO", "BR")
IDIOMA = _env("IDIOMA", "pt")


def _achar_binario(nome):
    caminho = shutil.which(nome)
    if caminho:
        return caminho
    padrao = os.path.expandvars(rf"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\{nome}.exe")
    achados = glob.glob(padrao)
    if achados:
        return achados[0]
    raise SystemExit(f"{nome} não encontrado. Instale com: winget install Gyan.FFmpeg")


def ffmpeg():
    return _env("FFMPEG_PATH") or _achar_binario("ffmpeg")


def ffprobe():
    return _env("FFPROBE_PATH") or _achar_binario("ffprobe")
