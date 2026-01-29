#!/usr/bin/env python
import argparse
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
import urllib.request

from omni_epd import displayfactory
from PIL import Image, ImageDraw, ImageFont
from colorthief import ColorThief

parser = argparse.ArgumentParser()
parser.add_argument('--horizontal', action='store_true', help='Use horizontal layout')
parser.add_argument('--idle', action='store_true', help='Display idle art if not playing')
parser.add_argument('--clear', action='store_true', help='Clear the screen')
parser.add_argument('--image', type=str, help='Display a specific image (for testing)')
args = parser.parse_args()

HEARTBEAT_FILE = Path("/tmp/spotify-playing")
HEARTBEAT_TIMEOUT = 600  # 10 minutes in seconds
ART_FOLDER = Path.home() / "art"

player_event = os.getenv('PLAYER_EVENT')

def open_epd():
    epd = displayfactory.load_display_driver("waveshare_epd.epd7in3e")

    epd.prepare()
    epd.mode = 'color'

    return epd

def clear_screen():
    print("Clear screen")
    epd = open_epd()
    epd.clear()
    epd.close()


def write_heartbeat():
    """Write current timestamp to heartbeat file."""
    HEARTBEAT_FILE.write_text(str(time.time()))
    print(f"Heartbeat written to {HEARTBEAT_FILE}")


def remove_heartbeat():
    """Remove heartbeat file."""
    if HEARTBEAT_FILE.exists():
        HEARTBEAT_FILE.unlink()
        print(f"Heartbeat removed: {HEARTBEAT_FILE}")


def is_playing():
    """Check if music is currently playing (heartbeat exists and is recent)."""
    if not HEARTBEAT_FILE.exists():
        return False
    try:
        heartbeat_time = float(HEARTBEAT_FILE.read_text().strip())
        age = time.time() - heartbeat_time
        return age < HEARTBEAT_TIMEOUT
    except (ValueError, OSError):
        return False


def display_idle_art(image_path=None):
    """Display a specific image, random image from art folder, or placeholder."""
    print("Display idle art")
    epd = open_epd()

    horizontal = args.horizontal
    if horizontal:
        width = epd.width
        height = epd.height
    else:
        width = epd.height
        height = epd.width

    image = Image.new("RGB", (width, height), (0, 0, 0))

    # Determine which image to display
    art_path = None
    if image_path:
        art_path = Path(image_path)
        if not art_path.exists():
            print(f"Image not found: {art_path}")
            art_path = None
    else:
        # Look for images in art folder
        art_images = []
        if ART_FOLDER.exists():
            for ext in ('*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp'):
                art_images.extend(ART_FOLDER.glob(ext))
                art_images.extend(ART_FOLDER.glob(ext.upper()))
        if art_images:
            art_path = random.choice(art_images)

    if art_path:
        print(f"Displaying: {art_path}")
        try:
            art = Image.open(art_path)
            # Scale and crop to fit screen
            art_ratio = art.width / art.height
            screen_ratio = width / height

            if art_ratio > screen_ratio:
                # Image is wider than screen, fit by height
                new_height = height
                new_width = int(height * art_ratio)
            else:
                # Image is taller than screen, fit by width
                new_width = width
                new_height = int(width / art_ratio)

            art = art.resize((new_width, new_height), Image.Resampling.LANCZOS)
            # Center crop
            left = (new_width - width) // 2
            top = (new_height - height) // 2
            art = art.crop((left, top, left + width, top + height))
            image = art.convert("RGB")
        except Exception as e:
            print(f"Error loading art: {e}")
            # Fall through to placeholder
    else:
        # No art available, show placeholder
        print("No art found, showing placeholder")
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        except OSError:
            font = ImageFont.load_default()
        text = "No art in ~/art/"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        draw.text((x, y), text, fill=(255, 255, 255), font=font)

    epd.display(image)
    epd.close()

