"""Cyber Neon Tk mixer console UI.

The UI is intentionally hardware-independent: it presents an offline-safe
control surface while routing every editable value through Flow8Service.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import simpledialog
from typing import Any, Hashable
from .service import ALL_CHANNELS, Flow8Service
BG="#070b18"; PANEL="#0c1325"; PANEL_2="#111a30"; CARD="#0b1222"
CYAN="#00e8ff"; CYAN_DIM="#177c9c"; PURPLE="#b84dff"; PINK="#ff3fc7"
TEXT="#edf5ff"; MUTED="#8290aa"; YELLOW="#ffd52e"; RED="#ff4e61"

class MixerConsole(tk.Frame):
    """A realistic, offline-safe mixer workstation view."""
    def __init__(self, master: tk.Misc, service: Flow8Service | None = None):
        super().__init__(master, bg=BG)
        self.service=service or Flow8Service(); self.selected_channel: Hashable=0
        self._dragging=False; self._fader_vars={}; self._fader_widgets={}
        self.status=tk.StringVar(value="READY  •  OFFLINE-SAFE CONTROL SURFACE")
        self.detail_title=tk.StringVar(value="MIC 1  (CH 1)"); self.detail_fader=tk.StringVar()
        self.detail_pan=tk.StringVar(); self.detail_mute=tk.StringVar(); self.phantom_text=tk.StringVar(value="OFF")
        self._build(); self._refresh()

    def _label(self,parent,text,*,color=TEXT,size=10,bold=False,**kwargs):
        return tk.Label(parent,text=text,bg=parent.cget("bg"),fg=color,font=("Segoe UI",size,"bold" if bold else "normal"),**kwargs)
    def _button(self,parent,text,command,*,color=CYAN,width=11):
        return tk.Button(parent,text=text,command=command,width=width,bg="#101b31",fg=TEXT,activebackground=color,activeforeground="#04101b",relief="flat",bd=1,highlightthickness=1,highlightbackground=color,font=("Segoe UI",9,"bold"),padx=5,pady=5)
    def _build(self):
        self.pack(fill="both",expand=True); self._build_header(); self._build_nav()
        body=tk.Frame(self,bg=BG); body.pack(fill="both",expand=True,padx=12,pady=(8,6)); body.columnconfigure(0,weight=1); body.columnconfigure(1,weight=0); body.rowconfigure(0,weight=1)
        self._build_mixer(body); self._build_detail(body); self._build_footer()
    def _status_pill(self,parent,text,color):
        return tk.Label(parent,text=text,bg="#131a2c",fg=color,font=("Segoe UI",8,"bold"),highlightthickness=1,highlightbackground=color,padx=10,pady=6)
    def _build_header(self):
        header=tk.Frame(self,bg="#090d20",height=82); header.pack(fill="x"); header.pack_propagate(False)
        logo=tk.Canvas(header,width=82,height=70,bg=header.cget("bg"),highlightthickness=0); logo.pack(side="left",padx=(16,2),pady=6)
        logo.create_polygon(40,5,74,62,7,62,fill="",outline=PURPLE,width=4); logo.create_polygon(40,20,57,51,23,51,fill="",outline=CYAN,width=2)
        title=tk.Frame(header,bg=header.cget("bg")); title.pack(side="left",pady=12); self._label(title,"FLOW 8",color="#baf8ff",size=22,bold=True).pack(anchor="w"); self._label(title,"Cyber Neon Workstation",color=PURPLE,size=11,bold=True).pack(anchor="w")
        tk.Label(header,text="Behringer FLOW 8 Control Surface  (Offline-Safe)",bg="#091426",fg=TEXT,font=("Segoe UI",12,"bold"),highlightthickness=1,highlightbackground=CYAN_DIM,padx=38,pady=8).pack(side="left",expand=True,padx=30)
        self._status_pill(header,"OFFLINE MODE",YELLOW).pack(side="right",padx=6); self._status_pill(header,"NO HARDWARE APPLIED",PINK).pack(side="right",padx=(6,14))
    def _build_nav(self):
        nav=tk.Frame(self,bg=BG); nav.pack(fill="x",padx=14,pady=(8,0))
        for index,label in enumerate(("☷  Mixer","⚙  Channel Detail","▱  Scenes","◈  Settings","∿  Diagnostics")):
            color=CYAN if index==0 else CYAN_DIM
            tk.Button(nav,text=label,bg="#10223a" if index==0 else PANEL,fg=TEXT,activebackground="#173d56",activeforeground=CYAN,relief="flat",highlightthickness=1,highlightbackground=color,font=("Segoe UI",10,"bold"),padx=22,pady=7).pack(side="left",padx=4)
    def _build_mixer(self,parent):
        outer=tk.Frame(parent,bg=PANEL,highlightthickness=1,highlightbackground=CYAN_DIM); outer.grid(row=0,column=0,sticky="nsew",padx=(0,10)); outer.rowconfigure(1,weight=1); outer.columnconfigure(0,weight=1)
        heading=tk.Frame(outer,bg=PANEL); heading.grid(row=0,column=0,sticky="ew",padx=12,pady=(10,4)); self._label(heading,"MIXER",color=CYAN,size=15,bold=True).pack(side="left"); self._label(heading,"7 INPUTS  +  MAIN L/R",color=MUTED,size=9).pack(side="left",padx=16,pady=3); self._button(heading,"UNDO  Ctrl+Z",self.undo,color=CYAN,width=13).pack(side="right",padx=3); self._button(heading,"REDO  Ctrl+Y",self.redo,color=PURPLE,width=13).pack(side="right",padx=3)
        strips=tk.Frame(outer,bg=PANEL); strips.grid(row=1,column=0,sticky="nsew",padx=8,pady=8)
        for column,channel in enumerate(ALL_CHANNELS): strips.columnconfigure(column,weight=1); self._build_strip(strips,channel,column)
    def _build_strip(self,parent,channel,column):
        is_main=isinstance(channel,str); accent=PURPLE if is_main else (CYAN if channel==0 else CYAN_DIM)
        card=tk.Frame(parent,bg=CARD,highlightthickness=2 if channel==0 else 1,highlightbackground=accent,cursor="hand2"); card.grid(row=0,column=column,sticky="nsew",padx=3); card.bind("<Button-1>",lambda _e,ch=channel:self._select_channel(ch))
        display="MAIN" if is_main else f"{channel+1:02d}"; sub="L / R" if is_main else f"IN {channel+1}"
        self._label(card,display,color=accent,size=15,bold=True).pack(pady=(9,0)); self._label(card,sub,color=TEXT,size=9,bold=True).pack(pady=(0,7)); self._button(card,"MUTE",lambda ch=channel:self._toggle_mute(ch),color=PINK if is_main else CYAN_DIM,width=8).pack(pady=(0,8))
        if not is_main:
            self._label(card,"PAN",color=MUTED,size=8).pack(); pan_var=tk.DoubleVar(value=0); pan=tk.Scale(card,from_=100,to=-100,orient="horizontal",variable=pan_var,showvalue=False,length=86,sliderlength=13,bg=CARD,fg=TEXT,troughcolor="#07101d",highlightthickness=0,activebackground=CYAN,command=lambda value,ch=channel:self._pan_changed(ch,value)); pan.pack(pady=(0,5)); self._label(card,"C",color=MUTED,size=8).pack()
        else: self._label(card,"MASTER BUS",color=MUTED,size=8).pack(pady=(23,9))
        var=tk.DoubleVar(value=0); fader=tk.Scale(card,from_=10,to=-60,resolution=1,orient="vertical",variable=var,showvalue=False,length=220,width=22,sliderlength=23,bg=CARD,fg=TEXT,troughcolor="#050b13",highlightthickness=0,activebackground=accent,command=lambda value,ch=channel:self._fader_changed(ch,value)); fader.pack(pady=(2,0)); fader.bind("<ButtonPress-1>",self._drag_start); fader.bind("<ButtonRelease-1>",self._drag_end); self._fader_vars[channel]=var; self._fader_widgets[channel]=fader
        value=tk.StringVar(value="-inf dB"); setattr(self,f"_value_{str(channel).replace('-','_')}",value); self._label(card,"────────",color=accent,size=8).pack(); tk.Label(card,textvariable=value,bg=CARD,fg=TEXT,font=("Consolas",10,"bold")).pack(pady=(1,1)); self._label(card,"dB",color=MUTED,size=8).pack(pady=(0,8))
    def _build_detail(self,parent):
        panel=tk.Frame(parent,bg=PANEL,width=300,highlightthickness=1,highlightbackground=PURPLE); panel.grid(row=0,column=1,sticky="nsew"); panel.grid_propagate(False); self._label(panel,"⚙  CHANNEL DETAIL",color=PURPLE,size=14,bold=True).pack(anchor="w",padx=16,pady=(14,5))
        selector=tk.Frame(panel,bg=PANEL); selector.pack(fill="x",padx=12,pady=4); self._button(selector,"‹",lambda:self._cycle(-1),color=CYAN,width=3).pack(side="left"); tk.Label(selector,textvariable=self.detail_title,bg=PANEL,fg=TEXT,font=("Segoe UI",13,"bold")).pack(side="left",expand=True); self._button(selector,"›",lambda:self._cycle(1),color=CYAN,width=3).pack(side="right")
        tabs=tk.Frame(panel,bg=PANEL); tabs.pack(fill="x",padx=12,pady=10)
        for text in ("Overview","Gain","Phantom","Info"): tk.Button(tabs,text=text,bg="#10233b" if text=="Overview" else PANEL_2,fg=TEXT,relief="flat",highlightthickness=1,highlightbackground=CYAN_DIM,padx=7,pady=5).pack(side="left",padx=2)
        info=tk.Frame(panel,bg="#0a1527",highlightthickness=1,highlightbackground="#214263"); info.pack(fill="x",padx=12,pady=5); self._label(info,"MICROPHONE / LINE INPUT",color=CYAN,size=9,bold=True).pack(anchor="w",padx=12,pady=(12,10))
        for label,variable in (("Type",self.detail_title),("Fader (Commanded)",self.detail_fader),("Pan",self.detail_pan),("Mute",self.detail_mute)):
            row=tk.Frame(info,bg=info.cget("bg")); row.pack(fill="x",padx=12,pady=5); self._label(row,label,color=MUTED,size=9).pack(side="left"); tk.Label(row,textvariable=variable,bg=info.cget("bg"),fg=TEXT,font=("Segoe UI",9,"bold")).pack(side="right")
        phantom=tk.Frame(panel,bg="#0a1527",highlightthickness=1,highlightbackground=PINK); phantom.pack(fill="x",padx=12,pady=(16,5)); tk.Label(phantom,text="⚡  +48V PHANTOM POWER",bg=phantom.cget("bg"),fg=PINK,font=("Segoe UI",10,"bold")).pack(anchor="w",padx=12,pady=(10,4)); row=tk.Frame(phantom,bg=phantom.cget("bg")); row.pack(fill="x",padx=12,pady=(3,10)); self._button(row,"⚡  TOGGLE +48V",self._toggle_phantom,color=PINK,width=17).pack(side="left"); tk.Label(row,textvariable=self.phantom_text,bg=phantom.cget("bg"),fg=TEXT,font=("Segoe UI",10,"bold")).pack(side="right",padx=4); self._label(panel,"Explicit confirmation required.\nPhantom power is never included in Undo/Redo or Scenes.",color=MUTED,size=8,justify="left").pack(anchor="w",padx=16,pady=8)
    def _build_footer(self):
        status=tk.Frame(self,bg="#0a1325",highlightthickness=1,highlightbackground=CYAN_DIM); status.pack(fill="x",padx=12,pady=(0,5)); tk.Label(status,text="∿  STATUS",bg=status.cget("bg"),fg=CYAN,font=("Segoe UI",10,"bold")).pack(side="left",padx=12,pady=8); tk.Label(status,textvariable=self.status,bg=status.cget("bg"),fg=TEXT,font=("Segoe UI",9)).pack(side="left",padx=18); self._status_pill(status,"MIDI OUT  CLOSED",RED).pack(side="right",padx=8,pady=5); self._status_pill(status,"MIDI IN  CLOSED",RED).pack(side="right",padx=8,pady=5)
        log=tk.Frame(self,bg=PANEL,highlightthickness=1,highlightbackground=PURPLE); log.pack(fill="x",padx=12,pady=(0,12)); tk.Label(log,text="⌁  COMMAND LOG",bg=PANEL,fg=PURPLE,font=("Segoe UI",11,"bold")).pack(anchor="w",padx=14,pady=(7,2)); tk.Label(log,text="TIME          TARGET              PARAMETER          VALUE          STATUS\n—             —                   —                  NO COMMANDS YET",bg=PANEL,fg=MUTED,font=("Consolas",8),justify="left",anchor="w").pack(fill="x",padx=18,pady=(0,9))
    def _channel_title(self,channel): return "MAIN L/R" if isinstance(channel,str) else f"MIC {channel+1}  (CH {channel+1})"
    def _select_channel(self,channel): self.selected_channel=channel; self._refresh()
    def _cycle(self,direction): self._select_channel(ALL_CHANNELS[(ALL_CHANNELS.index(self.selected_channel)+direction)%len(ALL_CHANNELS)])
    def _drag_start(self,_event):
        if not self._dragging: self.service.begin_drag(); self._dragging=True
    def _drag_end(self,_event):
        if self._dragging: self.service.end_drag(); self._dragging=False; self._refresh()
    def _fader_changed(self,channel,value): self.service.set_parameter(channel,"fader",int(float(value))); self._refresh(channel)
    def _pan_changed(self,channel,value): self.service.set_parameter(channel,"pan",int(float(value))); self._refresh(channel)
    def _toggle_mute(self,channel): self.service.set_parameter(channel,"mute",not self.service.state[channel]["mute"]); self._refresh(channel)
    def _toggle_phantom(self):
        if isinstance(self.selected_channel,int): self.service.set_parameter(self.selected_channel,"phantom_power",not self.service.phantom_power[self.selected_channel]); self._refresh()
    def undo(self): self.service.undo(); self._refresh()
    def redo(self): self.service.redo(); self._refresh()
    def capture(self,slot=None):
        name=simpledialog.askstring("Capture Snapshot","Snapshot name:",parent=self)
        if name: self.service.save_scene(name); self.service.status_message=f"SNAPSHOT SAVED: {name}"; self._refresh()
    def recall(self,slot=None):
        names=self.service.scenes.names()
        if names: self.service.recall_scene(names[-1]); self._refresh()
    def _refresh(self,changed_channel:Any=None):
        for channel,var in self._fader_vars.items():
            var.set(self.service.state[channel]["fader"]); value=getattr(self,f"_value_{str(channel).replace('-','_')}"); level=self.service.state[channel]["fader"]; value.set("-inf dB" if level<=-60 else f"{level:+d} dB")
        channel=self.selected_channel; state=self.service.state[channel]; self.detail_title.set(self._channel_title(channel)); self.detail_fader.set("-inf dB" if state["fader"]<=-60 else f"{state['fader']:+d} dB"); self.detail_pan.set("CENTER" if isinstance(channel,str) or state.get("pan",0)==0 else str(state["pan"])); self.detail_mute.set("ON" if state["mute"] else "OFF"); self.phantom_text.set("ON" if isinstance(channel,int) and self.service.phantom_power[channel] else "OFF"); self.status.set(self.service.status_message)

def main():
    root=tk.Tk(); root.title("FLOW 8 Cyber Neon Workstation"); root.geometry("1450x900"); root.minsize(1180,720); root.configure(bg=BG); MixerConsole(root); root.mainloop()

if __name__ == "__main__": main()
