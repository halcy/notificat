import requests
from PIL import Image
import io
import numpy as np
import math
import warnings
import colorsys

##
# Some styling tools, from tootmage
##

glyphs = {
    'reblog': '\U0000267a', # recycling symbol
    'favourite': '\U00002605 ', # star
    'follow': '➜', # arrow
    'mention': '\U0001f4e7', # envelope
    'avatar': "█"
}

# Ansi stuff
def ansi_rgb(r, g, b):
    r = int(round(r * 255.0))
    g = int(round(g * 255.0))
    b = int(round(b * 255.0))
    return "\33[38;2;{};{};{}m".format(str(r), str(g), str(b))

def ansi_reset():
    return "\33[m"

# Avatar tools
avatar_cache = {}
def get_avatar_cols(avatar_url):
    avatar_resp = requests.get(avatar_url)
    avatar_image = Image.open(io.BytesIO(avatar_resp.content))
    avatar_image = avatar_image.resize((60, 60))
    avatar_image = avatar_image.convert('RGBA').convert('RGB').convert('HSV')
    avatar = avatar_image.load()

    hue_bins = list(map(lambda x: [], range(1 + 255 // 10)))
    hue_weights = [0.0] * (1 + 255 // 10)
    center_x = avatar_image.size[0] / 2
    center_y = avatar_image.size[1] / 2
    for y in range(avatar_image.size[1]):
        for x in range(avatar_image.size[0]):
            x_dev = (x - center_x) / avatar_image.size[0]
            y_dev = (y - center_y) / avatar_image.size[1]
            center_dist = math.sqrt(math.pow(x_dev, 2.0) + math.pow(y_dev, 2.0))
            col = avatar[x, y]
            hue_bin = col[0] // 10
            hue_bins[hue_bin].append(col)
            hue_weights[hue_bin] += 0.5 + (col[1] / 255.0) * 0.5 + center_dist * 0.1 + abs(col[2] / 255.0 - 0.5) * 0.25

    hues_sorted = [x for _, x in sorted(zip(hue_weights, hue_bins))]
    primary_cols = []
    all_most_common_cols = []
    for hue in reversed(hues_sorted[-4:]):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            try:
                most_common_cols = list(reversed(sorted(set(hue), key=hue.count)))
                all_most_common_cols = most_common_cols + all_most_common_cols
                found_col = False
                for test_col in np.array(all_most_common_cols):
                    worst_difference = 100.0
                    if len(primary_cols) > 0:
                        for col in primary_cols:
                            worst_difference = min(np.linalg.norm(
                                col - np.array(colorsys.hsv_to_rgb(*test_col / 255.0)) 
                            ), worst_difference)
                    else:
                        worst_difference = 100.0
                        
                    if worst_difference > 0.2:
                        found_col = True
                        primary_cols.append(list(np.array(colorsys.hsv_to_rgb(*(test_col / 255.0)))))
                        break                    
                if not found_col:
                    median_col = np.median(hue, axis = 0)
                    primary_cols.append(list(np.array(colorsys.hsv_to_rgb(*(median_col / 255.0)))))
            except:
                primary_cols.append(primary_cols[0])
    return primary_cols

def get_avatar(avatar_url):
    if avatar_url in avatar_cache:
        return avatar_cache[avatar_url]
    else:
        try:
            avatar_cols = get_avatar_cols(avatar_url)
            avatar = ""
            for col in avatar_cols:
                avatar = avatar + ansi_rgb(*col) + glyphs["avatar"]
        except:
            avatar = ansi_rgb(0, 0, 0) + (glyphs["avatar"] * 4) # TODO use handle hash avatar instead
        avatar_cache[avatar_url] = avatar
    return avatar
