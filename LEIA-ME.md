# Automação de vídeos para canais dark

Pipeline: **pesquisa de nichos → referências → títulos → roteiro → narração → visuais → edição**.

## 0. Instalar num computador novo

Dê dois cliques em `instalar.bat`. Ele instala o Python 3.12 (se faltar), os pacotes, o CLIP, o FFmpeg e cria o `.env`.
O apresentador de IA (rosto falando) vem desligado e o SadTalker não está no pacote (ver "Apresentador de IA").

**Passar a ferramenta para outra pessoa:** rode `powershell -ExecutionPolicy Bypass -File empacotar.ps1`. Ele gera
`automacao-youtube-pacote.zip` sem as suas chaves (confere arquivo por arquivo), sem projetos, sem ambientes Python e
sem o rosto do seu apresentador. A outra pessoa descompacta, roda `instalar.bat` e cria as próprias chaves.
Quem usa o Claude Code pode copiar `extras\skill-roteiro-mestre` para `%USERPROFILE%\.claude\skills\roteiro-mestre`
(ajustando o caminho da pasta dentro do SKILL.md, se for outro).

## 1. Configurar (uma vez)

Abra o arquivo `.env` (no Bloco de Notas) e preencha:

| Chave | Onde conseguir | Custo |
|---|---|---|
| `NVIDIA_API_KEY` | https://build.nvidia.com → entre → "Get API Key" | créditos grátis |
| `YOUTUBE_API_KEY` | https://console.cloud.google.com → crie um projeto → ative **YouTube Data API v3** → Credenciais → Criar chave de API | grátis (10.000 unidades/dia) |
| `PIXABAY_API_KEY` | https://pixabay.com/api/docs/ (logado, a chave aparece na página) | grátis |
| `PEXELS_API_KEY` (opcional) | https://www.pexels.com/api/ | grátis |
| `UNSPLASH_ACCESS_KEY` (opcional) | https://unsplash.com/developers → New Application → copie a "Access Key" | grátis |

Fontes de imagem e vídeo, todas grátis: Wikimedia Commons, Pixabay, Pexels e Unsplash (se tiver chave), NASA (espaço, ciência,
engenharia; sem chave) e Openverse (reforço quando as outras não acham nada bom; sem chave tem limite de 200 buscas
por dia). Os créditos de Wikimedia, NASA e Openverse entram sozinhos na descrição.

A escolha de cada imagem/vídeo é feita pelo CLIP, um modelo de IA local e grátis que dá nota de 0 a ~0,4 para quanto
cada candidato combina com a cena (Wikimedia, Pixabay e Pexels concorrem juntos). O `instalar.bat` instala a versão para
processador, que funciona em qualquer PC. Com placa NVIDIA, troque pela versão CUDA (comando abaixo) para ficar
mais rápido; sem placa disponível ele volta para o processador sozinho. Na `folha_cenas.jpg`, cada cena mostra a nota; as em **vermelho** (abaixo de 0,22)
são as que merecem uma olhada. Versão CUDA (opcional, só com placa NVIDIA):
`.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130`.
O `open_clip_torch` já vem no `requirements.txt`. O modelo (~600 MB) é baixado sozinho na primeira vez.

Fotos de modelos específicos (ex.: "Saab 900") vêm do Wikimedia Commons, sem chave nem cadastro. Os créditos
(autor e licença) entram sozinhos no `descricao_youtube.txt`: **não apague essa parte ao publicar**, a licença exige.

Músicas de fundo (opcional): coloque arquivos `.mp3` sem direitos autorais na pasta `musicas`
(ex.: Biblioteca de Áudio do YouTube). A ferramenta escolhe uma aleatoriamente.

## 2. Usar

Abra o PowerShell nesta pasta e rode:

```
.\rodar.bat nichos --tema "história"          # ranking de nichos com dados reais do YouTube
.\rodar.bat novo "mistérios da história"      # referências + padrões + 10 títulos sugeridos
.\rodar.bat roteiro misterios-da-historia --titulo 3
.\rodar.bat abertura misterios-da-historia    # 2 aberturas de retenção; depois: --usar 1 (ou 2)
.\rodar.bat narrar  misterios-da-historia
.\rodar.bat visuais misterios-da-historia
.\rodar.bat editar  misterios-da-historia
```

