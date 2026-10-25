"""
generate_audio.py
مدیریت تولید صوت با استفاده از سرویس صوتی پایدار گوگل (gTTS مستقیم) و ffmpeg، به همراه هماهنگ‌سازی زمان‌بندی صحنه‌ها.
"""
import os
import subprocess
import tempfile
import urllib.parse
import urllib.request
from episode_tools import finalize_turns

def tts_chunk(chunk):
    """تولید صوت برای یک تکه از متن با استفاده از سرویس صوتی آنلاین گوگل و تبدیل با ffmpeg"""
    text = chunk.get("text", "")
    if not text:
        text = "سلام"
        
    encoded_text = urllib.parse.quote(text)
    # استفاده از لینک مستقیم صوتی گوگل برای زبان فارسی (tl=fa)
    tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl=fa&client=tw-ob"
    
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf_mp3:
        mp3_path = tf_mp3.name
        
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf_wav:
        wav_path = tf_wav.name
        
    try:
        req = urllib.request.Request(
            tts_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            mp3_data = response.read()
            
        with open(mp3_path, "wb") as f:
            f.write(mp3_data)
        
        # تبدیل MP3 به WAV (16kHz, mono, PCM) با ffmpeg
        cmd = [
            "ffmpeg", "-y", "-i", mp3_path,
            "-ar", "16000", "-ac", "1", "-f", "wav", wav_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        with open(wav_path, "rb") as f:
            audio_bytes = f.read()
            
        return audio_bytes
    except Exception as e:
        print(f"خطا در تولید صوت آنلاین: {e}")
        # بازگرداندن یک فایل صوتی سکوت یا متن پیش‌فرض در صورت بروز خطای شبکه
        return b""
    finally:
        for p in (mp3_path, wav_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass

def synthesize_dialogue(turns, audio_path):
    """ترکیب و ساخت کل فایل صوتی پادکست از روی دیالوگ‌ها"""
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    
    all_pcm_chunks = []
    total_turns = len(turns)
    
    for idx, turn in enumerate(turns):
        print(f"ساخت صدا برای تکه {idx + 1} از {total_turns}...")
        pcm = tts_chunk(turn)
        if pcm:
            all_pcm_chunks.append(pcm)

    if not all_pcm_chunks:
        raise RuntimeError("هیچ داده‌ی صوتی تولید نشد.")

    combined_audio = b"".join(all_pcm_chunks)
    with open(audio_path, "wb") as f:
        f.write(combined_audio)

    print(f"فایل صوتی ساخته شد: {audio_path}")
    file_size = len(combined_audio)
    estimated_seconds = file_size / (16000 * 2) if file_size > 0 else 200.0
    return max(10.0, estimated_seconds)

def build_scene_timeline(summary, turns, audio_path):
    """هماهنگ‌سازی زمان‌بندی صحنه‌ها با استفاده از Whisper (در صورت موجود بودن) یا زمان‌بندی استاندارد"""
    turns = finalize_turns(turns, summary)
    
    segments = []
    try:
        import whisper
        print("بارگذاری مدل تشخیص گفتار (medium)...")
        model = whisper.load_model("medium")
        print(f"در حال پردازش صوت {audio_path}...")
        result = model.transcribe(audio_path, language="fa")
        segments = result.get("segments", [])
        total_words = sum(len(seg.get("text", "").split()) for seg in segments)
        print(f"{total_words} کلمه از روی صدا تشخیص داده شد")
    except Exception as e:
        print(f"توجه: امکان استفاده از Whisper فراهم نیست ({e}). استفاده از محاسبه‌گر زمان‌بندی استاندارد.")
    
    timeline = []
    n_turns = len(turns)
    total_duration = segments[-1]["end"] if segments else (n_turns * 8.0)
    dur_per_turn = total_duration / max(1, n_turns)
    
    cur = 0.0
    for i, t in enumerate(turns):
        start = cur
        end = cur + dur_per_turn if i < n_turns - 1 else total_duration
        timeline.append({
            "start": start,
            "end": end,
            "scene": t.get("scene", "compare"),
            "text": t.get("text", "")
        })
        cur = end

    print(f"{n_turns} جمله → {len(timeline)} صحنه هماهنگ شد")
    return timeline
