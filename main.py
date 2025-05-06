import os
import requests
import subprocess
import json
from telegram import Bot
from gtts import gTTS
from flask import Flask, request
import base64

# === KONFIGURACJA ===
REPLICATE_TOKEN = os.getenv("REPLICATE_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === MODELE REPLICATE ===
WHISPER_VERSION = "b8e0f14c5e094efca1e8cc36b5864b95c9c5e523580a38cf3606cc4976eaa46d"  # Whisper
LLAMA_VERSION = "a8f2f19a28a49cfbf2705d1fe0e3e48c621cc48bafd1b90e66c911a66b6a41b3"    # LLaMA 3 (8B)

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    video_id = data.get("video_id")

    if not video_id:
        return "❌ Brak video_id", 400

    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    audio_file = "audio.mp3"

    # === 1. Pobierz audio z YouTube ===
    result = subprocess.run(
        ["yt-dlp", "--cookies", "cookies.txt", "-f", "bestaudio", "--extract-audio", "--audio-format", "mp3", "-o", audio_file, youtube_url],
        capture_output=True,
        text=True
    )

    if "sign in" in result.stderr.lower() or "cookies" in result.stderr.lower():
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❗ Błąd pobierania filmu – prawdopodobnie potrzebne ciasteczka (cookies.txt). Zaloguj się na YouTube i uzupełnij je.")
        return "❌ Błąd pobierania", 403

    if not os.path.exists(audio_file):
        return "❌ Nie udało się pobrać audio", 500

    # === 2. Wyślij audio do Whisper (Replicate) ===
    with open(audio_file, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    whisper_payload = {
        "version": WHISPER_VERSION,
        "input": {
            "audio": f"data:audio/mp3;base64,{audio_b64}"
        }
    }

    whisper_resp = requests.post(
        "https://api.replicate.com/v1/predictions",
        headers={
            "Authorization": f"Token {REPLICATE_TOKEN}",
            "Content-Type": "application/json"
        },
        json=whisper_payload
    )

    whisper_result = whisper_resp.json()
    print("📤 Whisper response:", whisper_result)

    # Czekaj na wynik transkrypcji
    prediction_url = whisper_result["urls"]["get"]
    while True:
        status_resp = requests.get(prediction_url, headers={"Authorization": f"Token {REPLICATE_TOKEN}"})
        status_data = status_resp.json()
        if status_data["status"] == "succeeded":
            transcript_text = status_data["output"]["transcription"]
            break
        elif status_data["status"] == "failed":
            return "❌ Błąd podczas transkrypcji", 500

    # === 3. Generuj podsumowanie z LLaMA ===
    llama_payload = {
        "version": LLAMA_VERSION,
        "input": {
            "prompt": f"Podsumuj po polsku w punktach:\n{transcript_text}"
        }
    }

    summary_resp = requests.post(
        "https://api.replicate.com/v1/predictions",
        headers={
            "Authorization": f"Token {REPLICATE_TOKEN}",
            "Content-Type": "application/json"
        },
        json=llama_payload
    )

    llama_result = summary_resp.json()
    prediction_url = llama_result["urls"]["get"]
    while True:
        status_resp = requests.get(prediction_url, headers={"Authorization": f"Token {REPLICATE_TOKEN}"})
        status_data = status_resp.json()
        if status_data["status"] == "succeeded":
            summary = status_data["output"]
            break
        elif status_data["status"] == "failed":
            return "❌ Błąd podczas podsumowania", 500

    # === 4. Głos MP3 ===
    tts = gTTS(text=summary, lang="pl")
    tts.save("summary.mp3")

    # === 5. Wyślij na Telegram ===
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="🎧 Streszczenie filmu:\n" + summary)
    with open("summary.mp3", "rb") as audio:
        bot.send_audio(chat_id=TELEGRAM_CHAT_ID, audio=audio, title="Streszczenie")

    return "✅ Gotowe"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
