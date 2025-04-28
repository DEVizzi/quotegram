import os
import random
import textwrap
import subprocess
import pickle
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from instagrapi import Client
from dotenv import load_dotenv
import warnings
import datetime

# LangChain imports
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage

# Load environment variables
load_dotenv()

# Environment variables
GENAI_KEY = os.getenv("GOOGLE_API_KEY")
IG_USER = os.getenv("IG_USERNAME")
IG_PASS = os.getenv("IG_PASSWORD")
SESSION_FILE = os.getenv("INSTAGRAM_SESSION_FILE", "ig_session.pkl")
HISTORY_FILE = os.getenv("QUOTE_HISTORY_FILE", "quote_history.txt")

# Configure Gemini via LangChain
llm = ChatGoogleGenerativeAI(
    model="models/gemini-1.5-flash",
    temperature=0.8,
    api_key=GENAI_KEY
)

# Paths & settings
IMG_DIR = "images"
MUSIC_DIR = "music"  # Folder containing royalty-free happy music files (e.g., .mp3)
EMOJI_FONT_PATH = "fonts/NotoEmoji-Regular.ttf"
WINDOWS_EMOJI_FONT = r"C:\\Windows\\Fonts\\seguiemj.ttf"
HANDWRITING_FONT_PATH = "fonts/DancingScript-Regular.ttf"

# Pen color palette
PEN_COLORS = [
    # Original Pen Colors
    "#000000", "#000066", "#3a0066", "#660000", "#404040", "#cc0f70",
    
    # Dark Blue Ink Shades
    "#0000A0",  # Dark Blue
    "#1E3A8A",  # Royal Blue
    "#1D4ED8",  # Strong Blue
    "#0A1172",  # Deep Ink Blue
    "#102542",  # Navy Ink
    "#001F54",  # Dark Sapphire Blue
    "#002147",  # Oxford Blue
    "#003366",  # Midnight Blue

    # Red Ink Shades
    "#8B0000",  # Dark Red
    "#B22222",  # Firebrick
    "#DC143C",  # Crimson
    "#FF0000",  # Bright Red
    "#800020",  # Burgundy
    "#7B1E3A",  # Wine Red
    "#581845",  # Deep Plum (purple-red mix)
]


# Padding ratio inside red box
PADDING_RATIO = 0.25  # 25% padding

def choose_image():
    return os.path.join(IMG_DIR, random.choice(os.listdir(IMG_DIR)))
    
def choose_music():
    """Pick a random royalty-free music file from MUSIC_DIR."""
    files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.wav', '.aac'))]
    if not files:
        raise RuntimeError("No music files found in MUSIC_DIR.")
    return os.path.join(MUSIC_DIR, random.choice(files))     

def combine_image_with_music_ffmpeg(image_path: str) -> str:
    """
    Alternative: Combine static image and background music using FFmpeg directly.
    """
    music_path = choose_music()
    out_video = image_path.rsplit('.', 1)[0] + '_ffmpeg.mp4'
    command = [
        'ffmpeg',
        '-y',
        '-loop', '1',
        '-i', image_path,
        '-i', music_path,
        '-c:v', 'libx264',
        '-t', '10',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-shortest',
        out_video
    ]
    subprocess.run(command, check=True)
    return out_video
    

