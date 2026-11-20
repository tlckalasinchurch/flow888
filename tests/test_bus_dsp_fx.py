"""Bus limiter / 9-band GEQ and FX engine controls (owner approval 2026-11-20).

No physical port is opened: the service's MIDI out is made "open" with a MagicMock driver.
"""
import json
import unittest
import urllib.error
import urllib.request
from unittest import mock

from flow8.command_boundary import Flow8CommandRejectedError
from flow8.lan_hub import Flow8LanHub
from flow8.service import Flow8Service

from tests._no_hardware import NoHardwareMixin
from tests._safety_helpers import dword, fake_open_port


def pc(channel, program):
    return (0xC0 | (channel - 1)) | (program << 8)


class ServiceDispatchTests(NoHardwareMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.service = Flow8Service(auto_connect=False)
        self.out, self.driver = fake_open_port(self.service.midi_out)

    def sent(self):
        return [call.args[1] for call in self.driver.midiOutShortMsg.call_args_list]

    def test_limiter_and_geq_bytes(self):
        self.service.set_bus_limiter("main", 100)
        self.service.set_bus_geq("mon1", 1, 40)
        self.service.set_bus_geq("mon2", 9, 90)
        self.assertEqual(self.sent(), [dword(8, 8, 100), dword(9, 11, 40), dword(10, 19, 90)])

    def test_fx_params_and_preset_bytes(self):
        self.service.set_fx_param("fx1", 1, 25)
        self.service.set_fx_param("fx2", 2, True)
        self.service.set_fx_param("fx2", 2, False)
        self.service.set_fx_preset("fx1", 9)
        self.service.set_fx_preset("fx2", 16)
        self.assertEqual(self.sent(), [
            dword(13, 1, 25), dword(14, 2, 127), dword(14, 2, 0), pc(13, 9), pc(14, 16)])

    def test_out_of_scope_targets_send_nothing(self):
        self.service.set_bus_limiter("fx1", 64)      # FX buses have no limiter
        self.service.set_bus_geq("main", 10, 64)     # only bands 1-9
        self.service.set_fx_param("fx3", 1, 10)
        self.service.set_fx_param("fx1", 3, 10)
        self.service.set_fx_preset("fx9", 1)
        self.assertEqual(self.sent(), [])

    def test_preset_outside_1_to_16_is_refused_before_the_driver(self):
        for bad in (0, 17):
            with self.assertRaises(Exception):
                self.service.set_fx_preset("fx1", bad)
        self.assertEqual(self.sent(), [])

    def test_geq_and_preset_changes_undo(self):
        self.service.set_bus_geq("main", 3, 64)
        self.service.set_bus_geq("main", 3, 80)
        self.service.set_fx_preset("fx2", 2)
        self.service.set_fx_preset("fx2", 5)
        self.driver.midiOutShortMsg.reset_mock()
        self.service.undo()
        self.service.undo()
        self.assertEqual(self.sent(), [pc(14, 2), dword(8, 13, 64)])

    def test_new_parameters_are_not_in_scenes(self):
        self.service.set_fader(1, 90)
        self.service.set_bus_geq("main", 1, 70)
        self.service.set_fx_preset("fx1", 3)
        state = self.service.known_mix_state()
        flat = {(ch, p) for ch, values in state.items() for p in values}
        self.assertNotIn(("main", "geq1"), flat)
        self.assertFalse(any(str(ch).startswith("fxe") for ch, _ in flat))

    def test_ble_mode_rejects_bus_dsp_and_fx(self):
        self.service.set_transport_mode("ble")
        for call in (lambda: self.service.set_bus_limiter("main", 64),
                     lambda: self.service.set_fx_preset("fx1", 1)):
            with self.assertRaises(Flow8CommandRejectedError):
                call()
        self.assertEqual(self.sent(), [])


class HubTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(Flow8Service, "is_connected", new_callable=mock.PropertyMock, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = Flow8Service(auto_connect=False)
        self.hub = Flow8LanHub(self.service, host="127.0.0.1", port=0)
        self.port = self.hub.start()
        self.addCleanup(self.hub.stop)

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))

    def post(self, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/action", data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status
        except urllib.error.HTTPError as err:
            err.close()
            return err.code

    def test_session_starts_unsynced(self):
        snap = self.get("/api/session")
        self.assertEqual(set(snap["busDsp"]), {"main", "mon1", "mon2"})
        self.assertEqual(snap["busDsp"]["main"]["limiterProvenance"], "UNSYNCED")
        self.assertEqual(len(snap["busDsp"]["mon2"]["geq"]), 9)
        self.assertEqual(snap["fxEngines"]["fx1"]["presetProvenance"], "UNSYNCED")

    def test_actions_reach_the_service(self):
        with mock.patch.object(self.service, "set_bus_limiter") as lim, \
                mock.patch.object(self.service, "set_bus_geq") as geq, \
                mock.patch.object(self.service, "set_fx_param") as par, \
                mock.patch.object(self.service, "set_fx_preset") as pre:
            self.assertEqual(self.post({"action": "setBusLimiter", "bus": "main", "value": 90}), 200)
            self.assertEqual(self.post({"action": "setBusGeq", "bus": "mon1", "band": 4, "value": 70}), 200)
            self.assertEqual(self.post({"action": "setFxParam", "engine": "fx2", "param": 2, "value": True}), 200)
            self.assertEqual(self.post({"action": "setFxPreset", "engine": "fx1", "value": 12}), 200)
        lim.assert_called_once_with("main", 90)
        geq.assert_called_once_with("mon1", 4, 70)
        par.assert_called_once_with("fx2", 2, True)
        pre.assert_called_once_with("fx1", 12)


if __name__ == "__main__":
    unittest.main()
