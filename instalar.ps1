# Instalação completa da ferramenta num computador novo (Windows 10/11).
# Passos: Python 3.12 -> ambiente .venv -> pacotes -> PyTorch para processador (CLIP) -> FFmpeg -> .env
# O PyTorch instalado é a versão para processador (funciona em qualquer PC). Com placa NVIDIA, o CLIP fica mais
# rápido trocando pela versão CUDA (comando no LEIA-ME.md, seção 1).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Tem($comando) { [bool](Get-Command $comando -ErrorAction SilentlyContinue) }

"== Python 3.12"
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) {
    if (-not (Tem winget)) { throw "Instale o Python 3.12 em https://www.python.org/downloads/ e rode de novo." }
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
}
if (-not (Test-Path $py)) { throw "Python 3.12 não encontrado em $py. Instale-o e rode de novo." }

"== Ambiente da ferramenta (.venv)"
if (-not (Test-Path .venv)) { & $py -m venv .venv }
$vpy = ".\.venv\Scripts\python.exe"
& $vpy -m pip install -q --upgrade pip
& $vpy -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu
& $vpy -m pip install -q -r requirements.txt

"== FFmpeg (edição de vídeo)"
if (-not (Tem ffmpeg) -and -not (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*" -ErrorAction SilentlyContinue)) {
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
}

"== Vozes Piper (espanhol, alemão, francês)"
New-Item -ItemType Directory -Force vozes_piper | Out-Null
foreach ($m in "es/es_ES/davefx/medium/es_ES-davefx-medium", "de/de_DE/thorsten_emotional/medium/de_DE-thorsten_emotional-medium",
               "fr/fr_FR/tom/medium/fr_FR-tom-medium") {
    $nome = Split-Path $m -Leaf
    foreach ($ext in ".onnx", ".onnx.json") {
        if (-not (Test-Path "vozes_piper\$nome$ext")) {
            Invoke-WebRequest "https://huggingface.co/rhasspy/piper-voices/resolve/main/$m$ext" -OutFile "vozes_piper\$nome$ext"
        }
    }
}

"== Pastas e arquivo de chaves"
foreach ($pasta in "projetos", "musicas", "biblioteca\paisagens") { New-Item -ItemType Directory -Force $pasta | Out-Null }
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    "  .env criado: abra no Bloco de Notas e cole as SUAS chaves (veja o LEIA-ME.md)"
}

"== Teste rápido"
& $vpy -c "import main; print('ferramenta OK')"
""
"Pronto! Próximos passos:"
"  1. Preencha o .env com as suas chaves (LEIA-ME.md, seção 1)"
"  2. Teste as chaves:  .venv\Scripts\python.exe testar_chaves.py"
"  3. (Só para vídeos de história com fundo de paisagens) baixe os clipes:"
"     .venv\Scripts\python.exe -m automacao.paisagens restaurar"
