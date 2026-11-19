"""BLE probe: normalisation and CLI paths, no radio."""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest import mock

from tools import ble_probe


class NormaliseTests(unittest.TestCase):
    def test_list_form(self):
        class Device:
            name = "FLOW 8 LE"
            address = "AA:BB"

        out = ble_probe._normalise([Device()])
        self.assertEqual(out[0]["name"], "FLOW 8 LE")
        self.assertEqual(out[0]["address"], "AA:BB")

    def test_dict_form_with_advertisement(self):
        class Device:
            name = None
            address = "CC:DD"

        class Adv:
            local_name = "FLOW 8 LE"
            rssi = -60
            service_uuids = ["14839ad4-8d7e-415c-9a42-167340cf2339"]

        out = ble_probe._normalise({"CC:DD": (Device(), Adv())})
        self.assertEqual(out[0]["name"], "FLOW 8 LE")
        self.assertEqual(out[0]["rssi"], -60)
        self.assertEqual(len(out[0]["serviceUuids"]), 1)


class CliTests(unittest.TestCase):
    def _run(self, argv):
        import io
        from contextlib import redirect_stdout

        out = io.StringIO()
        with redirect_stdout(out):
            code = ble_probe.main(argv)
        return code, out.getvalue()

    def test_missing_bleak_is_explained(self):
        with mock.patch.object(ble_probe, "BleakScanner", None):
            code, out = self._run(["--scan-seconds", "0"])
        self.assertEqual(code, 4)
        self.assertIn("pip install bleak", out)

    def test_no_device_exits_two(self):
        async def fake_scan(seconds, name):
            return []

        with mock.patch.object(ble_probe, "scan", fake_scan):
            code, out = self._run(["--scan-seconds", "0", "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)["devices"], [])

    def test_device_found_exits_zero(self):
        async def fake_scan(seconds, name):
            return [{"name": "FLOW 8 LE", "address": "AA:BB", "rssi": -50, "serviceUuids": []}]

        with mock.patch.object(ble_probe, "scan", fake_scan):
            code, out = self._run(["--scan-seconds", "0", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["devices"][0]["name"], "FLOW 8 LE")


if __name__ == "__main__":
    unittest.main()
