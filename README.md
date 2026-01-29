A very naive librespot event handler which displays now playing track information on a WaveShare EPD 7.3" Spectra 6 (E6) color epaper/eink screen

(Initial versions used an WaveShare EPD 7.5" red / black / white screen)

![Now playing screen - epd7in3e](photos/final-epd7in3e-1.jpg)

Uses:
 * librespot: https://github.com/librespot-org/librespot/ (requires dev branch / version 5.0 events)
 * omni-epd: https://github.com/robweber/omni-epd/
 * WaveShare 7.3inch E Ink Spectra 6 (E6) Full Color E-Paper Display: https://www.waveshare.com/7.3inch-e-paper-hat-e.htm

## Features

- Displays track name, album, artists, and duration with album art
- Extracts color theme from album cover for dynamic styling
- Supports portrait (default) and horizontal (`--horizontal`) layouts
- Idle art display: shows random images from `~/art/` when not playing

## Command-line options

| Flag | Description |
|------|-------------|
| `--horizontal` | Use horizontal layout (cover on right, text on left) |
| `--idle` | Display random art from `~/art/` if not playing |
| `--clear` | Clear the screen |
| `--image <path>` | Display a specific image (for testing) |

## Idle art display

When Spotify playback stops, the screen displays a random image from `~/art/` instead of going blank. A heartbeat file (`/tmp/spotify-playing`) tracks playback state, allowing cron jobs to refresh the display even after crashes or reboots.

Recommended cron jobs:
```
# Hourly idle art refresh
0 * * * * source ~/venv/bin/activate && python ~/screen/nowplaying.py --idle

# Daily screen clear at 4 AM (e-paper longevity)
0 4 * * * source ~/venv/bin/activate && python ~/screen/nowplaying.py --clear
```

![Now playing screen 2 - epd7in3e](photos/final-epd7in3e-2.jpg)
![Now playing screen 3 - epd7in3e](photos/final-epd7in3e-3.jpg)
![Now playing screen 1 - epd7in5b](photos/final-epd7in5b-1.jpg)
![Now playing screen 2 - epd7in5b](photos/final-epd7in5b-2.jpg)
![Now playing screen demo - epd7in5b](photos/demo-epd7in5b.jpg)