def generate_quote() -> str:
    """Generate unique inspirational quote using Gemini. Always returns a non-None fallback."""
    seen = set()
    fallback_quote = "Compose a short yet electrifying motivational quote that sparks action in 1-3 lines. Compose a short yet electrifying motivational quote that sparks action in 1-3 lines. Compose a short yet electrifying motivational quote that sparks action in 1-3 lines."
    
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            seen = set(line.strip() for line in f if line.strip())
    
    styles = {
        "Inspirational": [
            "Compose a short yet electrifying motivational quote that sparks action in 1-3 lines.",
            "Deliver an uplifting and spirit-boosting quote that inspires hope in 1-3 lines.",
            "Pen a bold and fearless quote that challenges limits in just 1-2 lines.",
            "Create a fierce and empowering quote that ignites confidence in 1-2 lines.",
            "Generate a heartfelt and emotional quote that touches the soul in 1-3 lines.",
            "Write a radiant sunrise of words that awakens dreams in 1-3 lines.",
        ],
        "Philosophical": [
            "Write a thought-provoking philosophical quote that invites deep reflection in 2 or 3 lines.",
            "Compose a wise and timeless quote that feels ancient yet eternal in 2-3 lines.",
            "Deliver a minimalist and powerful quote where every word hits like thunder in 1-2 lines.",
            "Write a paradoxical quote that twists reality and sparks wonder in 2-3 lines.",
        ],
        "Cheerful & Uplifting": [
            "Create a bright and joy-infused quote that radiates cheerfulness in 1-3 lines.",
            "Write a playful and sunshine-filled quote that lights up the heart in 1-3 lines.",
            "Pen an infectious laugh wrapped in words within 1-2 lines.",
        ],
        "Dreamy & Mystical": [
            "Weave a whimsical and dreamlike quote that stirs imagination in 1-3 lines.",
            "Write a celestial and starlit quote that feels like a night under infinite skies in 2-3 lines.",
            "Create a nature-inspired quote that draws wisdom from earth, sky, and sea in 1-3 lines.",
            "Craft a mythic and legendary quote that feels pulled from ancient epics in 2-3 lines.",
        ],
        "Bold & Fearless": [
            "Pen a quote that feels like a war-cry for the soul in 1-2 lines.",
            "Write a rebellious and unbreakable quote that defies norms in 1-2 lines.",
            "Create a fierce and roaring quote that commands courage in 1-3 lines.",
        ],
        "Calm & Serene": [
            "Write a serene and calming quote that soothes the mind in 2-3 lines.",
            "Compose a zen-like quote that floats like a quiet breeze across 1-2 lines.",
            "Craft a tranquil river of words that brings stillness in 2-3 lines.",
        ],
        "Sharp & Witty": [
            "Craft a sharp and witty quote that delivers clever insight in just 1-2 lines.",
            "Pen a sly and mischievous quote that hides wisdom in humor within 1-2 lines.",
            "Write a quick, punchy aphorism that leaves a lasting sting in 1-2 lines.",
        ],
        "Timeless & Wise": [
            "Compose a stoic and profound quote that could echo through centuries in 2-3 lines.",
            "Write a simple but eternal truth wrapped in elegant words within 1-2 lines.",
            "Deliver a sage’s whispered wisdom in a few profound lines.",
        ],
        "Futuristic & Visionary": [
            "Write a visionary and future-facing quote that inspires innovation in 2-3 lines.",
            "Compose a cosmic-minded quote that imagines humanity among the stars in 2-3 lines.",
            "Create a tech-infused philosophical quote about evolution and transcendence in 2-3 lines.",
        ],
    }

    all_styles = [quote for category in styles.values() for quote in category]

    for _ in range(10):
        prompt = random.choice(all_styles)
        msgs = [
            SystemMessage(content="You are a cheerful assistant. Strictly show only quotes."),
            HumanMessage(content=prompt + " Never repeat quotes."),
        ]
        try:
            resp = llm.invoke(msgs).content.strip()
        except Exception as e:
            print(f"⚠️ LLM invocation failed: {e}")
            continue  # Try again with a new prompt

        if not resp:
            continue  # Skip if response is empty
        
        line_count = resp.count('\n') + 1
        if 2 <= line_count <= 3 and resp not in seen:
            seen.add(resp)
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(resp + "\n")
            return resp

    # If nothing good is generated, return fallback
    print("⚠️ No valid quote generated after 10 attempts, using fallback.")
    return fallback_quote

    