Ou tudo de uma vez: `.\rodar.bat tudo "mistérios da história" --titulo 1`

### Roteiro com o Prompt Mestre

O roteiro segue as regras de `prompts/roteiro_mestre.md` (edite esse arquivo para mudar as regras).
As opções do comando são os campos do BLOCO DE ENTRADA:

```
.\rodar.bat roteiro duquesa --referencia "La duchessa che fu ripudiata il giorno delle nozze" --idioma italiano --meta "canal novo, meta de 500 inscritos"
.\rodar.bat tudo --referencia "https://www.youtube.com/watch?v=..." --idioma espanhol --nicho "drama contemporâneo"
```

- `--referencia` título ou link (de link do YouTube só lemos título e descrição, não o áudio)
- `--idioma` português, italiano, espanhol, inglês, alemão, francês (a voz da narração muda junto)
- `--nicho`, `--capitulos` (padrão 4), `--caracteres` (padrão 11000 ≈ 15 min; use 22000 para 30 min), `--meta`, `--obs`
- Os padrões ficam no `.env` (`IDIOMA_ROTEIRO`, `CAPITULOS`, `CARACTERES`, `META_CANAL`)

O roteiro gera: `ficha.md` (planejamento), `roteiro.md` (texto por capítulo), `revisao.md`
(checklist final + correções automáticas de anacronismos, números e fatos).
Um roteiro de 22.000 caracteres (30 min) leva cerca de 20 a 30 minutos para ser escrito. Se parar no meio,
rode o mesmo comando de novo: ele continua do último capítulo pronto.

### Abertura de retenção (os primeiros 30 a 45 segundos)

A abertura segue o prompt de retenção em `prompts/abertura_retencao.md`: a primeira frase confirma o título e a
thumbnail, sem saudação nem pedido de inscrição, abre pelo menos dois mistérios e guarda a revelação para o fim.
Depois do roteiro e ANTES de narrar:

```
.\rodar.bat abertura <projeto>            # gera abertura.md com 2 versões (chocante e misteriosa)
.\rodar.bat abertura <projeto> --usar 2   # troca a abertura do roteiro pela versão escolhida
```

O `abertura.md` mostra cada frase com a sugestão visual, os mistérios abertos (e onde são respondidos) e a divisão
sugerida do vídeo. O pedido de inscrição fica logo depois da abertura.

Outras opções:
- `.\rodar.bat vozes` lista as vozes; use `--voz pt-BR-FranciscaNeural` no `narrar`

### Apresentador de IA (desligado)

Um rosto fictício gerado por IA falava numa janela redonda na abertura e nos pedidos de inscrição (SadTalker,
precisa de placa NVIDIA). **Está desligado** (`APRESENTADOR=nao` no `.env`) e a pasta `apresentador/` com o
SadTalker não vem no pacote. O código continua na ferramenta: sem o SadTalker, o vídeo sai normalmente, só sem o
rosto. Quem tiver a pasta pode ligar com `APRESENTADOR=sim` ou rodar `.\rodar.bat apresentador <projeto>`; nesse caso,
**ao publicar, marque no YouTube "Conteúdo alterado ou sintético: Sim"**.

### Thumbnails

**Padrão do canal (desde 2026-10-12): estilo "cinema".** Cena cinematográfica realista criada por IA ocupando a
thumbnail inteira + 2 linhas grandes de texto (Impact). Cena e textos saem do título e do roteiro de cada vídeo.

