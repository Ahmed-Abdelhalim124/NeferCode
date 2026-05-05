import sqlite3
import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime

app  = Flask(__name__)
CORS(app, origins="*")                          

PREVIEW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nefercode_preview")

@app.route("/preview/<path:filename>")
def serve_preview(filename):
    """Serve the generated app HTML so the iframe can do same-origin fetch()."""
    return send_from_directory(PREVIEW_DIR, filename)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nefercode_db.sqlite")



def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def table_exists(conn, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,)
    )
    return cur.fetchone() is not None


def get_columns(conn, table: str) -> list:
    cur = conn.execute(f"PRAGMA table_info('{table}');")
    return [row[1] for row in cur.fetchall()]


def ensure_table(conn, table: str, data: dict):
   
    is_new_table = not table_exists(conn, table)
    
    if not is_new_table:
        existing_cols = get_columns(conn, table)
        for key in data:
            if key not in existing_cols and key != "id":
                conn.execute(f"ALTER TABLE \"{table}\" ADD COLUMN \"{key}\" TEXT;")
        conn.commit()
        return

    cols = ["id INTEGER PRIMARY KEY AUTOINCREMENT", "created_at TEXT"]
    for key in data:
        if key != "id":
            cols.append(f'"{key}" TEXT')
    sql = f'CREATE TABLE "{table}" ({", ".join(cols)});'
    conn.execute(sql)
    conn.commit()
    
    print(f"   🌱 Seeding '{table}' with dummy data...")
    seed_dummy_data(conn, table, data)


def seed_dummy_data(conn, table: str, schema: dict):

    import random
    import json
    import requests
    from datetime import datetime, timedelta
    
    GROQ_API_KEY = "Groq API"  # Using key 3
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    
    columns_desc = ", ".join([f'"{k}"' for k in schema.keys() if k != "id"])
    
    prompt = f"""You are a dummy data generator. Generate realistic sample data for a database table.

TABLE NAME: {table}
COLUMNS: {columns_desc}

Generate 8-10 realistic rows of sample data that would make sense for this table.
Be creative and context-aware based on the table name and column names.

RULES:
- Return ONLY a valid JSON array of objects
- Each object must have ALL the columns listed above (except "id" and "created_at")
- Make the data realistic and varied
- Use appropriate data types (numbers for prices/quantities, dates in YYYY-MM-DD format, etc.)
- For boolean-like fields (done, active, etc.), use string "true" or "false"
- NO markdown code fences, NO explanations, ONLY the JSON array

Example format:
[
  {{"column1": "value1", "column2": "value2"}},
  {{"column1": "value3", "column2": "value4"}}
]

Generate the data now:"""

    try:
        print(f"      🤖 Asking AI to generate dummy data for '{table}'...")
        
        response = requests.post(
            GROQ_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a dummy data generator. Return only valid JSON arrays with no markdown or explanations."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 2000
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"      ⚠️  AI request failed: {response.status_code}")
            raise Exception("AI unavailable")
        
        ai_response = response.json()["choices"][0]["message"]["content"].strip()
        
        ai_response = ai_response.replace("```json", "").replace("```", "").strip()
        
        dummy_rows = json.loads(ai_response)
        
        if not isinstance(dummy_rows, list):
            raise ValueError("AI didn't return an array")
        
        print(f"      ✅ AI generated {len(dummy_rows)} rows")
        
    except Exception as e:
        print(f"      ⚠️  AI generation failed ({e}), using fallback...")
        
        dummy_rows = []
        for i in range(5):
            row = {}
            for key in schema:
                if key == "id":
                    continue
                if "name" in key.lower() or "title" in key.lower():
                    row[key] = f"Sample {key.title()} {i+1}"
                elif "email" in key.lower():
                    row[key] = f"user{i+1}@example.com"
                elif "phone" in key.lower():
                    row[key] = f"555-010{i+1}"
                elif "price" in key.lower() or "amount" in key.lower() or "cost" in key.lower():
                    row[key] = f"{random.randint(5, 100)}.{random.randint(10, 99)}"
                elif "url" in key.lower() or "image" in key.lower() or "photo" in key.lower():
                    row[key] = f"https://via.placeholder.com/300?text=Item+{i+1}"
                elif "date" in key.lower():
                    row[key] = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
                elif "time" in key.lower():
                    row[key] = f"{random.randint(9, 20)}:{random.choice(['00', '30'])}"
                elif "status" in key.lower():
                    row[key] = random.choice(["Active", "Pending", "Completed", "Inactive"])
                elif "category" in key.lower() or "type" in key.lower():
                    row[key] = random.choice(["General", "Important", "Special", "Premium"])
                elif "done" in key.lower() or "completed" in key.lower() or "active" in key.lower():
                    row[key] = random.choice(["true", "false"])
                elif "description" in key.lower() or "content" in key.lower() or "text" in key.lower():
                    row[key] = f"This is a sample {key.lower()} for item {i+1}"
                elif "quantity" in key.lower() or "stock" in key.lower() or "count" in key.lower():
                    row[key] = str(random.randint(0, 100))
                else:
                    row[key] = f"Value {i+1}"
            dummy_rows.append(row)
    
    inserted = 0
    for row in dummy_rows:
        try:
            full_row = {}
            for key in schema:
                if key == "id":
                    continue
                full_row[key] = str(row.get(key, ""))
            
            full_row["created_at"] = datetime.utcnow().isoformat()
            
            cols = list(full_row.keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join([f'"{c}"' for c in cols])
            values = [full_row[c] for c in cols]
            
            conn.execute(
                f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders});',
                values
            )
            inserted += 1
            
        except Exception as e:
            print(f"      ⚠️  Skipped row: {e}")
    
    conn.commit()
    print(f"      ✅ Inserted {inserted}/{len(dummy_rows)} rows into '{table}'")


