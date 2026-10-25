"""
generate_audio.py
مدیریت تولید صوت و اتصال به سرویس TTS برای پادکست.
"""
import os
import json
import time
import requests

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TTS_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"

def tts_chunk(chunk):
    """تولید صوت برای یک تکه از متن با مدیریت هوشمند خطای 429 و تلاش مجدد"""
    headers = {"Content-Type": "application/json"}
    
    # تفکیک گوینده برای تنظیم صدا یا لحن در صورت نیاز
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
            
            # اگر خطای Too Many Requests رخ داد، زمان انتظار را بیشتر می‌کنیم
            if resp.status_code == 429:
                sleep_time = 12 * attempt
                print(f"محدودیت نرخ (429 Too Many Requests) در تولید صوت. استراحت به مدت {sleep_time} ثانیه (تلاش {attempt}/5)...")
                time.sleep(sleep_time)
                continue
                
            resp.raise_for_status()
            
            # استخراج داده صوتی از پاسخ
            data = resp.json()
            # بسته به ساختار بازگشتی پاسخ API صوتی
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
    """ترکیب و ساخت کل فایل صوتی پادکست از روی دیالوگ‌ها"""
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
        
        # وقفه کوتاه بین درخواست‌ها برای جلوگیری از فشار روی API و بروز خطای 429
        time.sleep(2)

    # ذخیره‌سازی نهایی فایل صوتی
    # ترکیب و ذخیره‌سازی بایت‌های صوتی در مسیر مشخص شده
    combined_audio = b"".join(all_pcm_chunks)
    with open(audio_path, "wb") as f:
        f.write(combined_audio)

    print(f"فایل صوتی ساخته شد: {audio_path}")
    
    # بازگرداندن مدت زمان تقریبی یا واقعی فایل صوتی
    # محاسبه از روی حجم فایل یا بازگرداندن ثانیه پیش‌فرض
    file_size = len(combined_audio)
    estimated_seconds = file_size / (16000 * 2) if file_size > 0 else 200.0
    return max(10.0, estimated_seconds)
