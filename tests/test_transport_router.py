"""Tests for flow8/transport_router.py — single-writer USB/BLE/Hybrid policy."""

import threading
import unittest
from unittest import mock

from flow8.command_boundary import (
    DispatchStatus,
    Flow8CommandBoundary,
    Flow8CommandRejectedError,
)
from flow8.service import Flow8Service
from flow8.state_model import Flow8StateStore
from flow8.transport_router import TRANSPORT_FEATURES, TransportRouter
from tests._no_hardware import NoHardwareMixin


FADER_SPEC = {"type": "fader", "min": 0, "max": 127, "channel": 1, "cc": 7}
PAN_SPEC = {"type": "pan", "min": 0, "max": 127, "channel": 1, "cc": 10}


class FakeMidiOut:
    def __init__(self, connected=True):
        self.is_connected = connected
        self.sent = []
        self._lock = threading.Lock()

    def send_cc(self, channel, cc, value):
        with self._lock:
            self.sent.append((channel, cc, value))


class FakeBle:
    def __init__(self, connected=True, accept=True):
        self._connected = connected
        self._accept = accept
        self.sent = []
        self._lock = threading.Lock()

    @property
    def is_connected(self):
        # Mirrors BleTransport: connected AND authenticated.
        return self._connected

    def send_fader(self, channel, raw_midi):
        if not self._accept:
            return False
        with self._lock:
            self.sent.append((channel, raw_midi))
        return True

    def status_snapshot(self):
        return {"connected": self._connected, "authenticated": self._connected}


class TransportRouterModeTests(unittest.TestCase):
    def _router(self, ble=None, usb_connected=True):
        midi = FakeMidiOut(connected=usb_connected)
        router = TransportRouter(midi, ble_provider=lambda: ble)
        return router, midi

    def test_usb_mode_never_touches_ble(self):
        ble = FakeBle()
        router, midi = self._router(ble=ble)
        router.set_mode("usb_midi")
        self.assertEqual(router.dispatch("ch1.fader", FADER_SPEC, 100), "usb_midi")
        self.assertEqual(midi.sent, [(1, 7, 100)])
        self.assertEqual(ble.sent, [])

    def test_ble_mode_routes_faders_and_rejects_others(self):
        ble = FakeBle()
        router, midi = self._router(ble=ble)
        router.set_mode("ble")
        self.assertEqual(router.dispatch("ch3.fader", FADER_SPEC, 90), "ble")
        self.assertEqual(ble.sent, [(3, 90)])
        self.assertEqual(midi.sent, [])
        with self.assertRaises(Flow8CommandRejectedError):
            router.dispatch("ch3.pan", PAN_SPEC, 64)
        with self.assertRaises(Flow8CommandRejectedError):
            router.dispatch("ch7.fader", FADER_SPEC, 64)  # strip 7: no BLE evidence
        with self.assertRaises(Flow8CommandRejectedError):
            router.dispatch("main.fader", FADER_SPEC, 64)
        self.assertEqual(midi.sent, [])
        self.assertEqual(len(ble.sent), 1)

    def test_ble_mode_offline_accepts_without_sending(self):
        router, midi = self._router(ble=FakeBle(connected=False), usb_connected=False)
        router.set_mode("ble")
        self.assertIsNone(router.dispatch("ch1.fader", FADER_SPEC, 64))

    def test_hybrid_prefers_ble_for_faders_but_never_duplicates(self):
        ble = FakeBle()
        router, midi = self._router(ble=ble)
        router.set_mode("hybrid")
        self.assertEqual(router.dispatch("ch2.fader", FADER_SPEC, 80), "ble")
        self.assertEqual(router.dispatch("ch2.pan", PAN_SPEC, 64), "usb_midi")
        main_spec = {"type": "fader", "min": 0, "max": 127, "channel": 8, "cc": 7}
        self.assertEqual(router.dispatch("main.fader", main_spec, 64), "usb_midi")
        self.assertEqual(ble.sent, [(2, 80)])
        self.assertEqual(midi.sent, [(1, 10, 64), (8, 7, 64)])

    def test_hybrid_falls_back_to_usb_when_ble_down(self):
        ble = FakeBle(connected=False)
        router, midi = self._router(ble=ble)
        router.set_mode("hybrid")
        self.assertEqual(router.dispatch("ch2.fader", FADER_SPEC, 80), "usb_midi")
        self.assertEqual(ble.sent, [])
        self.assertEqual(midi.sent, [(1, 7, 80)])

    def test_hybrid_ble_write_failure_never_retries_usb(self):
        ble = FakeBle(accept=False)
        ble.send_fader = lambda ch, raw: False
        router, midi = self._router(ble=ble)
        router.set_mode("hybrid")
        from flow8.command_boundary import Flow8CommandError
        with self.assertRaises(Flow8CommandError):
            router.dispatch("ch2.fader", FADER_SPEC, 80)
        self.assertEqual(midi.sent, [])  # no double-send

    def test_concurrent_dispatches_are_serialized_per_transport(self):
        ble = FakeBle()
        midi = FakeMidiOut()
        router = TransportRouter(midi, ble_provider=lambda: ble)
        router.set_mode("hybrid")
        errors = []

        def worker(n):
            try:
                for i in range(50):
                    router.dispatch("ch1.fader", FADER_SPEC, i % 128)
                    router.dispatch("ch1.pan", PAN_SPEC, i % 128)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(ble.sent), 8 * 50)
        self.assertEqual(len(midi.sent), 8 * 50)

    def test_features_describe_ble_as_faders_only(self):
        self.assertIn("0x06", TRANSPORT_FEATURES["ble"]["commands"])
        self.assertIn("rejected", TRANSPORT_FEATURES["ble"]["commands"])
        router, _ = self._router()
        self.assertEqual(router.supported_features("ble")["control"],
                         TRANSPORT_FEATURES["ble"]["control"])


