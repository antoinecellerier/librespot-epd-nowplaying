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

## Dependencies

- omni-epd: E-paper display abstraction layer
- PIL/Pillow: Image creation and manipulation
- colorthief: Extract color palette from album art for theming