def get_theme(cover_path):
    ct = ColorThief(cover_path)
    # This returns color_count +1 colors
    # quality = 1 best quality but takes 10s+
    p = ct.get_palette(color_count=2, quality=10)
    def luminance(color):
        # https://www.w3.org/TR/WCAG20/#relativeluminancedef
        def normalize(x):
            if x < 0.03928:
                return x/12.92
            return ((x+0.055)/1.055)**2.4
        r = normalize(color[0]/255.)
        g = normalize(color[1]/255.)
        b = normalize(color[2]/255.)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    # https://www.w3.org/TR/UNDERSTANDING-WCAG20/visual-audio-contrast-contrast.html
    def contrast_ratio(l1, l2):
        if l2 < l1:
            return (l1+0.05)/(l2+0.05)
        else:
            return (l2+0.05)/(l1+0.05)

    #print("p", p)
    l = list(map(luminance, p))
    #print("l", l)
    cr01 = contrast_ratio(l[0], l[1])
    cr02 = contrast_ratio(l[0], l[2])
    cr12 = contrast_ratio(l[1], l[2])
    #print("cr01", cr01, "cr02", cr02, "cr12", cr12)

    cr_aa_threshold = 4.5
    if cr01 >= cr_aa_threshold:
        bg = p[0]
        fg = p[1]
        if cr02 >= cr_aa_threshold:
            fg2 = p[2]
        else:
            fg2 = fg
    elif cr02 >= cr_aa_threshold:
        bg = p[0]
        fg = p[2]
        fg2 = fg
    elif cr12 >= cr_aa_threshold:
        bg = p[1]
        fg = p[2]
        fg2 = fg
    else:
        # likely incorrect if p[0] is near the mid point
        bg = (255-p[0][0], 255-p[0][1], 255-p[0][2])
        cr = contrast_ratio(l[0], luminance(bg))
        # if the contrast isn't high enough just go with white / black
        if cr < cr_aa_threshold:
            if l[0] < 0.5:
                bg = (255, 255, 255)
            else:
                bg = (0, 0, 0)
        fg = p[0]
        fg2 = fg

    #print(f"bg  {bg}")
    #print(f"fg  {fg}")
    #print(f"fg2 {fg2}")
    return bg, fg, fg2

