import os
import tempfile
import random
import textwrap
import tempfile
import requests
import subprocess
import pickle
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from instagrapi import Client
from dotenv import load_dotenv
import warnings
import datetime
from instagrapi.exceptions import ChallengeRequired
from typing import Optional, List
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
# LangChain imports
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage

# Load environment variables
load_dotenv()
#-------------------------------------------YOUTUBE--------------------------------------------------------------
# OAuth scope for uploading to YouTube
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", "token_youtube.pickle")
CLIENT_SECRETS_CONTENT = os.getenv("YOUTUBE_CLIENT_SECRETS_JSON")
#-------------------------------------------YOUTUBE--------------------------------------------------------------

# Instagram Graph API configuration
ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")  # Page access token
PAGE_ID = os.getenv("FB_PAGE_ID")  # Facebook Page ID
API_VERSION = "v17.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

# Environment variables
GENAI_KEY = os.getenv("GOOGLE_API_KEY")
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

#-------------------------------------------YOUTUBE--------------------------------------------------------------
def authenticate_youtube():
    """Authenticate the user via OAuth and return a YouTube service client."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            import json

        if not CLIENT_SECRETS_CONTENT:
            raise EnvironmentError("YOUTUBE_CLIENT_SECRETS_JSON environment variable is not set.")

        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as tmp_file:
            tmp_file.write(CLIENT_SECRETS_CONTENT)
            tmp_file.flush()
            flow = InstalledAppFlow.from_client_secrets_file(tmp_file.name, SCOPES)
            creds = flow.run_console()
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)


def upload_video(video_path: str, title: str, description: str, tags: Optional[List[str]] = None) -> str:
    """Upload a video file to YouTube and return the video ID."""
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    youtube = authenticate_youtube()

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags or [],
            'categoryId': '22'  # 22 = People & Blogs
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        }
    }

    media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    retry_count = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")
        except Exception as e:
            retry_count += 1
            if retry_count > 3:
                raise RuntimeError(f"Upload failed after 3 retries: {e}")
            print(f"Retrying upload due to error: {e}")

    video_id = response.get('id')
    print(f"✅ Uploaded to YouTube: https://youtu.be/{video_id}")
    return video_id

def parse_arguments():
    parser = argparse.ArgumentParser(description="Upload a video file to YouTube via API.")
    parser.add_argument("--video", required=True, help="Path to the video file (MP4)")
    parser.add_argument("--title", required=True, help="Title of the YouTube video")
    parser.add_argument("--description", default="", help="Description for the video")
    parser.add_argument("--tags", nargs="*", default=[], help="List of tags for the video")
    return parser.parse_args()

#-------------------------------------------YOUTUBE--------------------------------------------------------------


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
        '-t', '15',
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
    fallback_quote = "The future is not something we enter. It is something we create."
    
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            seen = set(line.strip() for line in f if line.strip())
    
    styles = {
    "Inspirational": [
        "Compose an electrifying motivational quote in 1 line. Max character length 100.",
        "Deliver an uplifting spirit-boosting quote in 1 line. Max character length 100.",
        "Pen a bold and fearless quote that challenges limits in 1 line. Max character length 100.",
        "Create a fierce and empowering confidence-igniting quote in 1 line. Max character length 100.",
        "Generate a heartfelt emotional quote that touches the soul in 1 line. Max character length 100.",
        "Write a radiant sunrise of words that awakens dreams in 1 line. Max character length 100.",
    ],
    "Philosophical": [
        "Write a thought-provoking philosophical quote in 1 line. Max character length 100.",
        "Compose a wise and timeless quote that feels ancient yet eternal in 1 line. Max character length 100.",
        "Deliver a minimalist powerful quote where every word hits like thunder in 1 line. Max character length 100.",
        "Write a paradoxical quote that twists reality and sparks wonder in 1 line. Max character length 100.",
    ],
    "Cheerful & Uplifting": [
        "Create a bright joy-infused quote that radiates cheerfulness in 1 line. Max character length 100.",
        "Write a playful sunshine-filled quote that lights up the heart in 1 line. Max character length 100.",
        "Pen an infectious laugh wrapped in words in 1 line. Max character length 100.",
    ],
    "Dreamy & Mystical": [
        "Weave a whimsical dreamlike quote that stirs imagination in 1 line. Max character length 100.",
        "Write a celestial starlit quote that feels like a night under infinite skies in 1 line. Max character length 100.",
        "Create a nature-inspired quote drawing wisdom from earth, sky, and sea in 1 line. Max character length 100.",
        "Craft a mythic legendary quote that feels pulled from ancient epics in 1 line. Max character length 100.",
    ],
    "Bold & Fearless": [
        "Pen a quote that feels like a war-cry for the soul in 1 line. Max character length 100.",
        "Write a rebellious unbreakable quote that defies norms in 1 line. Max character length 100.",
        "Create a fierce roaring quote that commands courage in 1 line. Max character length 100.",
    ],
    "Calm & Serene": [
        "Write a serene calming quote that soothes the mind in 1 line. Max character length 100.",
        "Compose a zen-like quote that floats like a quiet breeze in 1 line. Max character length 100.",
        "Craft a tranquil river of words that brings stillness in 1 line. Max character length 100.",
    ],
    "Sharp & Witty": [
        "Craft a sharp witty quote that delivers clever insight in 1 line. Max character length 100.",
        "Pen a sly mischievous quote that hides wisdom in humor in 1 line. Max character length 100.",
        "Write a quick punchy aphorism that leaves a sting in 1 line. Max character length 100.",
    ],
    "Timeless & Wise": [
        "Compose a stoic profound quote that could echo through centuries in 1 line. Max character length 100.",
        "Write a simple eternal truth wrapped in elegant words in 1 line. Max character length 100.",
        "Deliver a sage’s whispered wisdom in a few profound words in 1 line. Max character length 100.",
    ],
    "Futuristic & Visionary": [
        "Write a visionary future-facing quote that inspires innovation in 1 line. Max character length 100.",
        "Compose a cosmic-minded quote that imagines humanity among the stars in 1 line. Max character length 100.",
        "Create a tech-infused philosophical quote about evolution and transcendence in 1 line. Max character length 100.",
    ],
    "Mystery & Thriller": [
        "Craft a suspenseful quote that hints at secrets lurking in the shadows in 1 line. Max character length 100.",
        "Write a chilling one-liner that teases a dark twist or hidden danger. Max character length 100.",
        "Pen a mysterious quote that feels like a whisper from the unknown in 1 line. Max character length 100.",
        "Create a cryptic line that leaves the reader questioning reality in 1 line. Max character length 100.",
        "Deliver a noir-style quote dripping with tension and quiet menace in 1 line. Max character length 100.",
        "Write a thriller-charged quote that suggests something is watching or waiting in 1 line. Max character length 100.",
    ]
}

    all_styles = [q for cat in styles.values() for q in cat]
    for _ in range(3):
        prompt = random.choice(all_styles)
        def remove_emojis(text):
            return re.sub(r'[\U00010000-\U0010ffff\u200d\u2640-\u2642]', '', text)

        msgs = [
            SystemMessage(content="You are a cheerful assistant. Strictly show only plain-text quotes. Do not use any emojis, emoticons, or symbols."),
            HumanMessage(content=prompt + " Never repeat quotes. Do NOT use any emojis."),
        ]
        try:
            resp = llm.invoke(msgs).content.strip()
            resp = remove_emojis(resp)

        except Exception:
            continue
        if not resp:
            continue
        line_count = resp.count('\n') + 1
        if 1 <= line_count <= 3 and resp not in seen:
            seen.add(resp)
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(resp + "\n")
            return resp
    print("⚠️ No valid quote generated after 3 attempts, using fallback.")
    return fallback_quote

def generate_hashtags(text: str, num_tags: int = 8) -> str:
    prompt = (
        f"Generate {num_tags} high-performing, niche-relevant Instagram hashtags "
        f"for the following content. List them without spaces, each starting with '#': \"{text}\""
    )
    msgs = [
        SystemMessage(content="You are a helpful assistant that suggests relevant hashtags."),
        HumanMessage(content=prompt),
    ]
    try:
        resp = llm.invoke(msgs).content.strip()
        # split by whitespace or commas
        raw_tags = [tag.strip(' ,') for tag in resp.replace(',', ' ').split()]
        hashtags = [tag if tag.startswith('#') else f"#{tag}" for tag in raw_tags]
        return ' '.join(hashtags[:num_tags])
    except Exception as e:
        print(f"⚠️ Hashtag generation failed: {e}")
        return ""
    

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
    # draw.rectangle([x, y, x + w, y + h], outline="red", width=3)
    
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
    
    
    # Center text vertically and horizontally
    cy = text_y + (text_height - sum(draw.textbbox((0,0), l, font=best_font)[3] - draw.textbbox((0,0), l, font=best_font)[1] for l in best_lines) - spacing*(len(best_lines)-1)) // 2
    for line in best_lines:
        line_width = sum(draw.textbbox((0, 0), ch, font=best_font)[2] - draw.textbbox((0, 0), ch, font=best_font)[0] for ch in line)
        cx = text_x + (text_width - line_width) // 2
        for ch in line:
            draw.text((cx, cy), ch, fill=pen_color, font=best_font)
            bb = draw.textbbox((0, 0), ch, font=best_font)
            cx += bb[2] - bb[0]
        cy += (draw.textbbox((0, 0), line, font=best_font)[3] - draw.textbbox((0, 0), line, font=best_font)[1] + spacing)

    out = "temp_post.jpg"
    pil_img.save(out)
    return out

#----------------------------POSTING------------------------------------------------------------------------
# Helper: fetch Instagram Business Account ID from connected Facebook Page
def fetch_ig_business_account_id(page_id: str) -> str:
    endpoint = f"{BASE_URL}/{page_id}"
    params = {
        "fields": "instagram_business_account",
        "access_token": ACCESS_TOKEN
    }
    resp = requests.get(endpoint, params=params).json()
    ig_info = resp.get("instagram_business_account")
    if not ig_info or not ig_info.get("id"):
        raise RuntimeError(f"Unable to fetch Instagram Business Account ID: {resp}")
    return ig_info["id"]

# Determine IG_USER_ID (Instagram Business Account ID)
IG_USER_ID = os.getenv("IG_BUSINESS_ACCOUNT_ID")
if not IG_USER_ID:
    if not PAGE_ID:
        raise RuntimeError("Must provide either IG_BUSINESS_ACCOUNT_ID or FB_PAGE_ID in environment variables.")
    IG_USER_ID = fetch_ig_business_account_id(PAGE_ID)

# --- Instagram Graph API Reels Upload Flow ---
def init_reel_upload(caption: str, cover_url: str = None) -> (str, str):
    endpoint = f"{BASE_URL}/{IG_USER_ID}/media"
    params = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "access_token": ACCESS_TOKEN
    }
    if cover_url:
        params["cover_url"] = cover_url
    resp = requests.post(endpoint, data=params).json()
    if "id" not in resp or "uri" not in resp:
        raise RuntimeError(f"Error initializing reel upload: {resp}")
    return resp["id"], resp["uri"]


def upload_reel_video(upload_url: str, video_path: str) -> None:
    file_size = os.path.getsize(video_path)
    headers = {
        "Authorization": f"OAuth {ACCESS_TOKEN}",
        "offset": "0",
        "file_size": str(file_size)
    }
    with open(video_path, "rb") as f:
        resp = requests.post(upload_url, headers=headers, data=f)
    data = resp.json() if resp.headers.get('Content-Type','').startswith('application/json') else {}
    if not resp.ok or (data.get("success") is False):
        raise RuntimeError(f"Error uploading reel video: {data or resp.text}")


def publish_media_container(container_id: str) -> dict:
    endpoint = f"{BASE_URL}/{IG_USER_ID}/media_publish"
    params = {
        "creation_id": container_id,
        "access_token": ACCESS_TOKEN
    }
    resp = requests.post(endpoint, data=params).json()
    if "id" not in resp:
        raise RuntimeError(f"Error publishing media: {resp}")
    return resp


def post_reel(video_path: str, caption: str, cover_url: str = None) -> str:
    container_id, upload_url = init_reel_upload(caption, cover_url)
    upload_reel_video(upload_url, video_path)
    res = publish_media_container(container_id)
    return f"✅ Reel posted successfully (media ID: {res['id']})"

# Image posting unchanged; ensure create_image_container exists upstream

def post_image(image_url: str, caption: str) -> str:
    endpoint = f"{BASE_URL}/{IG_USER_ID}/media"
    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": ACCESS_TOKEN
    }
    resp = requests.post(endpoint, params=params).json()
    if "id" not in resp:
        raise RuntimeError(f"Error creating image container: {resp}")
    publish_resp = publish_media_container(resp["id"])
    return f"✅ Image posted successfully (media ID: {publish_resp['id']})"

# --- Main Workflow ---
if __name__ == "__main__":
    output_folder = os.path.expanduser(os.getenv("OUTPUT_FOLDER", "~/quotegram/output"))
    os.makedirs(output_folder, exist_ok=True)
    success = False

    while not success:
        try:
            # Generate image and quote
            img = choose_image()
            quote = generate_quote()
            post_img = overlay_text_in_box(img, quote)

            # Generate video
            video_path = combine_image_with_music_ffmpeg(post_img)
            print(f"✅ Video generated at {video_path}")

            # Build caption with hashtags
            hashtags = generate_hashtags(quote, num_tags=8)
            caption = f"{quote}\n\n{hashtags}" if hashtags else quote

            # Post as Instagram Reel
            result = post_reel(video_path, caption)
            print(result)
            
            # Post to YouTube Shorts
            tags = hashtags.replace("#", "").split() if hashtags else []
            yt_id = upload_video(video_path, title=quote, description=caption, tags=tags)
            print(f"✅ YouTube Shorts ID: {yt_id}")
            
            success = True

        except RuntimeError as e:
            print(f"⚠️ {e} — Retrying...")
        except Exception as e:
            print(f"Unexpected error: {e}")
            break
