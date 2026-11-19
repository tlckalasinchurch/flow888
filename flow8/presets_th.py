"""Clean-room Thai acoustic starting points for the FLOW 8.

These presets were written from scratch for this project out of standard
live-sound practice — high-pass first, subtractive EQ before additive, and a
gentle one-knob compressor — plus the FLOW 8's documented control surface.
No value, name, note or other text is taken from, converted from, or derived
from CueAir or any other vendor preset file; nothing proprietary is copied.

Only three things are ever proposed: the four EQ band gains (channels 1-7),
the low cut (channels 1-4) and the one-knob compressor (channels 1-4).
Fader, pan, mute, sends, preamp gain and +48V are never part of a preset.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from flow8.parameter_mapping import (
    compressor_percent_to_midi,
    eq_db_to_midi,
    low_cut_hz_to_midi,
)

#: Preset scope names, matching the console's scope toggles.
SCOPES = ("eq", "low_cut", "compressor")

EQ_BANDS = ("low", "low_mid", "hi_mid", "hi")

CATEGORIES = ("พูด/พิธีกร", "ร้อง", "เครื่องดนตรี", "เล่นกลับ (BGM)", "รีเซ็ต")

#: Low cut and compressor exist on the mic/combo channels only.
LOW_CUT_CHANNELS = (1, 2, 3, 4)
COMPRESSOR_CHANNELS = (1, 2, 3, 4)
EQ_CHANNELS = (1, 2, 3, 4, 5, 6, 7)


@dataclass(frozen=True)
class ThaiPreset:
    """One starting point: EQ gains in dB, low cut in Hz, compressor in percent."""

    id: str
    name: str
    category: str
    summary: str
    why: tuple[str, ...]
    eq_low_db: float = 0.0
    eq_low_mid_db: float = 0.0
    eq_hi_mid_db: float = 0.0
    eq_hi_db: float = 0.0
    low_cut_hz: Optional[float] = None
    compressor_percent: Optional[float] = None

    @property
    def eq_db(self) -> dict[str, float]:
        return {
            "low": self.eq_low_db,
            "low_mid": self.eq_low_mid_db,
            "hi_mid": self.eq_hi_mid_db,
            "hi": self.eq_hi_db,
        }

    @property
    def eq_raw(self) -> dict[str, int]:
        return {band: eq_db_to_midi(db) for band, db in self.eq_db.items()}

    @property
    def low_cut_raw(self) -> Optional[int]:
        if self.low_cut_hz is None:
            return None
        return low_cut_hz_to_midi(self.low_cut_hz)

    @property
    def compressor_raw(self) -> Optional[int]:
        if self.compressor_percent is None:
            return None
        return compressor_percent_to_midi(self.compressor_percent)

    def supports(self, scope: str, channel: int) -> bool:
        if scope == "eq":
            return channel in EQ_CHANNELS
        if scope == "low_cut":
            return channel in LOW_CUT_CHANNELS and self.low_cut_raw is not None
        if scope == "compressor":
            return channel in COMPRESSOR_CHANNELS and self.compressor_raw is not None
        return False

    def as_payload(self) -> dict:
        """Everything the console needs, including the exact raw values we send."""
        return {
            "id": self.id,
            "catalog": CATALOG_ID,
            "name": self.name,
            "category": self.category,
            "summary": self.summary,
            "why": list(self.why),
            "eqDb": self.eq_db,
            "eqRaw": self.eq_raw,
            "lowCutHz": self.low_cut_hz,
            "lowCutRaw": self.low_cut_raw,
            "compressorPercent": self.compressor_percent,
            "compressorRaw": self.compressor_raw,
        }

    def changes(self, channel: int, scopes: Sequence[str] = SCOPES) -> list[dict]:
        """Plan changes for one channel, in raw MIDI units. Sends nothing.

        Scopes the channel does not support are skipped, never guessed: a
        channel 5 plan simply has no low cut or compressor line.
        """
        if channel not in EQ_CHANNELS:
            raise ValueError(f"presets apply to input channels 1-7; got {channel}")
        active = {str(scope).lower() for scope in scopes}
        unknown = active - set(SCOPES)
        if unknown:
            raise ValueError(f"unknown preset scope: {sorted(unknown)}")

        changes: list[dict] = []
        if "eq" in active and self.supports("eq", channel):
            for band, raw in self.eq_raw.items():
                changes.append({
                    "channel": channel,
                    "parameter": f"eq_{band}",
                    "value": raw,
                    "reason": f"{self.name} · ปรับ EQ {band.replace('_', ' ')}",
                    "risk": "low" if abs(self.eq_db[band]) <= 3.0 else "medium",
                })
        if "low_cut" in active and self.supports("low_cut", channel):
            changes.append({
                "channel": channel,
                "parameter": "low_cut",
                "value": self.low_cut_raw,
                "reason": f"{self.name} · ตัดย่านต่ำ (Low Cut)",
                "risk": "low",
            })
        if "compressor" in active and self.supports("compressor", channel):
            changes.append({
                "channel": channel,
                "parameter": "compressor",
                "value": self.compressor_raw,
                "reason": f"{self.name} · ควบคุมไดนามิก",
                "risk": "medium",
            })
        return changes


CATALOG_ID = "thai-clean-room-v1"


THAI_PRESETS: dict[str, ThaiPreset] = {
    "th-pa-mc": ThaiPreset(
        id="th-pa-mc",
        name="ไมค์พูดพิธีกร (MC)",
        category="พูด/พิธีกร",
        summary="เสียงพูดบนเวทีให้ชัดและดังสม่ำเสมอ โดยไม่เกิดเสียงอู้หรือเสียงลมจากมือจับไมค์",
        why=(
            "ตัดย่านต่ำกว่า 110 Hz เพื่อลดเสียงลม เสียงลมหายใจ และเสียงกระแทกจากมือจับไมค์",
            "ลดย่าน 300–500 Hz เล็กน้อย เพราะเป็นย่านที่ทำให้เสียงพูดในห้องโถงฟังดูอู้",
            "เพิ่มย่าน 2–3 kHz ให้พยัญชนะชัดขึ้นโดยไม่ทำให้เสียงแข็ง",
            "คอมเพรสเซอร์เบา ๆ ช่วยคุมเสียงตะโกนหรือหัวเราะใกล้ไมค์ไม่ให้เสียงแตก",
        ),
        eq_low_db=-3.0,
        eq_low_mid_db=-2.5,
        eq_hi_mid_db=2.0,
        eq_hi_db=0.5,
        low_cut_hz=110.0,
        compressor_percent=25.0,
    ),
    "th-pa-lecture": ThaiPreset(
        id="th-pa-lecture",
        name="ไมค์ประชุม / บรรยาย",
        category="พูด/พิธีกร",
        summary="โทนเสียงพูดนุ่มชัดสำหรับห้องประชุมหรือเวทีบรรยายที่ speaker อยู่ใกล้ไมค์",
        why=(
            "ตัดย่านต่ำกว่า 90 Hz เพื่อลดเสียงสั่นจากโต๊ะและระบบปรับอากาศ",
            "ลดย่าน 400 Hz เล็กน้อยเพื่อลดความขุ่นเมื่อ speaker พูดใกล้ไมค์",
            "เพิ่มความชัดย่าน 2 kHz แบบพอดี เพื่อให้ฟังเข้าใจง่ายในห้องที่มีเสียงก้อง",
            "คอมเพรสเซอร์ต่ำช่วยให้ระดับเสียงคงที่เมื่อผู้พูดเอียงตัว",
        ),
        eq_low_db=-2.0,
        eq_low_mid_db=-1.5,
        eq_hi_mid_db=1.5,
        eq_hi_db=0.0,
        low_cut_hz=90.0,
        compressor_percent=20.0,
    ),
    "th-vocal-male": ThaiPreset(
        id="th-vocal-male",
        name="เสียงร้องสด (ชาย)",
        category="ร้อง",
        summary="คงความอบอุ่นของเสียงร้องชาย พร้อมดันความชัดให้ลอยเหนือวงดนตรี",
        why=(
            "ตัดย่านต่ำกว่า 85 Hz เพื่อกันเสียงอืดและ ป้องกันลำโพงซับ",
            "ลดย่าน 250 Hz เล็กน้อยเพื่อไม่ให้เสียงร้องกลบเบส",
            "เพิ่มย่าน 2.5 kHz เพื่อให้เนื้อเสียงร้องทะลุผ่านวง",
            "เพิ่มย่านสูงเล็กน้อยให้เสียงเปิด โดยไม่เกิดเสียงซิบบิแลนซ์",
            "คอมเพรสเซอร์ปานกลางช่วยคุมระดับเสียงร้องตลอดเพลง",
        ),
        eq_low_db=-1.0,
        eq_low_mid_db=-1.5,
        eq_hi_mid_db=2.0,
        eq_hi_db=1.5,
        low_cut_hz=85.0,
        compressor_percent=35.0,
    ),
    "th-vocal-female": ThaiPreset(
        id="th-vocal-female",
        name="เสียงร้องสด (หญิง)",
        category="ร้อง",
        summary="เสียงร้องใส โปร่ง ไม่บาดหู พร้อมคุมย่านความถี่ที่ทำให้เกิดเสียงแหลมแข็ง",
        why=(
            "ตัดย่านต่ำกว่า 110 Hz เพื่อเคลียร์ย่านต่ำที่ไม่มีเนื้อเสียงร้องหญิง",
            "ลดย่าน 400 Hz เล็กน้อยเพื่อลดความหนาในห้องเล็ก",
            "เพิ่มย่าน 3 kHz เบา ๆ เพื่อความชัด โดยไม่ทำให้เสียงบาด",
            "เพิ่มย่านสูงแบบพอดี และปล่อยให้ EQ 4 แบนด์ทำงานร่วมกับรีเวิร์บ",
            "คอมเพรสเซอร์ปานกลางเพื่อคุมเสียงดัง–ค่อยตามธรรมชาติ",
        ),
        eq_low_db=-2.0,
        eq_low_mid_db=-0.5,
        eq_hi_mid_db=2.0,
        eq_hi_db=1.0,
        low_cut_hz=110.0,
        compressor_percent=30.0,
    ),
    "th-vocal-harmony": ThaiPreset(
        id="th-vocal-harmony",
        name="เสียงร้องประสาน",
        category="ร้อง",
        summary="จัดเสียงประสานให้อยู่ด้านหลังเสียงร้องนำ โดยไม่แย่งย่านความถี่กัน",
        why=(
            "ตัดย่านต่ำกว่า 120 Hz เพื่อไม่ให้เสียงประสานทับย่านเบสและเสียงนำ",
            "ลดย่านต่ำและกลางต่ำลง เพื่อเปิดพื้นที่ให้เสียงร้องนำ",
            "เพิ่มความชัดเพียงเล็กน้อย ให้ยังได้ยินคำร้องครบ",
            "คอมเพรสเซอร์สูงขึ้นเล็กน้อยเพื่อให้ระดับเสียงประสานนิ่งเสมอกัน",
        ),
        eq_low_db=-2.5,
        eq_low_mid_db=-2.0,
        eq_hi_mid_db=1.0,
        eq_hi_db=0.5,
        low_cut_hz=120.0,
        compressor_percent=40.0,
    ),
    "th-acoustic-di": ThaiPreset(
        id="th-acoustic-di",
        name="กีตาร์โปร่ง (DI)",
        category="เครื่องดนตรี",
        summary="ลดความแข็งของสัญญาณ Piezo และทำให้เสียงกีตาร์โปร่งกลมกล่อมขึ้น",
        why=(
            "ตัดย่านต่ำกว่า 80 Hz ซึ่งเป็นย่านที่ไม่มีเนื้อเสียงกีตาร์จริง",
            "ลดย่านต่ำเพื่อลดเสียง boom จากตัวกล่องเมื่อเล่นใกล้ลำโพง",
            "ลดย่าน 250–400 Hz เล็กน้อยเพื่อลดความแข็งของปิ๊กอัพ",
            "เพิ่มย่าน 3 kHz เบา ๆ ให้ได้ยินรายละเอียดของการเกา",
            "คอมเพรสเซอร์ต่ำเพื่อรักษาไดนามิกของการตีคอร์ด",
        ),
        eq_low_db=-3.0,
        eq_low_mid_db=-1.0,
        eq_hi_mid_db=1.0,
        eq_hi_db=1.5,
        low_cut_hz=80.0,
        compressor_percent=15.0,
    ),
    "th-electric-clean": ThaiPreset(
        id="th-electric-clean",
        name="กีตาร์ไฟฟ้าคลีน",
        category="เครื่องดนตรี",
        summary="โทนคลีนที่อยู่ในช่องของตัวเอง ไม่กลบเสียงร้องหรือเบส",
        why=(
            "ตัดย่านต่ำกว่า 100 Hz เพื่อไม่ให้กีตาร์แย่งพื้นที่เบส",
            "ลดย่านต่ำเล็กน้อยเพื่อลดความอืดเวลาตีคอร์ดเปิดสาย",
            "เพิ่มย่าน 2.5 kHz ให้โน้ตแตกตัวชัดเมื่อเล่นร่วมกับวง",
            "คอมเพรสเซอร์เบา ๆ ช่วยให้ระดับเสียงสมดุลระหว่างตีคอร์ดกับเล่นไลน์",
        ),
        eq_low_db=-2.0,
        eq_low_mid_db=0.0,
        eq_hi_mid_db=1.5,
        eq_hi_db=1.0,
        low_cut_hz=100.0,
        compressor_percent=20.0,
    ),
    "th-bass-di": ThaiPreset(
        id="th-bass-di",
        name="เบสไฟฟ้า (DI)",
        category="เครื่องดนตรี",
        summary="ฐานเสียงต่ำที่กระชับ เว้นย่านกลางให้เสียงร้องและกีตาร์",
        why=(
            "ตัดย่านต่ำมาก ๆ ทิ้ง (30 Hz) เพราะต่ำกว่านั้นมีแต่เสียงรบกวน ไม่ใช่เนื้อเบส",
            "เสริมย่านต่ำเล็กน้อยให้ฐานเสียงแน่น",
            "ลดย่าน 250–300 Hz เพื่อไม่ให้เบสขุ่นและกลบเสียงร้อง",
            "ลดย่านสูงลงเล็กน้อยเพื่อให้เบสอยู่ใต้เครื่องดนตรีอื่น",
            "คอมเพรสเซอร์ค่อนข้างสูงเพื่อให้โน้ตทุกตัวดังใกล้เคียงกัน",
        ),
        eq_low_db=1.5,
        eq_low_mid_db=-2.0,
        eq_hi_mid_db=0.0,
        eq_hi_db=-1.0,
        low_cut_hz=30.0,
        compressor_percent=40.0,
    ),
    "th-keys-stereo": ThaiPreset(
        id="th-keys-stereo",
        name="คีย์บอร์ดสเตอรีโอ",
        category="เครื่องดนตรี",
        summary="โทนคีย์บอร์ดที่สะอาดและกลมกลืน ไม่แย่งพื้นที่ย่านกลางของเสียงร้อง",
        why=(
            "ตัดย่านต่ำกว่า 60 Hz เพื่อลดเสียงอืดจากเสียงเปียโน/แพด",
            "ลดย่านต่ำและกลางต่ำเล็กน้อยเพื่อเปิดพื้นที่ให้เสียงร้อง",
            "เพิ่มย่านสูงเล็กน้อยให้เสียงโปร่ง",
            "คอมเพรสเซอร์ต่ำเพื่อรักษาการเคลื่อนไหวของเสียงแพด",
        ),
        eq_low_db=-1.5,
        eq_low_mid_db=-1.0,
        eq_hi_mid_db=0.5,
        eq_hi_db=0.5,
        low_cut_hz=60.0,
        compressor_percent=15.0,
    ),
    "th-bgm": ThaiPreset(
        id="th-bgm",
        name="BGM เปิดงาน / ดนตรีพื้นหลัง",
        category="เล่นกลับ (BGM)",
        summary="ดนตรีพื้นหลังที่ฟังสบายและไม่บดบังการพูดคุยหรือพิธีบนเวที",
        why=(
            "ตัดย่านต่ำกว่า 70 Hz เพื่อลดเสียงก้องในห้องและ protect ซับ",
            "ลดย่านกลางต่ำลงเล็กน้อยเพื่อให้เสียงพูดทับได้ชัด",
            "ลดย่านสูงเล็กน้อยเพื่อไม่ให้เพลงบาดหูระหว่างพิธี",
            "คอมเพรสเซอร์ปานกลางเพื่อให้ระดับเพลงสม่ำเสมอตลอดงาน",
        ),
        eq_low_db=-1.0,
        eq_low_mid_db=-1.5,
        eq_hi_mid_db=0.0,
        eq_hi_db=-0.5,
        low_cut_hz=70.0,
        compressor_percent=30.0,
    ),
    "th-flat-reset": ThaiPreset(
        id="th-flat-reset",
        name="รีเซ็ต EQ (Flat)",
        category="รีเซ็ต",
        summary="คืนค่า EQ ทั้ง 4 แบนด์เป็น 0 dB ปิด Low Cut และปิด Compressor",
        why=(
            "ใช้เมื่อต้องการเริ่มต้นใหม่จากโทนเสียงกลาง ๆ ของช่องนั้น",
            "ทุกค่าเป็นค่ากลาง ไม่มีการลดหรือเพิ่มใด ๆ",
            "ไม่แตะ Gain, +48V, Fader, Pan และ Sends",
        ),
        eq_low_db=0.0,
        eq_low_mid_db=0.0,
        eq_hi_mid_db=0.0,
        eq_hi_db=0.0,
        low_cut_hz=20.0,          # raw 0 = low cut OFF on the FLOW 8
        compressor_percent=0.0,
    ),
}


def list_thai_presets(category: Optional[str] = None) -> list[ThaiPreset]:
    """All clean-room presets, optionally filtered by Thai category."""
    items = list(THAI_PRESETS.values())
    if category and str(category).strip() not in ("", "all"):
        items = [p for p in items if p.category == category]
    return items


def get_thai_preset(preset_id: str) -> Optional[ThaiPreset]:
    return THAI_PRESETS.get(str(preset_id))