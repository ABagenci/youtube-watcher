import requests

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbw4GoRYIsXBGxoWt7TTKkcPa_wwIq1EBMgWsVUHKfkNYnC3cuIGbY6WYb6UdP2uTI8H/exec"  # ← Twój adres z GAS
VIDEO_ID = "1JUbMksBruI"  # ← ID testowego filmu YouTube

print("🎯 Wysyłam video_id do Colaba przez webhook GAS...")
requests.post(WEBHOOK_URL, json={"video_id": VIDEO_ID})
print("✅ Gotowe! Jeśli wszystko działa, Colab się odpali.")
