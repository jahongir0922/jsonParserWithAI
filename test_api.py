import sys
sys.stdout.reconfigure(encoding="utf-8")
import requests
import json

matn = """
Чирчик 🇺🇿 - Курилиха (Иваново)🇷🇺 
груз: сырье
вес: 22 тонна

тент стандарт
груз готов
"""

response = requests.post(
    "http://localhost:8000/parse",
    json={"matn": matn}
)

print(json.dumps(response.json(), ensure_ascii=False, indent=2))
