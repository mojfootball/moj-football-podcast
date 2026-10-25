"""
generate_audio.py
مدیریت تولید صوت با ساختار درست API، دسته‌بندی هوشمند جملات، استفاده از wave.open و هماهنگ‌سازی با Whisper.
"""
import os
import json
import time
import wave
import io
import requests
from episode_tools import finalize_turns

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TTS_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"

def tts_chunk(chunk):
    """تولید صوت برای یک تکه از متن با ساختار استاندارد و معتبر درخواست صوتی"""
    headers = {"Content-Type": "application/json"}
    speaker = chunk.get("speaker", "male")
    text = chunk.get("text", "")
    
    # ساختار استاندارد و صحیح payload صوتی برای جلوگیری از خطای 400
    payload = {
        "contents": [{
            "parts": [{"text": f"به عنوان گوینده‌ی پادکست فوتبال، این متن را به صورت طبیعی و با لحن زنده بخوان:\n{text}"}]
        }],
        "generationConfig": {
            "response_mime_type": "audio/wav",
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": "Puck" if speaker == "male" else "Aoede"
                    }
                }
            }
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


def batch_turns(turns, max_sentences_per_chunk=2):
    """دسته‌بندی هوشمند جملات پشت سر هم برای کاهش تعداد درخواست‌های API به TTS"""
    batched = []
    current_speaker = None
    current_texts = []
    current_scene = None
    
    for turn in turns:
        spk = turn.get("speaker", "male")
        txt = turn.get("text", "")
        scene = turn.get("scene", "compare")
        
        if current_speaker is None:
            current_speaker = spk
            current_scene = scene
            current_texts = [txt]
        elif current_speaker == spk and len(current_texts) < max_sentences_per_chunk:
            current_texts.append(txt)
        else:
            batched.append({
                "speaker": current_speaker,
                "text": " ".join(current_texts),
                "scene": current_scene
            })
            current_speaker = spk
            current_scene = scene
            current_texts = [txt]
            
    if current_texts:
        batched.append({
            "speaker": current_speaker,
            "text": " ".join(current_texts),
            "scene": current_scene
        })
    return batched


def synthesize_dialogue(turns, audio_path):
    """ترکیب و ساخت کل فایل صوتی پادکست با استفاده از wave.open و دسته‌بندی جملات"""
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    
    processed_turns = batch_turns(turns, max_sentences_per_chunk=2)
    
    all_frames = []
    sample_rate = 16000
    channels = 1
    sampwidth = 2
    
    total_chunks = len(processed_turns)
    for idx, chunk in enumerate(processed_turns):
        print(f"ساخت صدا برای تکه {idx + 1} از {total_chunks}...")
        try:
            pcm_data = tts_chunk(chunk)
            if pcm_data:
                try:
                    with wave.open(io.BytesIO(pcm_data), 'rb') as wf:
                        sample_rate = wf.getframerate()
                        channels = wf.getnchannels()
                        sampwidth = wf.getsampwidth()
                        all_frames.append(wf.readframes(wf.getnframes()))
                except Exception:
                    all_frames.append(pcm_data)
        except Exception as e:
            print(f"خطا در ساخت صدای بخش {idx + 1}: {e}")
            raise e
        
        time.sleep(2)

    with wave.open(audio_path, 'wb') as wf:
        wf.setnchannels(channels if channels else 1)
        wf.setsampwidth(sampwidth if sampwidth else 2)
        wf.setframerate(sample_rate if sample_rate else 16000)
        for frames in all_frames:
            wf.writeframes(frames)

    print(f"فایل صوتی با هدر استاندارد ساخته شد: {audio_path}")
    
    total_frames_count = sum(len(f) for f in all_frames) / (channels * sampwidth if channels and sampwidth else 2)
    duration_seconds = total_frames_count / (sample_rate if sample_rate else 16000)
    return max(10.0, duration_seconds)


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
