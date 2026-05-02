import sys
sys.stdout.reconfigure(encoding="utf-8")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from parser import parse_yuk_xabar
import json

app = FastAPI(title="Yuk Tashish JSON Parser")


class ParseRequest(BaseModel):
    matn: str


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
