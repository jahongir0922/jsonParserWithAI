import sys
import json
import re
sys.stdout.reconfigure(encoding="utf-8")

from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

# golocations/cities.json dan shahar → davlat kodi xaritasi
import pathlib
_base = pathlib.Path(__file__).parent

_geo_data = json.loads((_base / "golocations" / "cities.json").read_text(encoding="utf-8"))
_geo_cities = next(item["data"] for item in _geo_data if item.get("type") == "table")
_CITY_COUNTRY: dict[str, str] = {
    city["name"].lower(): city["country_code"]
    for city in _geo_cities
}

# cities.json — transliteratsiya aliases
_aliases_raw = json.loads((_base / "cities.json").read_text(encoding="utf-8"))
_ALIASES: dict[str, str] = {k: v for group in _aliases_raw.values() for k, v in group.items()}
_ALIAS_COUNTRY: dict[str, str] = {
    k.lower(): iso.upper()
    for iso, group in _aliases_raw.items()
    for k in group
}
_CITY_NAMES = list(_CITY_COUNTRY.keys())


def get_country(address: str) -> str | None:
    """Manzildan davlat kodini topadi."""
    from difflib import get_close_matches
    for word in re.split(r"[\s,\-]+", address.lower()):
        if not word:
            continue
        # 1. cities.json dan to'g'ridan-to'g'ri davlat kodi
        if word in _ALIAS_COUNTRY:
            return _ALIAS_COUNTRY[word]
        # 2. Alias orqali geonamescache ga
        normalized = _ALIASES.get(word, word)
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

SYSTEM_PROMPT = """Siz yuk tashish xabarlarini (O'zbek, Rus, aralash tillarda) JSON ga o'girib beruvchi yordamchisiz.
Faqat JSON array qaytaring, boshqa hech narsa yozmang.

=== 1. MANZIL (fromAddress va toAddress) ===

QOIDA: Xabardagi BIRINCHI shahar/hudud = fromAddress (qayerdan), IKKINCHISI = toAddress (qayerga).

O'zbek qo'shimchalari (olib tashlash kerak):
- "-dan"/"-дан" = fromAddress. "Томск Асинодан" → fromAddress: "Tomsk, Asino"
- "-ga"/"-га"/"-nga" = toAddress. "Водийга" → toAddress: "Vodiy"

Rus formati:
- "Shahar1 - Shahar2" = fromAddress - toAddress. "Курган - Тошкент" → from: "Kurgan", to: "Toshkent"
- Birinchi qatordagi joy = fromAddress, ikkinchi qatordagi = toAddress

=== 2. MASHINA TURI (truckType) ===

truckType ga FAQAT quyidagi 7 ta qiymatdan biri kirishi mumkin:
["Tent", "Ref", "Chackman", "Plashatka", "Isuzu", "Tanar", "Paravoz"]

- "тент"/"ТЕНТ"/"tent" → "Tent"
- "реф"/"РЕФ"/"ref" → "Ref"
- "чакман"/"ЧАКМАН"/"chackman" → "Chackman"
- "плашатка"/"plashatka" → "Plashatka"
- "исузу"/"isuzu" → "Isuzu"
- "танар"/"tanar" → "Tanar"
- "паравоз"/"paravoz" → "Paravoz"

Yuqoridagi 7 ta so'zdan BOSHQA hech narsa truckType bo'lmaydi.
"ЮК", "ТАХТА", "ШАКАР", "АРПА", "ХАММА", "БОР", "YUK", "GRUZ" → truckType EMAS, bular yuk nomi.
Agar xabarda mashina turi topilmasa → []

=== 3. TELEFON ===

- Xabardagi BARCHA raqamlarni topib, vergul bilan ajrat
- Bo'shliqlarni olib tashla: "97 182 37 83" → "971823783"
- "ВАТСАП"/"WhatsApp" va "ТЕЛЕГРАМ"/"Telegram" degan yozuv raqam turi, raqamning o'zini yoz
- Misol: "97182 37 83 ВАТСАП" va "998 77 194 73 74 ТЕЛЕГРАМ" → phone: "971823783, 998771947374"

=== 4. TO'LOV ===
- "наличные"/"naqd"/"НАЛ" → paymentType: "Naqd"
- "перечисление"/"безнал" → paymentType: "Perechisleniya"
- "аванс есть"/"avans bor" → advance: 1 (miqdor ko'rsatilmasa)
- "аванс" + raqam → advance: raqam
- "ставка"/"фрахт"/"narxi" + raqam → deliveryCost: raqam
- "$" → currency: "USD", "сум" → currency: "UZS", "руб" → currency: "RUB"

=== 5. QOLGAN MAYDONLAR ===
- direction: "Shaharlararo" (kod o'zi to'g'irlaydi)
- loadName: faqat yuk nomi (тахта=tahta, шакар=shakar, арпа=arpa va h.k.), og'irliksiz
- weight: faqat raqam (tonna), null bo'lishi mumkin
- volume: faqat raqam (m3), null bo'lishi mumkin
- loadingTime: yuklash sanasi yoki "Srochno", null bo'lishi mumkin
- isAdditional: "догруз"/"dagruz" bo'lsa true, aks holda false
- descriptions: yuqoridagilarga kirmagan muhim izohlar (ГЛОНАСС, рабочий день va h.k.), null bo'lishi mumkin
- clientName: mijoz ismi bo'lsa, null bo'lishi mumkin

Kirill → Lotin harfiga o'gir.
Natija: [{...}, {...}]"""

