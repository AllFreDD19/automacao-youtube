# Automação de vídeos para canais dark (YouTube)

Ferramenta em Python que produz vídeos completos: roteiro → narração → visuais → edição → thumbnail.
Uso e comandos: ver `LEIA-ME.md`. Rodar com `.\rodar.bat <comando>`; chaves em `.env` (o dono preenche, nunca pedir no chat).

## Decisões do dono (valem para todos os canais)
- Meta: expandir para mais canais. Cada canal novo ganha uma seção em "Canais" (copiar o modelo no fim da seção).
- Meta de cada canal: 1.000 inscritos. Ritmo: 1 a 2 vídeos por dia em cada canal.
- Roteiros seguem o Prompt Mestre em `prompts/roteiro_mestre.md` (não alterar sem pedido): abertura de retenção nos
  primeiros 30-45 s (1a frase confirma título e thumb, 2+ loops de curiosidade, revelação só no último terço) e
  regra dos 3 CTAs (depois da abertura, no meio do vídeo e no final).
  Quando a seção do canal (em "Canais") disser outra coisa (formato, capítulos, CTAs), vale a seção do canal.
- Custo zero: só serviços gratuitos (Nemotron e FLUX com créditos NVIDIA, Clipchamp, Edge TTS, Kokoro e Piper locais,
  Pixabay, Pexels, Wikimedia, NASA, Openverse, Unsplash, FFmpeg, CLIP e Whisper locais).

## Tamanho dos roteiros
- Os vídeos têm 15 ou 30 minutos. Perguntar qual, se o pedido não disser.
- Conta: cerca de 735 caracteres por minuto de narração. 15 min = ~11.000 caracteres; 30 min = ~22.000 caracteres.
- Ao preencher o BLOCO DE ENTRADA do Prompt Mestre, usar esse total no campo de caracteres; nunca o padrão de 40.000.

## Canais
Antes de escrever roteiro, título, thumbnail ou descrição, identificar de qual canal é o pedido e seguir a seção dele.
Se o canal não for dito, perguntar. Campos "[preencher]": perguntar ao dono, nunca inventar.

### Le Disciple du Savoir (@LeDiscipleduSavoir, ID UCe06mEV939UUr0k6-vYs7Qg)
- Tema: filosofia e sabedoria antiga (estoicismo, desenvolvimento pessoal), narração personificada (sábio barbudo, ~50 anos).
- Idioma: francês. Voz: áudio feito no Clipchamp (texto colado direto).
- Formato: roteiro em narração contínua, sem capítulos, listas ou títulos internos; 1 a 3 CTAs fluidas no meio do texto.
- Abertura fixa (jingle) em todo vídeo. CTA padrão: "Rejoignez la communauté des personnes qui pensent différemment".
- Entregáveis por vídeo: roteiro, título principal + 3 alternativas, miniatura, 25 prompts de imagens em ordem cronológica
  (alternando o Disciple da biblioteca e imagens conceituais), descrição com 6 hashtags, anúncio para a comunidade.
- Temas: nunca repetir os já usados (lista de temas no histórico do canal).
- Tamanho: vídeos de 15 ou 30 minutos (ver "Tamanho dos roteiros"). Meta: 1.000 inscritos; 1 a 2 vídeos por dia.

### Impérios Caídos (@imperioscaidosofficial, ID UCZpm9Q4UMAOhZQ0erHwrWug)
- Tema: ascensão e queda de impérios e civilizações, guerras, mistérios da história, documentários cinematográficos
  (nicho D do Prompt Mestre: documentário narrativo real, não inventar fatos, datas, números nem citações).
- Idioma: espanhol. Voz: áudio feito no Clipchamp (texto colado direto).
- Formato: Prompt Mestre completo (4 capítulos, 3 CTAs).
- Tamanho: vídeos de 15 ou 30 minutos (ver "Tamanho dos roteiros"). Meta: 1.000 inscritos; 1 a 2 vídeos por dia.

### Fora da Missão (nome sugerido; @handle e ID: [preencher]; ainda não criado)
- Tema: gameplay do dono em vídeos de tutorial ou demonstração (explicar missão, mostrar o que dá para fazer ou o que existe no jogo).
  Jogo principal: GTA VI (lançamento 19/11/2026); depois, outros jogos. Idioma: português (Brasil). Público geral.
- Tipos de vídeo: missão (como passar, passo a passo), easter eggs e segredos, react (reação do narrador à
  própria gameplay e às descobertas). React a trailer ou vídeo de terceiros: só com pedido do dono, trechos curtos e
  comentário dominando (risco de Content ID); nunca reagir a vídeo de outro canal do YouTube.
  O nome não leva "GTA" (marca da Rockstar/Take-Two) para o canal poder mudar de jogo sem trocar de nome.
- Formato: o dono entrega a gameplay (vídeo) na pasta do projeto. Dois tipos: (1) narrado, com roteiro que descreve o que
  acontece na imagem; (2) curto, só com música de fundo e texto na tela, sem narração.
- Como "ver" o vídeo: nunca assumir o que acontece sem olhar. Extrair quadros com FFmpeg (1 a cada 2-3 s, mais denso nas trocas
  de cena), descrever cada trecho a partir dos quadros e só então escrever o roteiro; transcrever a fala do jogo com
  `automacao/transcrever.py`. Nomes de itens, missões e locais: conferir na tela ou perguntar ao dono, nunca inventar.
