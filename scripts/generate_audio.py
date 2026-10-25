"""
generate_audio.py
مدیریت تولید صوت با سرویس Gemini TTS و هماهنگ‌سازی زمان‌بندی با Whisper (با واردسازی امن).
"""
import os
import json
import time
import requests
from episode_tools import finalize_turns

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TTS_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"

def tts_chunk(chunk):
    """تولید صوت برای یک تکه از متن با استفاده از جمنای و مدیریت هوشمند خطای 429"""
    headers = {"Content-Type": "application/json"}
    speaker = chunk.get("speaker", "male")
    text = chunk.get("text", "")
    
    prompt = f"Speak the following Persian podcast dialogue naturally as a {speaker} podcast host:\n{text}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "audio/wav"
        }
    }

    last_error = None
    for attempt in range(1, 6):
        try:
            resp = requests.post(f"{TTS_URL}?key={API_KEY}", json=payload, headers=headers, timeout=90)
            
            if resp.status_code == 429:
                sleep_time = 12 * attempt
                print(f"محدودیت نرخ (429 Too Many Requests) در تولید صوت. استراحت به مدت {sleep_time} ثانیه (تلاش {attempt}/5)...")
                time.sleep(sleep_time)
                continue
                
            resp.raise_for_status()
            
            data = resp.json()
            candidate = data.get("candidates", [{}])[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            audio_bytes = None
            for p in parts:
                if "inlineData" in p and "data" in p["inlineData"]:
                    import base64
                    audio_bytes = base64.b64decode(p["inlineData"]["data"])
                    break
            
            if audio_bytes:
                return audio_bytes
            else:
                raise ValueError("داده‌ی صوتی در پاسخ API یافت نشد.")

        except requests.RequestException as e:
            last_error = e
            sleep_time = 10 * attempt
            print(f"خطا در ارتباط با سرور TTS (تلاش {attempt}/5): {e}. تکرار پس از {sleep_time} ثانیه...")
            time.sleep(sleep_time)
        except Exception as e:
            last_error = e
            print(f"خطای ناشناخته در ساخت صدا: {e}")
            break

    if last_error:
        raise last_error
    raise RuntimeError("تولید صدا پس از چندین تلاش ناموفق بود.")


def synthesize_dialogue(turns, audio_path):
    """ترکیب و ساخت کل فایل صوتی پادکست از روی دیالوگ‌ها با جمنای"""
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    
    all_pcm_chunks = []
    total_turns = len(turns)
    
    for idx, turn in enumerate(turns):
        print(f"ساخت صدا برای تکه {idx + 1} از {total_turns}...")
        try:
            pcm = tts_chunk(turn)
            if pcm:
                all_pcm_chunks.append(pcm)
        except Exception as e:
            print(f"خطا در ساخت صدای بخش {idx + 1}: {e}")
            raise e
        
        time.sleep(2)

    combined_audio = b"".join(all_pcm_chunks)
    with open(audio_path, "wb") as f:
        f.write(combined_audio)

    print(f"فایل صوتی ساخته شد: {audio_path}")
    file_size = len(combined_audio)
    estimated_seconds = file_size / (16000 * 2) if file_size > 0 else 200.0
    return max(10.0, estimated_seconds)


def build_scene_timeline(summary, turns, audio_path):
    """تشخیص گفتار با Whisper (در صورت نصب بودن) و هماهنگ‌سازی زمان‌بندی صحنه‌ها با دیالوگ‌ها"""
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

    print(f"{n_turns} جمله → {len(timeline)} صحنه هماهنگ با صدا")
    return timeline
