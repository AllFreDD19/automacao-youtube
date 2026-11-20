# Organiza o notebook: mostra o que ocupa espaço e MOVE para o HD externo só o que você escolher.
# Nada é apagado. Tudo o que for movido fica anotado em <HD>:\Arquivo-Notebook\movidos.csv (para desfazer).
#
# Rodar (PowerShell, na pasta do projeto):
#   powershell -ExecutionPolicy Bypass -File ferramentas\organizar_hd.ps1            (analisar e mover)
#   powershell -ExecutionPolicy Bypass -File ferramentas\organizar_hd.ps1 -Desfazer  (traz tudo de volta)
param([switch]$Desfazer, [int]$MinimoMB = 100)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Tamanho($caminho) {
    $item = Get-Item -LiteralPath $caminho -Force
    if ($item.PSIsContainer) {
        $soma = (Get-ChildItem -LiteralPath $caminho -Recurse -Force -File -ErrorAction SilentlyContinue |
                 Measure-Object -Property Length -Sum).Sum
        if ($null -eq $soma) { return 0 } else { return [int64]$soma }
    }
    return [int64]$item.Length
}
function MB($bytes) { "{0:N0} MB" -f ($bytes / 1MB) }
function Mover($origem, $destino) {
    # Move-Item não leva pastas de um disco para outro no Windows PowerShell: pastas vão pelo robocopy
    if ((Get-Item -LiteralPath $origem -Force).PSIsContainer) {
        robocopy $origem $destino /E /MOVE /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
        if ((Test-Path -LiteralPath $origem) -and -not (Get-ChildItem -LiteralPath $origem -Recurse -Force -File)) {
            Remove-Item -LiteralPath $origem -Recurse -Force  # sobrou só a pasta vazia
        }
        if ($LASTEXITCODE -ge 8 -or (Test-Path -LiteralPath $origem)) {
            throw "robocopy não terminou (código $LASTEXITCODE); confira $origem e $destino"
        }
    } else {
        Move-Item -LiteralPath $origem -Destination $destino
    }
}

# ---------- 1. escolher o HD externo ----------
$discos = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -ne "C:" -and $_.Size -gt 0 }
if (-not $discos) { Write-Host "Nenhum HD externo encontrado. Conecte o HD e rode de novo."; exit 1 }
Write-Host "`nDiscos encontrados (além do C:):"
foreach ($d in $discos) {
    Write-Host ("  {0}  {1}  livre: {2:N0} GB de {3:N0} GB" -f $d.DeviceID, $d.VolumeName, ($d.FreeSpace / 1GB), ($d.Size / 1GB))
}
$letra = (Read-Host "`nLetra do HD externo (ex.: E)").Trim().TrimEnd(":").ToUpper()
$hd = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -eq "$($letra):" }
if (-not $hd -or $letra -eq "C") { Write-Host "Letra inválida."; exit 1 }
$base = "$($letra):\Arquivo-Notebook"
$registro = Join-Path $base "movidos.csv"
New-Item -ItemType Directory -Force -Path $base | Out-Null

# ---------- desfazer ----------
if ($Desfazer) {
    if (-not (Test-Path $registro)) { Write-Host "Nada para desfazer ($registro não existe)."; exit 0 }
    $linhas = Import-Csv $registro
    foreach ($l in $linhas) {
        if (Test-Path -LiteralPath $l.Destino) {
            Write-Host "Voltando: $($l.Origem)"
            New-Item -ItemType Directory -Force -Path (Split-Path $l.Origem -Parent) | Out-Null
            Mover $l.Destino $l.Origem
        }
    }
    Rename-Item $registro ("movidos_desfeito_{0:yyyyMMdd_HHmm}.csv" -f (Get-Date))
    Write-Host "Pronto: tudo voltou para o lugar."
    exit 0
}

# ---------- 2. analisar ----------
$perfil = $env:USERPROFILE
$projeto = Split-Path $PSScriptRoot -Parent
# Nunca mexer: sistema, programas, configurações dos apps (AppData), OneDrive (mover apagaria da nuvem),
# o código da ferramenta, o ambiente Python (.venv) e as chaves (.env)
$proibidos = @("$perfil\AppData", "$perfil\OneDrive", "$projeto\automacao", "$projeto\.venv", "$projeto\.git",
               "$projeto\fontes", "$projeto\vozes_piper", "$projeto\musicas", "$projeto\.env")
function Proibido($c) { foreach ($p in $proibidos) { if ($c -like "$p*") { return $true } }; return $false }

