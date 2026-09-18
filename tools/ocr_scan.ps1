# Windows.Media.Ocr (설치된 한국어 인식기)로 PNG 목록의 글자 영역 탐지
# 사용: powershell -File ocr_scan.ps1 <list.txt> <out.tsv>
param([string]$ListFile, [string]$OutFile)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$out = New-Object System.IO.StreamWriter($OutFile, $false, [System.Text.Encoding]::UTF8)
foreach ($p in [System.IO.File]::ReadAllLines($ListFile)) {
    if (-not $p) { continue }
    try {
        $f = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p)) ([Windows.Storage.StorageFile])
        $s = Await ($f.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($s)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $r = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
        $words = @()
        foreach ($l in $r.Lines) { foreach ($w in $l.Words) { $b = $w.BoundingRect; $words += ('{0}@{1},{2},{3},{4}' -f $w.Text, [int]$b.X, [int]$b.Y, [int]$b.Width, [int]$b.Height) } }
        $out.WriteLine($p + "`t" + $words.Count + "`t" + ($words -join ' | '))
        $s.Dispose()
    } catch { $out.WriteLine($p + "`tERR`t" + $_.Exception.Message) }
}
$out.Close()
