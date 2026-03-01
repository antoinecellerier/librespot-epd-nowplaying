# Custom LUT Research for WaveShare 7.3" Spectra 6 (E6)

## Display Timing Breakdown (Pi Zero)

| Step | Time |
|------|------|
| Python imports | 1.4s |
| Driver load + prepare | 0.6s |
| getbuffer (quantize + pack) | 0.4s |
| SPI transfer | 0.4s |
| **E-ink hardware refresh** | **17.2s** |
| **Total** | **~20s** |

The 17.2s hardware refresh is the bottleneck. Everything else is already optimized.

## Controller IC

- **Panel:** GDEP073E01 (ED2208-GCA / EL073TF1U5)
- **IC:** Undisclosed variant of Solomon Systech **SPD1656** or UltraChip UC8159
- **SRAM:** 192KB (single frame buffer, 800x480x4bpp)
- **OTP:** 96KB (factory waveforms + config)
- **Datasheets:**
  - SPD1656: https://www.waveshare.com/w/upload/b/bf/SPD1656_1.1.pdf
  - UC8159c: https://cursedhardware.github.io/epd-driver-ic/UC8159c.pdf
- **OTP dump + reverse engineering:** https://gist.github.com/codeart1st/dfa41e6426388dc929c719c4913297e3

## Custom LUT Support

The controller **does support custom waveforms** via register writes.

### Enabling Custom LUTs

Set **PSR register (0x00), byte B, bit 7 (`LUT_SEL`)** to 1:
- `0`: LUT from flash/OTP (default)
- `1`: LUT from register (custom)

### LUT Write Commands

| Command | Name | Size | Purpose |
|---------|------|------|---------|
| 0x20 | LUTC | 220 bytes (20 groups x 11) | VCOM waveform |
| 0x21 | LUTB | 260 bytes (20 groups x 13) | Black source waveform |
| 0x22 | LUTW | 260 bytes (20 groups x 13) | White source waveform |
| 0x23 | LUTG1 | 260 bytes (20 groups x 13) | Gray1 source waveform |
| 0x24 | LUTG2 | 260 bytes (20 groups x 13) | Gray2 source waveform |
| 0x25 | LUTR0 | 260 bytes (20 groups x 13) | Red 0 source waveform |
| 0x26 | LUTR1 | 260 bytes (20 groups x 13) | Red 1 source waveform |
| 0x27 | LUTR2 | 260 bytes (20 groups x 13) | Red 2 source waveform |
| 0x28 | LUTR3 | 260 bytes (20 groups x 13) | Red 3 source waveform |
| 0x29 | LUTXON | 200 bytes (20 groups x 10) | Gate XON waveform |

### Source LUT Structure (LUTB/LUTW/LUTG1/LUTG2/LUTR0-3)

Each LUT = 20 groups (one per temperature range), each group = 13 bytes:

```
Byte 0:     RP[7:0]  - Repeat count (0x00 = end of LUT, 0x01 = 1x, 0x02 = 2x, ... 0xFF = 255x)
Bytes 1-2:  1st-4th LVL[2:0] - Voltage level for phases 1-4 (packed, 2 bits each)
Bytes 3-4:  5th-8th LVL[2:0] - Voltage level for phases 5-8
Bytes 5-12: 1st-8th TP[7:0]  - Frame count for each phase (0x00 = skip, 0x01 = 1 frame, ... 0xFF = 255 frames)
```

Source voltage levels (LVL[2:0]):
- 000: VSS (ground)
- 001: VSH (positive high)
- 010: VSL (negative high)
- 011: VSH_LV (positive low)
- 100: VSL_LV (negative low)
- 101: VSL_LV2 (negative low 2)
- 110: Reserved
- 111: HIZ (high impedance / floating)

### VCOM LUT Structure (LUTC)

Each group = 11 bytes:

```
Byte 0:     RP[7:0]  - Repeat count
Bytes 1-2:  1st-4th LVL[1:0] - VCOM level for phases 1-4
Byte 3:     (unused)
Bytes 4-11: 1st-8th TP[7:0]  - Frame count per phase
```

VCOM voltage levels (LVL[1:0]):
- 00: VCOM_DC
- 01: VSH + VCOM_DC (VCOMH)
- 10: VSL + VCOM_DC (VCOML)
- 11: HIZ (floating, for last phase end level control)

### PLL Control (0x30)

Controls frame rate. Default POR = 0x3C (50Hz). Current driver sends 0x03.

| Value | Frame Rate |
|-------|-----------|
| 0x00 | 12.5 Hz |
| 0x01 | 25 Hz |
| ... | ... |
| 0x0E | 187.5 Hz |
| 0x0F | 200 Hz |
| 0x39 | 200 Hz |
| 0x3A | 100 Hz |
| 0x3C | 50 Hz |

Higher frame rate = each TP frame count completes faster = faster total refresh.

### Partial Window Update (WINM 0x14 + WHRES 0x15 + WVRES 0x16)

