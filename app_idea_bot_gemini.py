import os
import random
import requests
import traceback
from datetime import datetime
from google import genai

# =========================
# CONFIG
# =========================

DEBUG = True  # Hataları görmek için True bırak, sonra istersen False yap

# Fallback için motivasyon cümleleri
MOTIVATION_QUOTES = [
    "Bugün attığın küçük adım, yarınki büyük sıçramanın provasıdır. 🚀",
    "Mükemmel olmasına gerek yok, bugün sadece *bir tık* ilerle yeter. 💪",
    "Fikirlerin bitmez, sadece yazmaya üşenme. 😊",
    "Küçük ama tutarlı projeler, hayat değiştirir. 🔁",
    "Her uygulama, bir 'ya şöyle bir şey olsa...' cümlesiyle başlar. ✨"
]

# Fallback için statik uygulama fikirleri
FALLBACK_IDEAS = [
    "📚 KPSS / TYT çalışma takip uygulaması: günlük hedefler, seri bazlı istatistik, mini bildirim hatırlatıcı.",
    "💸 Harcama vs. hedef para biriktirme uygulaması: günlük tek soru ile 'bunu alsam mı, almasam mı?' kararı verdiren koç.",
    "🍎 Günlük kalori + adım takibi, ama ultra sade tek ekran mantığıyla 'yap ya da yapma' gösteren app.",
    "📈 BIST / coin için 'bugünün 3 önemli haberi + 1 grafik' gösteren minimal dashboard.",
    "🧠 Her gün 3 soru çözdüren mikro sınav uygulaması: soru, çözüm, mini not; hepsi 5 dakikada biter.",
]

# Ortam değişkenlerini oku
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def dprint(*args, **kwargs):
    """Debug print."""
    if DEBUG:
        print("[DEBUG]", *args, **kwargs, flush=True)


# =========================
# GEMINI İLE FİKİR ÜRETME
# =========================

def build_gemini_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY ortam değişkeni tanımlı değil.")
    dprint("Gemini client oluşturuluyor, API key uzunluğu:", len(GEMINI_API_KEY))
    client = genai.Client(api_key=GEMINI_API_KEY)
    return client


def generate_idea_with_gemini():
    """
    Gemini'den tek bir, niş ve mantıklı uygulama fikri ister.
    Çıktı: Sade Türkçe metin (1 fikir).
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

    dprint("Gemini'ye istek gönderiliyor...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    text = getattr(response, "text", None)
    dprint("Gemini yanıt döndü, text var mı:", bool(text))
    if not text:
        raise RuntimeError("Gemini yanıtında text alanı boş geldi.")
    return text.strip()


# =========================
# MESAJ OLUŞTURMA
# =========================

def build_message():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    quote = random.choice(MOTIVATION_QUOTES)

    try:
        idea_text = generate_idea_with_gemini()
        header = "🧠 *Günün Uygulama Fikri (Gemini)*"
    except Exception as e:
        dprint("Gemini çağrısı sırasında hata oluştu!")
        dprint("Hata:", repr(e))
        dprint("Traceback:\n", traceback.format_exc())
        fallback_idea = random.choice(FALLBACK_IDEAS)
        idea_text = (
            fallback_idea
            + f"\n\n(ℹ️ Gemini hata verdi, fallback fikir gösterildi. Hata: {e})"
        )
        header = "🧠 *Günün Uygulama Fikri (Fallback)*"

    message = (
        f"{header}\n\n"
        f"{idea_text}\n\n"
        f"💬 {quote}\n\n"
        f"⏰ {now}"
    )
    return message


# =========================
# TELEGRAM'A MESAJ GÖNDERME
# =========================

def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN tanımlı değil.")
    if not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID tanımlı değil.")

    # Token'i güvenlik için tamamen göstermiyoruz (ilk 8 karakter + ...)
    token_preview = TELEGRAM_BOT_TOKEN[:8] + "..." if TELEGRAM_BOT_TOKEN else "YOK"
    dprint("Telegram'a mesaj gönderiliyor...")
    dprint("Bot token preview:", token_preview)
    dprint("Chat ID:", TELEGRAM_CHAT_ID)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }

    dprint("POST URL:", url)
    dprint("Payload:", payload)

    resp = requests.post(url, json=payload)
    dprint("Telegram response status code:", resp.status_code)
    dprint("Telegram response text:", resp.text)

    # 2xx değilse raise_for_status hata fırlatacak (logları gördüğümüz için sorun değil)
    resp.raise_for_status()
    return resp.json()


# =========================
# MAIN
# =========================

def print_env_debug():
    """Ortamdaki kritik değişkenler hakkında bilgi yaz (değerleri değil, var mı yok mu)."""
    dprint("=== ENV DEBUG ===")
    dprint("TELEGRAM_BOT_TOKEN set mi? ->", bool(TELEGRAM_BOT_TOKEN))
    dprint("TELEGRAM_CHAT_ID set mi?  ->", bool(TELEGRAM_CHAT_ID))
    dprint("GEMINI_API_KEY set mi?    ->", bool(GEMINI_API_KEY))
    if TELEGRAM_CHAT_ID:
        dprint("TELEGRAM_CHAT_ID değeri:", TELEGRAM_CHAT_ID)
    dprint("==================")


if __name__ == "__main__":
    print_env_debug()
    try:
        msg = build_message()
        dprint("Oluşturulan mesaj:\n", msg)
        send_telegram_message(msg)
        dprint("Mesaj başarıyla gönderildi ✅")
    except Exception as e:
        print("[FATAL] Script hata ile bitti:", repr(e))
        print("[FATAL] Traceback:\n", traceback.format_exc())
        # GitHub Actions'ta hata olsun diye exit 1
        raise
