#!/usr/bin/env python
import os
import sys
from datetime import datetime, timedelta
import urllib.request

from omni_epd import displayfactory, EPDNotFoundError
from PIL import Image, ImageDraw, ImageFont
from colorthief import ColorThief

player_event = os.getenv('PLAYER_EVENT')

user_name = ""
client_name = ""

shuffle = ""
repeat = ""
auto_play = ""
filter_explicit_content = ""

volume = ""
position_ms = ""

item_type = ""
track_name = ""
duration_ms = ""
is_explicit = ""
language = []
covers = []

track_number = ""
disc_number = ""
popularity = ""
album = ""
track_artists = []
album_artists = []

show_name = ""
publish_time = ""
description = ""

def open_epd():
    epd = displayfactory.load_display_driver("waveshare_epd.epd7in3e")

    epd.prepare()
    epd.mode = 'color'

    return epd

def clear_screen():
    print("Clear screen")
    epd = open_epd()
    epd.clear()

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
    lmin = min(l)
    lmax = max(l)

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

    horizontal = False
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
    else:
        image.paste(cover, (margin, height-cover.height-margin))

    draw = ImageDraw.Draw(image)
    # setting draw.font doesn't seem to effect the font used when using draw(..., font_size)
    # draw.fontmode = "1" # disable anti aliasing

    #print("adding text")
    x = 0
    y = 10

    def get_font(size):
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)

    def t(text, color, font_size, stroke=False):
        nonlocal x, y
        #print(f"printing {text}")
        font = get_font(font_size)
        tl = draw.textlength(text, font=font)
        if tl > width:
            # try to strip " - 2015 Remaster" or " (2015 Remaster)" suffixes
            text = text.split(" - ")[0].split(" (")[0]
            tl = draw.textlength(text, font=font)
            if tl > width:
                # reduce font size within 50-100% range to fit on screen width
                font = get_font(max(font_size*width//tl, font_size//2))
                tl = draw.textlength(text, font=font)
        x_offset = max((width-tl)//2, 0)
        if stroke:
            #sw = 4 #font_size//6
            draw.text((x+x_offset, y), text, stroke_width=sw, stroke_fill=color, fill="white", font=font)
        else:
            draw.text((x+x_offset, y), text, fill=color, font=font)
        y += font_size*3//2

    t(track_name, fg, 50)
    t(album, fg2, 40)
    t(", ".join(track_artists), fg, 40)
    t("", fg2, 10)
    t(f"{duration.seconds//60}:{duration.seconds%60:02d}", fg2, 40)

    if not horizontal:
        image.rotate(90)

    epd.display(image)

    epd.close()


#print(player_event)

if player_event in ('session_connected', 'session_disconnected'):
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
#   os.environ['TRACK_ID']
    position_ms = os.environ['POSITION_MS']
    if player_event in ('paused'): # paused seems to be what's received at end of playback
        clear_screen()

elif player_event in ('unavailable', 'end_of_track', 'preload_next', 'preloading', 'loading', 'stopped'):
#   os.environ['TRACK_ID']
    print(player_event)
    if player_event in ('stopped'): # when librespot stops. not sure if that ever happens
        clear_screen()
    pass

elif player_event == 'track_changed':
    print(player_event)
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


