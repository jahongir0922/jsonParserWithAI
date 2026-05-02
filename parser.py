import sys
import json
import re
sys.stdout.reconfigure(encoding="utf-8")

from openai import OpenAI
import geonamescache

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

# Shahar → davlat kodi xaritasi
_gc = geonamescache.GeonamesCache()
_CITY_COUNTRY: dict[str, str] = {
    city["name"].lower(): city["countrycode"]
    for city in _gc.get_cities().values()
}

# O'zbek/Rus imlosi → geonamescache nomi mapping
_ALIASES: dict[str, str] = {
    # O'zbekiston
    "toshkent": "tashkent", "buxoro": "bukhara", "buxaro": "bukhara",
    "samarqand": "samarkand", "qoqon": "kokand", "ko'qon": "kokand",
    "andijon": "andijan", "namangan": "namangan", "farg'ona": "fergana",
    "fargona": "fergana", "qarshi": "karshi", "navoiy": "navoiy",
    "urganch": "urgench", "xiva": "khiva", "termiz": "termez",
    "nukus": "nukus", "jizzax": "jizzakh", "guliston": "guliston",
    # Qozog'iston
    "almati": "almaty", "nursulton": "astana", "nur-sultan": "astana",
    "shymkent": "shymkent", "qaragandy": "karaganda", "alatau": "almaty",
    "taldiqorgon": "taldykorgan", "taldykurgan": "taldykorgan",
    # Rossiya
    "moskva": "moscow", "peterburg": "saint petersburg",
    "novosibirsk": "novosibirsk", "yekaterinburg": "yekaterinburg",
    # Qirg'iziston
    "bishkek": "bishkek", "osh": "osh",
    # Tojikiston
    "dushanbe": "dushanbe",
    # Turkmaniston
    "ashgabat": "ashgabat",
}
_CITY_NAMES = list(_CITY_COUNTRY.keys())


def get_country(address: str) -> str | None:
    """Manzildan davlat kodini topadi."""
    from difflib import get_close_matches
    for word in re.split(r"[\s,\-]+", address.lower()):
        if not word:
            continue
        # 1. Alias mapping
        normalized = _ALIASES.get(word, word)
        # 2. Aniq moslik
        if normalized in _CITY_COUNTRY:
            return _CITY_COUNTRY[normalized]
        # 3. Fuzzy moslik
        matches = get_close_matches(normalized, _CITY_NAMES, n=1, cutoff=0.82)
        if matches:
            return _CITY_COUNTRY[matches[0]]
    return None


def get_direction(from_addr: str, to_addr: str) -> str:
    from_country = get_country(from_addr)
    to_country = get_country(to_addr)
    if from_country and to_country and from_country == to_country:
        return "Shaharlararo"
    return "Xalqaro"

SYSTEM_PROMPT = """Siz O'zbek va Rus tilidagi yuk tashish xabarlarini JSON formatga o'girib beruvchi yordamchisiz.
Faqat JSON array qaytaring, boshqa hech narsa yozmang.

=== MANZILNI ANIQLASH QOIDALARI ===

O'zbek tilida:
- So'z oxirida "-dan"/"-dан" = QAYERDAN (fromAddress). Qo'shimchani olib tashla.
  Misol: "Toshkentdan" → fromAddress: "Toshkent"
- So'z oxirida "-ga"/"-ka"/"-qa"/"-nga" = QAYERGA (toAddress). Qo'shimchani olib tashla.
  Misol: "Samarqandga" → toAddress: "Samarqand"
- Ketma-ket ikki shahar nomi: birinchisi = fromAddress, ikkinchisi = toAddress
  Misol: "Andijon Nayman" + "Buxoro Kogon" → fromAddress: "Andijon, Nayman", toAddress: "Buxoro, Kogon"

Rus tilida:
- "Shahar1 - Shahar2" yoki "Shahar1 – Shahar2" = fromAddress - toAddress. Chiziqchani olib tashla.
  Misol: "Алматы - Ташкент" → fromAddress: "Almaty", toAddress: "Tashkent"
- "из Shahar1 в Shahar2" = fromAddress - toAddress

=== MASHINA TURLARI ===
Faqat quyidagi so'zlardan birini truckType ga qo'sh:
Tent, Ref, Chackman, Plashatka, Isuzu, Tanar, Paravoz
Agar xabarda "тент"/"tent" bo'lsa → "Tent"
Agar xabarda "реф"/"ref" bo'lsa → "Ref"
Agar "чакман"/"chackman" bo'lsa → "Chackman"
Agar yuqoridagilardan hech biri bo'lmasa → bo'sh array []

=== TO'LOV ===
- "naqd"/"наличные" → paymentType: "Naqd"
- "perechisleniya"/"перечисление"/"безнал" → paymentType: "Perechisleniya"
- "kombo"/"kombinatsiya" → paymentType: "Kombo"
- "stavka"/"фрахт"/"narxi"/"стоимость" + raqam → deliveryCost: raqam
- "avans"/"аванс" + raqam → advance: raqam
- "$" yoki "dollar" → currency: "USD"
- "sum"/"so'm"/"сум" → currency: "UZS"
- "rubl"/"рубл" → currency: "RUB"

=== MAYDONLAR ===
- direction: "Shaharlararo" deb yoz (kod o'zi to'g'irlaydi)
- fromAddress: faqat jo'nash shahri, qo'shimchasiz (majburiy)
- toAddress: faqat borish shahri, qo'shimchasiz (majburiy)
- truckType: mashina turlari array (yuqoridagi qoidaga ko'ra)
- loadName: faqat yuk nomi, og'irlik/hajmsiz (null bo'lishi mumkin)
- weight: yuk og'irligi FAQAT raqam (tonna), null bo'lishi mumkin
- volume: yuk hajmi FAQAT raqam (m3), null bo'lishi mumkin
- paymentType: "Naqd" | "Perechisleniya" | "Kombo" | null
- deliveryCost: narx FAQAT raqam, null bo'lishi mumkin
- currency: "USD" | "UZS" | "RUB" | null
- advance: avans FAQAT raqam, null bo'lishi mumkin
- loadingTime: yuklash vaqti yoki sanasi (misol: "Srochno", "08.06.2025"), null bo'lishi mumkin
- isAdditional: "dagruz"/"догруз"/"qo'shimcha yuk" bo'lsa true, aks holda false
- descriptions: yuqoridagi maydonlarga kirmagan qo'shimcha izohlar, null bo'lishi mumkin
- phone: barcha telefon raqamlarni vergul bilan yoz (WhatsApp, Telegram, oddiy raqam farqi yo'q). Raqamdagi bo'shliqlarni olib tashla. Misol: "97 182 37 83" va "998 77 194 73 74" → "971823783, 998771947374"
- clientName: mijoz ismi bo'lsa yoz, null bo'lishi mumkin

Kirill yozuvini lotin harfiga o'gir.
Faqat JSON array qaytaring: [{...}, {...}]"""

