import os
import random
import requests
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from google import genai
import re

DEBUG = True  # Test sürecinde True bırak, sonra istersen False yaparsın.

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
        "name_tr": "Sınav Notu Hesaplayıcı (TYT/KPSS/Üniversite)",
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


# ======================
# Play Store Scraper
# ======================

class PlayStoreScraper:
    BASE_SEARCH_URL = "https://play.google.com/store/search"
    BASE_DETAIL_URL = "https://play.google.com/store/apps/details"

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            # Biraz normal tarayıcıya benzesin diye User-Agent ayarlıyoruz
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

    def search_apps(self, query: str, max_results: int = 5):
        """
        Play Store arama sayfasından app id listesi çıkarır.
        """
        params = {"q": query, "c": "apps", "hl": "en", "gl": "us"}
        dprint(f"[Scraper] Play Store search: {query}")
        resp = self.session.get(self.BASE_SEARCH_URL, params=params, headers=self.headers, timeout=20)
        dprint("[Scraper] Search status code:", resp.status_code)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        app_ids = []
        seen_ids = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/store/apps/details?id=" in href:
                app_id = href.split("id=")[-1].split("&")[0]
                if app_id and app_id not in seen_ids:
                    seen_ids.add(app_id)
                    app_ids.append(app_id)
                    dprint("[Scraper] Found app id:", app_id)
                    if len(app_ids) >= max_results:
                        break

        dprint(f"[Scraper] Total app ids found for '{query}':", len(app_ids))
        return app_ids

    def fetch_app_details(self, app_id: str):
        """
        Uygulamanın detay sayfasından temel bilgileri çeker.
        Not: Play Store HTML yapısı değişebilir, bu v1 "best effort" bir scraper.
        """
        params = {"id": app_id, "hl": "en", "gl": "us"}
        dprint(f"[Scraper] Fetching details for app_id={app_id}")
        resp = self.session.get(self.BASE_DETAIL_URL, params=params, headers=self.headers, timeout=20)
        dprint("[Scraper] Detail status code:", resp.status_code)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Uygulama adı
        name = None
        h1 = soup.find("h1")
        if h1:
            span = h1.find("span")
            name = (span.get_text(strip=True) if span else h1.get_text(strip=True))
        if not name:
            name = app_id

        # Açıklama (summary)
        summary = ""
        meta_desc = soup.find("meta", itemprop="description")
        if meta_desc and meta_desc.get("content"):
            summary = meta_desc["content"].strip()
        else:
            # Fallback: bazı div'lerde açıklama olabilir
            desc_div = soup.find("div", attrs={"jsname": "bN97Pc"}) or soup.find("div", attrs={"jsname": "sngebd"})
            if desc_div:
                summary = desc_div.get_text(" ", strip=True)

        # Rating (best effort)
        rating = None
        aria_divs = soup.find_all("div", attrs={"aria-label": True})
        for div in aria_divs:
            label = div["aria-label"]
            if "Rated" in label and "stars out of five stars" in label:
                m = re.search(r"Rated ([0-9.]+) stars", label)
                if m:
                    try:
                        rating = float(m.group(1))
                    except ValueError:
                        pass
                break

        # Installs (best effort, metin içinde arama)
        installs = None
        full_text = soup.get_text(" ", strip=True)
        m2 = re.search(r"([0-9.,]+[KMB+]+)\s+downloads", full_text, re.IGNORECASE)
        if m2:
            installs = m2.group(1)

        return {
            "app_id": app_id,
            "name": name,
            "summary": summary,
            "rating": rating,
            "installs": installs,
        }


def gather_niche_apps(niche: dict, max_apps: int = 5):
    """
    Niş için tanımlı anahtar kelimelerden birini kullanarak Play Store'dan uygulama listesi çeker.
    İlk keyword öncelikli, sonuç çıkmazsa diğerlerine geçer.
    """
    scraper = PlayStoreScraper()
    app_details = []

    for keyword in niche["store_keywords"]:
        try:
            app_ids = scraper.search_apps(keyword, max_results=max_apps)
            if not app_ids:
                continue
            for app_id in app_ids[:max_apps]:
                try:
                    details = scraper.fetch_app_details(app_id)
                    app_details.append(details)
                except Exception as e:
                    dprint(f"[Scraper] WARN: detay çekilemedi ({app_id}):", repr(e))
            if app_details:
                break  # Bu keyword yeterli uygulama döndürdüyse diğer keyword'lere geçmeye gerek yok
        except Exception as e:
            dprint(f"[Scraper] WARN: arama başarısız ({keyword}):", repr(e))

    return app_details


# ======================
# GEMINI ANALİZ
# ======================

def build_gemini_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil.")
    dprint("Gemini client oluşturuluyor, API key uzunluğu:", len(GEMINI_API_KEY))
    return genai.Client(api_key=GEMINI_API_KEY)


def format_apps_for_prompt(apps, max_chars=2500):
    """
    Gemini'ye vereceğimiz ham veriyi kısa ama yeterli şekilde formatlayalım.
    """
    lines = []
    for i, app in enumerate(apps, start=1):
        summary = app.get("summary") or ""
        if len(summary) > 220:
            summary = summary[:220] + "..."
        lines.append(
            f"{i}) Name: {app.get('name')}\n"
            f"   Rating: {app.get('rating')}\n"
            f"   Installs: {app.get('installs')}\n"
            f"   Summary: {summary}\n"
        )
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (kısaltıldı)"
    return text


