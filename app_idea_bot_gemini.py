import os
import random
import requests
from datetime import datetime
from google import genai

# Ortam değişkenleri (GitHub Secrets'ten gelecek)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Fallback için statik motivasyon cümleleri
MOTIVATION_QUOTES = [
    "Bugün attığın küçük adım, yarınki büyük sıçramanın provasıdır. 🚀",
    "Mükemmel olmasına gerek yok, bugün sadece *bir tık* ilerle yeter. 💪",
    "Fikirlerin bitmez, sadece yazmaya üşenme. 😊",
    "Küçük ama tutarlı projeler, hayat değiştirir. 🔁",
    "Her uygulama, bir 'ya şöyle bir şey olsa...' cümlesiyle başlar. ✨"
]

FALLBACK_IDEAS = [
    "📚 KPSS / TYT çalışma takip uygulaması: günlük hedefler, seri bazlı istatistik, mini bildirim hatırlatıcı.",
    "💸 Harcama vs. hedef para biriktirme uygulaması: günlük tek soru ile 'bunu alsam mı, almasam mı?' kararı verdiren koç.",
    "🍎 Günlük kalori + adım takibi, ama ultra sade tek ekran mantığıyla 'yap ya da yapma' gösteren app.",
    "📈 BIST / coin için 'bugünün 3 önemli haberi + 1 grafik' gösteren minimal dashboard.",
    "🧠 Her gün 3 soru çözdüren mikro sınav uygulaması: soru, çözüm, mini not; hepsi 5 dakikada biter.",
]

def build_gemini_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY ortam değişkeni tanımlı değil.")
    return genai.Client(api_key=GEMINI_API_KEY)

def generate_idea_with_gemini():
    """
    Gemini'den tek bir, niş ve mantıklı uygulama fikri ister.
    Çıktı: Sade Türkçe metin (liste, markdown başlık vs. istemiyoruz).
    """
    client = build_gemini_client()

    prompt = """
Sen deneyimli bir mobil ürün ve growth danışmanısın.
Görevin, Android için *niş ama mantıklı* bir uygulama fikri önermek.

Kurallar:
- Çıktıyı TÜRKÇE yaz.
- Sadece *TEK* uygulama fikri üret.
- Fikir, Play Store’da çok kopyası olmayan ama gerçek kullanıcıya fayda sağlayacak bir şey olsun.
- Özellikle:
  - Öğrenciler, yazılımcılar, traderlar, içerik üreticileri gibi kitlelere yönelik olabilir.
  - Uygulama mümkün olduğunca tek ekran veya basit akış mantığında olsun.
  - Backend maliyeti düşük veya ücretsiz servislerle yapılabilir olsun (Firebase, GitHub Actions, vs.)

Çıktı formatı:
- İlk satırda kısa bir başlık (örn: "🎯 Akıllı KPSS Çalışma Koçu")
- Sonraki 5-10 satırda:
  - Fikrin ne işe yaradığını
  - Kullanıcıyı nasıl her gün geri getireceğini (habit / gamification)
  - Basit bir gelir modeli fikri (reklam, abonelik, tek seferlik ödeme vb.)

LÜTFEN:
- Madde işareti kullanabilirsin ama 1 fikrin etrafında toparla.
- Birden fazla fikir verme.
"""

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
    )

    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini yanıtında text alanı boş geldi.")
    return text.strip()

def build_message():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    quote = random.choice(MOTIVATION_QUOTES)

    try:
        idea_text = generate_idea_with_gemini()
        header = "🧠 *Günün Uygulama Fikri (Gemini)*"
    except Exception as e:
        # Gemini hata verirse fallback
        fallback_idea = random.choice(FALLBACK_IDEAS)
        idea_text = fallback_idea + f"\n\n(ℹ️ Gemini hata verdi, fallback fikir gösterildi: {e})"
        header = "🧠 *Günün Uygulama Fikri (Fallback)*"

    message = (
        f"{header}\n\n"
        f"{idea_text}\n\n"
        f"💬 {quote}\n\n"
        f"⏰ {now}"
    )
    return message

def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID tanımlı değil.")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    msg = build_message()
    send_telegram_message(msg)
