
$msiPath = "C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installer.msi"
$windowsInstaller = New-Object -ComObject WindowsInstaller.Installer
$database = $windowsInstaller.OpenDatabase($msiPath, 0)

$dirParent = @{}
$dirName = @{}
$view = $database.OpenView("SELECT Directory, Directory_Parent, DefaultDir FROM Directory")
$view.Execute()
while ($rec = $view.Fetch()) {
    $d = $rec.StringData(1)
    $p = $rec.StringData(2)
    $raw = $rec.StringData(3)
    $name = if ($raw -match "\|") { ($raw -split "\|")[1] } else { $raw }
    $dirParent[$d] = $p
    $dirName[$d] = $name
}
$view.Close()

function Get-FullPath($d) {
    if (-not $d -or $d -eq "TARGETDIR" -or $d -eq "LocalAppDataFolder") { return "" }
    $p = $dirParent[$d]
    $cur = $dirName[$d]
    if ($cur -eq ".") { $cur = "" }
    $parentPath = Get-FullPath $p
    if ($parentPath -and $cur) { return "$parentPath\$cur" }
    elseif ($cur) { return $cur }
    else { return $parentPath }
}

$compDir = @{}
$view = $database.OpenView("SELECT Component, Directory_ FROM Component")
$view.Execute()
while ($rec = $view.Fetch()) {
    $compDir[$rec.StringData(1)] = $rec.StringData(2)
}
$view.Close()

$view = $database.OpenView("SELECT File, Component_, FileName, FileSize FROM File")
$view.Execute()
$cabDir = "C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\cab_extracted"
$outDir = "C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed"

while ($rec = $view.Fetch()) {
    $fId = $rec.StringData(1)
    $comp = $rec.StringData(2)
    $rawName = $rec.StringData(3)
    $name = if ($rawName -match "\|") { ($rawName -split "\|")[1] } else { $rawName }
    $dId = $compDir[$comp]
    $dirPath = Get-FullPath $dId
    $destDir = Join-Path $outDir $dirPath
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
    $srcFile = Join-Path $cabDir $fId
    $destFile = Join-Path $destDir $name
    if (Test-Path $srcFile) {
        Copy-Item -Path $srcFile -Destination $destFile -Force
    } else {
        Write-Warning "Missing $srcFile"
    }
}
$view.Close()
Write-Host "Reconstruction complete."