class BoundaryRouterIntegrationTests(NoHardwareMixin, unittest.TestCase):
    """execute_command must route through the router exactly once."""

    def _boundary(self, mode, ble):
        midi = FakeMidiOut(connected=False)  # USB physically absent
        router = TransportRouter(midi, ble_provider=lambda: ble)
        router.set_mode(mode)
        boundary = Flow8CommandBoundary(
            midi_out=midi, state_store=Flow8StateStore(), transport_router=router
        )
        return boundary, midi

    def test_ble_mode_fader_dispatch_logged_as_ble(self):
        ble = FakeBle()
        boundary, midi = self._boundary("ble", ble)
        entry = boundary.execute_command("ch1.fader", 100)
        self.assertEqual(entry.dispatch_status, DispatchStatus.BLE_WRITE_ACCEPTED)
        self.assertEqual(entry.transport, "ble")
        self.assertTrue(entry.driver_dispatched)
        self.assertIsNone(entry.hardware_applied)
        self.assertEqual(ble.sent, [(1, 100)])
        self.assertEqual(midi.sent, [])

    def test_ble_mode_unsupported_param_rejected_before_state_commit(self):
        ble = FakeBle()
        boundary, _ = self._boundary("ble", ble)
        with self.assertRaises(Flow8CommandRejectedError):
            boundary.execute_command("ch1.pan", 64)
        st = boundary._state_store.get_parameter("ch1.pan")
        self.assertNotEqual(getattr(st, "commanded_raw_midi", None), 64)

    def test_hybrid_command_never_sent_twice(self):
        ble = FakeBle()
        boundary, midi = self._boundary("hybrid", ble)
        # USB offline + BLE up: fader must go BLE only.
        entry = boundary.execute_command("ch4.fader", 55)
        self.assertEqual(entry.transport, "ble")
        self.assertEqual(len(ble.sent) + len(midi.sent), 1)


class ServiceTransportStatusTests(NoHardwareMixin, unittest.TestCase):
    def test_transport_status_and_control_connected(self):
        svc = Flow8Service(auto_connect=False)
        self.assertEqual(svc.transport_mode, "usb_midi")
        snap = svc.transport_status()
        self.assertEqual(snap["mode"], "usb_midi")
        self.assertFalse(snap["controlConnected"])
        self.assertIn("usb_midi", snap["featuresByTransport"])
        self.assertIn("ble", snap["featuresByTransport"])
        self.assertIn("counts", svc.state_sync_snapshot())

    def test_ble_mode_fader_routes_via_router_single_write(self):
        svc = Flow8Service(auto_connect=False)
        ble = FakeBle()
        svc._ble_transport = ble
        svc._transport_mode = "ble"
        svc._transport_router.set_mode("ble")
        svc.set_fader(2, 77)
        self.assertEqual(ble.sent, [(2, 77)])
        # Non-BLE parameter in ble mode is rejected, not silently sent over USB.
        with self.assertRaises(Flow8CommandRejectedError):
            svc.set_pan(2, 64)

    def test_usb_mode_ignores_ble_even_when_connected(self):
        svc = Flow8Service(auto_connect=False)
        ble = FakeBle()
        svc._ble_transport = ble
        svc.set_fader(2, 66)  # usb_midi mode, USB offline -> offline accept
        self.assertEqual(ble.sent, [])


if __name__ == "__main__":
    unittest.main()