def generate_research_with_real_data(niche: dict, apps: list) -> str:
    """
    Gerçek Play Store verisini Gemini'ye yedirip pazar analizi çıkartır.
    """
    if not apps:
        raise RuntimeError("Bu niş için Play Store'dan hiç uygulama çekilemedi.")

    client = build_gemini_client()
    niche_name = niche["name_tr"]
    apps_text = format_apps_for_prompt(apps)

    prompt = f"""
Sen deneyimli bir ürün yöneticisi ve mobil uygulama stratejisti olarak çalışıyorsun.
Aşağıda Google Play Store'dan çekilmiş, *gerçek* uygulama örnekleri var.

Niş (Türkçe açıklama): {niche_name}

Ham veri (en çok ilgilendiğimiz app'ler):

{apps_text}

Lütfen TÜRKÇE ve aşağıdaki başlıklarla net, iş odaklı bir analiz üret:

1) 🎯 Nişin Gerçek Durumu
- Bu nişe göre genel tablo ne?
- Kullanıcıların çözdürmek istediği ana problemler bu app'lere göre neler?

2) 📱 Rakiplerin Güçlü Yanları
- Örnek uygulamalara bakarak ortak güçlü yönleri madde madde özetle.
- Özellikle: UX, basitlik, görsel kalite, fonksiyon seti.

3) 😬 Zayıf Noktalar ve Fırsatlar
- Örnek uygulamalarda muhtemel zayıflıkları çıkar (reklam, karmaşık akış, gereksiz kayıt, vb.)
- Bu zayıflıklardan yola çıkarak, bizim uygulamanın nasıl fark yaratabileceğine dair 4–6 madde yaz.

4) 🧠 Yeni Uygulama için Net Öneriler
- 'Eğer ben bu nişte yeni bir app çıkaracak olsam' diyerek konuş.
- 5–7 tane çok net özellik/farklılaşma fikri ver (örn: sadece öğrencilere özel mod, offline çalışma, kişiselleştirilmiş dashboard, vb.)

5) 💰 Gelir Modeli Alternatifleri
- Bu niş için mantıklı 2–3 gelir modeli öner (reklam, tek seferlik premium, abonelik, vs.)
- Her model için avantaj/dezavantajı 1'er cümle ile yaz.

6) ⚙️ İlk 1 Hafta MVP Planı
- 1 hafta içinde yapılabilecek minimum özellik setini madde madde yaz (3–6 madde).
- Abartma, gerçekten yapılabilecek kadar sade tut.

KISA AMA YOĞUN bir rapor olsun.
Gereksiz süsleme yok, direkt işimize yarayacak fikir ve tespitler ver.
"""

    dprint("Gemini'ye gerçek verili pazar analizi isteği gönderiliyor...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini yanıtında text alanı boş geldi (pazar analizi).")
    return text.strip()


# ======================
# TELEGRAM
# ======================

def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN tanımlı değil.")
    if not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID tanımlı değil.")

    token_preview = TELEGRAM_BOT_TOKEN[:8] + "..."
    dprint("Telegram'a mesaj gönderiliyor...")
    dprint("Bot token preview:", token_preview)
    dprint("Chat ID:", TELEGRAM_CHAT_ID)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }

    resp = requests.post(url, json=payload, timeout=20)
    dprint("Telegram status code:", resp.status_code)
    dprint("Telegram response:", resp.text)

    resp.raise_for_status()
    return resp.json()


def print_env_debug():
    dprint("=== ENV DEBUG (Play Store Scrape Ajanı) ===")
    dprint("TELEGRAM_BOT_TOKEN set mi? ->", bool(TELEGRAM_BOT_TOKEN))
    dprint("TELEGRAM_CHAT_ID set mi?  ->", bool(TELEGRAM_CHAT_ID))
    dprint("GEMINI_API_KEY set mi?    ->", bool(GEMINI_API_KEY))
    if TELEGRAM_CHAT_ID:
        dprint("TELEGRAM_CHAT_ID:", TELEGRAM_CHAT_ID)
    dprint("====================================")


# ======================
# MAIN
# ======================

if __name__ == "__main__":
    print_env_debug()
    try:
        niche = random.choice(NICHES)
        dprint("Seçilen niş:", niche["id"], "-", niche["name_tr"])
        apps = gather_niche_apps(niche, max_apps=5)
        dprint(f"Toplanan uygulama sayısı: {len(apps)}")
        if not apps:
            raise RuntimeError("Hiç uygulama toplanamadı, scraper kısmını kontrol etmelisin.")

        analysis = generate_research_with_real_data(niche, apps)
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        message = (
            "📊 *Günün Play Store Pazar Analizi (Gerçek Veri + Gemini)*\n\n"
            f"🎯 Niş: *{niche['name_tr']}*\n\n"
            f"{analysis}\n\n"
            f"⏰ {now}"
        )

        dprint("Oluşturulan mesaj:\n", message)
        send_telegram_message(message)
        dprint("Pazar analizi mesajı başarıyla gönderildi ✅")

    except Exception as e:
        print("[FATAL] Script hata ile bitti:", repr(e))
        print("[FATAL] Traceback:\n", traceback.format_exc())
        raise
