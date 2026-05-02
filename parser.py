import sys
import json
sys.stdout.reconfigure(encoding="utf-8")

from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

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
- direction: Agar ikki xil davlat bo'lsa "Xalqaro", aks holda "Shaharlararo" (majburiy)
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
- phone: "aloqaga_chiqish" so'zidan keyingi kontakt, yoki telefon raqam, yoki @username (majburiy)
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
        "content": '[{"direction": "Shaharlararo", "fromAddress": "Alatau", "toAddress": "Urgench", "truckType": ["Tent"], "loadName": "Rolton", "weight": 22, "volume": null, "paymentType": null, "deliveryCost": null, "currency": null, "advance": null, "loadingTime": "Segodnya", "isAdditional": false, "descriptions": null, "phone": null, "clientName": null}]',
    },
]


def parse_yuk_xabar(matn: str) -> dict:
    # Ketma-ket bo'sh qatorlarni birga qisqartirish
    import re
    matn = re.sub(r'\n{3,}', '\n\n', matn).strip()

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
    if start != -1 and end > start:
        content = content[start:end]

    return json.loads(content)
