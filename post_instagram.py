import os
import random
import textwrap
import requests
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from instagrapi import Client
from dotenv import load_dotenv
import datetime
from instagrapi.exceptions import ChallengeRequired
from typing import Optional, List
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.cloud import texttospeech
import tempfile
import argparse
# LangChain imports
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage

# Load environment variables
load_dotenv()
#-------------------------------------------YOUTUBE--------------------------------------------------------------
# OAuth scope for uploading to YouTube
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
#-------------------------------------------YOUTUBE--------------------------------------------------------------

# Instagram Graph API configuration
ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")  # Page access token
PAGE_ID = os.getenv("FB_PAGE_ID")  # Facebook Page ID
API_VERSION = "v17.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

# Environment variables
GENAI_KEY = os.getenv("GOOGLE_API_KEY")
HISTORY_FILE = os.getenv("QUOTE_HISTORY_FILE", "quote_history.txt")

# TTS Function
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "myvoiceoverbot-a0da14b71e20.json"

# Configure Gemini via LangChain
llm = ChatGoogleGenerativeAI(
    model="models/gemini-1.5-flash",
    temperature=0.8,
    api_key=GENAI_KEY
)

# Paths & settings
IMG_DIR = "images"
MUSIC_DIR = "music"  # Folder containing royalty-free happy music files (e.g., .mp3)

#HANDWRITING_FONT_PATH = "fonts/tasteofsweetlight.ttf"
def select_random_font() -> str:
    """
    Select a random font file from the fonts directory.
    Returns the full path to the selected font file.
    Raises RuntimeError if no font files are found.
    """
    font_dir = "fonts"
    font_files = [f for f in os.listdir(font_dir) if f.lower().endswith(('.ttf', '.otf'))]
    if not font_files:
        raise RuntimeError(f"No font files found in {font_dir}.")
    return os.path.join(font_dir, random.choice(font_files))

# Initialize with a random font, but allow changing later
HANDWRITING_FONT_PATH = select_random_font()


# Pen color palette
PEN_COLORS = [
    # Original Pen Colors
    "#000000",  # Black
    "#000066",  # Deep Navy
    "#3A0066",  # Violet-Indigo
    "#660000",  # Dark Maroon
    "#CC0F70",  # Magenta-Pink
    
    # Dark Blue Ink Shades
    "#0000A0",  # Dark Blue
    "#1E3A8A",  # Royal Blue
    "#0A1172",  # Deep Ink Blue
    "#102542",  # Navy Ink
    "#001F54",  # Dark Sapphire Blue
    "#002147",  # Oxford Blue
    "#003366",  # Midnight Blue

    # Red Ink Shades
    "#8B0000",  # Dark Red
    "#B22222",  # Firebrick
    "#DC143C",  # Crimson
    "#581845",  # Deep Plum
]



# Padding ratio inside red box
PADDING_RATIO = 0.15  # 15% padding
STRICT_MARGIN_PX = 25 

#-----------------SppechStuff--------------------------------


def synthesize_text(text, output_path="output.mp3"):
    """Generate TTS audio with a randomly selected female voice from various nationalities."""
    client = texttospeech.TextToSpeechClient()

    # (voice_name, language_code) pairs – all FEMALE
    female_voices = [
        ("en-US-Wavenet-C", "en-US"),  # US Mid-tone
        ("en-US-Wavenet-E", "en-US"),  # US Bright
        ("en-US-Wavenet-F", "en-US"),  # US Calm
        ("en-US-Wavenet-H", "en-US"),   # Cheerful, articulate
    ]

    voice_name, language_code = random.choice(female_voices)
    print(f"🌍 Selected Voice: {voice_name} ({language_code})")

    input_text = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=0.80,      # Slowed for dramatic pacing
        pitch=-2.0,              # Slightly deeper pitch
        volume_gain_db=2.0       # Optional boost
    )

    response = client.synthesize_speech(
        input=input_text,
        voice=voice,
        audio_config=audio_config
    )

    with open(output_path, "wb") as out:
        out.write(response.audio_content)
        print(f"✅ Audio content written to {output_path}")

    return output_path