FEW_SHOT = [
    {
        "role": "user",
        "content": "КУРГАН\nВОДИЙ\nЮК ТАХТА\nПАГРУЗКА 20/04/26\nОПЛАТА НАЛ",
    },
    {
        "role": "assistant",
        "content": '[{"direction": "Shaharlararo", "fromAddress": "Kurgan", "toAddress": "Vodiy", "truckType": [], "loadName": "Tahta", "weight": null, "volume": null, "paymentType": "Naqd", "deliveryCost": null, "currency": null, "advance": null, "loadingTime": "20/04/2026", "isAdditional": false, "descriptions": null, "phone": null, "clientName": null}]',
    },
    {
        "role": "user",
        "content": "ТОМСК АСИНОДАН\nВОДИЙГА\nЮК ТАХТА\n23 ТОННА\nОПЛАТА НАЛ\n97182 37 83\nВАТСАП МАХ\n998 77 194 73 74\nТЕЛЕГРАМ",
    },
    {
        "role": "assistant",
        "content": '[{"direction": "Shaharlararo", "fromAddress": "Tomsk, Asino", "toAddress": "Vodiy", "truckType": [], "loadName": "Tahta", "weight": 23, "volume": null, "paymentType": "Naqd", "deliveryCost": null, "currency": null, "advance": null, "loadingTime": null, "isAdditional": false, "descriptions": null, "phone": "971823783, 998771947374", "clientName": null}]',
    },
    {
        "role": "user",
        "content": "КУРСКИЙ\nТОШКЕНТ\nЮК АРПА\nВЕС: 22 ТОННА\nГРУЗ ГОТОВ\n97182 37 83\nВАТСАП",
    },
    {
        "role": "assistant",
        "content": '[{"direction": "Shaharlararo", "fromAddress": "Kursk", "toAddress": "Toshkent", "truckType": [], "loadName": "Arpa", "weight": 22, "volume": null, "paymentType": null, "deliveryCost": null, "currency": null, "advance": null, "loadingTime": null, "isAdditional": false, "descriptions": "Gruz gotov", "phone": "971823783", "clientName": null}]',
    },
    {
        "role": "user",
        "content": "Алматы - Ташкент\n15 тонн оборудование\nТент 2 авто\nНаличные 500$\n+77001234567",
    },
    {
        "role": "assistant",
        "content": '[{"direction": "Shaharlararo", "fromAddress": "Almaty", "toAddress": "Tashkent", "truckType": ["Tent"], "loadName": "Oborudovanie", "weight": 15, "volume": null, "paymentType": "Naqd", "deliveryCost": 500, "currency": "USD", "advance": null, "loadingTime": null, "isAdditional": false, "descriptions": "2 avto", "phone": "+77001234567", "clientName": null}]',
    },
]


def _split_messages(matn: str) -> list[str]:
    """Xabarni emoji separatorlar va bo'sh qatorlar bo'yicha bo'laklarga ajratadi."""
    # Emoji ketma-ketliklarini separator sifatida ishlatamiz
    cleaned = re.sub(r'[\U0001F300-\U0001FFFF\U00002600-\U000027FF]+', '\n---SEP---\n', matn)
    # 2+ bo'sh qatorni ham separator deb olamiz
    cleaned = re.sub(r'\n{3,}', '\n---SEP---\n', cleaned)
    blocks = re.split(r'\n---SEP---\n', cleaned)
    # Bo'sh va juda qisqa bloklarni olib tashlaymiz
    result = []
    for block in blocks:
        block = block.strip()
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
    ALLOWED_TRUCK_TYPES = {"Tent", "Ref", "Chackman", "Plashatka", "Isuzu", "Tanar", "Paravoz"}

    result = json.loads(content[start:end])
    for item in result:
        item["direction"] = get_direction(
            item.get("fromAddress", ""),
            item.get("toAddress", "")
        )
        item["truckType"] = [
            t for t in (item.get("truckType") or [])
            if t in ALLOWED_TRUCK_TYPES
        ]
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