FEW_SHOT = [
    {
        "role": "user",
        "content": "Тошкент Чиланзардан\nСамарқандга\nУн бор 10 тонна\nТент фура кк\n+998901234567",
    },
    {
        "role": "assistant",
        "content": '[{"direction": "Shaharlararo", "fromAddress": "Toshkent, Chilanzar", "toAddress": "Samarqand", "truckType": ["Tent"], "loadName": "Un", "weight": 10, "volume": null, "paymentType": null, "deliveryCost": null, "currency": null, "advance": null, "loadingTime": null, "isAdditional": false, "descriptions": null, "phone": "+998901234567", "clientName": null}]',
    },
    {
        "role": "user",
        "content": "Алматы - Ташкент\n15 тонн оборудование\nТент 2 авто\nНаличные 500$\n+77001234567",
    },
    {
        "role": "assistant",
        "content": '[{"direction": "Xalqaro", "fromAddress": "Almaty", "toAddress": "Tashkent", "truckType": ["Tent"], "loadName": "Oborudovanie", "weight": 15, "volume": null, "paymentType": "Naqd", "deliveryCost": 500, "currency": "USD", "advance": null, "loadingTime": null, "isAdditional": false, "descriptions": "2 avto", "phone": "+77001234567", "clientName": null}]',
    },
    {
        "role": "user",
        "content": "Алатау- Ургенч\nТент\nРолтон\nДо 22 тонн\nПогрузка сегодня",
    },
    {
        "role": "assistant",
        "content": '[{"direction": "Xalqaro", "fromAddress": "Alatau", "toAddress": "Urgench", "truckType": ["Tent"], "loadName": "Rolton", "weight": 22, "volume": null, "paymentType": null, "deliveryCost": null, "currency": null, "advance": null, "loadingTime": "Segodnya", "isAdditional": false, "descriptions": null, "phone": null, "clientName": null}]',
    },
]


def _split_messages(matn: str) -> list[str]:
    """Xabarni emoji separatorlar bo'yicha bo'laklarga ajratadi."""
    # Emoji ketma-ketliklarini separator sifatida ishlatamiz
    cleaned = re.sub(r'[\U0001F300-\U0001FFFF]+', '\n🔥\n', matn)
    # 3+ bo'sh qatorni ham separator deb olamiz
    cleaned = re.sub(r'\n{4,}', '\n🔥\n', cleaned)
    blocks = re.split(r'\n🔥\n', cleaned)
    # Bo'sh va juda qisqa bloklarni olib tashlaymiz
    result = []
    for block in blocks:
        block = re.sub(r'\n{3,}', '\n\n', block).strip()
        if len(block) > 15:
            result.append(block)
    return result


def _parse_single(matn: str) -> list[dict]:
    """Bitta xabar blokini parse qiladi."""
    response = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *FEW_SHOT,
            {"role": "user", "content": matn},
        ],
        temperature=0,
    )

    content = response.choices[0].message.content.strip()
    start = content.find("[")
    end = content.rfind("]") + 1
    if start == -1 or end <= start:
        return []
    result = json.loads(content[start:end])
    for item in result:
        item["direction"] = get_direction(
            item.get("fromAddress", ""),
            item.get("toAddress", "")
        )
    return result


def parse_yuk_xabar(matn: str) -> list[dict]:
    blocks = _split_messages(matn)

    # Bitta blok bo'lsa to'g'ridan-to'g'ri parse qilamiz
    if len(blocks) <= 1:
        return _parse_single(matn.strip())

    # Har bir blokni alohida parse qilamiz
    all_results = []
    for block in blocks:
        try:
            items = _parse_single(block)
            all_results.extend(items)
        except Exception:
            continue
    return all_results