def row_to_dict(row) -> dict:
    """sqlite3.Row → plain dict."""
    return dict(row) if row else {}



@app.route("/api/tables", methods=["GET"])
def list_tables():
    conn = get_conn()
    cur  = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    return jsonify({"tables": tables})


@app.route("/api/<string:table>/schema", methods=["GET"])
def get_schema(table):
    conn = get_conn()
    if not table_exists(conn, table):
        conn.close()
        return jsonify({"error": f"Table '{table}' does not exist"}), 404
    cols = get_columns(conn, table)
    conn.close()
    return jsonify({"table": table, "columns": cols})


@app.route("/api/<string:table>", methods=["GET"])
def get_all(table):
    conn = get_conn()
    if not table_exists(conn, table):
        conn.close()
        return jsonify({"data": []}), 200      

    limit  = request.args.get("limit",  type=int, default=1000)
    offset = request.args.get("offset", type=int, default=0)

    cur = conn.execute(
        f'SELECT * FROM "{table}" ORDER BY id DESC LIMIT ? OFFSET ?;',
        (limit, offset)
    )
    rows = [row_to_dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"data": rows})


@app.route("/api/<string:table>/<int:row_id>", methods=["GET"])
def get_one(table, row_id):
    conn = get_conn()
    if not table_exists(conn, table):
        conn.close()
        return jsonify({"error": "Table not found"}), 404
    cur  = conn.execute(f'SELECT * FROM "{table}" WHERE id = ?;', (row_id,))
    row  = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Row not found"}), 404
    return jsonify({"data": row_to_dict(row)})


@app.route("/api/<string:table>", methods=["POST"])
def insert(table):
    data = request.get_json(force=True, silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Body must be a JSON object"}), 400

    data.pop("id", None)

    conn = get_conn()
    ensure_table(conn, table, data)

    data["created_at"] = datetime.utcnow().isoformat()

    cols   = [k for k in data]
    placeholders = ", ".join(["?"] * len(cols))
    col_names    = ", ".join([f'"{c}"' for c in cols])
    values       = [data[c] for c in cols]

    cur = conn.execute(
        f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders});',
        values
    )
    conn.commit()
    new_id = cur.lastrowid

    cur = conn.execute(f'SELECT * FROM "{table}" WHERE id = ?;', (new_id,))
    row = row_to_dict(cur.fetchone())
    conn.close()
    return jsonify({"data": row}), 201


@app.route("/api/<string:table>/<int:row_id>", methods=["PUT"])
def update(table, row_id):
    data = request.get_json(force=True, silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Body must be a JSON object"}), 400

    data.pop("id", None)                        

    conn = get_conn()
    if not table_exists(conn, table):
        conn.close()
        return jsonify({"error": "Table not found"}), 404

    ensure_table(conn, table, data)

    set_clause = ", ".join([f'"{k}" = ?' for k in data])
    values     = list(data.values()) + [row_id]

    conn.execute(
        f'UPDATE "{table}" SET {set_clause} WHERE id = ?;',
        values
    )
    conn.commit()

    cur = conn.execute(f'SELECT * FROM "{table}" WHERE id = ?;', (row_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Row not found"}), 404
    return jsonify({"data": row_to_dict(row)})


@app.route("/api/<string:table>/<int:row_id>", methods=["DELETE"])
def delete_row(table, row_id):
    conn = get_conn()
    if not table_exists(conn, table):
        conn.close()
        return jsonify({"error": "Table not found"}), 404
    conn.execute(f'DELETE FROM "{table}" WHERE id = ?;', (row_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"}), 200


@app.route("/api/<string:table>", methods=["DELETE"])
def drop_table(table):
    conn = get_conn()
    if not table_exists(conn, table):
        conn.close()
        return jsonify({"error": "Table not found"}), 404
    conn.execute(f'DROP TABLE IF EXISTS "{table}";')
    conn.commit()
    conn.close()
    return jsonify({"message": f"Table '{table}' dropped"})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "db": DB_PATH})


if __name__ == "__main__":
    print("=" * 50)
    print(" 🗄️  Nefercode Local Backend")
    print(f" 📁  Database: {DB_PATH}")
    print(" 🌐  http://127.0.0.1:5000")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5000, debug=False)