def detect_paper_bbox(img_path):
    """Detect white paper region near image center."""
    img = cv2.imread(img_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 200), (180, 30, 255))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise RuntimeError("No paper region detected in image.")
    
    h_img, w_img = img.shape[:2]
    cx_min, cx_max = w_img*0.25, w_img*0.75
    cy_min, cy_max = h_img*0.25, h_img*0.75
    valid = []
    for c in contours:
        x,y,w,h = cv2.boundingRect(c)
        cx,cy = x+w/2, y+h/2
        if cx_min<=cx<=cx_max and cy_min<=cy<=cy_max:
            valid.append(c)
    if not valid:
        valid = contours
    c = max(valid, key=cv2.contourArea)
    return cv2.boundingRect(c)

def get_finger_bboxes(img, paper_box):
    """Detect skin regions within paper box."""
    x,y,w,h = paper_box
    crop = img[y:y+h, x:x+w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0,48,80), (20,255,255))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    fingers=[]
    for c in contours:
        fx,fy,fw,fh = cv2.boundingRect(c)
        fingers.append((x+fx, y+fy, fw, fh))
    return fingers

def detect_adjusted_bbox(img_path):
    """Handle multiple fingers while maximizing usable paper area"""
    x, y, w, h = detect_paper_bbox(img_path)
    img = cv2.imread(img_path)
    fingers = get_finger_bboxes(img, (x, y, w, h))

    paper_left = x
    paper_right = x + w
    paper_bottom = y + h
    margin = int(min(w, h) * 0.00)  # 2% margin

    # Separate fingers into zones
    left_fingers = [f for f in fingers if f[0] + f[2]/2 < x + w*0.2]
    right_fingers = [f for f in fingers if f[0] + f[2]/2 > x + w*0.8]
    center_fingers = [f for f in fingers if x + w*0.3 <= f[0] + f[2]/2 <= x + w*0.7]

    # Horizontal boundaries
    if left_fingers:
        # Use rightmost left finger's right edge
        left_bound = max(f[0] + f[2] for f in left_fingers) + margin
    else:
        left_bound = paper_left

    if right_fingers:
        # Use leftmost right finger's left edge
        right_bound = min(f[0] for f in right_fingers) - margin
    else:
        right_bound = paper_right

    # Vertical boundaries
    if center_fingers:
        # Find highest center finger (lowest Y)
        highest_finger_y = min(f[1] for f in center_fingers)
        bottom_bound = highest_finger_y - margin
        # Preserve minimum 60% vertical space
        bottom_bound = max(bottom_bound, y + int(h * 0.3))
    else:
        bottom_bound = paper_bottom

    # Calculate final dimensions with smart clustering
    new_x = max(paper_left, left_bound)
    new_w = max(right_bound - new_x, int(w * 0.4))  # Min 40% width
    new_h = max(bottom_bound - y, int(h * 0.6))  # Min 60% height

    # Expand horizontally if multiple fingers leave central space
    if len(left_fingers) >= 2 and len(right_fingers) >= 2:
        left_most = min(f[0] for f in left_fingers)
        right_most = max(f[0] + f[2] for f in right_fingers)
        new_x = left_most + margin
        new_w = right_most - new_x - margin

    return (int(new_x), y, int(new_w), int(new_h))

def get_emoji_font(size):
    """Load emoji-capable font."""
    for path in [EMOJI_FONT_PATH, WINDOWS_EMOJI_FONT]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    warnings.warn("Emoji font not found; emojis may not render.")
    return ImageFont.load_default()

