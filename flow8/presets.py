"""
Behringer FLOW 8 Curated Audio Engineering Presets.
Ported and adapted from CueAir audio engineering profiles (cuetone-basic.cueairpreset).
Scope: Behringer FLOW 8 ONLY.

Design Invariant:
Level Preservation Guarantee (preserve_levels = True):
Applying any channel preset shapes EQ, dynamics, and low-cut filtering to achieve
optimal tone without altering the channel's fader level, stereo pan/balance, or
preamp gain. This protects the live audio mix and prevents volume jumps.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ChannelPreset:
    """Represents an acoustic audio engineering profile for a mixer channel."""
    id: str
    name: str
    category: str
    summary: str
    notes: Dict[str, str]
    eq_low_db: float = 0.0        # -15.0 to +15.0 dB (CC 1)
    eq_low_mid_db: float = 0.0    # -15.0 to +15.0 dB (CC 2)
    eq_hi_mid_db: float = 0.0     # -15.0 to +15.0 dB (CC 3)
    eq_hi_db: float = 0.0         # -15.0 to +15.0 dB (CC 4)
    low_cut_hz: Optional[float] = None       # 20 to 600 Hz (Channels 1-4 only, CC 9)
    compressor_percent: Optional[float] = None # 0 to 100% (Channels 1-4 only, CC 11)
    preserve_levels: bool = True


@dataclass(frozen=True)
class FxPreset:
    """Represents an FX engine preset for FLOW 8 FX1 or FX2 slot."""
    id: str
    name: str
    group: str
    target_slot: int              # 1 for FX1 (Reverb/Delay), 2 for FX2 (Mod/Delay)
    algorithm_index: int          # 1..16 (Program Change 1-16)
    summary: str
    decay_or_speed: float         # Human unit (seconds / ms)
    notes: str


# ---------------------------------------------------------------------------
# Curated Channel Presets (Acoustically Adapted to FLOW 8 Topology)
# ---------------------------------------------------------------------------

CHANNEL_PRESETS: Dict[str, ChannelPreset] = {
    # --- Vocals & Speech ---
    "speech-mc-handheld": ChannelPreset(
        id="speech-mc-handheld",
        name="MC Wireless Handheld",
        category="Speech",
        summary="Optimized for handheld dynamic microphones in speech, presentation, or MC duties.",
        notes={
            "low_cut": "Filters handling noise, wind, and plosive pops below 120 Hz.",
            "eq_low": "Cuts proximity effect boominess (-3.0 dB).",
            "eq_low_mid": "Cleans up room resonance / boxiness at 350 Hz (-2.0 dB).",
            "eq_hi_mid": "Gentle presence lift (+1.5 dB) for vocal intelligibility.",
            "eq_hi": "Smooth air shelf (+1.0 dB).",
            "compressor": "Light 30% leveling to control sudden loud shouting without pumping."
        },
        low_cut_hz=120.0,
        eq_low_db=-3.0,
        eq_low_mid_db=-2.0,
        eq_hi_mid_db=1.5,
        eq_hi_db=1.0,
        compressor_percent=30.0,
        preserve_levels=True
    ),
    "vocal-male-lead": ChannelPreset(
        id="vocal-male-lead",
        name="Lead Vocal (Male)",
        category="Vocal",
        summary="Warm and articulate lead vocal profile for baritone/tenor singing in band contexts.",
        notes={
            "low_cut": "100 Hz high-pass to clear mud while preserving vocal chest resonance.",
            "eq_low": "Subtle -1.5 dB low trim to avoid masking bass.",
            "eq_low_mid": "-1.0 dB dip around 400 Hz for clarity.",
            "eq_hi_mid": "+2.5 dB articulation boost in the 2.5-3.5 kHz range.",
            "eq_hi": "+2.0 dB air shelf for sheen and open high end.",
            "compressor": "40% 1-knob compression for consistent vocal dynamics in the mix."
        },
        low_cut_hz=100.0,
        eq_low_db=-1.5,
        eq_low_mid_db=-1.0,
        eq_hi_mid_db=2.5,
        eq_hi_db=2.0,
        compressor_percent=40.0,
        preserve_levels=True
    ),
    "vocal-female-lead": ChannelPreset(
        id="vocal-female-lead",
        name="Lead Vocal (Female)",
        category="Vocal",
        summary="Silky and bright female vocal tuning with sibilance protection.",
        notes={
            "low_cut": "125 Hz cut to remove sub-harmonic stage rumble.",
            "eq_low": "-2.5 dB shelf to keep body clear and lightweight.",
            "eq_low_mid": "Flat 0.0 dB to preserve mid-range sweetness.",
            "eq_hi_mid": "+2.0 dB presence for forward vocal placement.",
            "eq_hi": "+3.0 dB smooth high boost for clarity and definition.",
            "compressor": "35% compression for natural vocal breath and power."
        },
        low_cut_hz=125.0,
        eq_low_db=-2.5,
        eq_low_mid_db=0.0,
        eq_hi_mid_db=2.0,
        eq_hi_db=3.0,
        compressor_percent=35.0,
        preserve_levels=True
    ),
    "podcast-broadcast": ChannelPreset(
        id="podcast-broadcast",
        name="Podcast / Broadcast Studio",
        category="Speech",
        summary="Radio broadcast vocal tone with tight proximity control and heavy leveling.",
        notes={
            "low_cut": "85 Hz cut for rich broadcast voice proximity effect.",
            "eq_low": "+1.5 dB warm proximity low enhancement.",
            "eq_low_mid": "-2.0 dB cut to avoid hollow boxiness.",
            "eq_hi_mid": "+2.0 dB crisp articulation boost.",
            "eq_hi": "+1.5 dB condenser air lift.",
            "compressor": "50% firm leveling to keep quiet and loud speakers balanced."
        },
        low_cut_hz=85.0,
        eq_low_db=1.5,
        eq_low_mid_db=-2.0,
        eq_hi_mid_db=2.0,
        eq_hi_db=1.5,
        compressor_percent=50.0,
        preserve_levels=True
    ),
    "vocal-worship-ballad": ChannelPreset(
        id="vocal-worship-ballad",
        name="Worship / Ballad Vocal",
        category="Vocal",
        summary="Deep, dynamic vocal curve crafted for emotive singing with space for reverb.",
        notes={
            "low_cut": "110 Hz clean cut.",
            "eq_low": "-1.0 dB gentle low attenuation.",
            "eq_low_mid": "-0.5 dB neutral mid transition.",
            "eq_hi_mid": "+2.0 dB smooth upper mid response.",
            "eq_hi": "+2.5 dB sheen for pairing with plate/hall reverb.",
            "compressor": "30% gentle control leaving dynamic peaks intact."
        },
        low_cut_hz=110.0,
        eq_low_db=-1.0,
        eq_low_mid_db=-0.5,
        eq_hi_mid_db=2.0,
        eq_hi_db=2.5,
        compressor_percent=30.0,
        preserve_levels=True
    ),

    # --- Instruments ---
    "acoustic-guitar-strum": ChannelPreset(
        id="acoustic-guitar-strum",
        name="Acoustic Guitar (Strummed)",
        category="Acoustic",
        summary="Removes piezo pickup quack and body boominess while preserving pick sparkle.",
        notes={
            "low_cut": "90 Hz high-pass to clear soundboard thumps.",
            "eq_low": "-3.5 dB cut at bottom end to avoid conflicting with bass and kick.",
            "eq_low_mid": "-3.0 dB notch at 300-500 Hz (piezo boxiness).",
            "eq_hi_mid": "+1.5 dB strum articulation.",
            "eq_hi": "+3.0 dB acoustic string sparkle.",
            "compressor": "25% light compression to smooth out heavy strumming."
        },
        low_cut_hz=90.0,
        eq_low_db=-3.5,
        eq_low_mid_db=-3.0,
        eq_hi_mid_db=1.5,
        eq_hi_db=3.0,
        compressor_percent=25.0,
        preserve_levels=True
    ),
    "acoustic-guitar-fingerstyle": ChannelPreset(
        id="acoustic-guitar-fingerstyle",
        name="Acoustic Guitar (Fingerstyle)",
        category="Acoustic",
        summary="Intimate, warm acoustic guitar profile with enhanced body and detail.",
        notes={
            "low_cut": "75 Hz subtle cut.",
            "eq_low": "+1.0 dB rich body response.",
            "eq_low_mid": "-1.0 dB clarity notch.",
            "eq_hi_mid": "+2.0 dB wood and fingernail presence.",
            "eq_hi": "+2.0 dB sweet acoustic highs.",
            "compressor": "20% transparent compression for consistent note sustain."
        },
        low_cut_hz=75.0,
        eq_low_db=1.0,
        eq_low_mid_db=-1.0,
        eq_hi_mid_db=2.0,
        eq_hi_db=2.0,
        compressor_percent=20.0,
        preserve_levels=True
    ),
    "bass-guitar-di": ChannelPreset(
        id="bass-guitar-di",
        name="Electric Bass (Direct In)",
        category="Bass",
        summary="Punchy direct bass guitar profile with sub control and string attack.",
        notes={
            "low_cut": "35 Hz sub-sonic protection filter.",
            "eq_low": "+3.5 dB solid low-end foundation.",
            "eq_low_mid": "+1.0 dB punch around 200 Hz.",
            "eq_hi_mid": "-2.5 dB scoop at 800 Hz to carve space for vocals.",
            "eq_hi": "+1.5 dB string attack and fret bite.",
            "compressor": "55% tight compression for rock-solid bass sustain and leveling."
        },
        low_cut_hz=35.0,
        eq_low_db=3.5,
        eq_low_mid_db=1.0,
        eq_hi_mid_db=-2.5,
        eq_hi_db=1.5,
        compressor_percent=55.0,
        preserve_levels=True
    ),
    "electric-guitar-clean": ChannelPreset(
        id="electric-guitar-clean",
        name="Electric Guitar (Clean / Mod)",
        category="Acoustic",
        summary="Fender-style clean electric guitar tuning with glassy highs and tight lows.",
        notes={
            "low_cut": "85 Hz cabinet resonance cut.",
            "eq_low": "0.0 dB flat low end.",
            "eq_low_mid": "+1.0 dB body warmth.",
            "eq_hi_mid": "+2.0 dB pick attack.",
            "eq_hi": "+2.5 dB glassy clean sheen.",
            "compressor": "35% compression for funk rhythm or chimey chords."
        },
        low_cut_hz=85.0,
        eq_low_db=0.0,
        eq_low_mid_db=1.0,
        eq_hi_mid_db=2.0,
        eq_hi_db=2.5,
        compressor_percent=35.0,
        preserve_levels=True
    ),

    # --- Drums & Percussion ---
    "drum-kick-punch": ChannelPreset(
        id="drum-kick-punch",
        name="Bass Drum / Kick (Punch)",
        category="Drums",
        summary="Modern punchy kick drum tuning: deep sub weight, sculpted mids, beater click.",
        notes={
            "low_cut": "30 Hz sub rumble filter.",
            "eq_low": "+4.0 dB deep 60 Hz fundamental thud.",
            "eq_low_mid": "-4.5 dB deep scoop (300-400 Hz boxiness cut).",
            "eq_hi_mid": "+3.5 dB sharp beater transient click (3 kHz).",
            "eq_hi": "0.0 dB neutral top.",
            "compressor": "65% aggressive compression for uniform punch."
        },
        low_cut_hz=30.0,
        eq_low_db=4.0,
        eq_low_mid_db=-4.5,
        eq_hi_mid_db=3.5,
        eq_hi_db=0.0,
        compressor_percent=65.0,
        preserve_levels=True
    ),
    "drum-snare-crack": ChannelPreset(
        id="drum-snare-crack",
        name="Snare Drum (Fat Crack)",
        category="Drums",
        summary="Snare drum curve balancing woody body punch with crisp snare wire snap.",
        notes={
            "low_cut": "75 Hz low cut to clear kick bleed.",
            "eq_low": "+2.0 dB body punch at 180 Hz.",
            "eq_low_mid": "-2.0 dB boxy ring suppression.",
            "eq_hi_mid": "+3.0 dB stick crack at 3.5 kHz.",
            "eq_hi": "+2.5 dB wire sizzle at 8 kHz.",
            "compressor": "50% snappy compression enhancing transient snap."
        },
        low_cut_hz=75.0,
        eq_low_db=2.0,
        eq_low_mid_db=-2.0,
        eq_hi_mid_db=3.0,
        eq_hi_db=2.5,
        compressor_percent=50.0,
        preserve_levels=True
    ),
    "drum-overheads": ChannelPreset(
        id="drum-overheads",
        name="Drum Overheads / Cymbals",
        category="Drums",
        summary="Airy cymbal clarity with heavy low cut to eliminate tom and kick bleed.",
        notes={
            "low_cut": "350 Hz high-pass to reject kick and floor tom stage wash.",
            "eq_low": "-6.0 dB shelf cut.",
            "eq_low_mid": "-2.0 dB harsh snare ringing dip.",
            "eq_hi_mid": "+1.0 dB ride cymbal bell definition.",
            "eq_hi": "+4.0 dB silky cymbal wash.",
            "compressor": "15% subtle peak taming."
        },
        low_cut_hz=350.0,
        eq_low_db=-6.0,
        eq_low_mid_db=-2.0,
        eq_hi_mid_db=1.0,
        eq_hi_db=4.0,
        compressor_percent=15.0,
        preserve_levels=True
    ),

    # --- Reset & Flat Reference ---
    "utility-flat-reset": ChannelPreset(
        id="utility-flat-reset",
        name="Reset to Flat (Bypass)",
        category="Utility",
        summary="Returns EQ to 0.0 dB flat and bypasses Low Cut and Compressor.",
        notes={
            "reset": "All 4 EQ bands set to 0.0 dB; Low Cut to 20 Hz; Compressor to 0%."
        },
        low_cut_hz=20.0,
        eq_low_db=0.0,
        eq_low_mid_db=0.0,
        eq_hi_mid_db=0.0,
        eq_hi_db=0.0,
        compressor_percent=0.0,
        preserve_levels=True
    )
}


# ---------------------------------------------------------------------------
# Curated FX Starting Points (FLOW 8 Multi-FX Engines)
# ---------------------------------------------------------------------------

FX_PRESETS: Dict[str, FxPreset] = {
    "fx1-room-mc": FxPreset(
        id="fx1-room-mc",
        name="MC & Speech Room Reverb",
        group="Reverb",
        target_slot=1,
        algorithm_index=2,  # Room Reverb
        summary="Short acoustic room reflection adding natural depth to speaking voices without muddying speech.",
        decay_or_speed=0.8,
        notes="Pre-delay 10ms, decay 0.8s. Keeps return fader moderate."
    ),
    "fx1-plate-vocal": FxPreset(
        id="fx1-plate-vocal",
        name="Studio Vocal Plate",
        group="Reverb",
        target_slot=1,
        algorithm_index=1,  # Plate Reverb
        summary="Classic dense vocal plate reverb suited for pop, worship, and ballad singing.",
        decay_or_speed=1.8,
        notes="Pre-delay 25ms, decay 1.8s. Rich high-frequency diffusion."
    ),
    "fx1-hall-warm": FxPreset(
        id="fx1-hall-warm",
        name="Concert Hall (Warm)",
        group="Reverb",
        target_slot=1,
        algorithm_index=3,  # Hall Reverb
        summary="Expansive hall reverb providing lush tails for acoustic guitar and vocal ballads.",
        decay_or_speed=2.4,
        notes="Pre-delay 35ms, decay 2.4s. High cut rolled off at 7 kHz."
    ),
    "fx2-slapback-echo": FxPreset(
        id="fx2-slapback-echo",
        name="Vintage Slapback Echo",
        group="Delay",
        target_slot=2,
        algorithm_index=5,  # Slap Delay
        summary="Single tight slapback echo (90-120ms) for rockabilly vocals and percussive guitars.",
        decay_or_speed=0.11,
        notes="Single repeat slapback, low feedback."
    ),
    "fx2-stereo-chorus": FxPreset(
        id="fx2-stereo-chorus",
        name="Lush Stereo Chorus",
        group="Modulation",
        target_slot=2,
        algorithm_index=9,  # Chorus
        summary="Thickens acoustic guitars, electric guitars, and backing vocals with subtle pitch animation.",
        decay_or_speed=1.2,
        notes="Subtle stereo modulation rate and depth."
    )
}


# ---------------------------------------------------------------------------
# Preset Catalog Helper Functions
# ---------------------------------------------------------------------------

def list_channel_presets(category: Optional[str] = None) -> List[ChannelPreset]:
    """Return all channel presets, optionally filtered by category."""
    if category is None or category.lower() == "all":
        return list(CHANNEL_PRESETS.values())
    cat_lower = category.lower()
    return [p for p in CHANNEL_PRESETS.values() if p.category.lower() == cat_lower]


def get_channel_preset(preset_id: str) -> Optional[ChannelPreset]:
    """Retrieve a channel preset by ID."""
    return CHANNEL_PRESETS.get(preset_id)


def list_fx_presets(group: Optional[str] = None) -> List[FxPreset]:
    """Return all FX presets, optionally filtered by group."""
    if group is None or group.lower() == "all":
        return list(FX_PRESETS.values())
    grp_lower = group.lower()
    return [p for p in FX_PRESETS.values() if p.group.lower() == grp_lower]


def get_fx_preset(preset_id: str) -> Optional[FxPreset]:
    """Retrieve an FX preset by ID."""
    return FX_PRESETS.get(preset_id)