- Edição: cortes por trecho com FFmpeg, legenda palavra a palavra (`automacao/historia.py`) quando houver narração; música de
  fundo baixa (-18 dB) com licença livre, da pasta `musicas/` que o dono preenche (guardar o crédito para a descrição).
- Direitos: gameplay do próprio dono; checar a política de conteúdo do estúdio do jogo antes de monetizar.
- Entregáveis por vídeo: roteiro (se narrado), título principal + 3 alternativas, miniatura (quadro do jogo), descrição com
  créditos da música.
- Tamanho: vídeos longos (horizontais, 1920x1080) de 10 a 15 minutos; roteiro narrado ~7.300 a 11.000 caracteres.
- Curtos: de 30 a 60 s, verticais (1080x1920), tirados da mesma gameplay (o melhor momento, texto grande na tela).
  Servem para YouTube Shorts, Instagram Reels e TikTok sem mudar o arquivo. Música: só faixas cuja licença
  permita usar fora do YouTube (a Biblioteca de Áudio do YouTube pode não valer no Instagram/TikTok); nos dois,
  dá para usar a música do próprio app em vez da nossa.
- Meta: 1.000 inscritos; 1 a 2 vídeos longos por dia, mais os curtos à parte.
- Identidade: mascote ORIGINAL (arquétipo de líder durão, sarcástico e calmo; opções em `canal_jogos/`, comando
  `jogo mascote`). Nunca usar personagem de outra obra (ex.: Yami de Black Clover) nem imitar a voz de dublador ou
  pessoa real: voz grave genérica do Clipchamp.
- Ferramenta: `automacao/jogos.py` (`.\rodar.bat jogo preparar|gravar|montar|curtos|thumb <projeto>`, ver LEIA-ME).
  Para escrever o `roteiro_jogo.json`: rodar `preparar`, ABRIR as imagens de `folhas/` e ler `mapa.md`; cada trecho
  usa só o que aparece nos quadros daquele intervalo. Abertura de retenção e 3 CTAs curtos (regra geral) também valem.

### Modelo para canal novo
```
### <Nome> (<@handle>, ID <UC...>)
- Tema:
- Idioma / Voz:
- Formato dos roteiros (capítulos, CTAs):
- Entregáveis por vídeo:
- Tamanho dos roteiros / Meta de inscritos:
```

## Como a ferramenta funciona (técnico)
- Narração: Kokoro local (inglês, voz am_michael); Piper local para espanhol (es_ES-davefx-medium), alemão
  (de_DE-thorsten_emotional-medium#neutral) e francês (fr_FR-tom-medium), modelos em `vozes_piper/` (baixados pelo
  instalar.ps1); Edge TTS para os demais idiomas. Só quando a ferramenta narra: nos canais com voz do Clipchamp
  (Le Disciple, Impérios Caídos) a ferramenta não narra. Nomes próprios lidos errado: campo "pronuncia_piper" do roteiro.json.
- Visuais: Wikimedia (foto exata, campo `busca_wiki`), Pixabay, Pexels, NASA, Openverse e Unsplash concorrem; o CLIP
  (`automacao/relevancia.py`) dá nota a cada candidato e escolhe o melhor. Créditos vão sozinhos para a descrição
  (não apagar ao publicar: a licença exige).
- Ritmo: uma frase por cena (~8 s); fala > 9 s ganha segundo visual na metade. Meta de 50% das cenas em vídeo
  (é meta: imagem certa vale mais que vídeo sem relação).
- Edição: transições por xfade (fusão entre cenas; zoom/flash na virada de seção), só na imagem: o áudio fica intacto.
- Thumbnail (`.\rodar.bat thumb <projeto>`, `automacao/thumb_ia.py`): estilo "cinema" (cena realista do FLUX da
  NVIDIA + 2 linhas grandes em Impact). Se o FLUX estiver fora do ar, montar com foto real do Wikimedia.
- Vídeo de HISTÓRIA com a voz gravada pelo dono: fundo contínuo de paisagens de drone + legenda palavra a palavra
  (`python -m automacao.historia projetos\<pasta> campo castelo floresta montanha`; antes, uma vez:
  `python -m automacao.paisagens restaurar` para baixar os clipes). Documentário com a voz do dono:
  `modelos/doc_voz.py`.
- Modelos de roteiro escrito à mão e de revisão: `modelos/` (montar_video_lista, trocar_visuais, visuais,
  reaproveitar, mini_folha, wiki_acervo, para_gravar).

## Lições (o que sempre revisar antes de entregar)
- O Nemotron inventa fatos, números e anedotas: ler `roteiro.md` antes de narrar; em vídeos com dados, escrever o
  roteiro à mão com fatos verificados.
- Conferir `folha_cenas.jpg`: notas do CLIP abaixo de 0,22 saem em vermelho. No máximo 2 rodadas de troca; o que
  sobrar, reaproveitar um visual bom do próprio vídeo (sempre depois da última busca).
- Máquina/lugar específico com poucas fotos livres: baixar as fotos reais antes e pôr direto nas cenas que falam dele.
- Thumbnails com logo de marca real + palavra negativa podem soar como acusação à marca; nunca usar pessoa real em
  imagem fabricada.
- Nunca usar trechos de vídeos de outros canais do YouTube (Content ID, strikes e "conteúdo reutilizado").
