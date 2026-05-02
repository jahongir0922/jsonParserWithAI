import sys
sys.stdout.reconfigure(encoding="utf-8")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import json

app = FastAPI(title="Yuk Tashish JSON Parser")

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

SYSTEM_PROMPT = """You extract freight/cargo shipment data from messages written in Uzbek or Russian.
Return ONLY a JSON object, no explanation.

Rules for detecting source and destination:
- Uzbek: suffix "-dan"/"-dан" = FROM (yuklash_joyi). Suffix "-ga"/"-ka"/"-qa"/"-nga" = TO (tushirish_joyi). Strip the suffix.
  Example: "Toshkentdan" -> yuklash_joyi: "Toshkent", "Samarqandga" -> tushirish_joyi: "Samarqand"
- Uzbek: two city names in a row -> first = FROM, second = TO
- Russian: "Город1 - Город2" or "Город1 – Город2" = FROM - TO
  Example: "Алматы - Ташкент" -> yuklash_joyi: "Almatы", tushirish_joyi: "Tashkent"
- Russian: "из Город1 в Город2" = FROM - TO

Fields to extract for each shipment:
- yuklash_joyi: departure city/district only (no suffix, no destination)
- tushirish_joyi: destination city/district only (no suffix, no source)
- yuk_turi: cargo name and quantity/weight
- mashina_turi: vehicle type only (Tent fura, Konteyner, Kamaz, etc.)
- mashina_soni: number of vehicles needed (integer, default 1)
- holat: "KK" if message contains KK/kk (empty/available vehicle), else null
- telefon: phone number(s), comma-separated, null if not present
- izoh: extra notes like "Srochna", "Pogрузка сегодня", loading/unloading days, special conditions. null if none.

Transliterate all Cyrillic to Latin script.
Return format (only this, nothing else):
{"yuklar": [...]}"""


class ParseRequest(BaseModel):
    matn: str


def parse_yuk_xabar(matn: str) -> dict:
    response = client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Тошкент Чиланзардан\nСамарқандга\nУн бор 10 тонна\nТент фура кк\n+998901234567",
            },
            {
                "role": "assistant",
                "content": '{"yuklar": [{"yuklash_joyi": "Toshkent, Chilanzar", "tushirish_joyi": "Samarqand", "yuk_turi": "Un 10 tonna", "mashina_turi": "Tent fura", "mashina_soni": 1, "holat": "KK", "telefon": "+998901234567", "izoh": null}]}',
            },
            {"role": "user", "content": matn},
        ],
        temperature=0,
    )

    content = response.choices[0].message.content.strip()
    start = content.find("{")
    end = content.rfind("}") + 1
    if start != -1 and end > start:
        content = content[start:end]

    return json.loads(content)


@app.post("/parse")
def parse(req: ParseRequest):
    try:
        return parse_yuk_xabar(req.matn)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Model JSON qaytarmadi")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    return {"status": "ishlayapti", "endpoint": "POST /parse"}
