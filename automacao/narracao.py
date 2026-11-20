"""Etapa 5: narração de cada cena. Inglês: Kokoro local; alemão: Piper local; outros idiomas: Edge TTS (gratuitos)."""
import asyncio
import re
import subprocess

import edge_tts
from edge_tts import communicate as _edge_communicate
from edge_tts import constants as _edge_constants

from . import config

# Desde 10/10/2026 a Microsoft recusa (erro 403) o endereço antigo do serviço de voz usado pelo edge-tts 7.2.8.
# Este endereço funciona (issue #490 do edge-tts; correção trazida da Fábrica de Vídeos do usuário em 24/10/2026).
# Quando sair uma versão corrigida do edge-tts, esta troca pode ser removida.
_edge_communicate.WSS_URL = ("wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
                             f"?Ocp-Apim-Subscription-Key={_edge_constants.TRUSTED_CLIENT_TOKEN}")


def duracao_audio(caminho):
    saida = subprocess.run(
        [config.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(caminho)],
        capture_output=True, text=True, check=True,
    )
    return float(saida.stdout.strip())


async def _narrar(texto, destino, voz, velocidade, limite, tom="+0Hz"):
    async with limite:
        for tentativa in range(3):
            try:
                await edge_tts.Communicate(texto, voz, rate=velocidade, pitch=tom, proxy=config.PROXY).save(str(destino))
                return
            except Exception:
                if tentativa == 2:
                    raise
                await asyncio.sleep(3)


async def _narrar_todas(tarefas, voz, velocidade, em_paralelo, tom="+0Hz"):
    limite = asyncio.Semaphore(em_paralelo)
    await asyncio.gather(*(_narrar(texto, destino, voz, velocidade, limite, tom) for texto, destino in tarefas))


# Equalização da voz (aproxima o timbre da gravação original do canal). "leve" = um pouco mais grave e menos
# brilho: na comparação de 2026-11-20 deixou o centroide espectral igual ao do canal francês (~1.120 Hz).
EQ_VOZ = {
    "leve": "bass=g=1.5:f=140,equalizer=f=3200:t=q:w=1.2:g=-2,equalizer=f=7000:t=q:w=1:g=-1.5",
}


def _usa_kokoro(roteiro, voz):
    """Kokoro só para inglês (não tem alemão; português e espanhol dele são fracos) e quando nenhuma voz do Edge
    foi pedida no comando (--voz en-US-...)."""
    if config.VOZ_PROVEDOR != "kokoro" or (voz and "Neural" in voz):
        return False
    return roteiro.get("idioma_codigo", "").startswith("en") or (roteiro.get("voz") or "").startswith("en-")


# Pronúncias corrigidas só na voz (a legenda continua com o texto original), no formato do Kokoro: [palavra](/fonemas/).
# Conferir nomes novos com: misaki.en.G2P(...)("palavra") antes de narrar.
PRONUNCIA_KOKORO = {
    "NCAP": "[NCAP](/ˈɛnkˌæp/)",
    "ISOFIX": "[ISOFIX](/ˈIsOfˌɪks/)",
}


def _pronuncia(texto, extra=None):
    """Troca só palavras inteiras ("Ju" não pega "July" nem "Junkers"). `extra` = {"Udet": "/ˈudɛt/"} do roteiro.json
    (campo "pronuncia"), para nomes próprios de cada vídeo."""
    import re
    trocas = dict(PRONUNCIA_KOKORO)
    trocas.update({p: f"[{p}]({f})" for p, f in (extra or {}).items()})
    for palavra in sorted(trocas, key=len, reverse=True):
        texto = re.sub(rf"(?<![\w\[]){re.escape(palavra)}(?![\w\]])", lambda _: trocas[palavra], texto)
    return texto


def _narrar_kokoro(tarefas, voz, extra=None):
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    # a primeira letra da voz diz o sotaque: a = americano, b = britânico
    pipe = KPipeline(lang_code=voz[0], repo_id="hexgrad/Kokoro-82M")
    for n, (texto, destino) in enumerate(tarefas, 1):
        audio = np.concatenate([a.cpu().numpy() for _, _, a in pipe(_pronuncia(texto, extra), voice=voz, speed=config.VOZ_KOKORO_VELOCIDADE)])
        wav = destino.with_suffix(".wav")
        sf.write(wav, audio, 24000)
        # mp3 como o Edge, para o resto da ferramenta não mudar nada
        subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "192k", str(destino)],
                       check=True)
        wav.unlink()
        if n % 20 == 0:
            print(f"    {n}/{len(tarefas)}")


def _voz_piper(roteiro, voz):
    """Piper local para alemão e espanhol (o Edge dá 403), a menos que uma voz do Edge seja pedida no comando."""
    if voz:
        return voz if voz.startswith("piper:") else None
    if (roteiro.get("voz") or "").startswith("piper:"):
        return roteiro["voz"]
    if roteiro.get("idioma_codigo", "").startswith("de"):
        return config.VOZ_PIPER_ALEMAO
    if roteiro.get("idioma_codigo", "").startswith("es"):
        return config.VOZ_PIPER_ESPANHOL
    if roteiro.get("idioma_codigo", "").startswith("fr"):
        return config.VOZ_PIPER_FRANCES
    return None


