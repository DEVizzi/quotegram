import os, random, textwrap
import cv2                                    # OpenCV for paper detection
from PIL import Image, ImageDraw, ImageFont   # Pillow for text overlay
from instagrapi import Client                 # Instagram client
import google.genai as genai                  # Google Gemini SDK

# Load environment variables
GENAI_KEY = os.getenv("GOOGLE_API_KEY")
IG_USER   = os.getenv("IG_USERNAME")
IG_PASS   = os.getenv("IG_PASSWORD")
genai.configure(api_key=GENAI_KEY)

# Paths & settings
IMG_DIR    = "images"
FONT_PATH  = "fonts/DancingScript-Regular.ttf"
FONT_SIZE  = 48
WRAP_WIDTH = 30

def choose_image():
    return os.path.join(IMG_DIR, random.choice(os.listdir(IMG_DIR)))

def generate_quote():
    resp = genai.chat.completions.create(
        model="models/chat-bison-001",
        temperature=0.7,
        messages=[{"author":"user","content":
                   "Write one short, happy, inspirational quote."}]
    )
    return resp.choices[0].message.content.strip()

def detect_paper_bbox(img_path):
    # Load and blur for noise reduction
    img = cv2.imread(img_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Threshold for white regions
    lower = (0, 0, 200)
    upper = (180, 30, 255)
    mask = cv2.inRange(hsv, lower, upper)
    # Morphological clean-up
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Select the largest contour
    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    return x, y, w, h

def overlay_text_in_box(image_path, text):
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    # Detect where the paper is
    x, y, w, h = detect_paper_bbox(image_path)

    # Wrap text and compute total height
    lines = textwrap.wrap(text, width=WRAP_WIDTH)
    line_h = FONT_SIZE + 10
    total_h = line_h * len(lines)

    # Starting y to vertically center text in the box
    start_y = y + (h - total_h) // 2

    for line in lines:
        text_w, _ = draw.textsize(line, font=font)
        start_x = x + (w - text_w) // 2
        draw.text((start_x, start_y), line, font=font)
        start_y += line_h

    out_path = "temp_post.jpg"
    img.save(out_path)
    return out_path

def post_to_instagram(img_path, caption):
    cl = Client()
    cl.login(IG_USER, IG_PASS)
    cl.photo_upload(img_path, caption)
    os.remove(img_path)

if __name__ == "__main__":
    img      = choose_image()
    quote    = generate_quote()
    post_img = overlay_text_in_box(img, quote)
    post_to_instagram(post_img, quote)
    print("✅ Posted:", quote)
