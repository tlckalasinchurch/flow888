Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

[Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementWatcher, Windows.Devices.Bluetooth, ContentType = WindowsRuntime] | Out-Null

$watcher = New-Object Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementWatcher
$watcher.ScanningMode = [Windows.Devices.Bluetooth.Advertisement.BluetoothLEScanningMode]::Active

$devices = @{}

$handler = [Windows.Foundation.TypedEventHandler[Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementWatcher, Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementReceivedEventArgs]]{
    param($w, $args)
    $addr = $args.BluetoothAddress.ToString('X12')
    $name = $args.Advertisement.LocalName
    $rssi = $args.RawSignalStrengthInDBm
    $uuids = $args.Advertisement.ServiceUuids | ForEach-Object { $_.ToString() }
    $devices[$addr] = [PSCustomObject]@{
        Address = $addr
        Name = $name
        RSSI = $rssi
        Services = ($uuids -join ', ')
    }
}

$watcher.add_Received($handler)
$watcher.Start()
Write-Host "Scanning for BLE advertisements (6 seconds)..."
Start-Sleep -Seconds 6
$watcher.Stop()

Write-Host "Found $($devices.Count) BLE devices:"
$devices.Values | Format-Table -AutoSize