'''
def synthesize_text(text, output_path="output.mp3"):
    """Generate TTS audio with each female voice speaking the same full text, then concatenate all outputs."""
    client = texttospeech.TextToSpeechClient()

    female_voices = [
        ("en-US-Wavenet-C", "en-US"),  # US Mid-tone
        ("en-US-Wavenet-E", "en-US"),  # US Bright
        ("en-US-Wavenet-F", "en-US"),  # US Calm
        ("en-US-Wavenet-H", "en-US"),   # Cheerful, articulate
    ]

    temp_audio_files = []

    for i, (voice_name, lang_code) in enumerate(female_voices):
        input_text = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code=lang_code,
            name=voice_name,
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.80,      # Slowed for dramatic pacing
            pitch=-2.0,              # Slightly deeper pitch
            volume_gain_db=2.0       # Optional boost
        )

        response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)

        temp_file = os.path.join(tempfile.gettempdir(), f"voice_line_{i}.mp3")
        with open(temp_file, "wb") as out:
            out.write(response.audio_content)
        temp_audio_files.append(temp_file)

        print(f"🎤 {voice_name} ({lang_code}) -> full line saved: {temp_file}")

    # Create concat list file for ffmpeg
    concat_list_path = os.path.join(tempfile.gettempdir(), "concat_list.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for path in temp_audio_files:
            f.write(f"file '{path}'\n")

    # Final concatenation using ffmpeg
    command = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        output_path
    ]

    subprocess.run(command, check=True)
    print(f"✅ Final output with all voices saved as: {output_path}")

    return output_path
'''
#-------------------------------------------YOUTUBE--------------------------------------------------------------
def authenticate_youtube():
    """
    Non‑interactive auth using a refresh token. Ensure the following env vars are set:
      - YOUTUBE_CLIENT_ID
      - YOUTUBE_CLIENT_SECRET
      - YOUTUBE_REFRESH_TOKEN
    """
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    # Refresh access token
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def upload_video(video_path: str, title: str, description: str, tags: Optional[List[str]] = None) -> str:
    """Upload a video file to YouTube and return the video ID."""
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Ensure a non-empty, valid YouTube title
    title = title.replace("\n", " ").strip()
    if not title:
        title = f"QuoteGram Reel {datetime.datetime.now():%Y-%m-%d %H:%M:%S}"  # default title
    if len(title) > 100:
        title = title[:100]
    
    youtube = authenticate_youtube()
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags or [],
            'categoryId': '22',  # People & Blogs
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
    # Stream upload in chunks
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")
        except Exception as e:
            # Handle invalidTitle by retrying with a safe default title
            if 'invalidTitle' in str(e):
                retry_count += 1
                new_title = f"QuoteGram Reel {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                body['snippet']['title'] = new_title
                print(f"Invalid title error, retrying with default title: {new_title}")
                continue

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

def get_audio_duration(path: str) -> float:
    """Get the duration of an audio file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    return float(result.stdout.strip())

import subprocess
import os
import tempfile

def get_audio_duration(path: str) -> float:
    """Get the duration of an audio file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    return float(result.stdout.strip())

def mix_audio_tracks(voice_path: str, music_path: str, output_path="mixed_audio.m4a") -> str:
    """Mix voiceover and background music into a single audio track (AAC in M4A), with 1s fade-in and 3s fade-out."""
    voice_delay_ms = 1300
    voice_duration = get_audio_duration(voice_path)
    total_duration = max(30, voice_duration + voice_delay_ms / 1000)
    fade_out_start = total_duration - 3

    command = [
        "ffmpeg",
        "-y",
        "-i", voice_path,
        "-i", music_path,
        "-filter_complex",
        f"[0:a]adelay={voice_delay_ms}|{voice_delay_ms}[voice];"
        f"[1:a]volume=0.2[music];"
        f"[music][voice]amix=inputs=2:duration=longest:dropout_transition=2[aout];"
        f"[aout]afade=t=in:st=0:d=1,afade=t=out:st={fade_out_start:.2f}:d=3[audio]",
        "-map", "[audio]",
        "-t", str(total_duration),
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(command, check=True)
    print(f"🎧 Mixed audio with fade saved at {output_path}")
    return output_path

def combine_image_with_music_ffmpeg(image_path: str, audio_path: str) -> str:
    """Combine image and mixed audio into a final video."""
    audio_duration = get_audio_duration(audio_path)
    out_video = image_path.rsplit('.', 1)[0] + '_final_video.mp4'

    command = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-t", str(audio_duration),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        out_video
    ]
    subprocess.run(command, check=True)
    print(f"🎬 Final video created at {out_video}")
    return out_video



