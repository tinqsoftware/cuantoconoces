param(
    [Parameter(Mandatory = $true)][string]$RuntimeDirectory,
    [Parameter(Mandatory = $true)][string]$LauncherPath,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = "Stop"
$bundle = Join-Path ([System.IO.Path]::GetTempPath()) ("QuizStudioBundle-" + [guid]::NewGuid().ToString("N"))
$payload = Join-Path ([System.IO.Path]::GetTempPath()) ("QuizStudioPayload-" + [guid]::NewGuid().ToString("N") + ".zip")
$temporaryOutput = "$OutputPath.tmp"

try {
    New-Item -ItemType Directory -Path (Join-Path $bundle "runtime") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $bundle "data") -Force | Out-Null
    Copy-Item -Path (Join-Path $RuntimeDirectory "*") -Destination (Join-Path $bundle "runtime") -Recurse -Force
    # Un marcador permite documentar el directorio aun antes del primer guardado.
    New-Item -ItemType File -Path (Join-Path $bundle "data\.keep") -Force | Out-Null
    Compress-Archive -Path (Join-Path $bundle "*") -DestinationPath $payload -CompressionLevel Optimal -Force

    $magic = New-Object byte[] 32
    $magicText = [System.Text.Encoding]::ASCII.GetBytes("QUIZSTUDIO_PORTABLE_V1")
    [Array]::Copy($magicText, $magic, $magicText.Length)
    $length = [BitConverter]::GetBytes([Int64](Get-Item $payload).Length)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $payloadSource = [System.IO.File]::OpenRead($payload)
    try { $hash = $sha.ComputeHash($payloadSource) } finally { $payloadSource.Dispose(); $sha.Dispose() }

    $targetDirectory = Split-Path -Parent $OutputPath
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    $out = [System.IO.File]::Open($temporaryOutput, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    try {
        $launcher = [System.IO.File]::OpenRead($LauncherPath)
        try { $launcher.CopyTo($out) } finally { $launcher.Dispose() }
        $content = [System.IO.File]::OpenRead($payload)
        try { $content.CopyTo($out) } finally { $content.Dispose() }
        $out.Write($magic, 0, $magic.Length)
        $out.Write($length, 0, $length.Length)
        $out.Write($hash, 0, $hash.Length)
        $out.Flush($true)
    } finally { $out.Dispose() }
    Move-Item -Path $temporaryOutput -Destination $OutputPath -Force
    Write-Host "Portable creado: $OutputPath"
}
finally {
    Remove-Item -Path $bundle -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $payload -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $temporaryOutput -Force -ErrorAction SilentlyContinue
}
