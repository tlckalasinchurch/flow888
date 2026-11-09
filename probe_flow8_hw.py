import subprocess
import json

def run_ps(cmd):
    p = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    return p.stdout, p.stderr, p.returncode

print("=== 1. PNP DEVICES MATCHING FLOW / BEHRINGER ===")
script1 = """
Get-PnpDevice | Where-Object { $_.FriendlyName -match 'FLOW|Behringer' -or $_.Manufacturer -match 'Behringer' } | Select-Object Class, FriendlyName, InstanceId, Status, Present | ConvertTo-Json
"""
out, err, rc = run_ps(script1)
if out.strip():
    try:
        data = json.loads(out)
        if isinstance(data, dict): data = [data]
        for d in data:
            print(f"[{d.get('Class')}] {d.get('FriendlyName')}")
            print(f"  InstanceId: {d.get('InstanceId')}")
            print(f"  Status: {d.get('Status')} | Present: {d.get('Present')}")
    except Exception as e:
        print("Raw:", out)
else:
    print("None found.")

print("\n=== 2. USB CONTROLLER & CONNECTED USB DEVICES ===")
script2 = """
Get-PnpDevice -Class USB | Select-Object FriendlyName, InstanceId, Status, Present | ConvertTo-Json
"""
out, err, rc = run_ps(script2)
if out.strip():
    try:
        data = json.loads(out)
        if isinstance(data, dict): data = [data]
        for d in data:
            print(f"{d.get('FriendlyName')} | Present: {d.get('Present')} | InstanceId: {d.get('InstanceId')}")
    except Exception as e:
        print("Raw:", out)

print("\n=== 3. AUDIO DEVICES (WASAPI / MMDevice) ===")
script3 = """
Get-PnpDevice -Class AudioEndpoint | Where-Object { $_.FriendlyName -match 'FLOW|Behringer' } | Select-Object FriendlyName, InstanceId, Status, Present | ConvertTo-Json
"""
out, err, rc = run_ps(script3)
if out.strip():
    try:
        data = json.loads(out)
        if isinstance(data, dict): data = [data]
        for d in data:
            print(f"{d.get('FriendlyName')} | Present: {d.get('Present')} | Status: {d.get('Status')}")
    except Exception as e:
        print("Raw:", out)

print("\n=== 4. BEHRINGER DRIVER IN REGISTRY / DRIVER STORE ===")
script4 = """
Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'Behringer|FLOW' } | Select-Object DisplayName, DisplayVersion, Publisher, InstallLocation, UninstallString | ConvertTo-Json
"""
out, err, rc = run_ps(script4)
if out.strip():
    print(out)
else:
    print("None in HKLM Uninstall.")