Can define a sub-region to refresh:
- Source output within window follows LUT[0x21-0x28]
- Source output outside window follows LUTC[0x20]
- Could refresh only the text area without re-driving album art

## OTP Waveform Structure

The 96KB OTP contains (per the LUT definition table in the datasheet):

| Address Range | Size | Content |
|--------------|------|---------|
| 0-20799 | 20800 (2080 x 10 temps) | Source waveform LUTs |
| 20800-22999 | 2200 (220 x 10 temps) | VCOM LUT |
| 23000-24999 | 2000 (200 x 10 temps) | XON LUT |
| 25000-25001 | 2 | Reserved |
| 25002-25010 | 9 | Temperature boundaries (TB0-TB8) |
| 25011-25030 | 20 | Per-temp VSHC/VSLC voltage levels |
| 25031-25040 | 10 | Per-temp VSL_LV2 settings |
| 25041-25599 | 559 | TBD |
| 25600 | 1 | VCM_DC |
| 25601-25615 | 15 | TBD |
| 25616-25625 | 10 | Per-temp frame rate (PLL) |

## Partial Screen Refresh Analysis

### Why Partial Refresh Matters

When playing an album, only the text (track name, duration) changes between tracks — the cover art
and color theme stay identical. A partial refresh of just the text area could dramatically reduce update time.

### How E-Paper Refresh Timing Works

The display refresh scans **gate lines sequentially** (480 physical gate rows). For each gate line,
all 800 source channels apply their waveform voltage simultaneously. Total refresh time is:

```
time = num_gate_rows × waveform_phases × frames_per_phase × (1 / PLL_frame_rate)
```

**Key insight:** Reducing the number of gate rows scanned (via WVRES window) proportionally reduces
refresh time. Reducing source columns (HRES window) does NOT save time — all gates still scan.

### Physical Display Geometry

- **Physical panel:** 800 sources (horizontal) × 480 gates (vertical)
- **Landscape/horizontal mode:** 800×480 logical = 800×480 physical (no rotation)
- **Portrait mode:** 480×800 logical → rotated 90° → 800×480 physical

### Rotation Impact on Partial Refresh

The Waveshare driver rotates portrait images 90° CCW via `image.rotate(90)`:

| Logical (portrait) | Physical (after rotation) |
|---|---|
| Y axis (vertical, 0-799) | Source axis (horizontal, 800 columns) |
| X axis (horizontal, 0-479) | Gate axis (vertical, 480 rows, inverted) |

This means:
- **Portrait mode:** Text area (top of logical image, small Y) maps to LEFT **source** columns.
  Text spans full logical width (X: 0-479) → covers ALL gate rows. **No gate savings possible.**
- **Horizontal mode:** Text column (left side, X: 0-319) maps to source columns 0-319.
  Text spans full height (Y: 0-479) → covers ALL gate rows. **No gate savings possible.**

**Neither current layout orientation benefits from gate-windowed partial refresh.**

### Layout Redesign for Partial Refresh

To exploit gate windowing, the text area must span a **subset of gate rows** (physical vertical axis)
while spanning the full source width (physical horizontal axis). This means:

**Landscape layout with text on top, cover below (no rotation):**
```
+--------------------------------------------------+
| Track Name                   (gate rows 0-159)   |  ← text band: 160 rows
| Album · Artist · 3:42                            |
+--------------------------------------------------+
|                                                  |
|              [ Album Cover ]     (rows 160-479)  |  ← cover band: 320 rows
|                                                  |
+--------------------------------------------------+
        800 source columns (full width)
```

- Text window: WVRES rows 0-159 → 160/480 = 33% of gates → **~5.7s** (vs 17s full)
- First display of a new album: full refresh (17s) to draw cover + text
- Subsequent tracks on same album: partial refresh of text band only (~5.7s)

**Alternative: portrait with text on LEFT physical side:**
```
Physical 800×480, text in left gate rows (smallest gate indices):
- Rotate so text maps to gate rows 0-159, cover to 160-479
- Requires changing the rotation from 90° CCW to custom mapping
```

### IC Support Status

| Feature | SPD1656 | UC8159 | Actual IC (ED2208-GCA) |
|---------|---------|--------|----------------------|
| Partial window command | WINM (0x14) + WHRES (0x15) + WVRES (0x16) | Not documented | PTLW (0x83) — **undocumented** |
| Gate window (WVRES) | Yes — limits gate scanning range | Unknown | Unknown |
| Source window (HRES) | Yes — changes source output only | Unknown | Unknown |
| LUT_SEL (register LUT) | PSR B[7] | PSR B[7] | Likely same |

- GxEPD2 marks this panel as `hasPartialUpdate = false`, `hasFastPartialUpdate = false`
- The `refresh(x, y, w, h)` method just does a full refresh — no windowing is implemented
- Command 0x83 (PTLW) exists on this IC but parameters are unknown
- **Nobody has published partial refresh results on any 6-color Spectra panel**

### Same-Album Detection

Even without hardware partial refresh, detecting same-album track changes is useful
for skipping theme extraction and reducing perceived latency:

