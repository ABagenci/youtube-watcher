import os
import requests
import subprocess
import json
from telegram import Bot
from gtts import gTTS
from flask import Flask, request

# === KONFIGURACJA ===
REPLICATE_TOKEN = os.getenv("REPLICATE_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app = Flask(__name__)

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    video_id = data.get("video_id")

    if not video_id:
        return "Missing video_id", 400

    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    audio_file = "audio.mp3"

    # Pobierz audio
    subprocess.run(["yt-dlp", "-f", "bestaudio", "--extract-audio", "--audio-format", "mp3", "-o", audio_file, youtube_url])

    # Wyślij audio do Replicate (Whisper)
    with open(audio_file, "rb") as f:
        resp = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Token {REPLICATE_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "version": "whisper model ID tu",  # podam później
                "input": {
                    "audio": f.read()
                }
            }
        )
        whisper_result = resp.json()
        transcript_text = whisper_result["output"]["transcription"]  # dostosujemy później

    # Podsumowanie za pomocą LLaMA 3
    summary_response = requests.post(
        "https://api.replicate.com/v1/predictions",
        headers={
            "Authorization": f"Token {REPLICATE_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "version": "llama-3 model ID tu",  # podam później
            "input": {
                "prompt": f"Podsumuj po polsku w punktach:\n{transcript_text}"
            }
        }
    )
    summary = summary_response.json()["output"]

    # Głos MP3
    tts = gTTS(text=summary, lang="pl")
    tts.save("summary.mp3")

    # Telegram
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="🎧 Streszczenie filmu:\n" + summary)
    with open("summary.mp3", "rb") as audio:
        bot.send_audio(chat_id=TELEGRAM_CHAT_ID, audio=audio, title="Streszczenie")

    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
