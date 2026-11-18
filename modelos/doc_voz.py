"""DOCUMENTÁRIO COM A VOZ DO USUÁRIO: um visual por cena, com a narração gravada por ele (padrão desde 2026-10-26).

Na pasta do projeto: roteiro.md escrito à mão ("## Roteiro" com "### 1", "### 2"...), narracao_usuario.mp3 e doc.json:
  {"titulo": "...", "secoes": ["capítulo 1", ...], "contexto": "em inglês: assunto, lugares, objetos concretos",
   "busca_cta": ["stock do tema para trechos de CTA", ...]}

Uso (na ordem; cada etapa grava no roteiro.json):
  python modelos/doc_voz.py projetos/<pasta> montar     # cenas + buscas de imagem (Nemotron) + correções
  python -m automacao.transcrever projetos/<pasta>/narracao_usuario.mp3 projetos/<pasta>/palavras.json fr
  python modelos/doc_voz.py projetos/<pasta> alinhar    # recorta a voz em audio/cena_XXX.wav
  python modelos/doc_voz.py projetos/<pasta> visuais    # ~40 min para 160 cenas
  (revisar folha_cenas.jpg; trocar as ruins por visuais bons do próprio vídeo: modelos/reaproveitar.py)
  python modelos/doc_voz.py projetos/<pasta> editar     # edicao.PAUSA = 0: as pausas já estão na gravação
"""
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
from automacao import config, edicao, historia, narracao, roteiro  # noqa: E402

CTA = re.compile(r"abonnez|commentaire|laissez un like|la cloche|subscribe|comment|iscriv|suscr|abonnier", re.I)
MARGEM = 0.12


def ler(pasta):
    return json.loads((pasta / "roteiro.json").read_text(encoding="utf-8"))


def salvar(pasta, r):
    (pasta / "roteiro.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


def montar(pasta):
    doc = json.loads((pasta / "doc.json").read_text(encoding="utf-8"))
    md = (pasta / "roteiro.md").read_text(encoding="utf-8")
    corpo = md.split("## Roteiro", 1)[1].split("## Abertura alternativa", 1)[0]
    caps = [c.strip() for c in re.split(r"^### \d+\s*$", corpo, flags=re.M) if c.strip()]
    cenas = []
    for n, (secao, texto) in enumerate(zip(doc["secoes"], caps), 1):
        for trecho in roteiro._dividir_em_cenas(texto):
            # o divisor quebra nas iniciais ("George H. W. Bush"): junta com a frase seguinte
            if cenas and cenas[-1]["capitulo"] == n and re.search(r"\b[A-Z]\.$", cenas[-1]["narracao"]):
                cenas[-1]["narracao"] += " " + trecho
            else:
                cenas.append({"secao": secao, "capitulo": n, "narracao": trecho})
    for i, c in enumerate(cenas, 1):
        c["id"] = i
    print(len(cenas), "cenas; pedindo buscas de imagem ao Nemotron...")
    ficha = {"titulo_final": doc["titulo"], "contexto": doc["contexto"]}
    for c, chave in zip(cenas, roteiro._palavras_chave(ficha, [c["narracao"] for c in cenas])):
        c["visual"] = chave.get("visual") if chave.get("visual") in ("stock", "ia") else "ia"
        for campo in ("busca_stock", "busca_segura", "busca_wiki", "prompt_imagem"):
            c[campo] = chave.get(campo, "")
    r = {"titulo": doc["titulo"], "idioma_codigo": doc.get("idioma", "fr"), "voz": "usuario", "nicho": "D",
         "ficha": ficha, "capitulos_texto": caps, "cenas": cenas}
    roteiro.completar_palavras_chave(r)
    # trechos de CTA: o Nemotron pede "subscribe button", "comment section"... troca por imagens do tema
    k = 0
    for c in cenas:
        if CTA.search(c["narracao"]):
            c.update(visual="stock", busca_stock=doc["busca_cta"][k % len(doc["busca_cta"])],
                     busca_segura=doc["busca_cta"][k % len(doc["busca_cta"])].split()[-1], busca_wiki="")
            k += 1
    salvar(pasta, r)
    for c in cenas:
        print(f"{c['id']:>3} stock={c['busca_stock']!r} wiki={c['busca_wiki']!r} | {c['narracao'][:55]}")


def alinhar(pasta):
    r = ler(pasta)
    audio = pasta / "narracao_usuario.mp3"
    whisper = json.loads((pasta / "palavras.json").read_text(encoding="utf-8"))
    total = narracao.duracao_audio(audio)
    palavras, dono = [], []
    for i, c in enumerate(r["cenas"]):
        for w in c["narracao"].split():
            palavras.append((w, None))
            dono.append(i)
    tempo = historia.alinhar(palavras, whisper, total)
    ini, fim = {}, {}
    for k, i in enumerate(dono):
        ini.setdefault(i, tempo[k][0])
        fim[i] = tempo[k][1]
    cortes = [0.0]
    for i in range(1, len(r["cenas"])):
        cortes.append(max(ini[i] - MARGEM, fim[i - 1], cortes[-1] + 0.3))
    cortes.append(total)
    (pasta / "audio").mkdir(exist_ok=True)
    for i, c in enumerate(r["cenas"]):
        destino = pasta / "audio" / f"cena_{c['id']:03d}.wav"
        subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-i", str(audio), "-ss", f"{cortes[i]:.3f}",
                        "-to", f"{cortes[i + 1]:.3f}", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(destino)],
                       check=True)
        c["audio"] = str(destino.relative_to(pasta))
        c["duracao"] = round(narracao.duracao_audio(destino), 3)
    salvar(pasta, r)
    # cena com ritmo fora do normal = recorte suspeito: mostra o que o Whisper ouviu nela
    t, taxas = 0.0, []
    for c in r["cenas"]:
        ouvido = " ".join(x["w"] for x in whisper if t <= x["s"] < t + c["duracao"])
        taxas.append((len(c["narracao"]) / c["duracao"], c["id"], c["narracao"][:60], ouvido[:60]))
        t += c["duracao"]
    taxas.sort()
    print(f"gravação {total:.1f}s | soma das cenas {t:.1f}s | {len(r['cenas'])} cenas")
    for x in taxas[:3] + taxas[-3:]:
        print(f"  {x[0]:.1f} car/s cena {x[1]} | {x[2]} || {x[3]}")


def produzir(pasta, etapa):
    import main
    edicao.PAUSA = 0.0
    a = SimpleNamespace(projeto=pasta.name, voz=None)
    main.cmd_visuais(a) if etapa == "visuais" else main.cmd_editar(a)


if __name__ == "__main__":
    pasta, etapa = Path(sys.argv[1]).resolve(), sys.argv[2]
    {"montar": montar, "alinhar": alinhar}.get(etapa, lambda p: produzir(p, etapa))(pasta)
