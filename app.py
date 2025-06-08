from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import mysql.connector
import os
from dotenv import load_dotenv

# --- .envファイルの読み込み ---
load_dotenv()

# --- FastAPIアプリの初期化 ---
app = FastAPI()

# --- CORS設定（Next.jsからのアクセスを許可） ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MySQL接続設定（環境変数から取得） ---
db_config = {
    'host': os.getenv("DB_HOST"),
    'port': int(os.getenv("DB_PORT", 3306)),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME")
}

# --- Pydanticモデル定義 ---
class Item(BaseModel):
    code: str
    name: str
    price: int

class PurchaseData(BaseModel):
    pos_id: str
    items: List[Item]

# --- 商品取得API ---
@app.get("/api/product/{code}")
def get_product(code: str):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT name, price FROM product_master WHERE code = %s", (code,))
        result = cursor.fetchone()

        if result:
            return result
        else:
            raise HTTPException(status_code=404, detail="商品がマスタ未登録です")

    except Exception as e:
        print("商品取得エラー:", e)
        raise HTTPException(status_code=500, detail="サーバーエラー")

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# --- 購入登録API ---
@app.post("/api/purchase")
def purchase(data: PurchaseData):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        total = sum(item.price for item in data.items)
        pos_no = data.pos_id[-3:]  # ✅ pos_noを末尾3文字に制限

        # 取引（親テーブル）
        cursor.execute("""
            INSERT INTO transaction (emp_cd, store_cd, pos_no, total_amt)
            VALUES (%s, %s, %s, %s)
        """, ("EMP001", "001", pos_no, total))
        trd_id = cursor.lastrowid

        # 取引明細（子テーブル）
        for item in data.items:
            cursor.execute("""
                INSERT INTO transaction_detail (trd_id, prd_code, prd_name, prd_price)
                VALUES (%s, %s, %s, %s)
            """, (trd_id, item.code, item.name, item.price))

        conn.commit()
        return {
            "message": "取引が登録されました",
            "total": total,
            "transaction_id": trd_id
        }

    except Exception as e:
        print("購入登録エラー:", e)
        raise HTTPException(status_code=500, detail="サーバーエラー")

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()