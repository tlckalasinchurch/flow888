$msiPath = "C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installer.msi"
$windowsInstaller = New-Object -ComObject WindowsInstaller.Installer
$database = $windowsInstaller.OpenDatabase($msiPath, 0)

# Build Directory map
$dirParent = @{}
$dirName = @{}
$view = $database.OpenView("SELECT Directory, Directory_Parent, DefaultDir FROM Directory")
$view.Execute()
while ($rec = $view.Fetch()) {
    $d = $rec.StringData(1)
    $p = $rec.StringData(2)
    $raw = $rec.StringData(3)
    # DefaultDir can be short|long or just name
    $name = $raw
    if ($raw -match "\|") {
        $name = ($raw -split "\|")[1]
    }
    $dirParent[$d] = $p
    $dirName[$d] = $name
}
$view.Close()

function Get-FullPath($d) {
    if (-not $d -or $d -eq "TARGETDIR" -or $d -eq "LocalAppDataFolder") {
        return ""
    }
    $p = $dirParent[$d]
    $cur = $dirName[$d]
    if ($cur -eq ".") { $cur = "" }
    $parentPath = Get-FullPath $p
    if ($parentPath -and $cur) {
        return "$parentPath\$cur"
    } elseif ($cur) {
        return $cur
    } else {
        return $parentPath
    }
}

# Build Component map
$compDir = @{}
$view = $database.OpenView("SELECT Component, Directory_ FROM Component")
$view.Execute()
while ($rec = $view.Fetch()) {
    $c = $rec.StringData(1)
    $d = $rec.StringData(2)
    $compDir[$c] = $d
}
$view.Close()

# Query Files
$results = @()
$view = $database.OpenView("SELECT File, Component_, FileName, FileSize, Version FROM File ORDER BY Sequence")
$view.Execute()
while ($rec = $view.Fetch()) {
    $fId = $rec.StringData(1)
    $comp = $rec.StringData(2)
    $rawName = $rec.StringData(3)
    $fSize = $rec.StringData(4)
    $fVer = $rec.StringData(5)

    $fileName = $rawName
    if ($rawName -match "\|") {
        $fileName = ($rawName -split "\|")[1]
    }

    $dId = $compDir[$comp]
    $dirPath = Get-FullPath $dId

    $fullRelPath = if ($dirPath) { "$dirPath\$fileName" } else { $fileName }

    $results += [PSCustomObject]@{
        FileId = $fId
        Component = $comp
        FileName = $fileName
        RelPath = $fullRelPath
        Size = [int64]$fSize
        Version = $fVer
    }
}
$view.Close()

$results | Format-Table -AutoSize FileId, Size, RelPath, Version | Out-File -FilePath "C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\file_mapping.txt" -Encoding utf8

# Print summary to console
Write-Host "Total files in File table: $($results.Count)"
Write-Host "`nTop 20 largest files:"
$results | Sort-Object -Property Size -Descending | Select-Object -First 20 | Format-Table -AutoSize FileId, Size, RelPath

Write-Host "`nFiles in app directory:"
$results | Where-Object { $_.RelPath -match "^mixing-station-pc\\app\\" -or $_.RelPath -match "mixing-station-pc\\.+" } | Format-Table -AutoSize FileId, Size, RelPath
