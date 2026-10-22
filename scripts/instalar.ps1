[CmdletBinding()]
param(
    [string]$Destino = 'C:\Users\lucas\laya-games',
    [string]$Python = '3.14'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Executar {
    param([string]$Programa, [string[]]$Argumentos)
    & $Programa @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "Falha ao executar $Programa (código $LASTEXITCODE)." }
}

try {
    Write-Host 'Preparando Laya Games v0.1...' -ForegroundColor Cyan
    $Origem = Split-Path -Parent $PSScriptRoot
    New-Item -ItemType Directory -Force -Path $Destino | Out-Null
    $Destino = (Resolve-Path $Destino).Path
    if ([System.IO.Path]::GetFullPath($Origem).TrimEnd('\') -ne $Destino.TrimEnd('\')) {
        if (-not (Test-Path (Join-Path $Destino 'pyproject.toml'))) {
            if (Test-Path (Join-Path $Origem '.git')) {
                Executar 'git' @('clone', '--local', $Origem, $Destino)
                Write-Host 'Clone local criado. Para incluir alterações ainda não commitadas, rode no próprio checkout com -Destino.'
            } else { throw 'Execute este script em um clone do repositório, ou use -Destino apontando para o checkout atual.' }
        }
    }
    if (-not (Test-Path (Join-Path $Destino 'pyproject.toml'))) {
        throw 'pyproject.toml não encontrado no destino.'
    }
    $Venv = Join-Path $Destino '.venv'
    if (-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) {
        Write-Host "Criando ambiente Python $Python em $Venv"
        Executar 'py' @("-$Python", '-m', 'venv', $Venv)
    }
    $Exe = Join-Path $Venv 'Scripts\python.exe'
    Executar $Exe @('-c', 'import sys; esperado = tuple(map(int, sys.argv[1].split("."))); assert sys.version_info[:2] == esperado, "O venv existente usa outra versão do Python. Crie outro destino ou recrie o venv."', $Python)
    Executar $Exe @('-m', 'pip', 'install', '--upgrade', 'pip')
    Write-Host 'Instalando PyTorch com CUDA 12.6...'
    Executar $Exe @('-m', 'pip', 'install', 'torch==2.14.1', '--index-url', 'https://download.pytorch.org/whl/cu126')
    Write-Host 'Instalando dependências fixadas...'
    Executar $Exe @('-m', 'pip', 'install', '-e', $Destino)
    Executar $Exe @('-m', 'pip', 'check')
    $env:LAYA_HOME = $Destino
    New-Item -ItemType Directory -Force -Path (Join-Path $Destino 'modelos\laya_v000') | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $Destino 'runs') | Out-Null
    Write-Host 'Baixando convaiinnovations/laya (modelo base, sem treino)...'
    # Destino via ambiente: nenhum caminho do usuário é interpolado como código Python.
    $Download = @'
import os
from pathlib import Path
from huggingface_hub import snapshot_download
snapshot_download(repo_id="convaiinnovations/laya", local_dir=str(Path(os.environ["LAYA_HOME"]) / "modelos" / "laya_v000"), ignore_patterns=["multilingual/*", "typed-decisions/*", "*.onnx"])
'@
    Executar $Exe @('-c', $Download)
    Write-Host 'Verificando CUDA e GPU...'
    $Verificar = @'
import torch
print("PyTorch:", torch.__version__)
print("CUDA disponível:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("VRAM (MB):", round(torch.cuda.get_device_properties(0).total_memory / 2**20))
else:
    print("CUDA indisponível. O jogo utilizará CPU; confira driver NVIDIA e a instalação CUDA do torch.")
'@
    Executar $Exe @('-c', $Verificar)
    [Environment]::SetEnvironmentVariable('LAYA_HOME', $Destino, 'User')
    Write-Host "Instalação concluída em $Destino" -ForegroundColor Green
    Write-Host "LAYA_HOME=$Destino (salvo para novas janelas do PowerShell)."
    Write-Host "Para iniciar: & '$Exe' -m jogos.snake --partidas 1 --nivel 15 --versao v000 --modo normal"
} catch {
    Write-Error "Instalação interrompida: $($_.Exception.Message)"
    exit 1
}