def _respeitar_grafia(texto, extra=None):
    """Troca só no que a voz fala (a legenda usa o texto original) nomes que o Piper lê errado, ex.:
    {"Xinyi": "Chinyi"} no campo "pronuncia_piper" do roteiro.json. Casa palavra inteira."""
    for original, falado in (extra or {}).items():
        texto = re.sub(rf"(?<!\w){re.escape(original)}(?!\w)", falado, texto)
    return texto


def _narrar_piper(tarefas, voz, extra=None):
    import wave
    from piper import PiperVoice, SynthesisConfig

    modelo, _, locutor = voz.removeprefix("piper:").partition("#")
    v = PiperVoice.load(str(config.RAIZ / "vozes_piper" / f"{modelo}.onnx"))
    mapa = v.config.speaker_id_map or {}
    cfg = SynthesisConfig(speaker_id=mapa.get(locutor, int(locutor) if locutor.isdigit() else None),
                          length_scale=config.VOZ_PIPER_LENGTH_SCALE)
    for n, (texto, destino) in enumerate(tarefas, 1):
        wav = destino.with_suffix(".wav")
        with wave.open(str(wav), "wb") as w:
            v.synthesize_wav(_respeitar_grafia(texto, extra), w, syn_config=cfg)
        subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "192k", str(destino)],
                       check=True)
        wav.unlink()
        if n % 20 == 0:
            print(f"    {n}/{len(tarefas)}")


def narrar_cenas(roteiro, pasta_projeto, voz=None, velocidade=None, em_paralelo=6):
    piper = _voz_piper(roteiro, voz)
    kokoro = not piper and _usa_kokoro(roteiro, voz)
    voz = piper or ((voz or config.VOZ_KOKORO) if kokoro else (voz or roteiro.get("voz") or config.VOZ))
    velocidade = velocidade or config.VOZ_VELOCIDADE
    pasta = pasta_projeto / "audio"
    pasta.mkdir(exist_ok=True)
    destinos = {cena["id"]: pasta / f"cena_{cena['id']:03d}.mp3" for cena in roteiro["cenas"]}
    tarefas = [(c["narracao"], destinos[c["id"]]) for c in roteiro["cenas"] if not destinos[c["id"]].exists()]
    if tarefas:
        if piper:
            print(f"  narrando {len(tarefas)} cena(s) com Piper ({voz})...")
            _narrar_piper(tarefas, voz, roteiro.get("pronuncia_piper"))
        elif kokoro:
            print(f"  narrando {len(tarefas)} cena(s) com Kokoro ({voz})...")
            _narrar_kokoro(tarefas, voz, roteiro.get("pronuncia"))
        else:
            print(f"  narrando {len(tarefas)} cena(s), {em_paralelo} por vez...")
            asyncio.run(_narrar_todas(tarefas, voz, velocidade, em_paralelo))
    for cena in roteiro["cenas"]:
        cena["audio"] = str(destinos[cena["id"]].relative_to(pasta_projeto))
        cena["duracao"] = round(duracao_audio(destinos[cena["id"]]), 3)
    total = sum(c["duracao"] for c in roteiro["cenas"])
    print(f"  narração total: {total / 60:.1f} min")
    return roteiro


def listar_vozes():
    vozes = asyncio.run(edge_tts.list_voices(proxy=config.PROXY))
    return [v for v in vozes if v["Locale"].startswith("pt-")]


def narrar_texto(texto, destino, voz, velocidade="+0%", tom="+0Hz", eq=None):
    """Narra um texto inteiro num arquivo só (substitui o Clipchamp). Parágrafos separados por linha em branco viram
    blocos narrados um a um (se um falhar, só ele é refeito) e são juntados com uma pausa curta, como no Clipchamp."""
    from pathlib import Path
    destino = Path(destino)
    blocos = [b.strip() for b in re.split(r"\n\s*\n", texto) if b.strip()]
    pasta = destino.parent / f"_{destino.stem}_blocos"
    pasta.mkdir(parents=True, exist_ok=True)
    tarefas = [(b, pasta / f"bloco_{i:03d}.mp3") for i, b in enumerate(blocos, 1)]
    faltam = [(b, d) for b, d in tarefas if not d.exists() or d.stat().st_size == 0]
    print(f"  {len(blocos)} bloco(s), {len(texto):,} caracteres, voz {voz} ({velocidade}, tom {tom}, eq {eq or '-'})")
    if faltam:
        asyncio.run(_narrar_todas(faltam, voz, velocidade, 4, tom))
    pausa = pasta / "pausa.mp3"
    if not pausa.exists():
        subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "anullsrc=r=24000:cl=mono", "-t", "0.45", "-b:a", "48k", str(pausa)], check=True)
    lista = pasta / "lista.txt"
    itens = []
    for _, d in tarefas:
        itens += [d, pausa]
    lista.write_text("".join(f"file '{x.resolve().as_posix()}'\n" for x in itens[:-1]), encoding="utf-8")
    filtro = ["-af", EQ_VOZ[eq]] if eq in EQ_VOZ else []
    subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
                    *filtro, "-ar", "48000", "-ac", "2", "-b:a", "192k", str(destino)], check=True)
    for x in pasta.iterdir():
        x.unlink()
    pasta.rmdir()
    total = duracao_audio(destino)
    print(f"  {destino} ({int(total // 60)} min {int(total % 60)} s)")
    return destino