`.\rodar.bat thumb <projeto>` gera 3 opções (imagens pelo FLUX da NVIDIA, grátis com a chave NVIDIA), cada uma com
um texto diferente. **Confira as 3**: a IA às vezes desenha logo de marca real (apagar com `thumb_ia.borrar_logo`).
Se o FLUX estiver fora do ar, monte com uma foto real do Wikimedia.
- `--cena "a broken down car..."` (descrição em inglês; sem a opção, sai do título)
- `--pais "Germany"` (nome do país em inglês) põe bandeira; no estilo cinema, sem a opção, sai sem bandeira
- `--estilo destaque` = âncora de TV fictício + faixas de texto (abandonado: o âncora ficou ruim)
- `--estilo obra` = foto aérea realista + bandeira, sem texto
- `--estilo texto` = estilo antigo (foto de banco + texto grande)

### Canal de jogos (Fora da Missão)

Vídeos de missão, easter egg e react feitos com a SUA gameplay. Crie uma pasta por vídeo em `projetos\` e ponha a
gravação (mp4, mkv, mov) em `projetos\<nome>\gameplay\`.

```
.\rodar.bat jogo preparar <nome>     # quadros, folhas de contato, fala do jogo (Whisper) e roteiro_jogo.json modelo
                                     # (--sem-fala pula a transcrição; --intervalo 2 tira mais quadros)
```
Depois preencha o `roteiro_jogo.json` olhando as `folhas\` e o `mapa.md` (peça ao Claude Code: "escreva o roteiro do
projeto <nome>"). Cada trecho diz de qual vídeo, de onde (`de`) e até onde (`ate`) vem a imagem, o que o narrador
fala, o capítulo e um texto opcional na tela. Para vídeo só com música e texto, use `"tipo": "sem_narracao"`.

```
.\rodar.bat jogo gravar <nome>       # para_gravar.txt: cole no Clipchamp, salve o áudio como narracao_usuario.mp3
.\rodar.bat jogo montar <nome>       # video_final.mp4 (1920x1080), descricao_youtube.txt, titulos.txt
.\rodar.bat jogo curtos <nome>       # curtos\*.mp4 verticais (1080x1920) para Shorts, Reels e TikTok
.\rodar.bat jogo thumb <nome>        # thumbnail_1.jpg, _2... com um quadro do jogo + 2 linhas de texto
.\rodar.bat jogo mascote             # 4 opções do mascote do canal em canal_jogos\ (FLUX, chave NVIDIA)
```

- Cada trecho dura o tempo da fala dele: se a fala for mais longa que o `ate`, o jogo continua rodando; se for mais
  curta, o fim do trecho fica de fora (a ferramenta avisa).
- Som do jogo por baixo da narração: `"som_jogo": 0.3` (geral ou por trecho; 1.0 = volume cheio).
- Música: da pasta `musicas`. Ponha o crédito exigido pela licença num `.txt` com o mesmo nome da música
  (ex.: `trilha.mp3` + `trilha.txt`); ele vai sozinho para a descrição.
- Curtos: até 60 s. Para o Instagram/TikTok, confira se a licença da música vale lá; senão use `"musica": false`
  e escolha a música no próprio app.

## 3. Arquivos gerados (em `projetos/<nome>/`)

- `referencias.md` — vídeos que mais performaram acima da média do canal (outliers)
- `titulos.json` — padrões encontrados + títulos e textos de thumbnail
- `roteiro.md` / `roteiro.json` — roteiro por cenas. **Pode editar o JSON antes de narrar.**
- `audio/`, `visuais/`, `cenas/` — partes do vídeo
- `folha_cenas.jpg` — miniatura de todas as cenas com a busca usada: **olhe antes de editar**. Para trocar uma
  cena, apague o arquivo dela em `visuais/`, mude `busca_stock` no `roteiro.json` e rode `visuais` de novo
- `video_final.mp4` — vídeo pronto (1920x1080, legendas, música)
- `thumbnail_*.jpg` — thumbnails 1280x720 (comando `thumb`)
- `descricao_youtube.txt` — descrição, capítulos com tempo e tags

Dicas:
- Para refazer uma cena, apague o arquivo dela em `audio/` ou `visuais/` e rode a etapa de novo;
  só ela é refeita.
- Como ler a pesquisa: **outlier** = quantas vezes o vídeo superou a média do próprio canal.
  Nicho bom = muitas views + canais pequenos conseguindo outliers.
