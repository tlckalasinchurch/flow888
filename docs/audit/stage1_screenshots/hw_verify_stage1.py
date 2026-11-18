"""Stage 1 physical-hardware verification harness (real FLOW 8 over WinMM).

  python docs/audit/stage1_screenshots/hw_verify_stage1.py d01 <seconds>   passive: sends NO MIDI
  python docs/audit/stage1_screenshots/hw_verify_stage1.py d02             sends ch1 EQ/lowcut/comp (preset) -- changes the mix
  python docs/audit/stage1_screenshots/hw_verify_stage1.py d05 <seconds>   operator moves ch1 fader, unplugs/replugs USB; sends no DSP command

Never sends +48V. Logs: raw IN, outbound (every send_cc), UI diffs, screenshots -> docs/audit/hw_stage1/.
"""
import importlib.util
import json
import os
import sys
import time

sys.path.insert(0, os.getcwd())
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("cap", f"{HERE}/capture_stage1.py")
cap = importlib.util.module_from_spec(spec); spec.loader.exec_module(cap)
from flow8.service import Flow8Service  # noqa: E402
from flow8.ui.app import Flow8App  # noqa: E402
from flow8.ui.components.channel_detail import ChannelDetailPanel, SelectionTarget  # noqa: E402

OUT = os.path.abspath("docs/audit/hw_stage1"); os.makedirs(OUT, exist_ok=True)
mode = sys.argv[1]
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 60
T0 = time.time()
log = open(f"{OUT}/{mode}_events.jsonl", "w", encoding="utf-8")


def rec(kind, **kw):
    kw.update(kind=kind, t=round(time.time() - T0, 3), wall=time.strftime("%H:%M:%S"))
    log.write(json.dumps(kw, default=str) + "\n"); log.flush()


service = Flow8Service(auto_connect=False)
orig_in = service._on_midi_in_event
service._on_midi_in_event = lambda e: (rec("midi_in_raw", **{k: e.get(k) for k in ("status", "channel", "data1", "data2")}), orig_in(e))[1]
orig_send = service.midi_out.send_cc
def send_spy(ch, c, v):
    rec("midi_out_send_cc", ch=ch, cc=c, value=v)
    return orig_send(ch, c, v)
service.midi_out.send_cc = send_spy

app = Flow8App(service=service, show_placeholder=False, connect_hardware=False)
root, con = app.root, app.mixer_console
root.deiconify(); root.geometry("1366x768+0+0"); root.update()
ok = service.connect()
rec("connect", ok=ok, error=service.connection_error, out_open=service.midi_out_open, in_open=service.midi_in_open, listening=service.midi_in_listening)
print("connect:", ok, service.connection_error)


def snap():
    s = {}
    for i, st in con.strips.items():
        s[i] = dict(fader=st.fader_val.get(), pan=st.pan_val.get(), mute=st.is_muted.get(),
                    fprov=st.fader_provenance.name)
    return s


def shot(name):
    cap.grab(root, f"{OUT}/{mode}_{name}.png"); rec("screenshot", name=name)


def pump(duration, watch=True):
    prev = snap(); end = time.time() + duration
    while time.time() < end:
        root.update(); time.sleep(0.02)
        cur = snap()
        if watch and cur != prev:
            for i in cur:
                if cur[i] != prev[i]:
                    rec("ui_change", strip=i, before=prev[i], after=cur[i])
            prev = cur


def insp():
    i = con.inspector
    return dict(eq={k: v.get() for k, v in i.eq_vars.items()}, eq_badge=i.eq_badge.label.cget("text"),
                low_cut=i.low_cut_var.get(), comp=i.comp_var.get(), widget_id=str(i), eq_var_ids={k: id(v) for k, v in i.eq_vars.items()},
                n_children=len(i.winfo_children()))


if mode == "d01":
    print("PASSIVE WINDOW OPEN", secs, "s -- move faders, pans, mutes now. Nothing is sent.")
    shot("before"); pump(secs); shot("after")
elif mode == "d02":
    con.select_target(SelectionTarget.input(1)); con.inspector.show_tab(ChannelDetailPanel.TAB_EQ); pump(0.5, False)
    for step, fn in (("0_open", None), ("1_preset", lambda: service.apply_channel_preset(1, "vocal-worship-ballad")),
                     ("2_undo", con.undo), ("3_redo", con.redo)):
        if fn:
            fn()
        pump(1.0, False); rec("inspector", step=step, **insp()); shot(step)
elif mode == "d05":
    con.select_target(SelectionTarget.input(1)); con.inspector.show_tab(ChannelDetailPanel.TAB_EQ)
    # No DSP commands are sent: known state = values the operator moves on the mixer (OBSERVED).
    print("D05 window", secs, "s: (1) move ch1 fader, (2) UNPLUG USB, wait, (3) REPLUG")
    last = None; end = time.time() + secs
    while time.time() < end:
        root.update(); time.sleep(0.05)
        st = (service.midi_out_open, service.midi_in_open, service.midi_in_listening, service.ledger.can_undo,
              service.state_store.get_parameter("ch1.fader").provenance.name,
              con.strips[1].fader_val.get(), con.strips[1].fader_provenance.name)
        if st != last:
            rec("conn_state", out_open=st[0], in_open=st[1], listening=st[2], can_undo=st[3], ch1_fader_store_prov=st[4],
                ch1_fader_ui=st[5], ch1_fader_ui_prov=st[6]); last = st
            if st[4] != "UNSYNCED" or st[0] is False:
                shot(f"snap_{int(time.time()-T0)}s")
    shot("1_end")
con.after_cancel  # noqa
rec("done", out_sends=None)
log.close(); app.close()