def overlay_text_in_box(image_path, text):
    """Draw text with emoji support in adjusted paper area with red border."""
    pil_img = Image.open(image_path)
    draw = ImageDraw.Draw(pil_img)
    x, y, w, h = detect_adjusted_bbox(image_path)
    
    # Draw red border around maximum available area
    draw.rectangle([x, y, x + w, y + h], outline="red", width=3)
    
    # Apply padding inside the red border
    pad = int(min(w, h) * PADDING_RATIO)
    text_x = x + pad
    text_y = y + pad
    text_width = w - 2 * pad
    text_height = h - 2 * pad
    
    pen_color = random.choice(PEN_COLORS)
    min_fs, max_fs = 10, 200
    best_font = None
    
    # Fit font to padded area
    for fs in range(max_fs, min_fs-1, -2):
        font = ImageFont.truetype(HANDWRITING_FONT_PATH, fs)
        words = text.split()
        lines = []
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            bb = draw.textbbox((0,0), test, font=font)
            if bb[2] - bb[0] <= text_width:
                line = test
            else:
                lines.append(line)
                line = word
        lines.append(line)
        spacing = int(fs * 0.2)
        total_h = sum(draw.textbbox((0,0), l, font=font)[3] - draw.textbbox((0,0), l, font=font)[1] for l in lines) + spacing * (len(lines)-1)
        if total_h <= text_height:
            best_font, best_lines = font, lines
            break
    
    if not best_font:
        best_font = ImageFont.truetype(HANDWRITING_FONT_PATH, min_fs)
        best_lines = textwrap.wrap(text, width=40)
    
    emoji_font = get_emoji_font(best_font.size)
    
    def is_emoji(ch):
        import unicodedata
        return unicodedata.category(ch) in ('So','Sk') or 'EMOJI' in unicodedata.name(ch,'')
    
    # Center text vertically and horizontally
    cy = text_y + (text_height - sum(draw.textbbox((0,0), l, font=best_font)[3] - draw.textbbox((0,0), l, font=best_font)[1] for l in best_lines) - spacing*(len(best_lines)-1)) // 2
    for line in best_lines:
        line_width = sum(
            (draw.textbbox((0,0), ch, font=emoji_font if is_emoji(ch) else best_font)[2] 
             - draw.textbbox((0,0), ch, font=emoji_font if is_emoji(ch) else best_font)[0])
            for ch in line
        )
        cx = text_x + (text_width - line_width) // 2
        for ch in line:
            fnt = emoji_font if is_emoji(ch) else best_font
            draw.text((cx, cy), ch, fill=pen_color, font=fnt)
            bb = draw.textbbox((0,0), ch, font=fnt)
            cx += bb[2] - bb[0]
        cy += (draw.textbbox((0,0), line, font=best_font)[3] - draw.textbbox((0,0), line, font=best_font)[1] + spacing)
    
    out = "temp_post.jpg"
    pil_img.save(out)
    return out

@tool
def post_to_instagram(image_path: str, caption: str) -> str:
    """Post image (or video with background music) to Instagram with session management."""
    # Session management (unchanged)
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "rb") as f:
                cl = pickle.load(f)
            cl.get_timeline_feed()
        except Exception:
            cl = Client()
            cl.login(IG_USER, IG_PASS)
            with open(SESSION_FILE, "wb") as f:
                pickle.dump(cl, f)
    else:
        cl = Client()
        cl.login(IG_USER, IG_PASS)
        with open(SESSION_FILE, "wb") as f:
            pickle.dump(cl, f)

    # New: wrap the static image into a short video with background music
    try:
        video_path = combine_image_with_music(image_path)
        cl.video_upload(video_path, caption)
        os.remove(video_path)
    except Exception:
        # Fallback to image post if video upload fails
        cl.photo_upload(image_path, caption)

    os.remove(image_path)
    return "✅ Posted successfully."

if __name__ == "__main__":
    output_folder = r"C:\Users\IzazUlHaque\OneDrive - Black Duck Software\Desktop\MYpROJ\quotegram\output"
    os.makedirs(output_folder, exist_ok=True)
    success = False
    
    while not success:
        try:
            img = choose_image()
            quote = generate_quote()
            print(f"Generated quote:\n{quote}")
            post_img = overlay_text_in_box(img, quote)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            #final_path = os.path.join(output_folder, f"quote_{timestamp}.png")
            #Image.open(post_img).save(final_path)
            #print(f"✅ Image saved to {final_path}")

            video_path = combine_image_with_music_ffmpeg(post_img)
            final_video_path = os.path.join(output_folder, f"quote_{timestamp}.mp4")
            os.rename(video_path, final_video_path)
            print(f"✅ Video saved to {final_video_path}")
            
            # Instagram posting disabled
            # print(post_to_instagram.invoke({"image_path": post_img, "caption": quote}))
                     
            success = True
        except RuntimeError as e:
            print(f"⚠️ {e} — Trying another image...")