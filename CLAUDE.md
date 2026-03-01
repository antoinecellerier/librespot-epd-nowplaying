# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A librespot event handler that displays now playing track information on a WaveShare EPD 7.3" Spectra 6 (E6) color e-paper screen. The script is invoked by librespot via the `--onevent` flag when playback events occur.

## Testing

Run the test script which simulates a track_changed event with mock environment variables:
```bash
./test
```

To test horizontal layout mode:
```bash
./test --horizontal
```

See `LOCAL_DEV.md` (gitignored) for remote device deployment and testing instructions.

## Documentation

When making changes, keep documentation up to date:
- `CLAUDE.md` - Architecture, commands, and development guidance
- `LOCAL_DEV.md` - Remote device deployment and testing workflows

## Architecture

**nowplaying.py** - Single-file application that:
1. Parses librespot event data from environment variables (`PLAYER_EVENT`, `NAME`, `ALBUM`, `ARTISTS`, `COVERS`, etc.)
2. Downloads album cover art and extracts a color theme using ColorThief
3. Renders track info and cover art to an image using PIL
4. Displays on the e-paper screen via omni-epd

Key layout modes:
- Portrait (default): Cover at bottom, text at top
- Horizontal (`--horizontal`): Cover on right, text column on left (vertically centered)

### Cover Art Cache

Album cover art, resized images, and color themes are cached in `$XDG_CACHE_HOME/nowplaying/` (defaults to `~/.cache/nowplaying/`) to avoid expensive recomputation on the Pi Zero (~4s uncached vs ~0.05s cached).

Per cover URL (keyed by SHA256 hash):
- `{hash}_{coversize}.jpg` - pre-resized cover image for the target display size
- `{hash}.json` - theme colors (bg/fg/fg2) and track metadata (name, album, artists, duration)

The cache has no eviction policy; entries accumulate but are small (one JPEG + one JSON per unique cover).

### EPD-Aware Contrast Checking

The 6-color e-ink display (black, white, red, green, blue, yellow) renders colors very differently from an RGB monitor — e.g., dark grays render as black, cyan and blue are indistinguishable. Theme color contrast checks use `epd_perceived_color()` which simulates display rendering by quantizing a swatch to the 6-color palette with Floyd-Steinberg dithering, then averaging the result. This ensures the WCAG contrast ratio reflects what the display actually shows, not the raw RGB values.

### Idle Art Display

When Spotify is not playing, the script displays random art from `~/art/`:
- **Heartbeat file** (`/tmp/spotify-playing`): Written on `track_changed` and `playing` events, removed on `paused`/`stopped`
- **`--idle` flag**: Check heartbeat; if missing or stale (>10 min), display random art from `~/art/`
- **`--clear` flag**: Clear the screen (for scheduled maintenance)
- **`--image <path>` flag**: Display a specific image (for testing)
- On pause/stop events, idle art is displayed automatically instead of blanking

Recommended cron jobs on pizero:
```
# Hourly idle art refresh
0 * * * * source ~/stuff/venv/bin/activate && python ~/stuff/screen/nowplaying.py --idle

# Daily screen clear at 4 AM (e-paper longevity)
0 4 * * * source ~/stuff/venv/bin/activate && python ~/stuff/screen/nowplaying.py --clear
```

## Dependencies

- omni-epd: E-paper display abstraction layer
- PIL/Pillow: Image creation and manipulation
- colorthief: Extract color palette from album art for theming
