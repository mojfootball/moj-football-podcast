import os
import json
import time
import base64
import wave
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
TTS_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash-preview-tts:generateContent"
)

MALE_NAME = "مجتبآ"
FEMALE_NAME = "پگاه"
MALE_VOICE = "Algenib"
MALE_VOICE = "Algenib"
FEMALE_VOICE = "Pulcherrima"

SAMPLE_RATE = 24000

STYLE_INSTRUCTION = (
    "با لحنی پرانرژی، محکم، شاد و هیجان‌انگیز صحبت کن، مثل دو مجری ورزشی حرفه‌ای "
    "زنده روی آنتن که کاملاً سرحال و جذابن. به‌هیچ‌وجه آروم، یکنواخت، خسته، آهسته "
    "یا با لحن کتاب‌خوانی/لالایی صحبت نکن:"
)


def turns_to_text_block(turns):
    lines = [STYLE_INSTRUCTION, ""]
    for t in turns:
        name = MALE_NAME if t["speaker"] == "male" else FEMALE_NAME
        lines.append(name + ": " + t["text"])
    return "\n".join(lines)


def tts_chunk(turns_chunk):
    text_block = turns_to_text_block(turns_chunk)
    payload = {
        "contents": [{"parts": [{"text": text_block}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "multiSpeakerVoiceConfig": {
                    "speakerVoiceConfigs": [
                        {
                            "speaker": MALE_NAME,
                            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": MALE_VOICE}},
                        },
                        {
                            "speaker": FEMALE_NAME,
                            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": FEMALE_VOICE}},
                        },
                    ]
                }
            },
        },
    }

    last_error = None
    for attempt in range(5):
        if attempt > 0:
            time.sleep(10 * attempt)
        try:
            resp = requests.post(f"{TTS_URL}?key={GEMINI_API_KEY}", json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            part = data["candidates"][0]["content"]["parts"][0]
            inline = part.get("inlineData") or part.get("inline_data")
            return base64.b64decode(inline["data"])
        except requests.RequestException as e:
            last_error = e
            print(f"تلاش {attempt + 1} برای یه تکه از صدا ناموفق بود: {e}")

    raise last_error


def chunk_turns(turns, size=6):
    for i in range(0, len(turns), size):
        yield turns[i:i + size]


def synthesize_dialogue(turns, output_path):
    all_pcm = bytearray()
    chunks = list(chunk_turns(turns, size=6))
    for i, chunk in enumerate(chunks):
        print(f"ساخت صدا برای تکه {i + 1} از {len(chunks)}...")
        pcm = tts_chunk(chunk)
        all_pcm.extend(pcm)

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(bytes(all_pcm))

    print(f"فایل صوتی ساخته شد: {output_path}")


if __name__ == "__main__":
    import sys
    from fetch_match_details import get_match_details
    from generate_analysis import summarize_match, generate_persian_script

    match_id = int(sys.argv[1])
    details = get_match_details(match_id)
    summary = summarize_match(details)
    turns = generate_persian_script(summary)

    with open("dialogue.json", "w", encoding="utf-8") as f:
        json.dump(turns, f, ensure_ascii=False, indent=2)

    synthesize_dialogue(turns, "episode.wav")
