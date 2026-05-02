import sys
sys.stdout.reconfigure(encoding="utf-8")
import requests
import json

matn = """Талдыкурган - Ташкент 10-15 тонн оборудование тентовки 
боковая загрузка
по 3 дня на загрузку и выгрузку 
2 авто боковая загрузка



Алатау- Ургенч
Тент 
Ролтон 
До 22 тонн
Погрузка сегодня




Алатау-  Нукус
Тент 
Ролтон 
До 22 тонн
Погрузка сегодня


Алатау- Коканд 
Тент 
Ролтон 
До 22 тонн
Погрузка сегодня"""

response = requests.post(
    "http://localhost:8000/parse",
    json={"matn": matn}
)

print(json.dumps(response.json(), ensure_ascii=False, indent=2))