```python
# In draw_now_playing(), detect same cover URL as last display
LAST_COVER_FILE = Path("/tmp/nowplaying-last-cover")

def is_same_album(cover_url):
    try:
        return LAST_COVER_FILE.read_text().strip() == cover_url
    except (OSError, ValueError):
        return False

# On same album: skip cover download/theme/resize (already cached)
# On new album: full refresh needed anyway
# Future: if partial refresh works, only send text data + partial DRF
```

### Testing Plan for Command 0x83 (PTLW)

Since 0x83 is undocumented, experimental testing is needed:

1. **Probe parameter count:** Send 0x83 with increasing data bytes, check BUSY_N behavior
2. **Try SPD1656-like parameters:** WINM format (1 byte enable), then WHRES/WVRES-like
   window coordinates
3. **Try UC8159-like approach:** Single command with packed start/end coordinates
4. **Monitor with logic analyzer:** If available, capture SPI traffic during normal refresh
   to see if the factory firmware ever uses 0x83 internally

### Fallback: Software-Only Partial Optimization

If hardware partial refresh doesn't work, a software-only approach still helps:

1. **Same-album detection** — skip redundant cover/theme processing
2. **Keep EPD powered on** between same-album tracks (skip PON/POF: saves ~0.4s)
3. **Pre-render next track** — if `preload_next` event fires, start rendering the next image
4. **Non-blocking refresh** — send image data, trigger DRF, exit without waiting for BUSY_N.
   The display refreshes while the script exits. Next invocation waits if still busy.

## Strategy for Faster Refresh

### Phase 1: Software optimizations (no hardware risk)

1. **Same-album detection** — skip cover processing on same-album track changes
2. **Non-blocking display** — trigger refresh and exit, don't wait 17s
3. **Keep EPD initialized** — daemon mode or skip PON/POF between rapid track changes

### Phase 2: Custom LUT waveforms (moderate risk)

4. **Decode OTP waveforms** — Parse the 96KB dump into the LUT structures above
5. **Analyze phase structure** — Understand how many phases/frames the factory waveform uses
6. **Create shortened "draft" waveforms** — Fewer phases, fewer frames per phase
7. **Increase PLL frame rate** — Push from current setting toward 200Hz
8. **Write via register** — Set LUT_SEL=1, send custom LUTs via 0x20-0x29

### Phase 3: Partial refresh (experimental, higher risk)

9. **Probe command 0x83** — Determine PTLW parameters experimentally
10. **Redesign layout for gate windowing** — Text in contiguous gate row band
11. **Implement partial refresh path** — Only send + refresh text area on same-album skips

### Expected Results

| Optimization | Time Saved | Risk |
|---|---|---|
| Non-blocking refresh | 17s script time (display still takes 17s) | None |
| Same-album detection | Skip 0.05s cache lookup overhead | None |
| Custom LUT (shortened) | 3-7s off refresh (target 10-14s) | Medium — ghosting |
| Increased PLL | ~1-3s off refresh | Low |
| Partial window (text only, ~33% gates) | ~11s off refresh (target ~6s) | High — untested |
| Combined LUT + partial | Target **~4-6s** for same-album skips | High |

### Risks

- Bad waveforms cause ghosting, wrong colors, or stuck pigment particles
- The actual IC may differ from SPD1656 in undocumented ways
- No published examples of custom LUTs or partial refresh for 6-color Spectra panels
- Panel damage unlikely but possible with extreme voltage/timing parameters
- Command 0x83 parameters are completely unknown — could brick display state (recoverable via reset)

## References

### Datasheets
- SPD1656 (closest match): https://www.waveshare.com/w/upload/b/bf/SPD1656_1.1.pdf
- UC8159c (other candidate): https://cursedhardware.github.io/epd-driver-ic/UC8159c.pdf

### Reverse Engineering
- OTP dump + command table: https://gist.github.com/codeart1st/dfa41e6426388dc929c719c4913297e3
- Understanding ACeP technology: https://hackaday.io/project/179058-understanding-acep-tecnology

### Libraries
- GxEPD2 (Arduino, reference impl): https://github.com/ZinggJM/GxEPD2
  - Panel source: `src/epd7c/GxEPD2_730c_GDEP073E01.cpp` — `hasPartialUpdate = false`
- Adafruit CircuitPython SPD1656: https://github.com/adafruit/Adafruit_CircuitPython_SPD1656
- LUT playground tool (B/W, but educational): https://github.com/nlimper/LUT-playground

### Hardware
- Waveshare product page: https://www.waveshare.com/7.3inch-e-paper-hat-e.htm
- Waveshare wiki: https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT_(E)_Manual

### Community
- Forum discussion on refresh rate: https://forum.core-electronics.com.au/t/7-3-6-color-epd-refresh-rate-ws-27875/23398
- Ben Krasnow fast partial refresh (B/W, educational): https://benkrasnow.blogspot.com/2017/10/fast-partial-refresh-on-42-e-paper.html
- Glider open-source e-ink monitor: https://github.com/Modos-Labs/Glider
