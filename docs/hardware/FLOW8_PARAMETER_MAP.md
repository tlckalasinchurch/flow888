# Phase 3: Behringer FLOW 8 Parameter Mapping & Conversions

**Document ID:** `FLOW8_PARAMETER_MAP`  
**Purpose:** Exact mathematical conversion functions between physical audio engineering units and 7-bit MIDI CC values (`0..127`).

---

## 1. Fader & Level Taper (Volume)

Audio faders require logarithmic-style non-linear tapering to provide fine resolution around unity gain ($0 \text{ dB}$).

### Mathematical Formulas:
- **MIDI $\to$ Decibels:**
  $$\text{dB} = \begin{cases}
  -\infty & \text{if } \text{MIDI} = 0 \\
  -70.0 + \left(\frac{\text{MIDI} - 1}{126}\right) \times 80.0 & \text{if } 1 \le \text{MIDI} \le 127
  \end{cases}$$
  - $\text{MIDI} = 0 \implies \text{OFF} (-\infty \text{ dB})$
  - $\text{MIDI} = 1 \implies -70.0 \text{ dB}$
  - $\text{MIDI} = 111 \implies 0.0 \text{ dB}$ (Unity Gain)
  - $\text{MIDI} = 127 \implies +10.0 \text{ dB}$ (Max Boost)

- **Decibels $\to$ MIDI:**
  $$\text{MIDI} = \begin{cases}
  0 & \text{if } \text{dB} \le -70.0 \\
  \text{round}\left(1 + \frac{\text{dB} + 70.0}{80.0} \times 126\right) & \text{if } -70.0 < \text{dB} \le +10.0
  \end{cases}$$

---

## 2. Preamp Gain (Channels 1–4)

Preamplifier gain maps linearly across $-20.0 \text{ dB}$ to $+60.0 \text{ dB}$ ($80.0 \text{ dB}$ span):

$$\text{Gain}_{\text{dB}} = -20.0 + \left(\frac{\text{MIDI}}{127}\right) \times 80.0$$

$$\text{MIDI} = \text{round}\left(\frac{\text{Gain}_{\text{dB}} + 20.0}{80.0} \times 127\right)$$

- $\text{MIDI} = 0 \implies -20.0 \text{ dB}$
- $\text{MIDI} = 32 \implies 0.0 \text{ dB}$ (Line level reference)
- $\text{MIDI} = 127 \implies +60.0 \text{ dB}$ (Full mic boost)

---

## 3. Parametric EQ Bands (Channels 1–7)

4-Band Parametric EQ on FLOW 8 uses 7-bit continuous gain values:

$$\text{EQ Gain}_{\text{dB}} = -15.0 + \left(\frac{\text{MIDI}}{127}\right) \times 30.0$$

- $\text{MIDI} = 0 \implies -15.0 \text{ dB}$ (Full cut)
- $\text{MIDI} = 64 \implies 0.0 \text{ dB}$ (Flat response)
- $\text{MIDI} = 127 \implies +15.0 \text{ dB}$ (Full boost)

---

## 4. Low Cut Filter (Channels 1–4)

Low cut filter frequency ranges logarithmically from $20 \text{ Hz}$ to $600 \text{ Hz}$:

$$f_{\text{Hz}} = 20.0 \times \left(\frac{600.0}{20.0}\right)^{\frac{\text{MIDI}}{127}}$$

- $\text{MIDI} = 0 \implies 20 \text{ Hz}$ (Sub-audible)
- $\text{MIDI} = 64 \implies \approx 110 \text{ Hz}$ (Standard speech HPF)
- $\text{MIDI} = 127 \implies 600 \text{ Hz}$

---

## 5. Pan & Stereo Balance (Channels 1–7)

Pan positions are mapped symmetrically:

$$\text{Pan Position} = \begin{cases}
100\% \text{ Left} & \text{if } \text{MIDI} = 0 \\
\text{Center} & \text{if } \text{MIDI} = 64 \\
100\% \text{ Right} & \text{if } \text{MIDI} = 127
\end{cases}$$

---

## 6. 1-Knob Dynamics Compressor (Channels 1–4)

Compressor intensity maps linearly from $0\%$ (Bypass) to $100\%$ (Heavy Compression):

$$\text{Comp \%} = \min\left(100.0, \frac{\text{MIDI}}{100} \times 100.0\right)$$
Values above 100 are safely clamped to $100\%$.
