import os, sqlite3, random, re, json, datetime
from flask import Flask, request, jsonify, render_template_string
from groq import Groq

app = Flask(__name__)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
DB = "nexus.db"

# ═══════════════════════════════════════════════════════════
#  DATABASE — richer schema
# ═══════════════════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY, name TEXT, category TEXT,
                  price REAL, stock INTEGER, rating REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks
                 (id INTEGER PRIMARY KEY, title TEXT, status TEXT,
                  priority TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS notes
                 (id INTEGER PRIMARY KEY, content TEXT, tag TEXT,
                  created_at TEXT)""")
    if c.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        c.executemany("INSERT INTO products(name,category,price,stock,rating) VALUES(?,?,?,?,?)", [
            ("Gemini Pro API",    "AI Services",  99.0,  500, 4.8),
            ("Cloud Database",   "Infrastructure", 49.0, 999, 4.6),
            ("Analytics Suite",  "Data Tools",   120.0,  250, 4.9),
            ("Vector Search",    "AI Services",   79.0,  400, 4.7),
            ("ML Pipeline",      "Data Tools",   199.0,  150, 4.5),
            ("Edge Inference",   "AI Services",  149.0,  300, 4.8),
        ])
    conn.commit(); conn.close()

# ═══════════════════════════════════════════════════════════
#  AGENT TOOL FUNCTIONS
# ═══════════════════════════════════════════════════════════

# — Weather Agent —
WEATHER_PROFILES = {
    "chennai":      {"base": 32, "humidity": 78, "wind": 14},
    "mumbai":       {"base": 30, "humidity": 82, "wind": 18},
    "delhi":        {"base": 28, "humidity": 55, "wind": 12},
    "bangalore":    {"base": 24, "humidity": 65, "wind": 10},
    "tirunelveli":  {"base": 33, "humidity": 72, "wind": 16},
    "madurai":      {"base": 34, "humidity": 70, "wind": 15},
    "coimbatore":   {"base": 27, "humidity": 68, "wind": 11},
    "hyderabad":    {"base": 29, "humidity": 60, "wind": 13},
    "kolkata":      {"base": 31, "humidity": 80, "wind": 17},
    "pune":         {"base": 26, "humidity": 62, "wind": 12},
    "london":       {"base": 12, "humidity": 75, "wind": 22},
    "new york":     {"base": 18, "humidity": 60, "wind": 20},
    "tokyo":        {"base": 22, "humidity": 65, "wind": 15},
    "dubai":        {"base": 38, "humidity": 55, "wind": 19},
    "singapore":    {"base": 30, "humidity": 85, "wind": 14},
    "paris":        {"base": 14, "humidity": 70, "wind": 18},
    "sydney":       {"base": 20, "humidity": 65, "wind": 21},
}

CONDITIONS = ["Sunny", "Partly Cloudy", "Overcast", "Humid & Clear", "Breezy"]

def extract_entity(msg, keywords, stop_words=None):
    """Generic entity extractor after keyword trigger."""
    stop = stop_words or {"the","a","an","is","are","was","what","how","tell","me","about",
                          "get","check","show","give","please","today","now","current","right","like"}
    msg_clean = msg.strip().rstrip("?.")
    for kw in keywords:
        for pat in [
            rf"{kw}\s+(?:in|at|for|of|about)\s+(.+)",
            rf"(.+?)\s+{kw}",
            rf"{kw}\s+(.+)",
        ]:
            m = re.search(pat, msg_clean, re.IGNORECASE)
            if m:
                entity = m.group(1).strip()
                words = [w for w in entity.split() if w.lower() not in stop]
                if words:
                    return " ".join(words)
    return None

def weather_agent(msg):
    city_raw = extract_entity(msg, ["weather", "temperature", "temp", "climate", "forecast"])
    city = city_raw.title() if city_raw else "Unknown City"
    profile = WEATHER_PROFILES.get(city.lower(), None)
    if profile:
        temp    = profile["base"] + random.randint(-2, 3)
        humidity= profile["humidity"] + random.randint(-5, 5)
        wind    = profile["wind"] + random.randint(-3, 3)
    else:
        temp    = random.randint(18, 38)
        humidity= random.randint(45, 85)
        wind    = random.randint(8, 25)
    condition = random.choice(CONDITIONS)
    feels_like = temp - random.randint(1, 3)
    uv = random.randint(1, 11)
    return {
        "agent": "Weather Agent",
        "city": city,
        "temperature_c": temp,
        "feels_like_c": feels_like,
        "condition": condition,
        "humidity_pct": humidity,
        "wind_kmh": wind,
        "uv_index": uv,
        "visibility_km": random.randint(5, 20),
        "sunrise": "06:12 AM",
        "sunset": "06:48 PM",
    }

# — News Agent —
NEWS_DB = {
    "ai": [
        {"title": "Google DeepMind releases AlphaFold 3 with protein-ligand binding predictions", "source": "Nature", "time": "2h ago", "category": "AI Research"},
        {"title": "OpenAI's GPT-5 reportedly achieves PhD-level reasoning on GPQA benchmark", "source": "TechCrunch", "time": "4h ago", "category": "AI Research"},
        {"title": "Anthropic raises $4B Series E, valuation hits $18.4 billion", "source": "Bloomberg", "time": "6h ago", "category": "AI Business"},
        {"title": "Meta open-sources Llama 3.1 405B, largest open-weight model to date", "source": "Reuters", "time": "8h ago", "category": "Open Source"},
    ],
    "tech": [
        {"title": "Apple unveils M4 Ultra chip with 192GB unified memory for Mac Pro", "source": "The Verge", "time": "3h ago", "category": "Hardware"},
        {"title": "NVIDIA's Blackwell GPU architecture ships to hyperscalers ahead of schedule", "source": "AnandTech", "time": "5h ago", "category": "Hardware"},
        {"title": "GitHub Copilot Workspace now handles full PR lifecycle end-to-end", "source": "GitHub Blog", "time": "7h ago", "category": "DevTools"},
    ],
    "crypto": [
        {"title": "Bitcoin ETF sees record $1.2B inflows as institutional adoption accelerates", "source": "CoinDesk", "time": "1h ago", "category": "Markets"},
        {"title": "Ethereum completes Pectra upgrade, reduces validator exit queue by 40%", "source": "Decrypt", "time": "3h ago", "category": "Blockchain"},
    ],
    "business": [
        {"title": "India's startup ecosystem crosses 100 unicorns, second only to USA", "source": "Economic Times", "time": "2h ago", "category": "Startups"},
        {"title": "Global AI investment hits $200B in 2024, up 300% from prior year", "source": "PitchBook", "time": "4h ago", "category": "Investment"},
    ],
    "general": [
        {"title": "AI breakthrough: Models now pass bar exam, medical licensing tests consistently", "source": "WSJ", "time": "2h ago", "category": "AI"},
        {"title": "Tech sector adds 500K jobs globally in Q1 2025 despite automation fears", "source": "FT", "time": "5h ago", "category": "Jobs"},
        {"title": "Renewable energy output surpasses fossil fuels for first time in G7 nations", "source": "Guardian", "time": "6h ago", "category": "Climate"},
        {"title": "India's GDP grows at 8.2% making it fastest growing major economy", "source": "Mint", "time": "8h ago", "category": "Economy"},
    ],
}

def news_agent(msg):
    m = msg.lower()
    if any(w in m for w in ["ai", "artificial", "machine learning", "llm", "openai", "gemini"]):
        category, articles = "AI & Machine Learning", NEWS_DB["ai"]
    elif any(w in m for w in ["crypto", "bitcoin", "ethereum", "blockchain"]):
        category, articles = "Crypto & Blockchain", NEWS_DB["crypto"]
    elif any(w in m for w in ["business", "startup", "market", "economy", "invest"]):
        category, articles = "Business & Markets", NEWS_DB["business"]
    elif any(w in m for w in ["tech", "software", "hardware", "apple", "google", "dev"]):
        category, articles = "Technology", NEWS_DB["tech"]
    else:
        category, articles = "Top Headlines", NEWS_DB["general"]
    return {
        "agent": "News Agent",
        "category": category,
        "articles": articles[:4],
        "total_sources": 47,
        "last_updated": datetime.datetime.now().strftime("%I:%M %p"),
    }

# — Crypto Agent —
CRYPTO_DATA = {
    "bitcoin":   {"symbol": "BTC", "base": 67800,  "change": 2.3,  "mcap": "1.33T", "vol": "38.2B"},
    "ethereum":  {"symbol": "ETH", "base": 3580,   "change": 1.8,  "mcap": "430B",  "vol": "18.5B"},
    "solana":    {"symbol": "SOL", "base": 182,    "change": 4.1,  "mcap": "85B",   "vol": "5.2B"},
    "bnb":       {"symbol": "BNB", "base": 610,    "change": 0.9,  "mcap": "92B",   "vol": "2.1B"},
    "xrp":       {"symbol": "XRP", "base": 0.62,   "change": -0.5, "mcap": "34B",   "vol": "1.8B"},
    "cardano":   {"symbol": "ADA", "base": 0.48,   "change": 1.2,  "mcap": "17B",   "vol": "0.9B"},
    "dogecoin":  {"symbol": "DOGE","base": 0.16,   "change": 3.8,  "mcap": "23B",   "vol": "2.4B"},
    "polygon":   {"symbol": "MATIC","base": 0.92,  "change": -1.1, "mcap": "9B",    "vol": "0.6B"},
}

def crypto_agent(msg):
    m = msg.lower()
    found = []
    for coin, data in CRYPTO_DATA.items():
        if coin in m or data["symbol"].lower() in m:
            found.append((coin, data))
    if not found:
        # default: top 4
        found = list(CRYPTO_DATA.items())[:4]
    results = []
    for coin, data in found[:4]:
        price = data["base"] * (1 + random.uniform(-0.02, 0.02))
        change = data["change"] + random.uniform(-0.3, 0.3)
        results.append({
            "name": coin.title(),
            "symbol": data["symbol"],
            "price_usd": round(price, 2 if price > 10 else 4),
            "change_24h": round(change, 2),
            "market_cap": data["mcap"],
            "volume_24h": data["vol"],
        })
    return {
        "agent": "Crypto Agent",
        "coins": results,
        "market_sentiment": random.choice(["Bullish 📈", "Neutral ➡️", "Cautiously Bullish 📊"]),
        "fear_greed_index": random.randint(55, 80),
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S UTC"),
    }

# — Database Agent —
def db_agent(msg):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    m = msg.lower()
    result = {}

    # ADD task
    if any(w in m for w in ["add task", "create task", "new task"]):
        title_m = re.search(r'task[:\s]+["\']?(.+?)["\']?$', msg, re.IGNORECASE)
        title = title_m.group(1).strip() if title_m else "New Task"
        priority = "high" if "urgent" in m or "high" in m else "medium" if "medium" in m else "low"
        conn.execute("INSERT INTO tasks(title,status,priority,created_at) VALUES(?,?,?,?)",
                     (title, "pending", priority, datetime.datetime.now().isoformat()))
        conn.commit()
        result = {"agent": "Database Agent", "action": "task_created", "task": title, "priority": priority}

    # ADD note
    elif any(w in m for w in ["add note", "save note", "note:", "remember"]):
        note_m = re.search(r'(?:note|remember)[:\s]+(.+)', msg, re.IGNORECASE)
        content = note_m.group(1).strip() if note_m else msg
        conn.execute("INSERT INTO notes(content,tag,created_at) VALUES(?,?,?)",
                     (content, "general", datetime.datetime.now().isoformat()))
        conn.commit()
        result = {"agent": "Database Agent", "action": "note_saved", "content": content}

    # SEARCH products
    elif any(w in m for w in ["search", "find", "look for"]) and any(w in m for w in ["product", "item"]):
        term_m = re.search(r'(?:search|find|look for)\s+(.+)', msg, re.IGNORECASE)
        term = term_m.group(1).replace("product","").replace("item","").strip() if term_m else ""
        rows = conn.execute("SELECT * FROM products WHERE name LIKE ? OR category LIKE ?",
                            (f"%{term}%", f"%{term}%")).fetchall()
        result = {"agent": "Database Agent", "action": "product_search",
                  "query": term, "products": [dict(r) for r in rows]}

    # LIST tasks
    elif "task" in m and any(w in m for w in ["list", "show", "my", "all", "pending"]):
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10").fetchall()
        result = {"agent": "Database Agent", "action": "list_tasks",
                  "tasks": [dict(r) for r in rows], "count": len(rows)}

    # SQL query
    elif "sql" in m or "query" in m:
        query_m = re.search(r'(?:sql|query)[:\s]+(.+)', msg, re.IGNORECASE)
        if query_m:
            q = query_m.group(1).strip()
            if q.lower().startswith("select"):
                try:
                    rows = conn.execute(q).fetchall()
                    result = {"agent": "Database Agent", "action": "sql_query",
                              "query": q, "rows": [dict(r) for r in rows], "count": len(rows)}
                except Exception as e:
                    result = {"agent": "Database Agent", "action": "sql_error", "error": str(e)}
            else:
                result = {"agent": "Database Agent", "action": "sql_blocked",
                          "message": "Only SELECT queries are allowed for safety."}
        else:
            result = {"agent": "Database Agent", "action": "sql_hint",
                      "message": "Provide a SELECT query like: sql: SELECT * FROM products"}

    # Default: show all products
    else:
        rows = conn.execute("SELECT * FROM products").fetchall()
        result = {"agent": "Database Agent", "action": "list_products",
                  "products": [dict(r) for r in rows], "count": len(rows)}

    conn.close()
    return result

# — Calculator Agent —
def calc_agent(msg):
    import math as _math
    m = msg
    # Handle "X% of Y"
    pct = re.search(r'([\d.]+)%\s+of\s+([\d,]+)', m, re.IGNORECASE)
    if pct:
        a, b = float(pct.group(1)), float(pct.group(2).replace(',',''))
        result = round(a/100*b, 4)
        expr = f"{a}% of {b}"
        return {"agent":"Calculator Agent","expression":expr,"result":result,"status":"success"}
    # Handle sqrt
    sq = re.search(r'sqrt\(?([\d.]+)\)?', m, re.IGNORECASE)
    if sq:
        result = round(_math.sqrt(float(sq.group(1))), 6)
        return {"agent":"Calculator Agent","expression":f"sqrt({sq.group(1)})","result":result,"status":"success"}
    # General expression
    expr_m = re.search(r'(?:calculate|compute|what is|=)\s*([0-9\s\+\-\*\/\^\(\)\.]+)', m, re.IGNORECASE)
    if not expr_m:
        expr_m = re.search(r'([0-9][\d\s\+\-\*\/\^\(\)\.]+[\d\)])', m)
    if expr_m:
        raw = expr_m.group(1).strip()
        expr = raw.replace("^","**").replace("×","*").replace("÷","/")
        try:
            result = eval(expr, {"__builtins__":{},"sqrt":_math.sqrt,"pi":_math.pi}, {})
            return {"agent":"Calculator Agent","expression":raw,"result":round(result,6),"status":"success"}
        except: pass
    return {"agent":"Calculator Agent","status":"error","message":"Could not parse. Try: calculate 15% of 85000, or sqrt(144), or 250 * 4.5"}

# — Unit Converter Agent —
def converter_agent(msg):
    m = msg.lower()
    # Temperature
    t = re.search(r'([\d.]+)\s*°?([cf])\s+(?:to|in)\s+°?([cf])', m)
    if t:
        val, frm, to = float(t.group(1)), t.group(2), t.group(3)
        if frm == "c" and to == "f":
            res = val * 9/5 + 32
            return {"agent": "Converter Agent", "from": f"{val}°C", "to": f"{round(res,2)}°F"}
        elif frm == "f" and to == "c":
            res = (val - 32) * 5/9
            return {"agent": "Converter Agent", "from": f"{val}°F", "to": f"{round(res,2)}°C"}
    # km/miles
    km = re.search(r'([\d.]+)\s*km\s+(?:to|in)\s+miles?', m)
    if km:
        res = float(km.group(1)) * 0.621371
        return {"agent": "Converter Agent", "from": f"{km.group(1)} km", "to": f"{round(res,3)} miles"}
    mi = re.search(r'([\d.]+)\s*miles?\s+(?:to|in)\s+km', m)
    if mi:
        res = float(mi.group(1)) * 1.60934
        return {"agent": "Converter Agent", "from": f"{mi.group(1)} miles", "to": f"{round(res,3)} km"}
    # kg/lbs
    kg = re.search(r'([\d.]+)\s*kg\s+(?:to|in)\s+(?:lb|lbs|pounds?)', m)
    if kg:
        res = float(kg.group(1)) * 2.20462
        return {"agent": "Converter Agent", "from": f"{kg.group(1)} kg", "to": f"{round(res,3)} lbs"}
    # INR/USD
    cur = re.search(r'([\d.]+)\s*(usd|inr|eur|gbp)\s+(?:to|in)\s+(usd|inr|eur|gbp)', m)
    if cur:
        rates = {"usd":1,"inr":83.5,"eur":0.92,"gbp":0.79}
        val, f, t2 = float(cur.group(1)), cur.group(2), cur.group(3)
        res = val / rates[f] * rates[t2]
        return {"agent": "Converter Agent", "from": f"{val} {f.upper()}",
                "to": f"{round(res,2)} {t2.upper()}"}
    return {"agent": "Converter Agent", "message": "Try: 100 km to miles, 25 C to F, 1000 USD to INR"}

# ═══════════════════════════════════════════════════════════
#  MASTER ROUTER — smarter keyword + intent detection
# ═══════════════════════════════════════════════════════════
def route_message(msg):
    m = msg.lower()
    if any(w in m for w in ["weather","temperature","temp","climate","forecast","humid","rain","sunny"]):
        return "weather"
    if any(w in m for w in ["news","headline","latest","happening","update","story","article"]):
        return "news"
    if any(w in m for w in ["bitcoin","ethereum","crypto","coin","btc","eth","sol","doge","blockchain","price of","value of"]):
        return "crypto"
    if any(w in m for w in ["calculate","compute","what is","×","÷","sqrt"]) or re.search(r'\d+\s*[\+\-\*\/\^]\s*\d+', m):
        return "calc"
    if any(w in m for w in ["convert","in miles","to km","to usd","to inr","°c","°f","kg to","lbs"]):
        return "converter"
    if any(w in m for w in ["database","product","sql","query","task","note","record","stock","rating","add task","save note","list task"]):
        return "db"
    return "chat"

# ═══════════════════════════════════════════════════════════
#  SYSTEM PROMPT — makes Groq use tool data properly
# ═══════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are AI Nexus, an advanced multi-agent AI assistant. You have 6 specialized agents:

1. Weather Agent — real-time weather for any city worldwide
2. News Agent — curated news across AI, tech, crypto, business, general
3. Crypto Agent — live prices for Bitcoin, Ethereum, Solana and 50+ coins
4. Database Agent — product catalog, tasks, notes with full CRUD
5. Calculator Agent — math, percentages, expressions
6. Converter Agent — currency, temperature, distance, weight

RULES:
- When tool_data is provided in the message, USE IT to answer. Don't say you can't access real-time data.
- Present numbers clearly. For weather use the exact city name and metrics provided.
- For crypto: show price, 24h change, market cap.
- For news: summarize the top headlines naturally.
- For database: confirm actions clearly (task created, note saved, products listed).
- Be concise, confident, and helpful. No disclaimers about being an AI.
- Format responses cleanly — use line breaks for lists.
"""

# ═══════════════════════════════════════════════════════════
#  MEMORY per session (in-memory, last 10 turns)
# ═══════════════════════════════════════════════════════════
chat_memory = []

# ═══════════════════════════════════════════════════════════
#  PREMIUM HTML UI
# ═══════════════════════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>AI Nexus — Multi-Agent Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Mono:wght@300;400&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {
  --bg:#07090f; --surf:#0c1018; --panel:#10151f; --panel2:#141b27;
  --border:rgba(255,255,255,0.055); --border2:rgba(255,255,255,0.10);
  --text:#dde4ef; --muted:#4e5f73; --muted2:#7a8fa8;
  --accent:#b8f84a; --accent-dim:rgba(184,248,74,0.12);
  --accent-glow:rgba(184,248,74,0.25);
  --blue:#38bdf8; --blue-dim:rgba(56,189,248,0.10);
  --amber:#f59e0b; --green:#22c55e; --red:#f43f5e; --purple:#a78bfa;
  --r:12px; --transition:0.18s ease;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;font-size:14px;display:flex;line-height:1.6}

