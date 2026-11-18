"""Troca visuais ruins vistos na folha_cenas.jpg por visuais BONS que já estão no vídeo, de cenas distantes (regra do
usuário de 2026-10-17: sem 2ª rodada de busca). Rodar só DEPOIS da última busca de visuais.

Uso: python modelos/reaproveitar.py projetos/<pasta> trocas.json
trocas.json: {"trocas": {"destino": origem, ...}, "sem_extra": [ids], "extra_vira_principal": [ids]}
  trocas: o visual principal da cena destino passa a ser o principal da origem;
  sem_extra: tira o 2º visual (a imagem principal fica a fala toda);
  extra_vira_principal: principal ruim e 2º visual bom."""
import json
import sys
from pathlib import Path

pasta = Path(sys.argv[1])
cfg = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
arq = pasta / "roteiro.json"
r = json.loads(arq.read_text(encoding="utf-8"))
cena = {c["id"]: c for c in r["cenas"]}
sem_extra = list(cfg.get("sem_extra", []))
for d in cfg.get("extra_vira_principal", []):
    c = cena[d]
    c.update(visual_arquivo=c["visual_extra"], visual_tipo=c["visual_extra_tipo"], credito=c.get("credito_extra"),
             chave=c.get("chave_extra"))
    sem_extra.append(d)
for d, o in cfg.get("trocas", {}).items():
    c, src = cena[int(d)], cena[int(o)]
    assert src.get("visual_arquivo"), f"cena {o} sem visual"
    c.update(visual_arquivo=src["visual_arquivo"], visual_tipo=src["visual_tipo"], credito=src.get("credito"),
             visual_reaproveitado=int(o))
for d in sem_extra:
    for campo in ("visual_extra", "visual_extra_tipo", "credito_extra", "chave_extra"):
        cena[d].pop(campo, None)
arq.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
sem = [c["id"] for c in r["cenas"] if not c.get("visual_arquivo")]
video = sum(c.get("visual_tipo") == "video" for c in r["cenas"])
print(f"trocadas: {len(cfg.get('trocas', {}))} | extras removidos: {len(sem_extra)} | sem visual: {sem or 'nenhuma'}"
      f" | vídeo em {video} de {len(r['cenas'])} cenas")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automacao import folha_contato  # noqa: E402
print("folha nova:", folha_contato.gerar(r, pasta))
