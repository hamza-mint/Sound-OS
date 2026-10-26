# test_basic.py - أبسط تجربة: نسجل صوتنا ونحوله لنص
import sys
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

sys.stdout.reconfigure(encoding="utf-8")   # عشان العربي يظهر صح في الـ Terminal

SAMPLE_RATE = 16000   # Whisper بيشتغل على 16 kHz
SECONDS = 4           # مدة التسجيل

# 1) تسجيل من الميكروفون
print(f"سجّل دلوقتي... اتكلم لمدة {SECONDS} ثواني")
audio = sd.rec(int(SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE,
               channels=1, dtype="float32")
sd.wait()                                   # استنى لحد ما التسجيل يخلص
import sys as _s
name = _s.argv[1] if len(_s.argv) > 1 else "test"
sf.write(f"{name}.wav", audio, SAMPLE_RATE)    # احفظه كملف WAV
print("تم التسجيل")

# 2) تحميل الموديل)
print("بحمّل الموديل...")
model = WhisperModel("small", device="cpu", compute_type="int8")

# 3) تحويل الصوت لنص
audio_data, _ = sf.read("test.wav", dtype="float32")   # يقرأ الملف كـ array
segments, info = model.transcribe(audio_data)          # من غير av
text = " ".join(s.text.strip() for s in segments)

print(f"اللغة: {info.language} (ثقة {info.language_probability:.0%})")
print(f"النص: {text}")