/* ── SIDEBAR ── */
.sidebar{width:252px;min-width:252px;background:var(--surf);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;position:relative}
.sidebar::after{content:'';position:absolute;top:-100px;left:-60px;width:280px;height:280px;background:radial-gradient(circle,rgba(184,248,74,0.06) 0%,transparent 65%);pointer-events:none}

.logo-area{padding:22px 20px 18px;border-bottom:1px solid var(--border)}
.live-badge{display:inline-flex;align-items:center;gap:6px;background:var(--accent-dim);border:1px solid rgba(184,248,74,0.22);border-radius:6px;padding:4px 9px;margin-bottom:12px}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--accent);box-shadow:0 0 7px var(--accent);animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}
.live-text{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.1em;color:var(--accent)}
.logo-name{font-family:'Syne',sans-serif;font-size:24px;font-weight:800;color:#fff;letter-spacing:-.03em;line-height:1}
.logo-name em{color:var(--accent);font-style:normal}
.logo-sub{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;letter-spacing:.04em;margin-top:4px}

.nav-section{padding:16px 14px;flex:1;overflow-y:auto}
.nav-group-label{font-size:9px;letter-spacing:.14em;color:var(--muted);font-family:'DM Mono',monospace;padding:0 8px;margin:0 0 6px;text-transform:uppercase}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;cursor:pointer;transition:all var(--transition);color:var(--muted2);font-size:13px;font-weight:400;border:1px solid transparent;margin-bottom:1px}
.nav-item:hover{background:rgba(255,255,255,0.035);color:var(--text);border-color:var(--border)}
.nav-item.active{background:var(--accent-dim);border-color:rgba(184,248,74,0.2);color:var(--accent)}
.nav-icon{width:30px;height:30px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:13px;background:rgba(255,255,255,0.04);flex-shrink:0;transition:all var(--transition)}
.nav-item.active .nav-icon{background:rgba(184,248,74,0.1)}
.nav-label-text{font-weight:500;flex:1}
.nav-tag{font-size:9px;padding:2px 6px;border-radius:20px;font-family:'DM Mono',monospace;letter-spacing:.04em}
.tag-live{background:var(--blue-dim);color:var(--blue)}
.tag-new{background:rgba(167,139,250,0.12);color:var(--purple)}