def mix_audio_tracks(voice_path: str, music_path: str, output_path="mixed_audio.m4a") -> str:
    """Mix voiceover and background music into a single audio track (AAC in M4A)."""
    voice_delay_ms = 2000
    voice_duration = get_audio_duration(voice_path)
    total_duration = max(30, voice_duration + voice_delay_ms / 1000)

    command = [
        "ffmpeg",
        "-y",
        "-i", voice_path,
        "-i", music_path,
        "-filter_complex",
        f"[0:a]adelay={voice_delay_ms}|{voice_delay_ms}[voice];"
        f"[1:a]volume=0.2[music];"
        f"[music][voice]amix=inputs=2:duration=longest:dropout_transition=2[aout]",
        "-map", "[aout]",
        "-t", str(total_duration),
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(command, check=True)
    print(f"🎧 Mixed audio saved at {output_path}")
    return output_path


def generate_quote() -> tuple[str, str]:
    """Generate a unique quote along with its style."""
    seen = set()
    fallback_quote = "The future is not something we enter. It is something we create."
    fallback_style = "Inspirational"
    
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            seen = set(line.strip() for line in f if line.strip())
    
    styles = {
    "Inspirational": [
        "Strike lightning in the dark—make them feel *invincible* in under 100 chars.",
        "Turn 'rock bottom' into a springboard—*one line to make them rise.*",
        "Write a quote that punches fear in the face and *hands courage a mic.*",
        "Burn the bridges. Light the sky with the flames.",
        "Write the kind of line that makes someone stand up straighter.",
        "Speak to the broken part—and dare it to rise again.",
        "Say something that makes quitting feel like betrayal.",
        "Craft a line that breaks chains you can't see.",
        "Let words kick the door open on self-doubt.",
        "Make rock bottom look like the start of a climb.",
        "Say what a lion would whisper to itself in a storm.",
        "Write like someone's counting on it to survive tonight.",
        "One sentence. Full spine. No fear. All in.",
    ],
    "Philosophical": [
        "Drop a quote that feels like it was whispered by the universe itself.",
        "Make time pause—one paradox so deep, you need to *read it in silence.*",
        "Say something so true, it hurts. Then makes them *wiser for the pain.*",
        "What if reality is just a thought that stuck?",
        "Fold infinity into a sentence—and make it believable.",
        "Say something that would make a monk raise an eyebrow.",
        "Write a line that breaks logic… and makes more sense.",
        "Let the words echo like a thought you've always had—but never caught.",
        "Wrap a contradiction in poetry and call it truth.",
        "Make them ask, 'Was that wise or dangerous?'",
        "Write the kind of sentence you'd find carved into a forgotten ruin.",
        "Say something that feels like a riddle from the stars.",
        "Make minds pause. Then spiral.",
    ],
    "Cheerful & Uplifting": [
        "Write a smile that fits in a sentence—one line that hugs the soul.",
        "Deliver joy like a surprise confetti bomb on a rainy day.",
        "Make them laugh, *then realize they're healing.*",
        "Turn gloom into glitter with just one sentence.",
        "Be the sunshine that barges in without knocking.",
        "Say something that feels like a warm mug and fuzzy socks.",
        "Write a line that makes Monday feel like Saturday.",
        "Be a joy thief—steal sadness with a sentence.",
        "Let words feel like a hug from someone you missed.",
        "Throw dopamine like it's candy on Halloween.",
        "Make their brain throw a tiny party.",
        "Wrap hope in humor, and let it dance.",
        "Say something so sweet, it rewires their day.",
    ],
    "Dreamy & Mystical": [
        "Whisper a quote that feels like the moon wrote it for dreamers.",
        "Let one line pull them through a portal of wonder and stardust.",
        "Write a sentence that sounds like a prophecy from an ancient star.",
        "Say something so surreal it feels like déjà vu from another life.",
        "Let your words wear stardust and carry secrets.",
        "Speak in moonlight, dream in shadows.",
        "Weave a line that smells like forest rain and forgotten magic.",
        "Let your quote sound like a spell said by someone in love with the sky.",
        "Say something that glows in the dark, quietly.",
        "Write a myth too small for books but too big to forget.",
        "Let them taste eternity in 12 words or less.",
        "Let dreams lean closer when they read it.",
        "Say what a cloud might whisper before vanishing.",
    ],
    "Bold & Fearless": [
        "Pen a quote that makes people quit their job *or* start a revolution.",
        "Say something so raw, it smells like fire and freedom.",
        "One line: all spine, no apology.",
        "Write like your fears are tied to a rocket—then launch.",
        "Say something so brave, even silence listens.",
        "Be the alarm clock for people who forgot they're powerful.",
        "Let your quote carry the weight of rebellion and clarity.",
        "Say what others swallowed—and shout it loud.",
        "Dare them to try. DARE THEM.",
        "Make fear feel embarrassed for even showing up.",
        "Sound like a war cry disguised as poetry.",
        "Make comfort zones shake.",
        "Say something that would get you banned in a past century.",
    ],
    "Calm & Serene": [
        "Deliver peace like a cold stream over tired thoughts—one silent sentence.",
        "Let the words feel like closing your eyes in a storm… and finding stillness.",
        "Make them breathe deeper with one line—like the earth just exhaled.",
        "Be the pause between two heartbeats.",
        "Say something that feels like being held by silence.",
        "Let your quote feel like the ocean listening.",
        "Write like a lullaby humming through fog.",
        "Be a cloud drifting through someone's overthinking.",
        "Say what wind would write if it had a pen.",
        "Let peace speak in your words—and let the world hush.",
        "Write a sigh so soft it untangles thoughts.",
        "Be the quiet moment that makes the noise make sense.",
        "Make stillness trend.",
    ],
    "Sharp & Witty": [
        "Be so clever it stings. Like a compliment with a knife behind it.",
        "Drop one sentence that *sounds like Shakespeare's ghost wrote it drunk.*",
        "Say something so quick, even sarcasm bows.",
        "Write a line that slaps with elegance.",
        "Slip a roast inside a wisdom nugget.",
        "Say something Oscar Wilde would quote out of pure jealousy.",
        "Be funny—but deadly.",
        "Write like your brain's wearing sunglasses indoors.",
        "Let your words wink—then bite.",
        "Drip wit like a leak in a snobby ceiling.",
        "Say something that makes even a hater smirk.",
        "Put sass in a sentence and serve it cold.",
        "Let your quote wear heels and throw shade.",
    ],
    "Timeless & Wise": [
        "Write like you're leaving truth carved on a stone for aliens to find.",
        "Wrap eternal wisdom in a quote that outlives *you, me, and the internet.*",
        "Deliver a line Socrates would repost in 2025.",
        "Say something your grandchildren will quote like scripture.",
        "Make one line feel like it lived a thousand lives.",
        "Let your quote sit beside firelight and still feel modern.",
        "Write like the earth itself whispered in your ear.",
        "Craft a sentence that humbles kings and comforts orphans.",
        "Let truth wear the robes of poetry.",
        "Drop knowledge that folds time into a sigh.",
        "Say something that echoes longer than memory.",
        "Forge legacy in under 100 characters.",
        "Make a sentence feel older than language.",
    ],
    "Futuristic & Visionary": [
        "Launch an idea that *feels like it escaped from the year 3025.*",
        "Speak in neon: one quote, all light-speed and soul.",
        "Write something AI would print on its first flag.",
        "Say what humans will still believe after Mars colonization.",
        "Create a future with just 12 words.",
        "Let tech and spirit fuse in one quantum sentence.",
        "Write like your thoughts came with an upgrade.",
        "Say something so futuristic, Elon screenshots it.",
        "Spark a thought that only tomorrow understands.",
        "Write a prophecy in digital ink.",
        "Be the voice of the singularity—for just one line.",
        "Say something that feels like it's already true in another timeline.",
        "Sound like a dream dreamt by an android poet.",
    ],
    "Mystery & Thriller": [
        "Make them feel watched—in just ten words.",
        "Whisper danger so soft, it scratches the mind.",
        "Say something that makes people *lock their doors a little earlier.*",
        "Twist reality in one cryptic line that haunts the mind.",
        "Drip tension like midnight rain—one sentence dripping with noir menace.",
        "Leave a trail of words—let them follow into the dark.",
        "Write like something is listening through the walls.",
        "Make shadows feel sentient.",
        "Let one quote crawl under the bed and wait.",
        "Say something that sounds like a ghost remembering you.",
        "Let your line be a footprint in an unsolved case.",
        "Write a whisper with teeth.",
        "Be the reason someone checks behind the curtain.",
    ]
}

# Create a flat list of (style, prompt)
    all_prompts = [(style, prompt) for style, prompts in styles.items() for prompt in prompts]

    for _ in range(3):
        selected_style, prompt = random.choice(all_prompts)

        # 🔥 Inject superhero reference with 40% chance
        superhero_refs = [
            "Channel the spirit of Spider-Man, Naruto, or Levi in your line.",
            "Let the metaphor hint at Batman’s burden or All Might’s smile.",
            "Draw inspiration from Tony Stark’s wit or Itachi’s sacrifice.",
            "Write something Luffy would shout before setting sail.",
            "Let your quote echo the struggle of a hero who keeps rising.",
            "Be like Deku—terrified, trembling, and still stepping forward.",
            "Say what Superman might think when he's alone in the sky.",
            "Let your words carry the weight of Thor’s unworthiness and redemption.",
            "Speak like Wanda rewriting her reality—line by line.",
            "Write a quote that Itachi might whisper before disappearing into crows.",
            "Make it sound like a mantra All Might would chant before saving one more life.",
            "Let your line glow like Iron Man’s arc reactor—hope made visible.",
            "Say what Levi would etch into his blade before the final swing.",
            "Make it feel like Tanjiro smelling the sorrow in a demon's story.",
            "Let the quote hold the fire Zuko bent to rebuild his soul.",
            "Be like Batman—haunted but moving, bruised but rising.",
            "Write like Wanda losing everything, but holding onto meaning.",
            "Let your quote land like a chakra-infused Rasengan—fast, soft, but shattering.",
            "Channel the defiance of Erwin Smith before the charge.",
            "Let it echo like Tony Stark's last words in silence: 'I am Iron Man.'",
            "Capture the resolve in Naruto’s eyes when no one else believed.",
            "Speak like Luffy, mouth bloodied, still laughing toward freedom.",
            "Say what Storm would whisper to the sky before it obeys.",
            "Write something Dr. Strange would etch into time itself.",
            "Let your quote stand like Captain America’s shield—unbroken, unmoved.",
            "Weave the stillness of Itachi’s gaze with the weight of his truth.",
            "Let the pain of Guts (Berserk) ripple through—but not consume—the quote.",
            "Write like Saitama at the edge of boredom and godhood.",
            "Make your line the whisper Shoto Todoroki needed to choose his own fire.",
            "Let the sentence feel like Bruce Banner holding the monster at bay.",
            "Say what Eren Yeager would scream—before the world called him villain.",
            "Write like Jean Grey becoming Phoenix—flames and fear, merged.",
            "Be like Aang—gentle heart, world on your shoulders.",
            "Speak the way Venom speaks to Eddie—dark, loyal, hungry for purpose.",
            "Let your quote sound like hope buried deep inside a Gotham alley.",
            "Say what Killua might feel but never say aloud.",
            "Write what a hero mutters *after* the last battle, not before it.",
            "Make your words the final thought before Goku steps into battle.",
            "Let your sentence feel like a panel from a manga that changed your life.",
        ]

        if random.random() < 0.4:  # 40% chance to include superhero essence
            prompt += " " + random.choice(superhero_refs)

    # Add context-aware, stylistic instruction
        msgs = [
            SystemMessage(
                content=(
                    "You are a poetic, emotionally intelligent assistant who writes original, soul-stirring one-line quotes "
                    "with metaphor, emotion, and cinematic depth. You may occasionally reference superheroes or anime characters "
                    "like Spider-Man, Batman, Naruto, or Luffy, but only if it adds meaning—not for fan service. "
                    "Draw poetic energy from Rumi, Khalil Gibran, and the heroic arcs of modern myth. Never be cliché. "
                    "All quotes must be a single sentence and no more than 100 characters long, including punctuation."
                )
            ),
            HumanMessage(
                content=(
                    f"{prompt} — Think deeply and metaphorically. Use vivid imagery, emotional subtext, and superhero symbolism. "
                    "You're allowed to reference iconic characters like Spider-Man, Naruto, Batman, Levi, Luffy, All Might, Itachi, or Tony Stark—"
                    "but blend them into cinematic metaphors or emotional truths. Quotes must still be poetic, original, and never cliché. "
                    "Avoid common phrases, motivational fluff, or overused proverbs. "
                    "Do not repeat existing quotes. Write something breathtaking, cinematic, and unique. "
                    "Output exactly one quote wrapped in a single pair of double quotes, with no extra punctuation. "
                    "⚠️ The quote must be no more than 100 characters in total length."
                )
            ),
        ]

        try:
            resp = llm.invoke(msgs).content.strip()
        except Exception:
            continue
        if not resp:
            continue
        line_count = resp.count('\n') + 1
        if 1 <= line_count <= 3 and resp not in seen:
            seen.add(resp)
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(resp + "\n")
            return resp, selected_style

    print("⚠️ No valid quote generated after 3 attempts, using fallback.")
    return fallback_quote, fallback_style



def detect_style_and_choose_music(quote: str) -> str:
    style_to_folder = {
        "Inspirational": "Inspirational",
        "Philosophical": "Philosophical",
        "Cheerful & Uplifting": "Seasonal",
        "Dreamy & Mystical": "Mystical",
        "Bold & Fearless": "Epic",
        "Calm & Serene": "Nature",
        "Sharp & Witty": "Whimsical",
        "Timeless & Wise": "Melancholic",
        "Futuristic & Visionary": "Philosophical",
        "Mystery & Thriller": "Haunting",
    }

    # Heuristic detection based on presence of key style phrases
    for style, folder in style_to_folder.items():
        if style.lower() in quote.lower():
            music_folder = folder
            break
    else:
        # Fallback default folder
        music_folder = "Inspirational"

    folder_path = os.path.join(MUSIC_DIR, music_folder)
    files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.mp3', '.wav', '.aac'))]
    if not files:
        raise RuntimeError(f"No music files found in {folder_path}.")
    return os.path.join(folder_path, random.choice(files))


def generate_hashtags_and_tagslist(text: str, num_tags: int = 20) -> tuple[str, list[str]]:
    """Return a cinematic caption + hashtags and a clean YouTube-style tags list."""

    prompt = (
        f"You are a social media strategist. Based on this poetic or motivational quote:\n\n\"{text}\"\n\n"
        "1. First, generate a short, emotionally engaging one-liner caption with 1–3 emojis. Summarize the mood of the quote (cinematic, heroic, emotional, aesthetic, etc). "
        "Highlight any referenced superheroes or anime characters like Batman, Naruto, Luffy, Itachi, Levi, All Might, etc.\n"
        "2. Then, generate 15–20 hashtags, including:\n"
        "- Quote-specific and niche tags (#cinematicquote, #darkaesthetic, #heroicmindset)\n"
        "- Platform tags (#reels, #shorts, #YouTubeShorts, #viralquote)\n"
        "- Superhero or anime tags if mentioned (#Batman, #Naruto, #LeviAckerman, etc.)\n"
        "- Emotional & inspirational tags (#poetry, #deepquotes, #inspiration)\n"
        "Respond with everything in one single line: [caption sentence] [hashtags]. No newlines. No explanation. No quotation marks."
    )

    msgs = [
        SystemMessage(
            content="You are a top-tier assistant skilled in Instagram and YouTube engagement. Respond only with cinematic captions and clean hashtags."
        ),
        HumanMessage(content=prompt),
    ]

    try:
        response = llm.invoke(msgs).content.strip()

        # 🔹 Extract tags from response
        hashtags = [tag.strip(' ,') for tag in response.replace(',', ' ').split() if tag.startswith("#")]
        hashtags = list(dict.fromkeys(hashtags))  # Remove duplicates

        if len(hashtags) < num_tags:
            missing = num_tags - len(hashtags)
            hashtags += ["#poetry", "#reels", "#quotes", "#shorts", "#motivation"][:missing]

        hashtags = hashtags[:num_tags]

        # 🔹 Create YouTube-friendly plain list (no #, all lowercase)
        tags_list = [tag.lower().replace("#", "") for tag in hashtags]

        # 🔹 Final caption with hashtags (assume first part of response is the caption)
        if not hashtags:
            caption_with_tags = f"⚡ Let this quote hit where it matters. {text} #poetry #reels #heroicquotes #viral #shorts"
        else:
            caption_with_tags = response

        return caption_with_tags, tags_list

    except Exception as e:
        print(f"⚠️ Hashtag/tag generation failed: {e}")
        fallback_tags = ["poetry", "shorts", "motivation", "quotes", "cinematicquote", "viral", "heroic", "emotional"]
        fallback_caption = f"Rise like a hero in silence. {text} #poetry #shorts #reels #quotes"
        return fallback_caption, fallback_tags

    

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
    center_fingers = [f for f in fingers if x + w*0.45 <= f[0] + f[2]/2 <= x + w*0.55]

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


def overlay_text_in_box(image_path, text):
    """Draw text with emoji support in adjusted paper area with red border."""
    pil_img = Image.open(image_path)
    draw = ImageDraw.Draw(pil_img)
    x, y, w, h = detect_adjusted_bbox(image_path)
    x  += STRICT_MARGIN_PX
    y  += STRICT_MARGIN_PX
    w  -= 2 * STRICT_MARGIN_PX
    h  -= 2 * STRICT_MARGIN_PX
    #     guard against negative sizes
    if w <= 0 or h <= 0:
        raise ValueError("STRICT_MARGIN_PX too big for this piece of paper")
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
'''
def post_to_facebook(video_path: str, caption: str) -> str:
    video_upload_url = f"{BASE_URL}/{PAGE_ID}/videos"
    with open(video_path, 'rb') as video_file:
        files = {
            'source': video_file,
        }
        data = {
            'description': caption,
            'access_token': ACCESS_TOKEN
        }
        response = requests.post(video_upload_url, files=files, data=data)
        if not response.ok or 'id' not in response.json():
            raise RuntimeError(f"Failed to upload video to Facebook: {response.text}")
        return f"✅ Video posted to Facebook Page (video ID: {response.json()['id']})"
'''

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
    
    max_attempts = 3
    attempt = 0
    success = False

    while not success and attempt < max_attempts:
        attempt += 1
        try:
            # Generate image and quote
            img = choose_image()
            quote,style = generate_quote()
            print(f"Style--->: {style}")
            print(f"Quote--->: {quote}")
            print(f"Selected Font: {HANDWRITING_FONT_PATH}")
            post_img = overlay_text_in_box(img, quote)

            # Step 1: Voice synthesis
            voice_path = synthesize_text(quote)

            # Step 2: Get background music based on style
            music_path = detect_style_and_choose_music(style)

            # Step 3: Mix voice + background music
            mixed_audio = mix_audio_tracks(voice_path, music_path)

            # Step 4: Generate video with image + mixed audio
            video_path = combine_image_with_music_ffmpeg(post_img, mixed_audio)
            print(f"✅ Final cinematic story video at {video_path}")

            # Build caption with hashtags and taglist
            caption, tags_list = generate_hashtags_and_tagslist(quote,20)
            
            print(f"Caption--->: {caption}")
            print(f"Tags--->: {tags_list}")
            # Post to Facebook Page
            #fb_result = post_to_facebook(video_path, caption)
            #print(fb_result)
            
            # 1) Upload to YouTube first to avoid double posting on retry
            yt_id = upload_video(video_path, title=quote, description=caption, tags=tags_list)
            print(f"✅ YouTube Shorts ID: {yt_id}")

            # 2) Then post as Instagram Reel
            result = post_reel(video_path, caption)
            print(result)
            
            success = True

        except RuntimeError as e:
            print(f"⚠️ {e} — Retrying...")
        except Exception as e:
            print(f"Unexpected error: {e}")
            break