Write-Host "`nAnalisando (pode levar alguns minutos)..."
$candidatos = @()
$pastas = @("Downloads", "Desktop", "Documents", "Videos", "Pictures", "Music") | ForEach-Object { Join-Path $perfil $_ }
foreach ($p in $pastas) {
    if (-not (Test-Path $p)) { continue }
    Get-ChildItem -LiteralPath $p -Force -ErrorAction SilentlyContinue | ForEach-Object {
        if (Proibido $_.FullName) { return }
        if ($projeto -like "$($_.FullName)*") { return }  # a pasta que contém o projeto: só os itens de dentro
        $candidatos += [pscustomobject]@{ Caminho = $_.FullName; Bytes = (Tamanho $_.FullName); Usado = $_.LastWriteTime }
    }
}
# Dentro do projeto: só vídeos prontos/antigos (projetos\*) e pacotes .zip
if (Test-Path "$projeto\projetos") {
    Get-ChildItem -LiteralPath "$projeto\projetos" -Directory -Force | ForEach-Object {
        $candidatos += [pscustomobject]@{ Caminho = $_.FullName; Bytes = (Tamanho $_.FullName); Usado = $_.LastWriteTime }
    }
}
Get-ChildItem -LiteralPath (Split-Path $projeto -Parent) -Filter *.zip -Force -ErrorAction SilentlyContinue | ForEach-Object {
    $candidatos += [pscustomobject]@{ Caminho = $_.FullName; Bytes = $_.Length; Usado = $_.LastWriteTime }
}
$lista = @($candidatos | Where-Object { $_.Bytes -ge ($MinimoMB * 1MB) } | Sort-Object Bytes -Descending)
if (-not $lista) { Write-Host "Nada acima de $MinimoMB MB. (Use -MinimoMB 20 para ver itens menores.)"; exit 0 }

$livreC = (Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -eq "C:" }).FreeSpace
Write-Host ("`nC: tem {0:N1} GB livres. Itens acima de {1} MB (maiores primeiro):`n" -f ($livreC / 1GB), $MinimoMB)
for ($i = 0; $i -lt $lista.Count; $i++) {
    $x = $lista[$i]
    Write-Host ("{0,3}. {1,10}  usado em {2:dd/MM/yyyy}  {3}" -f ($i + 1), (MB $x.Bytes), $x.Usado, $x.Caminho)
}

# ---------- 3. escolher e mover ----------
Write-Host "`nDigite os números do que vai para o HD (ex.: 1,3,5-8) ou ENTER para sair sem mover nada."
$resp = Read-Host "Mover"
if (-not $resp.Trim()) { Write-Host "Nada movido."; exit 0 }
$escolha = @()
foreach ($parte in $resp.Split(",")) {
    $parte = $parte.Trim()
    if ($parte -match "^(\d+)-(\d+)$") { $escolha += [int]$Matches[1]..[int]$Matches[2] }
    elseif ($parte -match "^\d+$") { $escolha += [int]$parte }
}
$escolhidos = @($escolha | Sort-Object -Unique | Where-Object { $_ -ge 1 -and $_ -le $lista.Count } | ForEach-Object { $lista[$_ - 1] })
$total = ($escolhidos | Measure-Object Bytes -Sum).Sum
if ($total -gt $hd.FreeSpace) { Write-Host "O HD não tem espaço para $(MB $total)."; exit 1 }
Write-Host "`nVai mover $($escolhidos.Count) item(ns), $(MB $total), para $base"
foreach ($x in $escolhidos) { Write-Host "  $($x.Caminho)" }
if ((Read-Host "Confirmar? (s/n)").Trim().ToLower() -ne "s") { Write-Host "Cancelado."; exit 0 }

foreach ($x in $escolhidos) {
    # Mantém o caminho original dentro do HD (ex.: E:\Arquivo-Notebook\Downloads\arquivo.zip)
    $relativo = $x.Caminho.Substring(3)  # tira "C:\"
    $destino = Join-Path $base $relativo
    New-Item -ItemType Directory -Force -Path (Split-Path $destino -Parent) | Out-Null
    try {
        Write-Host "Movendo $($x.Caminho) ..."
        Mover $x.Caminho $destino
        [pscustomobject]@{ Origem = $x.Caminho; Destino = $destino; Bytes = $x.Bytes; Data = (Get-Date -Format s) } |
            Export-Csv -Append -NoTypeInformation -Encoding UTF8 $registro
    } catch {
        Write-Host "  não deu (arquivo em uso ou sem permissão): $($_.Exception.Message)"
    }
}
$livreC2 = (Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -eq "C:" }).FreeSpace
Write-Host ("`nPronto. C: agora tem {0:N1} GB livres. Registro: {1}" -f ($livreC2 / 1GB), $registro)
Write-Host "Para trazer tudo de volta: powershell -ExecutionPolicy Bypass -File ferramentas\organizar_hd.ps1 -Desfazer"