.sidebar-stats{padding:12px 14px;border-top:1px solid var(--border)}
.stat-row{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px}
.stat-cell{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:8px 10px}
.stat-val{font-size:16px;font-weight:600;color:#fff;font-family:'Syne',sans-serif}
.stat-lbl{font-size:9px;color:var(--muted);font-family:'DM Mono',monospace;letter-spacing:.06em;margin-top:1px}
.model-chip{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:9px 12px;display:flex;align-items:center;gap:8px}
.model-info{flex:1}
.model-name{font-size:12px;font-weight:500;color:var(--text)}
.model-engine{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace}
.online-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 6px var(--green);flex-shrink:0;animation:blink 3s infinite}

/* ── MAIN ── */
.main{flex:1;display:flex;flex-direction:column;min-width:0;background:var(--bg)}

/* ── TOPBAR ── */
.topbar{height:54px;padding:0 24px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);flex-shrink:0;background:rgba(7,9,15,0.92);backdrop-filter:blur(16px)}
.topbar-left{display:flex;flex-direction:column}
.topbar-title{font-family:'Syne',sans-serif;font-size:14px;font-weight:700;color:#fff;letter-spacing:-.01em}
.topbar-sub{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;margin-top:1px}
.topbar-right{display:flex;align-items:center;gap:8px}
.status-chip{display:flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;border:1px solid var(--border);background:var(--surf);font-size:10px;color:var(--muted2);font-family:'DM Mono',monospace}
.status-chip .dot{width:5px;height:5px;border-radius:50%}
.btn-sm{padding:5px 12px;border-radius:7px;border:1px solid var(--border);background:transparent;color:var(--muted2);font-size:11px;font-family:'DM Mono',monospace;cursor:pointer;transition:all var(--transition)}
.btn-sm:hover{border-color:var(--border2);color:var(--text);background:rgba(255,255,255,0.04)}

/* ── CHAT ── */
.chat-area{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:0;scroll-behavior:smooth}
.chat-area::-webkit-scrollbar{width:3px}
.chat-area::-webkit-scrollbar-thumb{background:#1a2333;border-radius:3px}

/* EMPTY STATE */
.empty{margin:auto;text-align:center;max-width:520px;padding:32px 16px}
.empty-glow{width:80px;height:80px;border-radius:22px;background:var(--accent-dim);border:1px solid rgba(184,248,74,0.18);display:flex;align-items:center;justify-content:center;font-size:32px;margin:0 auto 20px;position:relative}
.empty-glow::before{content:'';position:absolute;inset:-1px;border-radius:22px;background:radial-gradient(circle at 50% 0%,rgba(184,248,74,0.15),transparent 60%)}
.empty-title{font-family:'Syne',sans-serif;font-size:24px;font-weight:800;color:#fff;letter-spacing:-.03em;margin-bottom:8px}
.empty-sub{font-size:13px;color:var(--muted2);line-height:1.75;margin-bottom:24px;max-width:400px;margin-left:auto;margin-right:auto}
.agent-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:20px}
.agent-card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:left;cursor:pointer;transition:all var(--transition)}
.agent-card:hover{border-color:rgba(184,248,74,0.25);background:var(--accent-dim);transform:translateY(-2px)}
.agent-card-icon{font-size:18px;margin-bottom:6px}
.agent-card-name{font-size:11px;font-weight:600;color:var(--text)}
.agent-card-hint{font-size:10px;color:var(--muted);margin-top:2px;font-family:'DM Mono',monospace}
.suggestions{display:flex;flex-wrap:wrap;gap:7px;justify-content:center}
.sugg{padding:7px 13px;border-radius:8px;border:1px solid var(--border);background:var(--panel);font-size:12px;color:var(--text);cursor:pointer;transition:all var(--transition);font-family:'DM Sans',sans-serif}
.sugg:hover{border-color:rgba(184,248,74,0.3);color:var(--accent);background:var(--accent-dim);transform:translateY(-1px)}

/* MESSAGES */
.msg-row{display:flex;gap:12px;padding:14px 0;border-bottom:1px solid rgba(255,255,255,0.02);animation:msgIn .28s cubic-bezier(.22,1,.36,1) both}
@keyframes msgIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg-row.user{flex-direction:row-reverse}
.av{width:32px;height:32px;border-radius:9px;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px;font-size:12px}
.av-user{background:rgba(184,248,74,0.1);border:1px solid rgba(184,248,74,0.2);color:var(--accent);font-weight:800;font-family:'Syne',sans-serif;font-size:10px}
.av-bot{background:var(--blue-dim);border:1px solid rgba(56,189,248,0.18)}
.msg-body{flex:1;min-width:0;max-width:82%;display:flex;flex-direction:column}
.msg-row.user .msg-body{align-items:flex-end}
.msg-meta{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;margin-bottom:5px;display:flex;align-items:center;gap:6px}
.agent-pill{padding:1px 7px;border-radius:4px;font-size:9px;letter-spacing:.07em;font-family:'DM Mono',monospace;font-weight:400}
.bubble{display:inline-block;padding:11px 15px;border-radius:13px;font-size:13.5px;line-height:1.75;max-width:100%;word-break:break-word;text-align:left;white-space:pre-wrap}
.bubble-user{background:#111d2e;border:1px solid rgba(184,248,74,0.09);border-bottom-right-radius:3px;color:var(--text)}
.bubble-bot{background:#0a1220;border:1px solid var(--border);border-bottom-left-radius:3px;color:var(--text)}

/* THINKING */
.thinking{display:inline-flex;align-items:center;gap:5px;padding:11px 15px;background:#0a1220;border:1px solid var(--border);border-radius:13px;border-bottom-left-radius:3px}
.th-dot{width:6px;height:6px;border-radius:50%;animation:tdot 1.3s infinite ease-in-out}
.th-dot:nth-child(1){background:var(--accent);animation-delay:0s}
.th-dot:nth-child(2){background:var(--blue);animation-delay:.2s}
.th-dot:nth-child(3){background:var(--purple);animation-delay:.4s}
@keyframes tdot{0%,60%,100%{transform:translateY(0);opacity:.3}30%{transform:translateY(-5px);opacity:1}}

/* RICH CARDS */
.card{background:var(--panel);border:1px solid var(--border);border-radius:11px;overflow:hidden;margin-top:10px;animation:msgIn .35s ease both}
.card-header{padding:10px 14px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;background:var(--panel2)}
.card-header-icon{font-size:14px}
.card-header-title{font-size:11px;font-weight:600;color:var(--text);letter-spacing:.02em}
.card-header-sub{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;margin-left:auto}
.card-body{padding:12px 14px}

/* weather card */
.weather-main{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px}
.weather-temp{font-family:'Syne',sans-serif;font-size:48px;font-weight:800;color:#fff;line-height:1}
.weather-deg{font-size:20px;color:var(--muted2);margin-top:4px}
.weather-city{font-size:13px;font-weight:600;color:var(--text)}
.weather-cond{font-size:11px;color:var(--muted2);font-family:'DM Mono',monospace}
.weather-icon-big{font-size:44px}
.weather-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.w-stat{background:var(--panel2);border:1px solid var(--border);border-radius:7px;padding:8px;text-align:center}
.w-stat-val{font-size:13px;font-weight:600;color:var(--text)}
.w-stat-lbl{font-size:9px;color:var(--muted);font-family:'DM Mono',monospace;letter-spacing:.05em;margin-top:2px}

/* news card */
.news-item{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid rgba(255,255,255,0.04)}
.news-item:last-child{border-bottom:none;padding-bottom:0}
.news-num{font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:var(--panel2);min-width:28px;line-height:1.1;margin-top:2px}
.news-content{flex:1}
.news-title{font-size:12px;font-weight:500;color:var(--text);line-height:1.5}
.news-meta{display:flex;gap:6px;margin-top:4px;align-items:center}
.news-src{font-size:10px;color:var(--accent);font-family:'DM Mono',monospace}
.news-time{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace}
.news-cat{font-size:9px;padding:1px 6px;border-radius:4px;background:var(--blue-dim);color:var(--blue);font-family:'DM Mono',monospace}

/* crypto card */
.crypto-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}
.crypto-item{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:10px 12px}
.crypto-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.crypto-sym{font-family:'DM Mono',monospace;font-size:11px;font-weight:400;color:var(--muted2)}
.crypto-change{font-size:11px;font-family:'DM Mono',monospace;font-weight:400;padding:2px 6px;border-radius:5px}
.up{background:rgba(34,197,94,.12);color:#4ade80}
.dn{background:rgba(244,63,94,.10);color:#fb7185}
.crypto-price{font-family:'Syne',sans-serif;font-size:18px;font-weight:700;color:#fff;line-height:1}
.crypto-name{font-size:11px;color:var(--muted2);margin-top:2px}
.crypto-mcap{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;margin-top:4px}
.sentiment-bar{margin-top:10px;padding:8px 12px;background:var(--panel2);border-radius:8px;border:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.sentiment-label{font-size:11px;color:var(--muted2)}
.sentiment-val{font-size:12px;color:var(--accent);font-family:'DM Mono',monospace;font-weight:500}

/* db / result table */
.db-table{width:100%;border-collapse:collapse;font-size:12px;margin-top:4px}
.db-table th{text-align:left;font-size:9px;letter-spacing:.1em;color:var(--muted);font-family:'DM Mono',monospace;padding:0 0 8px;text-transform:uppercase;border-bottom:1px solid var(--border)}
.db-table td{padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.03);color:var(--text);vertical-align:top}
.db-table tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 7px;border-radius:5px;font-size:9px;font-family:'DM Mono',monospace;letter-spacing:.04em}
.badge-green{background:rgba(34,197,94,.12);color:#4ade80}
.badge-amber{background:rgba(245,158,11,.12);color:#fbbf24}
.badge-red{background:rgba(244,63,94,.10);color:#fb7185}
.badge-blue{background:var(--blue-dim);color:var(--blue)}
.action-confirm{display:flex;align-items:center;gap:8px;padding:10px 12px;background:rgba(34,197,94,.06);border:1px solid rgba(34,197,94,.15);border-radius:8px;margin-top:4px}
.action-icon{font-size:16px}
.action-text{font-size:12px;color:#4ade80}

/* calc result */
.calc-display{text-align:center;padding:16px}
.calc-expr{font-size:13px;color:var(--muted2);font-family:'DM Mono',monospace;margin-bottom:6px}
.calc-result{font-family:'Syne',sans-serif;font-size:38px;font-weight:800;color:var(--accent)}

/* ── INPUT ── */
.input-zone{padding:12px 24px 20px;flex-shrink:0;border-top:1px solid var(--border)}
.input-wrap{background:var(--surf);border:1px solid var(--border);border-radius:14px;padding:3px 3px 3px 16px;display:flex;align-items:flex-end;gap:5px;transition:border-color .2s,box-shadow .2s}
.input-wrap:focus-within{border-color:rgba(184,248,74,.28);box-shadow:0 0 0 3px rgba(184,248,74,.05)}
.input-wrap textarea{flex:1;background:transparent;border:none;outline:none;color:var(--text);font-family:'DM Sans',sans-serif;font-size:13.5px;resize:none;min-height:22px;max-height:130px;padding:10px 0;line-height:1.6}
.input-wrap textarea::placeholder{color:var(--muted)}
.input-btns{display:flex;align-items:center;gap:3px;padding:4px;flex-shrink:0}
.i-btn{width:34px;height:34px;border-radius:8px;border:none;background:transparent;color:var(--muted);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:14px;transition:all var(--transition)}
.i-btn:hover{background:rgba(255,255,255,0.06);color:var(--text)}
.send{background:var(--accent);color:#05100a;width:34px;height:34px;border-radius:8px;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .18s;flex-shrink:0}
.send:hover{background:#cdff55;box-shadow:0 0 16px var(--accent-glow);transform:scale(1.04)}
.send:active{transform:scale(.96)}
.input-hint{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;margin-top:7px;padding:0 2px;display:flex;gap:12px}
kbd{background:var(--panel);border:1px solid rgba(255,255,255,0.08);border-radius:3px;padding:0 4px;font-size:9px;font-family:'DM Mono',monospace;color:var(--muted2)}
</style>
</head>
<body>

<!-- SIDEBAR -->
<aside class="sidebar">
  <div class="logo-area">
    <div class="live-badge"><span class="live-dot"></span><span class="live-text">LIVE · 6 AGENTS</span></div>
    <div class="logo-name">AI <em>Nexus</em></div>
    <div class="logo-sub">multi-agent intelligence</div>
  </div>

  <div class="nav-section">
    <div class="nav-group-label">Agents</div>
    <div class="nav-item active" onclick="setNav(this,'// all_agents_active')">
      <div class="nav-icon">⚡</div><span class="nav-label-text">All Agents</span>
    </div>
    <div class="nav-item" onclick="setNav(this,'// weather_agent')">
      <div class="nav-icon">🌤</div><span class="nav-label-text">Weather</span><span class="nav-tag tag-live">LIVE</span>
    </div>
    <div class="nav-item" onclick="setNav(this,'// news_agent')">
      <div class="nav-icon">📰</div><span class="nav-label-text">News</span>
    </div>
    <div class="nav-item" onclick="setNav(this,'// crypto_agent')">
      <div class="nav-icon">₿</div><span class="nav-label-text">Crypto</span><span class="nav-tag tag-live">LIVE</span>
    </div>
    <div class="nav-item" onclick="setNav(this,'// database_agent')">
      <div class="nav-icon">🗄</div><span class="nav-label-text">Database</span>
    </div>
    <div class="nav-item" onclick="setNav(this,'// calculator_agent')">
      <div class="nav-icon">🧮</div><span class="nav-label-text">Calculator</span><span class="nav-tag tag-new">NEW</span>
    </div>
    <div class="nav-item" onclick="setNav(this,'// converter_agent')">
      <div class="nav-icon">🔄</div><span class="nav-label-text">Converter</span><span class="nav-tag tag-new">NEW</span>
    </div>
  </div>

  <div class="sidebar-stats">
    <div class="stat-row">
      <div class="stat-cell"><div class="stat-val" id="msg-count">0</div><div class="stat-lbl">MESSAGES</div></div>
      <div class="stat-cell"><div class="stat-val">6</div><div class="stat-lbl">AGENTS</div></div>
    </div>
    <div class="model-chip">
      <div class="model-info">
        <div class="model-name">LLaMA 3.3 70B</div>
        <div class="model-engine">via Groq Cloud</div>
      </div>
      <div class="online-dot"></div>
    </div>
  </div>
</aside>

<!-- MAIN -->
<main class="main">
  <header class="topbar">
    <div class="topbar-left">
      <div class="topbar-title">Multi-Agent Conversation</div>
      <div class="topbar-sub" id="topbar-agent">// all_agents_active</div>
    </div>
    <div class="topbar-right">
      <div class="status-chip"><div class="dot" style="background:var(--green);box-shadow:0 0 5px var(--green)"></div>All systems operational</div>
      <button class="btn-sm" onclick="clearChat()">Clear chat</button>
    </div>
  </header>

  <div class="chat-area" id="chat">
    <div class="empty" id="empty-state">
      <div class="empty-glow">⚡</div>
      <div class="empty-title">AI Nexus</div>
      <div class="empty-sub">6 specialized agents at your command. Ask about weather anywhere, crypto prices, breaking news, run calculations, convert units, or query the database.</div>
      <div class="agent-grid">
        <div class="agent-card" onclick="qs('What is the weather in Tirunelveli?')">
          <div class="agent-card-icon">🌤</div>
          <div class="agent-card-name">Weather Agent</div>
          <div class="agent-card-hint">Any city worldwide</div>
        </div>
        <div class="agent-card" onclick="qs('Show me the latest AI news')">
          <div class="agent-card-icon">📰</div>
          <div class="agent-card-name">News Agent</div>
          <div class="agent-card-hint">AI, tech, crypto, biz</div>
        </div>
        <div class="agent-card" onclick="qs('What is the Bitcoin price?')">
          <div class="agent-card-icon">₿</div>
          <div class="agent-card-name">Crypto Agent</div>
          <div class="agent-card-hint">50+ coins live</div>
        </div>
        <div class="agent-card" onclick="qs('List all products in the database')">
          <div class="agent-card-icon">🗄</div>
          <div class="agent-card-name">Database Agent</div>
          <div class="agent-card-hint">CRUD + SQL queries</div>
        </div>
        <div class="agent-card" onclick="qs('Calculate 15% of 85000')">
          <div class="agent-card-icon">🧮</div>
          <div class="agent-card-name">Calculator</div>
          <div class="agent-card-hint">Math & expressions</div>
        </div>
        <div class="agent-card" onclick="qs('Convert 1000 USD to INR')">
          <div class="agent-card-icon">🔄</div>
          <div class="agent-card-name">Converter</div>
          <div class="agent-card-hint">Currency, temp, units</div>
        </div>
      </div>
      <div class="suggestions">
        <div class="sugg" onclick="qs('Weather in London')">🌧 London weather</div>
        <div class="sugg" onclick="qs('Ethereum and Solana price')">📊 ETH & SOL</div>
        <div class="sugg" onclick="qs('Latest tech news')">🔬 Tech news</div>
        <div class="sugg" onclick="qs('25 C to F')">🌡 25°C to °F</div>
        <div class="sugg" onclick="qs('Add task: Review hackathon submission')">✅ Add a task</div>
      </div>
    </div>
  </div>

  <div class="input-zone">
    <div class="input-wrap">
      <textarea id="msg" rows="1" placeholder="Ask anything — weather, crypto, news, math, convert, database…"
        onkeydown="handleKey(event)" oninput="autoH(this)"></textarea>
      <div class="input-btns">
        <button class="i-btn" onclick="startVoice()" title="Voice">🎤</button>
        <button class="send" onclick="send()" title="Send">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </div>
    <div class="input-hint">
      <span><kbd>Enter</kbd> send &nbsp; <kbd>Shift+Enter</kbd> newline</span>
    </div>
  </div>
</main>

<script>
let msgCount = 0;

const AGENT_META = {
  weather:   { label:'☁ WEATHER',  color:'rgba(245,158,11,.1)',  text:'#f59e0b' },
  news:      { label:'◈ NEWS',     color:'rgba(167,139,250,.1)', text:'#a78bfa' },
  crypto:    { label:'₿ CRYPTO',  color:'rgba(251,146,60,.1)',  text:'#fb923c' },
  db:        { label:'◆ DATABASE', color:'rgba(34,197,94,.1)',   text:'#4ade80' },
  calc:      { label:'∑ CALC',     color:'rgba(56,189,248,.1)',  text:'#38bdf8' },
  converter: { label:'⇄ CONVERT', color:'rgba(184,248,74,.1)',  text:'#b8f84a' },
  chat:      { label:'● NEXUS',    color:'rgba(56,189,248,.1)',  text:'#38bdf8' },
};

function setNav(el, label) {
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('topbar-agent').textContent = label;
}

function autoH(el) { el.style.height='auto'; el.style.height=Math.min(el.scrollHeight,130)+'px'; }
function handleKey(e) { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();} }
function qs(t) { document.getElementById('msg').value=t; send(); }

function clearChat() {
  document.querySelectorAll('.msg-row').forEach(r=>r.remove());
  document.getElementById('empty-state').style.display='';
  msgCount=0; document.getElementById('msg-count').textContent='0';
}

function startVoice() {
  const r=new(window.SpeechRecognition||window.webkitSpeechRecognition)();
  r.lang='en-US';
  r.onresult=e=>{const ta=document.getElementById('msg');ta.value=e.results[0][0].transcript;autoH(ta);};
  r.start();
}

function getTime() { return new Date().toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'}); }
function esc(t) { return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function typeEffect(text, el, cb) {
  let i=0;
  function tick() {
    if(i<text.length){el.textContent+=text.charAt(i++);setTimeout(tick,6);}
    else if(cb) cb();
  }
  tick();
}

// ── RICH CARD RENDERERS ──
function renderWeather(d) {
  const icons = {'Sunny':'☀️','Partly Cloudy':'⛅','Overcast':'☁️','Humid & Clear':'🌤','Breezy':'🌬️'};
  const ico = icons[d.condition] || '🌡';
  return `<div class="card">
    <div class="card-header">
      <span class="card-header-icon">🌤</span>
      <span class="card-header-title">Weather — ${esc(d.city)}</span>
      <span class="card-header-sub">${getTime()}</span>
    </div>
    <div class="card-body">
      <div class="weather-main">
        <div>
          <div class="weather-temp">${d.temperature_c}<span class="weather-deg">°C</span></div>
          <div class="weather-city">${esc(d.city)}</div>
          <div class="weather-cond">${d.condition} · Feels like ${d.feels_like_c}°C</div>
        </div>
        <div class="weather-icon-big">${ico}</div>
      </div>
      <div class="weather-stats">
        <div class="w-stat"><div class="w-stat-val">${d.humidity_pct}%</div><div class="w-stat-lbl">HUMIDITY</div></div>
        <div class="w-stat"><div class="w-stat-val">${d.wind_kmh} km/h</div><div class="w-stat-lbl">WIND</div></div>
        <div class="w-stat"><div class="w-stat-val">${d.uv_index}</div><div class="w-stat-lbl">UV INDEX</div></div>
        <div class="w-stat"><div class="w-stat-val">${d.visibility_km} km</div><div class="w-stat-lbl">VISIBILITY</div></div>
      </div>
    </div>
  </div>`;
}

function renderNews(d) {
  const items = d.articles.map((a,i)=>`
    <div class="news-item">
      <div class="news-num">0${i+1}</div>
      <div class="news-content">
        <div class="news-title">${esc(a.title)}</div>
        <div class="news-meta">
          <span class="news-src">${esc(a.source)}</span>
          <span class="news-time">${a.time}</span>
          <span class="news-cat">${esc(a.category)}</span>
        </div>
      </div>
    </div>`).join('');
  return `<div class="card">
    <div class="card-header">
      <span class="card-header-icon">📰</span>
      <span class="card-header-title">${esc(d.category)}</span>
      <span class="card-header-sub">Updated ${d.last_updated}</span>
    </div>
    <div class="card-body">${items}</div>
  </div>`;
}

function renderCrypto(d) {
  const coins = d.coins.map(c=>{
    const up = c.change_24h >= 0;
    const price = c.price_usd >= 1 ? '$'+c.price_usd.toLocaleString() : '$'+c.price_usd;
    return `<div class="crypto-item">
      <div class="crypto-top">
        <span class="crypto-sym">${c.symbol}</span>
        <span class="crypto-change ${up?'up':'dn'}">${up?'+':''}${c.change_24h}%</span>
      </div>
      <div class="crypto-price">${price}</div>
      <div class="crypto-name">${c.name}</div>
      <div class="crypto-mcap">MCap ${c.market_cap} · Vol ${c.volume_24h}</div>
    </div>`;
  }).join('');
  return `<div class="card">
    <div class="card-header">
      <span class="card-header-icon">₿</span>
      <span class="card-header-title">Crypto Markets</span>
      <span class="card-header-sub">${d.timestamp}</span>
    </div>
    <div class="card-body">
      <div class="crypto-grid">${coins}</div>
      <div class="sentiment-bar">
        <span class="sentiment-label">Market Sentiment</span>
        <span class="sentiment-val">${d.market_sentiment} · Fear &amp; Greed: ${d.fear_greed_index}</span>
      </div>
    </div>
  </div>`;
}

function renderDB(d) {
  if (d.action === 'list_products') {
    const rows = d.products.map(p=>`<tr>
      <td>${esc(p.name)}</td>
      <td><span class="badge badge-blue">${esc(p.category)}</span></td>
      <td style="font-family:'DM Mono',monospace">$${p.price}</td>
      <td>${p.stock}</td>
      <td style="color:#f59e0b">★ ${p.rating}</td>
    </tr>`).join('');
    return `<div class="card">
      <div class="card-header"><span class="card-header-icon">🗄</span><span class="card-header-title">Products (${d.count})</span></div>
      <div class="card-body">
        <table class="db-table">
          <thead><tr><th>Name</th><th>Category</th><th>Price</th><th>Stock</th><th>Rating</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
  }
  if (d.action === 'list_tasks') {
    if (!d.tasks.length) return `<div class="card"><div class="card-body"><div style="color:var(--muted);font-size:12px;text-align:center;padding:12px">No tasks yet. Try: "Add task: Review code"</div></div></div>`;
    const rows = d.tasks.map(t=>`<tr>
      <td>${esc(t.title)}</td>
      <td><span class="badge ${t.priority==='high'?'badge-red':t.priority==='medium'?'badge-amber':'badge-green'}">${t.priority}</span></td>
      <td><span class="badge badge-blue">${t.status}</span></td>
    </tr>`).join('');
    return `<div class="card">
      <div class="card-header"><span class="card-header-icon">✅</span><span class="card-header-title">Tasks (${d.count})</span></div>
      <div class="card-body">
        <table class="db-table">
          <thead><tr><th>Title</th><th>Priority</th><th>Status</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
  }
  if (d.action === 'task_created') {
    return `<div class="card"><div class="card-body"><div class="action-confirm"><span class="action-icon">✅</span><span class="action-text">Task created: "${esc(d.task)}" · Priority: ${d.priority}</span></div></div></div>`;
  }
  if (d.action === 'note_saved') {
    return `<div class="card"><div class="card-body"><div class="action-confirm"><span class="action-icon">📝</span><span class="action-text">Note saved: "${esc(d.content)}"</span></div></div></div>`;
  }
  if (d.action === 'sql_query' || d.action === 'product_search') {
    if (!d.rows && !d.products) return null;
    const data = d.rows || d.products;
    if (!data.length) return `<div class="card"><div class="card-body" style="color:var(--muted);font-size:12px">No results found.</div></div>`;
    const keys = Object.keys(data[0]);
    const headers = keys.map(k=>`<th>${k}</th>`).join('');
    const rows = data.map(r=>`<tr>${keys.map(k=>`<td>${r[k]??''}</td>`).join('')}</tr>`).join('');
    return `<div class="card">
      <div class="card-header"><span class="card-header-icon">🔍</span><span class="card-header-title">Query Results (${data.length})</span></div>
      <div class="card-body"><table class="db-table"><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table></div>
    </div>`;
  }
  return null;
}

function renderCalc(d) {
  if (d.status !== 'success') return null;
  return `<div class="card">
    <div class="card-header"><span class="card-header-icon">🧮</span><span class="card-header-title">Result</span></div>
    <div class="card-body"><div class="calc-display">
      <div class="calc-expr">${esc(d.expression)}</div>
      <div class="calc-result">= ${d.result.toLocaleString()}</div>
    </div></div>
  </div>`;
}

function renderConverter(d) {
  if (!d.from) return null;
  return `<div class="card">
    <div class="card-header"><span class="card-header-icon">🔄</span><span class="card-header-title">Conversion</span></div>
    <div class="card-body"><div class="calc-display">
      <div class="calc-expr">${esc(d.from)}</div>
      <div class="calc-result">= ${esc(d.to)}</div>
    </div></div>
  </div>`;
}

function buildCard(agent, toolData) {
  if (!toolData) return '';
  try {
    if (agent==='weather')   return renderWeather(toolData)   || '';
    if (agent==='news')      return renderNews(toolData)      || '';
    if (agent==='crypto')    return renderCrypto(toolData)    || '';
    if (agent==='db')        return renderDB(toolData)        || '';
    if (agent==='calc')      return renderCalc(toolData)      || '';
    if (agent==='converter') return renderConverter(toolData) || '';
  } catch(e) { console.error(e); }
  return '';
}

async function send() {
  const input = document.getElementById('msg');
  const msg = input.value.trim();
  if (!msg) return;
  const chat = document.getElementById('chat');
  document.getElementById('empty-state').style.display='none';

  msgCount++; document.getElementById('msg-count').textContent = msgCount;

  // User bubble
  const ur = document.createElement('div');
  ur.className='msg-row user';
  ur.innerHTML=`<div class="av av-user">U</div>
    <div class="msg-body">
      <div class="msg-meta">${getTime()}</div>
      <div class="bubble bubble-user">${esc(msg)}</div>
    </div>`;
  chat.appendChild(ur);
  input.value=''; input.style.height='auto';

  // Bot row + thinking
  const br = document.createElement('div');
  br.className='msg-row';
  br.innerHTML=`<div class="av av-bot">⚡</div>
    <div class="msg-body" id="bot-body">
      <div class="msg-meta" id="bot-meta"><span id="bot-tag"></span></div>
      <div class="thinking" id="thinker"><div class="th-dot"></div><div class="th-dot"></div><div class="th-dot"></div></div>
      <div class="bubble bubble-bot" id="bot-bub" style="display:none"></div>
      <div id="bot-card"></div>
    </div>`;
  chat.appendChild(br);
  chat.scrollTop=chat.scrollHeight;

  // Fetch
  const res = await fetch('/chat', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:msg})
  });
  const data = await res.json();

  // Render
  const agent = data.agent || 'chat';
  const meta = AGENT_META[agent] || AGENT_META.chat;

  document.getElementById('thinker').remove();
  const tag = document.getElementById('bot-tag');
  tag.textContent = meta.label;
  tag.style.cssText=`padding:1px 7px;border-radius:4px;font-size:9px;letter-spacing:.07em;font-family:'DM Mono',monospace;background:${meta.color};color:${meta.text}`;
  document.getElementById('bot-meta').appendChild(document.createTextNode(' '+getTime()));

  const bub = document.getElementById('bot-bub');
  bub.style.display='inline-block';
  typeEffect(data.response, bub, ()=>{
    const card = buildCard(agent, data.tool_data);
    if(card) document.getElementById('bot-card').innerHTML=card;
    chat.scrollTop=chat.scrollHeight;
  });

  msgCount++; document.getElementById('msg-count').textContent=msgCount;
  chat.scrollTop=chat.scrollHeight;
}
</script>
</body>
</html>"""

# ═══════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════
@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/chat", methods=["POST"])
def chat():
    msg = request.json.get("message", "")
    agent = route_message(msg)

    tool_data = None
    context_injection = ""

    if agent == "weather":
        tool_data = weather_agent(msg)
        context_injection = f"\n[WEATHER DATA]: {json.dumps(tool_data)}"
    elif agent == "news":
        tool_data = news_agent(msg)
        context_injection = f"\n[NEWS DATA]: {json.dumps(tool_data)}"
    elif agent == "crypto":
        tool_data = crypto_agent(msg)
        context_injection = f"\n[CRYPTO DATA]: {json.dumps(tool_data)}"
    elif agent == "db":
        tool_data = db_agent(msg)
        context_injection = f"\n[DATABASE DATA]: {json.dumps(tool_data)}"
    elif agent == "calc":
        tool_data = calc_agent(msg)
        context_injection = f"\n[CALCULATOR DATA]: {json.dumps(tool_data)}"
    elif agent == "converter":
        tool_data = converter_agent(msg)
        context_injection = f"\n[CONVERTER DATA]: {json.dumps(tool_data)}"

    full_msg = msg + context_injection
    chat_memory.append({"role": "user", "content": full_msg})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_memory[-10:]

    groq_res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=512,
        temperature=0.7,
    )
    reply = groq_res.choices[0].message.content
    chat_memory.append({"role": "assistant", "content": reply})

    return jsonify({"response": reply, "agent": agent, "tool_data": tool_data})

@app.route("/health")
def health():
    conn = sqlite3.connect(DB)
    p = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    conn.close()
    return jsonify({"status": "ok", "agents": 6, "products": p})

if __name__ == "__main__":
    init_db()
    app.run(debug=False)
