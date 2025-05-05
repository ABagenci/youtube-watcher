import requests

WEBHOOK_URL = "https://script.google.com/macros/s/TWÓJ_WEBHOOK/exec"  # ← Twój adres z GAS
VIDEO_ID = "iFyeXRu-asE"  # ← ID testowego filmu YouTube

print("🎯 Wysyłam video_id do Colaba przez webhook GAS...")
requests.post(WEBHOOK_URL, json={"video_id": VIDEO_ID})
print("✅ Gotowe! Jeśli wszystko działa, Colab się odpali.")
