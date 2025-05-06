from flask import Flask, request, jsonify
import subprocess
import os
import requests
from gtts import gTTS
import replicate

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")

os.environ["REPLICATE_API_TOKEN"] = REPLICATE_TOKEN

# ======== FUNKCJE TELEGRAM =========

def send_telegram_message(message, parse_mode=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Błąd wysyłania wiadomości na Telegram: {e}")

def send_telegram_audio(audio_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
    try:
        with open(audio_path, "rb") as audio:
            response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID}, files={"audio": audio})
            response.raise_for_status()
    except Exception as e:
        send_telegram_message(f"❗ Błąd wysyłania audio: {e}")

def log_error_to_telegram(title, message):
    full_message = f"{title}\n```\n{message}\n```"
    send_telegram_message(full_message, parse_mode="Markdown")

# ======== YT-DLP: POBIERANIE AUDIO =========

def download_audio(video_id):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    output_path = f"downloads/{video_id}.mp3"
    cookies_path = os.path.abspath("cookies.txt")

    send_telegram_message("📥 Rozpoczynam pobieranie filmu...")
    send_telegram_message(f"🎬 URL: {video_url}")
    send_telegram_message(f"🧾 Ścieżka cookies: {cookies_path}")
    send_telegram_message(f"📁 Ścieżka MP3: {output_path}")

    command = [
        "yt-dlp",
        "--cookies", cookies_path,
        "-f", "bestaudio",
        "--extract-audio",
        "--audio-format", "mp3",
        "-o", output_path,
        video_url
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            log_error_to_telegram("❗ yt-dlp zakończone błędem", result.stderr)
            return None

        send_telegram_message("✅ Pomyślnie pobrano audio.")
        return output_path

    except Exception as e:
        log_error_to_telegram("❗ Błąd wykonania yt-dlp", str(e))
        return None

# ======== TRANSKRYPCJA WHISPER + STRESZCZENIE LLaMA =========

def transcribe_audio(audio_path):
    send_telegram_message("🧠 Rozpoczynam transkrypcję...")
    try:
        output = replicate.run(
            "openai/whisper",
            input={"audio": open(audio_path, "rb")}
        )
        transcript = output["transcription"]
        send_telegram_message("✅ Transkrypcja zakończona.")
        return transcript
    except Exception as e:
        log_error_to_telegram("❗ Błąd transkrypcji", str(e))
        return None

def summarize_text(text):
    send_telegram_message("📄 Tworzę podsumowanie...")
    try:
        output = replicate.run(
            "meta/meta-llama-3-8b-instruct",
            input={"prompt": f"Streszcz poniższy tekst:\n{text}"}
        )
        summary = "".join(output)
        send_telegram_message("✅ Podsumowanie gotowe.")
        return summary
    except Exception as e:
        log_error_to_telegram("❗ Błąd streszczania", str(e))
        return None

# ======== GENEROWANIE AUDIO Z GTTS =========

def generate_tts(text, output_path="summary.mp3"):
    send_telegram_message("🔊 Generuję plik audio z podsumowaniem...")
    try:
        tts = gTTS(text)
        tts.save(output_path)
        send_telegram_message("✅ Audio z podsumowaniem gotowe.")
        return output_path
    except Exception as e:
        log_error_to_telegram("❗ Błąd TTS (gTTS)", str(e))
        return None

# ======== FLASK: OBSŁUGA WEBHOOKA =========

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    video_id = data.get("video_id")
    if not video_id:
        send_telegram_message("❗ Brak video_id w zapytaniu.")
        return jsonify({"error": "No video_id"}), 400

    send_telegram_message(f"📡 Odebrano webhook dla: `{video_id}`", parse_mode="Markdown")

    audio_path = download_audio(video_id)
    if not audio_path:
        return jsonify({"error": "Błąd pobierania"}), 500

    transcript = transcribe_audio(audio_path)
    if not transcript:
        return jsonify({"error": "Błąd transkrypcji"}), 500

    summary = summarize_text(transcript)
    if not summary:
        return jsonify({"error": "Błąd streszczenia"}), 500

    send_telegram_message(f"📝 *Streszczenie filmu:*\n{summary}", parse_mode="Markdown")

    summary_audio = generate_tts(summary)
    if summary_audio:
        send_telegram_audio(summary_audio)

    return jsonify({"status": "OK"}), 200

# ======== KEEP ALIVE (PING) =========

@app.route('/')
def ping():
    return "✅ Agent działa", 200

# ======== START SERVERA =========

if __name__ == '__main__':
    os.makedirs("downloads", exist_ok=True)
    app.run(host='0.0.0.0', port=8080)