def draw_now_playing():
    #print(f"Draw now playing {track_name}")
    epd = open_epd()

    horizontal = args.horizontal
    if horizontal:
        width = epd.width
        height = epd.height
    else:
        width = epd.height
        height = epd.width


    cover_path = "/tmp/cover.jpg"

    #print("downloading cover")
    urllib.request.urlretrieve(covers[0], cover_path)

    #printprint("computing theme")
    bg, fg, fg2 = get_theme(cover_path)

    #print("creating image")
    image = Image.new("RGB", (width, height), bg)

    cover = Image.open(cover_path)
    margin = 0 # cover margin
    if horizontal:
        coversize = height-2*margin
    else:
        coversize = width-2*margin
    cover = cover.resize((coversize, coversize))

    if horizontal:
        image.paste(cover, (width-coversize-margin, (height-cover.height)//2))
        text_width = width - coversize - margin
    else:
        image.paste(cover, (margin, height-cover.height-margin))
        text_width = width

    draw = ImageDraw.Draw(image)
    # setting draw.font doesn't seem to effect the font used when using draw(..., font_size)
    # draw.fontmode = "1" # disable anti aliasing

    #print("adding text")
    x = 0
    # font sizes for: track_name, album, artists, spacer, duration
    font_sizes = [50, 40, 40, 10, 40]
    # total text block height (sum of line heights, minus trailing space on last line)
    text_height = sum(fs * 3 // 2 for fs in font_sizes) - font_sizes[-1] // 2
    if horizontal:
        y = (height - text_height) // 2
    else:
        y = 10

    def get_font(size):
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)

    def t(text, color, font_size, min_font_size=0, stroke=False):
        nonlocal x, y
        #print(f"printing {text}")
        font = get_font(font_size)
        tl = draw.textlength(text, font=font)
        if tl > text_width:
            # try to strip " - 2015 Remaster" or " (2015 Remaster)" suffixes
            text = text.split(" - ")[0].split(" (")[0]
            tl = draw.textlength(text, font=font)
            if tl > text_width:
                # reduce font size within 50-100% range to fit on screen width
                if min_font_size == 0:
                    min_font_size = font_size//2
                font = get_font(max(font_size*text_width//tl, min_font_size))
                tl = draw.textlength(text, font=font)
        x_offset = max((text_width-tl)//2, 0)
        if stroke:
            sw = font_size // 6
            draw.text((x+x_offset, y), text, stroke_width=sw, stroke_fill=color, fill="white", font=font)
        else:
            draw.text((x+x_offset, y), text, fill=color, font=font)
        y += font_size*3//2

    t(track_name, fg, 50, 30)
    t(album, fg2, 40, 30)
    t(", ".join(track_artists), fg, 40, 30)
    t("", fg2, 10)
    t(f"{duration.seconds//60}:{duration.seconds%60:02d}", fg2, 40)

    epd.display(image)

    epd.close()


# Handle command-line flags (--idle, --clear, --image)
if args.clear:
    clear_screen()
elif args.image:
    display_idle_art(args.image)
elif args.idle:
    if is_playing():
        print("Music is playing, skipping idle art refresh")
    else:
        display_idle_art()
elif player_event is None:
    # No event and no flags, nothing to do
    pass

# Handle librespot events
elif player_event in ('session_connected', 'session_disconnected'):
    user_name = os.environ['USER_NAME']
    # os.environ['CONNECTION_ID']

elif player_event == 'session_client_changed':
    # os.environ['CLIENT_ID']
    client_name = os.environ['CLIENT_NAME']
    # os.environ['CLIENT_BRAND_NAME']
    # os.environ['CLIENT_MODEL_NAME']

elif player_event == 'shuffle_changed':
    shuffle = os.environ['SHUFFLE']

elif player_event == 'repeat_changed':
    repeat = os.environ['REPEAT']

elif player_event == 'auto_play_changed':
    auto_play = os.environ['AUTO_PLAY']

elif player_event == 'filter_explicit_content_changed':
    filter_explicit_content = os.environ['FILTER']

elif player_event == 'volume_changed':
    volume = os.environ['VOLUME']

elif player_event in ('seeked', 'position_correction', 'playing', 'paused'):
    print(player_event)
    position_ms = os.environ['POSITION_MS']
    if player_event == 'playing':
        write_heartbeat()
    elif player_event == 'paused':  # paused seems to be what's received at end of playback
        remove_heartbeat()
        display_idle_art()

elif player_event in ('unavailable', 'end_of_track', 'preload_next', 'preloading', 'loading', 'stopped'):
    print(player_event)
    if player_event == 'stopped':  # when librespot stops. not sure if that ever happens
        remove_heartbeat()
        display_idle_art()

elif player_event == 'track_changed':
    print(player_event)
    write_heartbeat()
    item_type = os.environ['ITEM_TYPE']
    # os.environ['TRACK_ID']
    # os.environ['URI']
    track_name = os.environ['NAME']
    duration = timedelta(milliseconds=int(os.environ['DURATION_MS']))
    is_explicit = os.environ['IS_EXPLICIT']
    language = os.environ['LANGUAGE'].split('\n')
    covers = os.environ['COVERS'].split('\n')

    if item_type == 'Track':
        track_number = os.environ['NUMBER']
        disc_number = os.environ['DISC_NUMBER']
        popularity = os.environ['POPULARITY']
        album = os.environ['ALBUM']
        track_artists = os.environ['ARTISTS'].split('\n')
        album_artists = os.environ['ALBUM_ARTISTS'].split('\n')

        draw_now_playing()

    elif item_type == 'Episode':
        show_name = os.environ['SHOW_NAME']
        publish_time = datetime.utcfromtimestamp(int(os.environ['PUBLISH_TIME'])).strftime('%Y-%m-%d')
        description = os.environ['DESCRIPTION']
