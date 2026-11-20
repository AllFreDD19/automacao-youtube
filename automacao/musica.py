"""Música de fundo por clima: biblioteca em musicas/<clima>/ (cada faixa com um .txt de crédito ao lado).

Faixas iniciais: Kevin MacLeod (incompetech.com), licença CC BY 4.0, grátis e válida também fora do YouTube
(Instagram, TikTok); exige o crédito na descrição, que a edição põe sozinha. Climas montados pelo nome/estilo das
faixas, sem ouvir: o dono ouve e troca as que não combinarem (basta apagar o .mp3 e o .txt ou pôr outras faixas
com o seu .txt na pasta do clima).

Uso: python main.py musica baixar      (baixa e normaliza a biblioteca inicial)
     python main.py musica listar
"""
import random
import subprocess
import urllib.parse

import requests

from . import config

CREDITO = ('"{titulo}" Kevin MacLeod (incompetech.com)\n'
           "Licensed under Creative Commons: By Attribution 4.0 License\n"
           "http://creativecommons.org/licenses/by/4.0/")
CATALOGO = {
    # documentário de guerra, queda, colapso (Impérios Caídos)
    "tenso": ["Lightless Dawn", "Ossuary 6 - Air", "Long Note Four", "Impact Lento", "Aftermath", "Gathering Darkness"],
    # tragédia, fim de uma era, despedida
    "melancolico": ["Dark Times", "Despair and Triumph", "Heartbreaking", "Sad Trio", "Bittersweet"],
    # filosofia, reflexão, calma (Le Disciple)
    "sereno": ["Clean Soul", "Meditation Impromptu 01", "Meditation Impromptu 02", "At Rest", "Long Note Two",
               "Healing"],
    # enigmas, segredos, mistérios da história
    "misterio": ["Echoes of Time", "Ossuary 5 - Rest", "Night Vigil", "Unseen Horrors"],
}
ALVO_LUFS = -20  # todas as faixas no mesmo volume antes da mistura (as originais variam de -12 a -36 LUFS)
EXTENSOES = (".mp3", ".wav", ".m4a", ".ogg")


def baixar(climas=None):
    for clima, titulos in CATALOGO.items():
        if climas and clima not in climas:
            continue
        pasta = config.PASTA_MUSICAS / clima
        pasta.mkdir(parents=True, exist_ok=True)
        for titulo in titulos:
            destino = pasta / f"{titulo}.mp3"
            if destino.exists():
                continue
            url = ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
                   + urllib.parse.quote(titulo) + ".mp3")
            r = requests.get(url, timeout=120, headers={"User-Agent": config.USER_AGENT})
            if not r.ok:
                print(f"  {titulo}: erro {r.status_code}")
                continue
            bruto = pasta / f"_{titulo}.mp3"
            bruto.write_bytes(r.content)
            subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", "-i", str(bruto),
                            "-af", f"loudnorm=I={ALVO_LUFS}:TP=-2:LRA=11", "-ar", "48000", "-b:a", "192k",
                            str(destino)], check=True)
            bruto.unlink()
            destino.with_suffix(".txt").write_text(CREDITO.format(titulo=titulo), encoding="utf-8")
            print(f"  {clima}/{titulo}")


def listar():
    for pasta in sorted(p for p in config.PASTA_MUSICAS.glob("*") if p.is_dir()):
        faixas = sorted(f.stem for f in pasta.iterdir() if f.suffix.lower() in EXTENSOES)
        print(f"{pasta.name} ({len(faixas)}): {', '.join(faixas)}")


def escolher(roteiro, duracao):
    """Faixas do clima do vídeo, embaralhadas, até cobrir `duracao` (mais 30 s de folga), e os créditos delas.

    Clima: campo "tom_musica" do roteiro.json; sem ele, o do canal (campo "canal" + config.MUSICA_CANAIS);
    sem nenhum dos dois, uma faixa solta da raiz de musicas/ (comportamento antigo). "tom_musica": "nenhuma" desliga.
    """
    clima = roteiro.get("tom_musica") or config.MUSICA_CANAIS.get(roteiro.get("canal", ""))
    if clima == "nenhuma":
        return [], []
    pasta = config.PASTA_MUSICAS / clima if clima else config.PASTA_MUSICAS
    faixas = [p for p in pasta.glob("*") if p.suffix.lower() in EXTENSOES and not p.name.startswith("_")]
    if not faixas:
        if clima:
            print(f"  sem músicas em musicas/{clima} (rode: python main.py musica baixar); vídeo sem música")
        return [], []
    random.shuffle(faixas)
    escolhidas, total = [], 0.0
    while total < duracao + 30:
        f = faixas[len(escolhidas) % len(faixas)]
        escolhidas.append(f)
        total += _duracao(f) - 4  # 4 s de fusão entre faixas
        if len(escolhidas) > 40:
            break
    creditos = []
    for f in dict.fromkeys(escolhidas):
        txt = f.with_suffix(".txt")
        if txt.exists():
            creditos.append(txt.read_text(encoding="utf-8").strip())
        else:
            print(f"  ATENÇÃO: {f.name} sem .txt de crédito ao lado; confira a licença antes de publicar")
    return escolhidas, creditos


def _duracao(arquivo):
    r = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(arquivo)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 120.0


def filtro_mistura(n_faixas, primeira_entrada, duracao):
    """Filtro do FFmpeg: emenda as faixas com fusão de 4 s, deixa baixo, abaixa mais sob a voz (ducking) e
    some no fim. Entradas: [0:a] = narração; [primeira_entrada..] = faixas. Saída: [a]."""
    partes = []
    atual = f"[{primeira_entrada}:a]"
    for i in range(1, n_faixas):
        prox = f"[{primeira_entrada + i}:a]"
        partes.append(f"{atual}{prox}acrossfade=d=4:c1=tri:c2=tri[mx{i}]")
        atual = f"[mx{i}]"
    fim = max(duracao - 4, 0)
    partes.append(f"{atual}aformat=sample_rates=48000:channel_layouts=stereo,volume={config.MUSICA_VOLUME},"
                  f"afade=t=in:d=3,afade=t=out:st={fim:.2f}:d=4,atrim=0:{duracao:.2f}[mus]")
    partes.append("[0:a]asplit=2[voz][chave]")
    # Ducking: sob a fala a música cai mais ~6-8 dB; nas pausas volta devagar (sem "bombear")
    partes.append("[mus][chave]sidechaincompress=threshold=0.02:ratio=5:attack=40:release=900[musb]")
    partes.append("[voz][musb]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
    return ";".join(partes)
