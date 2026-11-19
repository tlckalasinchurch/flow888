"""Tests for flow8/transport_router.py — single-writer USB/BLE/Hybrid policy."""

import threading
import time
import unittest
from unittest import mock

from flow8.command_boundary import (
    DispatchStatus,
    Flow8CommandBoundary,
    Flow8CommandError,
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
    """Mirrors BleTransport readiness: is_connected means link up AND the
    0x36 auth ACK was received. `accept=False` simulates a GATT write that
    returns failure; `raise_on_write` simulates a write exception."""

    def __init__(self, connected=True, authenticated=True, accept=True, raise_on_write=False):
        self._connected = connected
        self._authenticated = authenticated
        self._accept = accept
        self._raise = raise_on_write
        self.sent = []
        self._lock = threading.Lock()

    @property
    def is_connected(self):
        return self._connected and self._authenticated

    def send_fader(self, channel, raw_midi):
        if self._raise:
            raise RuntimeError("GATT write exploded")
        if not self._accept:
            return False
        with self._lock:
            self.sent.append((channel, raw_midi))
        return True

    def status_snapshot(self):
        return {
            "connected": self._connected,
            "authenticated": self._authenticated,
        }


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

    def test_ble_mode_offline_rejects_fail_closed(self):
        # BLE session absent entirely.
        router, midi = self._router(ble=None, usb_connected=True)
        router.set_mode("ble")
        with self.assertRaises(Flow8CommandRejectedError):
            router.dispatch("ch1.fader", FADER_SPEC, 64)
        # BLE link down.
        router, midi = self._router(ble=FakeBle(connected=False), usb_connected=True)
        router.set_mode("ble")
        with self.assertRaises(Flow8CommandRejectedError):
            router.dispatch("ch1.fader", FADER_SPEC, 64)
        # BLE link up but auth ACK never arrived -> still not ready.
        router, midi = self._router(
            ble=FakeBle(connected=True, authenticated=False), usb_connected=True
        )
        router.set_mode("ble")
        with self.assertRaises(Flow8CommandRejectedError):
            router.dispatch("ch1.fader", FADER_SPEC, 64)
        # In every case nothing was sent on any transport — USB is not a
        # fallback in ble mode.
        self.assertEqual(midi.sent, [])

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
        for ble in (FakeBle(accept=False), FakeBle(raise_on_write=True)):
            router, midi = self._router(ble=ble)
            router.set_mode("hybrid")
            with self.assertRaises(Flow8CommandError):
                router.dispatch("ch2.fader", FADER_SPEC, 80)
            self.assertEqual(midi.sent, [])  # no double-send
            self.assertEqual(ble.sent, [])

    def test_hybrid_ble_drop_between_selection_and_write_never_falls_back(self):
        class FlippingBle(FakeBle):
            """is_connected is True at selection, False on every later read."""

            def __init__(self):
                super().__init__()
                self._reads = 0

            @property
            def is_connected(self):
                self._reads += 1
                return self._reads == 1

        ble = FlippingBle()
        router, midi = self._router(ble=ble)
        router.set_mode("hybrid")
        with self.assertRaises(Flow8CommandError) as ctx:
            router.dispatch("ch2.fader", FADER_SPEC, 80)
        self.assertNotIsInstance(ctx.exception, Flow8CommandRejectedError)
        self.assertEqual(midi.sent, [])  # no USB fallback
        self.assertEqual(ble.sent, [])

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

    def _param_state(self, boundary, param_id):
        return boundary._state_store.get_parameter(param_id)

    def test_ble_offline_rejects_and_preserves_state(self):
        """BLE mode + no session -> REJECTED, no commanded value committed."""
        boundary, _ = self._boundary("ble", FakeBle(connected=False))
        with self.assertRaises(Flow8CommandRejectedError):
            boundary.execute_command("ch1.fader", 100)
        st = self._param_state(boundary, "ch1.fader")
        self.assertIsNone(st.commanded_raw_midi)
        self.assertIsNone(st.observed_raw_midi)
        self.assertNotEqual(st.sync_status.value, "SYNCED")
        last = boundary.command_log[-1]
        self.assertEqual(last.dispatch_status, DispatchStatus.REJECTED)
        self.assertFalse(last.command_accepted)
        self.assertIsNone(last.hardware_applied)

    def test_ble_unauthenticated_rejects(self):
        boundary, _ = self._boundary(
            "ble", FakeBle(connected=True, authenticated=False)
        )
        with self.assertRaises(Flow8CommandRejectedError):
            boundary.execute_command("ch1.fader", 100)
        self.assertIsNone(self._param_state(boundary, "ch1.fader").commanded_raw_midi)

    def test_hybrid_ble_drop_midflight_is_dispatch_failed_and_commits_nothing(self):
        class FlippingBle(FakeBle):
            def __init__(self):
                super().__init__()
                self._reads = 0

            @property
            def is_connected(self):
                self._reads += 1
                return self._reads == 1

        ble = FlippingBle()
        boundary, midi = self._boundary("hybrid", ble)
        with self.assertRaises(Flow8CommandError):
            boundary.execute_command("ch1.fader", 100)
        self.assertEqual(midi.sent, [])
        self.assertEqual(ble.sent, [])
        self.assertIsNone(self._param_state(boundary, "ch1.fader").commanded_raw_midi)
        last = boundary.command_log[-1]
        self.assertEqual(last.dispatch_status, DispatchStatus.DISPATCH_FAILED)

    def test_ble_write_returns_false_is_dispatch_failed(self):
        boundary, _ = self._boundary("ble", FakeBle(accept=False))
        with self.assertRaises(Flow8CommandError):
            boundary.execute_command("ch1.fader", 100)
        st = self._param_state(boundary, "ch1.fader")
        self.assertIsNone(st.commanded_raw_midi)  # failed dispatch commits nothing
        last = boundary.command_log[-1]
        self.assertEqual(last.dispatch_status, DispatchStatus.DISPATCH_FAILED)
        self.assertFalse(last.driver_dispatched)
        self.assertIsNone(last.hardware_applied)

    def test_ble_write_exception_is_dispatch_failed(self):
        boundary, _ = self._boundary("ble", FakeBle(raise_on_write=True))
        with self.assertRaises(Flow8CommandError):
            boundary.execute_command("ch1.fader", 100)
        last = boundary.command_log[-1]
        self.assertEqual(last.dispatch_status, DispatchStatus.DISPATCH_FAILED)
        self.assertIsNone(self._param_state(boundary, "ch1.fader").commanded_raw_midi)

    def test_successful_ble_dispatch_status_and_state(self):
        ble = FakeBle()
        boundary, _ = self._boundary("ble", ble)
        entry = boundary.execute_command("ch2.fader", 90)
        self.assertEqual(entry.dispatch_status, DispatchStatus.BLE_WRITE_ACCEPTED)
        self.assertEqual(entry.transport, "ble")
        self.assertIsNone(entry.hardware_applied)  # GATT accept != mixer applied
        st = self._param_state(boundary, "ch2.fader")
        self.assertEqual(st.commanded_raw_midi, 90)
        self.assertIsNone(st.observed_raw_midi)  # never fabricated

    def test_mode_switch_under_load_no_duplicate_or_corrupt(self):
        """Toggling modes while commands fly: every command has exactly one writer."""
        ble = FakeBle()
        midi = FakeMidiOut(connected=True)
        router = TransportRouter(midi, ble_provider=lambda: ble)
        boundary = Flow8CommandBoundary(
            midi_out=midi, state_store=Flow8StateStore(), transport_router=router
        )
        errors = []
        stop = threading.Event()

        def switcher():
            for mode in ("usb_midi", "ble", "hybrid"):
                if stop.is_set():
                    return
                router.set_mode(mode)
                time.sleep(0.001)

        def worker():
            try:
                for _ in range(200):
                    try:
                        boundary.execute_command("ch1.fader", 64)
                    except (Flow8CommandRejectedError, Flow8CommandError):
                        pass  # ble-mode offline rejections are expected mid-switch
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        threads.append(threading.Thread(target=switcher))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        stop.set()
        self.assertEqual(errors, [])
        # Every accepted command went to exactly one transport; totals match.
        total = len(ble.sent) + len(midi.sent)
        dispatched = sum(
            1 for e in boundary.command_log if e.driver_dispatched
        )
        self.assertEqual(total, dispatched)


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
