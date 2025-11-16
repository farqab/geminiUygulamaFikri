import os
import random
import requests
import traceback
from datetime import datetime
from google import genai

DEBUG = True  # İstersen sonra False yaparsın

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def dprint(*args, **kwargs):
    if DEBUG:
        print("[DEBUG]", *args, **kwargs, flush=True)


# İncelemek istediğimiz nişler / kategoriler
NICHES = [
    {
        "id": "exam_calculator",
        "name_tr": "Sınav Notu Hesaplayıcı (TYT/KPSS/üniversite)",
        "store_keywords": ["exam grade calculator", "not hesaplama", "sinav ortalama hesaplama"],
    },
    {
        "id": "habit_tracker_students",
        "name_tr": "Öğrenciler için Alışkanlık Takip Uygulaması",
        "store_keywords": ["habit tracker", "study habit tracker", "öğrenci çalışma takibi"],
    },
    {
        "id": "study_planner",
        "name_tr": "Çalışma Planlayıcı / Pomodoro",
        "store_keywords": ["study planner", "pomodoro study timer", "ders çalışma planı"],
    },
    {
        "id": "personal_finance",
        "name_tr": "Kişisel Bütçe / Harcama Takip",
        "store_keywords": ["expense tracker", "budget manager", "harcama takip"],
    },
    {
        "id": "market_prices",
        "name_tr": "Hal / Market Fiyatı Takip Uygulamaları",
        "store_keywords": ["grocery price tracker", "market prices", "fiyat karşılaştırma"],
    },
]


def build_gemini_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil.")
    dprint("Gemini client oluşturuluyor, API key uzunluğu:", len(GEMINI_API_KEY))
    return genai.Client(api_key=GEMINI_API_KEY)


def generate_research_for_niche(niche: dict) -> str:
    """
    Belirli bir Play Store nişi için rekabet + fırsat analizi üretir.
    Gerçek Play Store scraping yapmıyoruz, Gemini'e 'bu kategorideki tipik uygulamaları analiz et'
    şeklinde akıllı bir analiz yaptırıyoruz.
    """
    client = build_gemini_client()

    keywords = ", ".join(niche["store_keywords"])
    name_tr = niche["name_tr"]

    prompt = f"""
Sen deneyimli bir ürün yöneticisi ve growth danışmanısın.
Görevin, Google Play Store'daki şu niş için rakip ve fırsat analizi yapmak:

Niş (Türkçe açıklama): {name_tr}
Tahmini Play Store arama kelimeleri: {keywords}

Analizi TÜRKÇE yaz. Lütfen aşağıdaki başlıkları sırayla kullan:

1) 🎯 Nişin Özeti
- Bu uygulama kategorisi ne işe yarar?
- Kimler kullanır (hedef kitle)?
- Kullanıcıların en sık çözdürmek istediği problem ne?

2) 📱 Tipik Rakip Uygulama Özellikleri
- Bu kategorideki uygulamaların genelde sunduğu temel özellikleri madde madde yaz.
- Kullanıcı deneyimi açısından sık görülen iyi yanları ekle.

3) 😬 Kullanıcı Şikayetleri ve Eksikler
- Bu tip uygulamaların kullanıcı yorumlarında sık görülen şikayetleri tahmini olarak özetle
  (örneğin: reklam fazlalığı, karmaşık tasarım, kayıt zorunluluğu, vb.)
- Her maddeyi '•' ile başlat ve kısa, net yaz.

4) 🧠 Sen Nasıl Farklılaşırdın?
- Bu nişte yeni bir uygulama yapsak, diğerlerinden net şekilde ayrışmak için 4–6 tane güçlü fikir öner.
- Özellikle: sadelik, offline çalışma, ücretsiz özellikler, öğrenciler için ekstra faydalar gibi
  niş fikirler üret.
- Her maddeyi '•' ile yaz.

5) 💰 Gelir Modeli Önerileri
- Bu niş için mantıklı 2–3 gelir modeli fikri yaz (reklam, tek seferlik premium, abonelik, vb.)
- Her model için: avantaj + dezavantajı 1 cümle ile açıkla.

6) ⚙️ Hızlı MVP Önerisi (1. Versiyon)
- MVP'de olması gereken en az özellikleri yaz (3–6 madde).
- Özellikle: 'ilk 1 haftada kodlanabilir' seviyede sade tut.

KISA AMA YOĞUN BİR RAPOR OLSUN.
Gereksiz süsleme yapma, direkt işimize yarayacak bilgiyi ver.
"""

    dprint(f"Gemini'ye Play Store nişi için istek gönderiliyor: {name_tr}")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini yanıtında text alanı boş geldi (rekabet analizi).")
    return text.strip()


def build_message():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    niche = random.choice(NICHES)
    dprint("Seçilen niş:", niche["id"], "-", niche["name_tr"])

    try:
        analysis = generate_research_for_niche(niche)
        header = "📊 *Günün Play Store Pazar Analizi (Gemini)*"
        niche_line = f"🎯 Niş: *{niche['name_tr']}*"
        body = analysis
    except Exception as e:
        dprint("Gemini çağrısı sırasında hata oluştu (pazar analizi)!")
        dprint("Hata:", repr(e))
        dprint("Traceback:\n", traceback.format_exc())
        header = "📊 *Günün Play Store Pazar Analizi (Fallback)*"
        niche_line = "🎯 Niş: *Genel Uygulama Pazarı*"
        body = (
            "Bugün Gemini'den detaylı analiz alınamadı, ama genel strateji:\n"
            "• Sadelik\n• Net hedef kitle\n• Kullanıcı yorumlarını sürekli dinleyip hızlı iterasyon.\n\n"
            f"(Hata detayı: {e})"
        )

    message = (
        f"{header}\n\n"
        f"{niche_line}\n\n"
        f"{body}\n\n"
        f"⏰ {now}"
    )
    return message


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN tanımlı değil.")
    if not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID tanımlı değil.")

    token_preview = TELEGRAM_BOT_TOKEN[:8] + "..."
    dprint("Telegram'a pazar analizi mesajı gönderiliyor...")
    dprint("Bot token preview:", token_preview)
    dprint("Chat ID:", TELEGRAM_CHAT_ID)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }

    dprint("POST URL:", url)
    dprint("Payload hazır, istek atılıyor...")
    resp = requests.post(url, json=payload)
    dprint("Telegram response status code:", resp.status_code)
    dprint("Telegram response text:", resp.text)

    resp.raise_for_status()
    return resp.json()


def print_env_debug():
    dprint("=== ENV DEBUG (Play Store Ajanı) ===")
    dprint("TELEGRAM_BOT_TOKEN set mi? ->", bool(TELEGRAM_BOT_TOKEN))
    dprint("TELEGRAM_CHAT_ID set mi?  ->", bool(TELEGRAM_CHAT_ID))
    dprint("GEMINI_API_KEY set mi?    ->", bool(GEMINI_API_KEY))
    if TELEGRAM_CHAT_ID:
        dprint("TELEGRAM_CHAT_ID:", TELEGRAM_CHAT_ID)
    dprint("====================================")


if __name__ == "__main__":
    print_env_debug()
    try:
        msg = build_message()
        dprint("Oluşturulan pazar analizi mesajı:\n", msg)
        send_telegram_message(msg)
        dprint("Pazar analizi mesajı başarıyla gönderildi ✅")
    except Exception as e:
        print("[FATAL] Play Store ajan script hata ile bitti:", repr(e))
        print("[FATAL] Traceback:\n", traceback.format_exc())
        raise
