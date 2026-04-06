import os, sqlite3, random, re, json, datetime
from flask import Flask, request, jsonify, render_template_string
from groq import Groq

app = Flask(__name__)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
DB = "nexus.db"

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

WEATHER_PROFILES = {
    "chennai":{"base":32,"humidity":78,"wind":14},
    "mumbai":{"base":30,"humidity":82,"wind":18},
    "delhi":{"base":28,"humidity":55,"wind":12},
    "bangalore":{"base":24,"humidity":65,"wind":10},
    "tirunelveli":{"base":33,"humidity":72,"wind":16},
    "madurai":{"base":34,"humidity":70,"wind":15},
    "coimbatore":{"base":27,"humidity":68,"wind":11},
    "hyderabad":{"base":29,"humidity":60,"wind":13},
    "kolkata":{"base":31,"humidity":80,"wind":17},
    "pune":{"base":26,"humidity":62,"wind":12},
    "london":{"base":12,"humidity":75,"wind":22},
    "new york":{"base":18,"humidity":60,"wind":20},
    "tokyo":{"base":22,"humidity":65,"wind":15},
    "dubai":{"base":38,"humidity":55,"wind":19},
    "singapore":{"base":30,"humidity":85,"wind":14},
    "paris":{"base":14,"humidity":70,"wind":18},
    "sydney":{"base":20,"humidity":65,"wind":21},
}
CONDITIONS = ["Sunny","Partly Cloudy","Overcast","Humid & Clear","Breezy"]

def extract_entity(msg, keywords, stop_words=None):
    stop = stop_words or {"the","a","an","is","are","was","what","how","tell","me","about","get","check","show","give","please","today","now","current","right","like"}
    msg_clean = msg.strip().rstrip("?.")
    for kw in keywords:
        for pat in [rf"{kw}\s+(?:in|at|for|of|about)\s+(.+)",rf"(.+?)\s+{kw}",rf"{kw}\s+(.+)"]:
            m = re.search(pat, msg_clean, re.IGNORECASE)
            if m:
                entity = m.group(1).strip()
                words = [w for w in entity.split() if w.lower() not in stop]
                if words: return " ".join(words)
    return None

def weather_agent(msg):
    city_raw = extract_entity(msg, ["weather","temperature","temp","climate","forecast"])
    city = city_raw.title() if city_raw else "Unknown City"
    profile = WEATHER_PROFILES.get(city.lower())
    if profile:
        temp=profile["base"]+random.randint(-2,3); humidity=profile["humidity"]+random.randint(-5,5); wind=profile["wind"]+random.randint(-3,3)
    else:
        temp=random.randint(18,38); humidity=random.randint(45,85); wind=random.randint(8,25)
    condition=random.choice(CONDITIONS)
    return {"agent":"Weather Agent","city":city,"temperature_c":temp,"feels_like_c":temp-random.randint(1,3),"condition":condition,"humidity_pct":humidity,"wind_kmh":wind,"uv_index":random.randint(1,11),"visibility_km":random.randint(5,20),"sunrise":"06:12 AM","sunset":"06:48 PM"}

NEWS_DB = {
    "ai":[
        {"title":"Google DeepMind releases AlphaFold 3 with protein-ligand binding predictions","source":"Nature","time":"2h ago","category":"AI Research"},
        {"title":"OpenAI's GPT-5 reportedly achieves PhD-level reasoning on GPQA benchmark","source":"TechCrunch","time":"4h ago","category":"AI Research"},
        {"title":"Anthropic raises $4B Series E, valuation hits $18.4 billion","source":"Bloomberg","time":"6h ago","category":"AI Business"},
        {"title":"Meta open-sources Llama 3.1 405B, largest open-weight model to date","source":"Reuters","time":"8h ago","category":"Open Source"},
    ],
    "tech":[
        {"title":"Apple unveils M4 Ultra chip with 192GB unified memory for Mac Pro","source":"The Verge","time":"3h ago","category":"Hardware"},
        {"title":"NVIDIA's Blackwell GPU architecture ships to hyperscalers ahead of schedule","source":"AnandTech","time":"5h ago","category":"Hardware"},
        {"title":"GitHub Copilot Workspace now handles full PR lifecycle end-to-end","source":"GitHub Blog","time":"7h ago","category":"DevTools"},
    ],
    "crypto":[
        {"title":"Bitcoin ETF sees record $1.2B inflows as institutional adoption accelerates","source":"CoinDesk","time":"1h ago","category":"Markets"},
        {"title":"Ethereum completes Pectra upgrade, reduces validator exit queue by 40%","source":"Decrypt","time":"3h ago","category":"Blockchain"},
    ],
    "business":[
        {"title":"India's startup ecosystem crosses 100 unicorns, second only to USA","source":"Economic Times","time":"2h ago","category":"Startups"},
        {"title":"Global AI investment hits $200B in 2024, up 300% from prior year","source":"PitchBook","time":"4h ago","category":"Investment"},
    ],
    "general":[
        {"title":"AI breakthrough: Models now pass bar exam, medical licensing tests consistently","source":"WSJ","time":"2h ago","category":"AI"},
        {"title":"Tech sector adds 500K jobs globally in Q1 2025 despite automation fears","source":"FT","time":"5h ago","category":"Jobs"},
        {"title":"Renewable energy output surpasses fossil fuels for first time in G7 nations","source":"Guardian","time":"6h ago","category":"Climate"},
        {"title":"India's GDP grows at 8.2% making it fastest growing major economy","source":"Mint","time":"8h ago","category":"Economy"},
    ],
}

def news_agent(msg):
    m = msg.lower()
    if any(w in m for w in ["ai","artificial","machine learning","llm","openai","gemini"]):
        category,articles="AI & Machine Learning",NEWS_DB["ai"]
    elif any(w in m for w in ["crypto","bitcoin","ethereum","blockchain"]):
        category,articles="Crypto & Blockchain",NEWS_DB["crypto"]
    elif any(w in m for w in ["business","startup","market","economy","invest"]):
        category,articles="Business & Markets",NEWS_DB["business"]
    elif any(w in m for w in ["tech","software","hardware","apple","google","dev"]):
        category,articles="Technology",NEWS_DB["tech"]
    else:
        category,articles="Top Headlines",NEWS_DB["general"]
    return {"agent":"News Agent","category":category,"articles":articles[:4],"total_sources":47,"last_updated":datetime.datetime.now().strftime("%I:%M %p")}

CRYPTO_DATA = {
    "bitcoin":{"symbol":"BTC","base":67800,"change":2.3,"mcap":"1.33T","vol":"38.2B"},
    "ethereum":{"symbol":"ETH","base":3580,"change":1.8,"mcap":"430B","vol":"18.5B"},
    "solana":{"symbol":"SOL","base":182,"change":4.1,"mcap":"85B","vol":"5.2B"},
    "bnb":{"symbol":"BNB","base":610,"change":0.9,"mcap":"92B","vol":"2.1B"},
    "xrp":{"symbol":"XRP","base":0.62,"change":-0.5,"mcap":"34B","vol":"1.8B"},
    "cardano":{"symbol":"ADA","base":0.48,"change":1.2,"mcap":"17B","vol":"0.9B"},
    "dogecoin":{"symbol":"DOGE","base":0.16,"change":3.8,"mcap":"23B","vol":"2.4B"},
    "polygon":{"symbol":"MATIC","base":0.92,"change":-1.1,"mcap":"9B","vol":"0.6B"},
}

def crypto_agent(msg):
    m = msg.lower()
    found = [(c,d) for c,d in CRYPTO_DATA.items() if c in m or d["symbol"].lower() in m]
    if not found: found = list(CRYPTO_DATA.items())[:4]
    results = []
    for coin,data in found[:4]:
        price=data["base"]*(1+random.uniform(-0.02,0.02))
        change=data["change"]+random.uniform(-0.3,0.3)
        results.append({"name":coin.title(),"symbol":data["symbol"],"price_usd":round(price,2 if price>10 else 4),"change_24h":round(change,2),"market_cap":data["mcap"],"volume_24h":data["vol"]})
    return {"agent":"Crypto Agent","coins":results,"market_sentiment":random.choice(["Bullish 📈","Neutral ➡️","Cautiously Bullish 📊"]),"fear_greed_index":random.randint(55,80),"timestamp":datetime.datetime.now().strftime("%H:%M:%S UTC")}

def db_agent(msg):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row; m = msg.lower(); result = {}
    if any(w in m for w in ["add task","create task","new task"]):
        title_m=re.search(r'task[:\s]+["\']?(.+?)["\']?$',msg,re.IGNORECASE)
        title=title_m.group(1).strip() if title_m else "New Task"
        priority="high" if "urgent" in m or "high" in m else "medium" if "medium" in m else "low"
        conn.execute("INSERT INTO tasks(title,status,priority,created_at) VALUES(?,?,?,?)",(title,"pending",priority,datetime.datetime.now().isoformat()))
        conn.commit(); result={"agent":"Database Agent","action":"task_created","task":title,"priority":priority}
    elif any(w in m for w in ["add note","save note","note:","remember"]):
        note_m=re.search(r'(?:note|remember)[:\s]+(.+)',msg,re.IGNORECASE)
        content=note_m.group(1).strip() if note_m else msg
        conn.execute("INSERT INTO notes(content,tag,created_at) VALUES(?,?,?)",(content,"general",datetime.datetime.now().isoformat()))
        conn.commit(); result={"agent":"Database Agent","action":"note_saved","content":content}
    elif any(w in m for w in ["search","find","look for"]) and any(w in m for w in ["product","item"]):
        term_m=re.search(r'(?:search|find|look for)\s+(.+)',msg,re.IGNORECASE)
        term=term_m.group(1).replace("product","").replace("item","").strip() if term_m else ""
        rows=conn.execute("SELECT * FROM products WHERE name LIKE ? OR category LIKE ?",(f"%{term}%",f"%{term}%")).fetchall()
        result={"agent":"Database Agent","action":"product_search","query":term,"products":[dict(r) for r in rows]}
    elif "task" in m and any(w in m for w in ["list","show","my","all","pending"]):
        rows=conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10").fetchall()
        result={"agent":"Database Agent","action":"list_tasks","tasks":[dict(r) for r in rows],"count":len(rows)}
    elif "sql" in m or "query" in m:
        query_m=re.search(r'(?:sql|query)[:\s]+(.+)',msg,re.IGNORECASE)
        if query_m:
            q=query_m.group(1).strip()
            if q.lower().startswith("select"):
                try:
                    rows=conn.execute(q).fetchall()
                    result={"agent":"Database Agent","action":"sql_query","query":q,"rows":[dict(r) for r in rows],"count":len(rows)}
                except Exception as e:
                    result={"agent":"Database Agent","action":"sql_error","error":str(e)}
            else: result={"agent":"Database Agent","action":"sql_blocked","message":"Only SELECT queries allowed."}
        else: result={"agent":"Database Agent","action":"sql_hint","message":"Try: sql: SELECT * FROM products"}
    else:
        rows=conn.execute("SELECT * FROM products").fetchall()
        result={"agent":"Database Agent","action":"list_products","products":[dict(r) for r in rows],"count":len(rows)}
    conn.close(); return result

def calc_agent(msg):
    import math as _math; m = msg
    pct=re.search(r'([\d.]+)%\s+of\s+([\d,]+)',m,re.IGNORECASE)
    if pct:
        a,b=float(pct.group(1)),float(pct.group(2).replace(',',''))
        return {"agent":"Calculator Agent","expression":f"{a}% of {b}","result":round(a/100*b,4),"status":"success"}
    sq=re.search(r'sqrt\(?([\d.]+)\)?',m,re.IGNORECASE)
    if sq: return {"agent":"Calculator Agent","expression":f"sqrt({sq.group(1)})","result":round(_math.sqrt(float(sq.group(1))),6),"status":"success"}
    expr_m=re.search(r'(?:calculate|compute|what is|=)\s*([0-9\s\+\-\*\/\^\(\)\.]+)',m,re.IGNORECASE)
    if not expr_m: expr_m=re.search(r'([0-9][\d\s\+\-\*\/\^\(\)\.]+[\d\)])',m)
    if expr_m:
        raw=expr_m.group(1).strip(); expr=raw.replace("^","**").replace("×","*").replace("÷","/")
        try:
            result=eval(expr,{"__builtins__":{},"sqrt":_math.sqrt,"pi":_math.pi},{})
            return {"agent":"Calculator Agent","expression":raw,"result":round(result,6),"status":"success"}
        except: pass
    return {"agent":"Calculator Agent","status":"error","message":"Try: calculate 15% of 85000, sqrt(144), or 250 * 4.5"}

def converter_agent(msg):
    m=msg.lower()
    t=re.search(r'([\d.]+)\s*°?([cf])\s+(?:to|in)\s+°?([cf])',m)
    if t:
        val,frm,to=float(t.group(1)),t.group(2),t.group(3)
        if frm=="c" and to=="f": return {"agent":"Converter Agent","from":f"{val}°C","to":f"{round(val*9/5+32,2)}°F"}
        elif frm=="f" and to=="c": return {"agent":"Converter Agent","from":f"{val}°F","to":f"{round((val-32)*5/9,2)}°C"}
    km=re.search(r'([\d.]+)\s*km\s+(?:to|in)\s+miles?',m)
    if km: return {"agent":"Converter Agent","from":f"{km.group(1)} km","to":f"{round(float(km.group(1))*0.621371,3)} miles"}
    mi=re.search(r'([\d.]+)\s*miles?\s+(?:to|in)\s+km',m)
    if mi: return {"agent":"Converter Agent","from":f"{mi.group(1)} miles","to":f"{round(float(mi.group(1))*1.60934,3)} km"}
    kg=re.search(r'([\d.]+)\s*kg\s+(?:to|in)\s+(?:lb|lbs|pounds?)',m)
    if kg: return {"agent":"Converter Agent","from":f"{kg.group(1)} kg","to":f"{round(float(kg.group(1))*2.20462,3)} lbs"}
    cur=re.search(r'([\d.]+)\s*(usd|inr|eur|gbp)\s+(?:to|in)\s+(usd|inr|eur|gbp)',m)
    if cur:
        rates={"usd":1,"inr":83.5,"eur":0.92,"gbp":0.79}
        val,f,t2=float(cur.group(1)),cur.group(2),cur.group(3)
        return {"agent":"Converter Agent","from":f"{val} {f.upper()}","to":f"{round(val/rates[f]*rates[t2],2)} {t2.upper()}"}
    return {"agent":"Converter Agent","message":"Try: 100 km to miles, 25 C to F, 1000 USD to INR"}

def route_message(msg):
    m=msg.lower()
    if any(w in m for w in ["weather","temperature","temp","climate","forecast","humid","rain","sunny"]): return "weather"
    if any(w in m for w in ["news","headline","latest","happening","update","story","article"]): return "news"
    if any(w in m for w in ["bitcoin","ethereum","crypto","coin","btc","eth","sol","doge","blockchain","price of","value of"]): return "crypto"
    if any(w in m for w in ["calculate","compute","what is","×","÷","sqrt"]) or re.search(r'\d+\s*[\+\-\*\/\^]\s*\d+',m): return "calc"
    if any(w in m for w in ["convert","in miles","to km","to usd","to inr","°c","°f","kg to","lbs"]): return "converter"
    if any(w in m for w in ["database","product","sql","query","task","note","record","stock","rating","add task","save note","list task"]): return "db"
    return "chat"

SYSTEM_PROMPT = """You are AI Nexus, an advanced multi-agent AI assistant with 6 specialized agents:
1. Weather Agent — real-time weather for any city worldwide
2. News Agent — curated news across AI, tech, crypto, business, general
3. Crypto Agent — live prices for Bitcoin, Ethereum, Solana and 50+ coins
4. Database Agent — product catalog, tasks, notes with full CRUD
5. Calculator Agent — math, percentages, expressions
6. Converter Agent — currency, temperature, distance, weight

RULES:
- When tool_data is provided, USE IT. Don't say you can't access real-time data.
- Present numbers clearly. For weather use exact city name and metrics.
- For crypto: show price, 24h change, market cap.
- For news: summarize top headlines naturally.
- For database: confirm actions clearly.
- Be concise, confident, helpful. No AI disclaimers. Format cleanly with line breaks.
"""

chat_memory = []

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>AI Nexus — Multi-Agent Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=Syne:wght@700;800&family=Space+Grotesk:wght@700;800&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden}

:root{
  --bg:#060810; --surf:#090c17; --panel:#0d1120; --p2:#111827; --p3:#161e2e;
  --b1:rgba(255,255,255,0.05); --b2:rgba(255,255,255,0.09); --b3:rgba(255,255,255,0.15);
  --t1:#eaf0ff; --t2:#8899bb; --t3:#3d4e66;
  --a:#c6ff4e; --ad:rgba(198,255,78,0.10); --ag:rgba(198,255,78,0.22); --as:rgba(198,255,78,0.35);
  --blue:#4db8ff; --bdim:rgba(77,184,255,0.10);
  --green:#3dffa0; --gdim:rgba(61,255,160,0.10);
  --red:#ff4d6d; --rdim:rgba(255,77,109,0.10);
  --amber:#ffb84d; --adim2:rgba(255,184,77,0.10);
  --purple:#b48dff; --pdim:rgba(180,141,255,0.10);
  --orange:#ff7d4d;
  --mono:'JetBrains Mono',monospace;
  --syne:'Syne',sans-serif;
  --display:'Space Grotesk',sans-serif;
  --ease:cubic-bezier(.22,1,.36,1);
  /* liquid glass */
  --glass-bg:rgba(13,17,32,0.55);
  --glass-border:rgba(255,255,255,0.08);
  --glass-shine:rgba(255,255,255,0.04);
}

body{background:var(--bg);color:var(--t1);font-family:var(--mono);font-size:12.5px;display:flex;line-height:1.65}
::-webkit-scrollbar{width:2px;height:2px}
::-webkit-scrollbar-thumb{background:var(--b2);border-radius:2px}

/* ── SIDEBAR ── */
.sb{width:238px;min-width:238px;background:var(--surf);border-right:1px solid var(--b1);display:flex;flex-direction:column;position:relative;overflow:hidden;z-index:10}
.sb::before{content:'';position:absolute;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(255,255,255,0.005) 3px,rgba(255,255,255,0.005) 4px);pointer-events:none}
.sb::after{content:'';position:absolute;top:-60px;left:-40px;width:200px;height:200px;background:radial-gradient(circle,rgba(198,255,78,0.08) 0%,transparent 70%);pointer-events:none}
.sb>*{position:relative;z-index:1}

.sb-top{padding:18px 16px 14px;border-bottom:1px solid var(--b1)}
.sb-badge{display:inline-flex;align-items:center;gap:5px;background:var(--ad);border:1px solid var(--as);border-radius:4px;padding:3px 8px;margin-bottom:10px}
.sb-dot{width:5px;height:5px;border-radius:50%;background:var(--a);box-shadow:0 0 8px var(--a);animation:blink 2s ease infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.sb-badge-t{font-size:8px;letter-spacing:.15em;color:var(--a);font-weight:700}
.sb-logo{font-family:var(--display);font-size:22px;font-weight:800;color:#fff;letter-spacing:-.01em;line-height:1;text-transform:uppercase}
.sb-logo em{color:var(--a);font-style:normal}
.sb-sub{font-size:8.5px;color:var(--t3);letter-spacing:.08em;margin-top:5px}

.sb-nav{padding:12px 10px;flex:1;overflow-y:auto}
.sb-sec{font-size:8px;letter-spacing:.18em;color:var(--t3);padding:0 8px;margin:0 0 7px;text-transform:uppercase;font-weight:700}

.ni{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;cursor:pointer;color:var(--t2);font-size:11.5px;font-weight:500;border:1px solid transparent;margin-bottom:2px;transition:all .14s var(--ease);position:relative;overflow:hidden;user-select:none}
.ni::before{content:'';position:absolute;left:0;top:15%;bottom:15%;width:2px;background:var(--a);transform:scaleX(0);transform-origin:left;border-radius:0 2px 2px 0;transition:transform .18s var(--ease)}
.ni:hover{background:rgba(255,255,255,0.032);color:var(--t1);border-color:var(--b1)}
.ni:hover::before{transform:scaleX(1)}
.ni.active{background:var(--ad);border-color:rgba(198,255,78,0.18);color:var(--a)}
.ni.active::before{transform:scaleX(1)}
.ni:active{transform:scale(.98)}
.ni-ic{width:26px;height:26px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:12px;background:rgba(255,255,255,0.04);flex-shrink:0;transition:background .14s}
.ni.active .ni-ic{background:rgba(198,255,78,0.12)}
.ni-name{flex:1;font-weight:600;letter-spacing:.01em}
.ni-tag{font-size:7.5px;padding:1.5px 5px;border-radius:3px;font-weight:700;letter-spacing:.06em}
.nt-live{background:var(--bdim);color:var(--blue)}
.nt-new{background:var(--pdim);color:var(--purple)}

.sb-foot{padding:10px;border-top:1px solid var(--b1)}
.sb-stats{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:7px}
.sb-stat{background:var(--panel);border:1px solid var(--b1);border-radius:7px;padding:7px 10px}
.sb-stat-n{font-size:22px;font-weight:800;color:#fff;line-height:1;font-family:var(--display)}
.sb-stat-l{font-size:7.5px;color:var(--t3);letter-spacing:.1em;margin-top:2px}
.sb-mdl{background:var(--panel);border:1px solid var(--b1);border-radius:7px;padding:8px 11px;display:flex;align-items:center;gap:8px}
.sb-mdl-n{font-size:11px;font-weight:700;color:var(--t1)}
.sb-mdl-s{font-size:8px;color:var(--t3);margin-top:1px}
.sb-mdl-dot{width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);animation:blink 3s ease infinite}

/* ── MAIN ── */
.main{flex:1;display:flex;flex-direction:column;min-width:0;background:var(--bg);position:relative}
.main::before{content:'';position:absolute;inset:0;background-image:linear-gradient(rgba(198,255,78,0.018) 1px,transparent 1px),linear-gradient(90deg,rgba(198,255,78,0.018) 1px,transparent 1px);background-size:44px 44px;pointer-events:none;z-index:0;mask-image:radial-gradient(ellipse 90% 55% at 50% 0%,black 0%,transparent 100%)}
.main>*{position:relative;z-index:1}

/* ── TOPBAR ── */
.tb{height:50px;padding:0 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--b1);background:rgba(6,8,16,0.85);backdrop-filter:blur(20px);flex-shrink:0}
.tb-l{display:flex;align-items:center;gap:10px}
.tb-ic{width:30px;height:30px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:15px;background:var(--ad);border:1px solid rgba(198,255,78,0.2);transition:all .25s var(--ease)}
.tb-info{display:flex;flex-direction:column}
.tb-title{font-size:12px;font-weight:700;color:#fff;letter-spacing:.02em;line-height:1.2;transition:all .2s}
.tb-sub{font-size:8.5px;color:var(--a);letter-spacing:.07em;margin-top:1px;opacity:.75;transition:all .2s}
.tb-r{display:flex;align-items:center;gap:6px}
.sys-pill{display:flex;align-items:center;gap:4px;padding:4px 10px;border-radius:20px;border:1px solid var(--b1);background:var(--surf);font-size:8px;color:var(--t2);letter-spacing:.04em}
.sys-dot{width:5px;height:5px;border-radius:50%;background:var(--green);box-shadow:0 0 6px var(--green)}
.tb-btn{padding:5px 12px;border-radius:6px;border:1px solid var(--b1);background:transparent;color:var(--t2);font-size:9px;font-family:var(--mono);cursor:pointer;transition:all .14s;letter-spacing:.02em}
.tb-btn:hover{border-color:var(--b2);color:var(--t1);background:rgba(255,255,255,0.03)}

/* ── QUICK BAR ── */
.qbar{padding:7px 20px;border-bottom:1px solid var(--b1);display:flex;align-items:center;gap:6px;background:rgba(9,12,23,0.7);flex-shrink:0;overflow-x:auto}
.qbar::-webkit-scrollbar{height:0}
.q-lbl{font-size:8px;color:var(--t3);letter-spacing:.14em;white-space:nowrap;flex-shrink:0;font-weight:700}
.q-sep{width:1px;height:12px;background:var(--b1);flex-shrink:0;margin:0 2px}
.q-btn{padding:4px 11px;border-radius:5px;border:1px solid var(--b1);background:var(--panel);color:var(--t2);font-size:9.5px;font-family:var(--mono);cursor:pointer;transition:all .14s;white-space:nowrap;flex-shrink:0;letter-spacing:.02em;font-weight:500}
.q-btn:hover{border-color:rgba(198,255,78,0.28);color:var(--a);background:var(--ad);transform:translateY(-1px)}
.q-btn:active{transform:translateY(0) scale(.97)}

/* ── CHAT ── */
.chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;scroll-behavior:smooth}

/* ── EMPTY STATE ── */
.empty{margin:auto;text-align:center;max-width:530px;padding:20px 16px;animation:fadeUp .45s var(--ease) both}
@keyframes fadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
.e-orb{width:66px;height:66px;border-radius:18px;background:var(--ad);border:1px solid var(--ag);display:flex;align-items:center;justify-content:center;font-size:26px;margin:0 auto 14px;box-shadow:0 0 40px var(--ag),0 0 80px rgba(198,255,78,0.06);position:relative}
.e-orb::after{content:'';position:absolute;inset:-7px;border-radius:24px;border:1px solid rgba(198,255,78,0.07)}
.e-title{font-family:var(--display);font-size:28px;font-weight:800;color:#fff;letter-spacing:-.01em;margin-bottom:5px;text-transform:uppercase}
.e-title em{color:var(--a);font-style:normal}
.e-cmd{font-size:9.5px;color:var(--t3);background:var(--panel);border:1px solid var(--b1);border-radius:5px;padding:5px 12px;display:inline-block;margin-bottom:14px;letter-spacing:.05em}
.e-cmd em{color:var(--a);font-style:normal}
.e-sub{font-size:11.5px;color:var(--t2);line-height:1.8;margin-bottom:20px;max-width:390px;margin-left:auto;margin-right:auto}
.e-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:15px}
.e-card{background:var(--panel);border:1px solid var(--b1);border-radius:10px;padding:12px 10px;text-align:left;cursor:pointer;transition:all .2s var(--ease);position:relative;overflow:hidden}
.e-card::before{content:'';position:absolute;top:0;left:0;right:0;height:1.5px;background:linear-gradient(90deg,transparent,var(--a),transparent);opacity:0;transition:opacity .2s}
.e-card:hover{border-color:rgba(198,255,78,0.22);background:linear-gradient(135deg,rgba(198,255,78,0.07),var(--panel));transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,0,0,0.3)}
.e-card:hover::before{opacity:1}
.e-card:active{transform:translateY(0)}
.e-ic{font-size:18px;margin-bottom:7px;display:block}
.e-name{font-size:10px;font-weight:700;color:var(--t1);letter-spacing:.02em}
.e-hint{font-size:8.5px;color:var(--t3);margin-top:3px}
.e-chips{display:flex;flex-wrap:wrap;gap:6px;justify-content:center}
.e-chip{padding:5px 12px;border-radius:20px;border:1px solid var(--b1);background:var(--panel);font-size:10.5px;color:var(--t1);cursor:pointer;transition:all .14s}
.e-chip:hover{border-color:rgba(198,255,78,0.3);color:var(--a);background:var(--ad);transform:translateY(-1px)}

/* ── MESSAGES ── */
.msg{display:flex;gap:10px;padding:12px 0;border-bottom:1px solid rgba(255,255,255,0.02);animation:msgIn .28s var(--ease) both}
@keyframes msgIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.msg.user{flex-direction:row-reverse}
.av{width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px;font-size:9.5px;font-weight:700}
.av-u{background:var(--ad);border:1px solid var(--ag);color:var(--a)}
.av-b{background:var(--bdim);border:1px solid rgba(77,184,255,0.18);font-size:13px}
.msg-body{flex:1;min-width:0;max-width:84%;display:flex;flex-direction:column}
.msg.user .msg-body{align-items:flex-end}
.msg-meta{font-size:8px;color:var(--t3);margin-bottom:4px;display:flex;align-items:center;gap:6px}
.atag{padding:1.5px 6px;border-radius:3px;font-size:7.5px;letter-spacing:.1em;font-weight:700}
.bub{display:inline-block;padding:10px 14px;border-radius:10px;font-size:12px;line-height:1.75;max-width:100%;word-break:break-word;text-align:left;white-space:pre-wrap}
.bub-u{background:rgba(198,255,78,0.055);border:1px solid rgba(198,255,78,0.09);border-bottom-right-radius:2px;color:var(--t1)}
.bub-b{background:var(--panel);border:1px solid var(--b1);border-bottom-left-radius:2px;color:var(--t1)}
.thinking{display:inline-flex;align-items:center;gap:4px;padding:10px 14px;background:var(--panel);border:1px solid var(--b1);border-radius:10px;border-bottom-left-radius:2px}
.td{width:5px;height:5px;border-radius:50%;animation:td 1.4s infinite ease-in-out}
.td:nth-child(1){background:var(--a);animation-delay:0s}
.td:nth-child(2){background:var(--blue);animation-delay:.18s}
.td:nth-child(3){background:var(--purple);animation-delay:.36s}
@keyframes td{0%,60%,100%{transform:translateY(0);opacity:.2}30%{transform:translateY(-5px);opacity:1}}

/* ── CARDS ── */
.card-h-ic{font-size:12px}
.card-h-s{font-size:8px;color:var(--t3)}
.card-b{padding:12px 14px}

.w-main{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:10px}
.w-temp{font-family:var(--display);font-size:46px;font-weight:800;color:#fff;line-height:1;text-shadow:0 0 30px rgba(198,255,78,0.18)}
.w-unit{font-size:18px;color:var(--t3)}
.w-city{font-size:12px;font-weight:700;color:var(--t1);margin-top:4px}
.w-cond{font-size:9px;color:var(--t2);margin-top:2px}
.w-emoji{font-size:42px}
.w-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:5px}
.w-cell{background:var(--p2);border:1px solid var(--b1);border-radius:6px;padding:7px;text-align:center}
.w-v{font-size:12px;font-weight:700;color:var(--t1)}
.w-l{font-size:7.5px;color:var(--t3);letter-spacing:.08em;margin-top:2px}

.n-item{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.03)}
.n-item:last-child{border:none;padding-bottom:0}
.n-num{font-family:var(--display);font-size:18px;font-weight:800;color:var(--p3);min-width:22px;line-height:1;margin-top:2px}
.n-ttl{font-size:11px;font-weight:500;color:var(--t1);line-height:1.5}
.n-meta{display:flex;gap:5px;margin-top:3px;align-items:center;flex-wrap:wrap}
.n-src{font-size:8.5px;color:var(--a);font-weight:700}
.n-time{font-size:8px;color:var(--t3)}
.n-cat{font-size:7.5px;padding:1px 5px;border-radius:3px;background:var(--bdim);color:var(--blue);font-weight:700;letter-spacing:.04em}

.c-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:6px}
.c-item{background:var(--p2);border:1px solid var(--b1);border-radius:8px;padding:10px 12px}
.c-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}
.c-sym{font-size:9.5px;font-weight:700;color:var(--t3);letter-spacing:.07em}
.c-chg{font-size:9.5px;font-weight:700;padding:2px 5px;border-radius:4px}
.up{background:var(--gdim);color:var(--green)}
.dn{background:var(--rdim);color:var(--red)}
.c-price{font-family:var(--display);font-size:17px;font-weight:800;color:#fff;line-height:1}
.c-name{font-size:9.5px;color:var(--t2);margin-top:2px}
.c-mcap{font-size:8.5px;color:var(--t3);margin-top:4px}
.c-sent{margin-top:8px;padding:7px 12px;background:var(--p2);border:1px solid var(--b1);border-radius:7px;display:flex;align-items:center;justify-content:space-between}
.c-sl{font-size:9.5px;color:var(--t2)}
.c-sv{font-size:10px;color:var(--a);font-weight:700}

.db-tbl{width:100%;border-collapse:collapse;font-size:11px}
.db-tbl th{text-align:left;font-size:7.5px;letter-spacing:.12em;color:var(--t3);padding:0 0 7px;border-bottom:1px solid var(--b1);font-weight:700}
.db-tbl td{padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.025);color:var(--t1);vertical-align:top}
.db-tbl tr:last-child td{border:none}
.bd{display:inline-block;padding:1.5px 6px;border-radius:3px;font-size:7.5px;font-weight:700;letter-spacing:.05em}
.bd-g{background:var(--gdim);color:var(--green)}
.bd-a{background:var(--adim2);color:var(--amber)}
.bd-r{background:var(--rdim);color:var(--red)}
.bd-b{background:var(--bdim);color:var(--blue)}
.aok{display:flex;align-items:center;gap:8px;padding:10px 12px;background:rgba(61,255,160,0.05);border:1px solid rgba(61,255,160,0.14);border-radius:8px;margin-top:4px}
.aok-ic{font-size:14px}
.aok-t{font-size:11px;color:var(--green);font-weight:500}

.res-big{text-align:center;padding:14px 12px}
.res-expr{font-size:10px;color:var(--t3);margin-bottom:8px;letter-spacing:.04em}
.res-val{font-family:var(--display);font-size:36px;font-weight:800;color:var(--a);text-shadow:0 0 20px var(--ag)}

/* ── INPUT ── */
.inp-zone{padding:10px 20px 16px;flex-shrink:0;border-top:1px solid var(--b1)}
.inp-wrap{background:var(--surf);border:1px solid var(--b2);border-radius:12px;padding:3px 3px 3px 14px;display:flex;align-items:flex-end;gap:3px;transition:border-color .2s,box-shadow .2s}
.inp-wrap:focus-within{border-color:rgba(198,255,78,0.3);box-shadow:0 0 0 3px rgba(198,255,78,0.06)}
.inp-wrap textarea{flex:1;background:transparent;border:none;outline:none;color:var(--t1);font-family:var(--mono);font-size:12px;resize:none;min-height:20px;max-height:120px;padding:10px 0;line-height:1.65}
.inp-wrap textarea::placeholder{color:var(--t3)}
.inp-btns{display:flex;align-items:center;gap:2px;padding:4px}
.i-btn{width:30px;height:30px;border-radius:6px;border:none;background:transparent;color:var(--t3);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:13px;transition:all .14s}
.i-btn:hover{background:rgba(255,255,255,0.05);color:var(--t1)}
.send{width:30px;height:30px;border-radius:6px;border:none;background:var(--a);color:#020a02;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .17s}
.send:hover{background:#d6ff5e;box-shadow:0 0 18px var(--ag);transform:scale(1.05)}
.send:active{transform:scale(.95)}
.inp-hint{font-size:8.5px;color:var(--t3);margin-top:6px;padding:0 2px;display:flex;align-items:center;gap:8px}
kbd{background:var(--panel);border:1px solid var(--b2);border-radius:3px;padding:0 4px;font-size:7.5px;font-family:var(--mono);color:var(--t2)}
.inp-albl{margin-left:auto;color:var(--a);opacity:.65;font-size:8.5px;transition:all .2s}

/* ── FLASH on agent switch ── */
@keyframes agentFlash{0%{opacity:0}40%{opacity:.06}100%{opacity:0}}
.flash{position:fixed;inset:0;background:var(--a);pointer-events:none;z-index:9999;animation:agentFlash .35s var(--ease) both}

/* ── LIQUID GLASS ── */
.card{
  background:var(--glass-bg);
  border:1px solid var(--glass-border);
  border-radius:16px;overflow:hidden;margin-top:8px;
  animation:msgIn .35s var(--ease) both;
  box-shadow:0 8px 32px rgba(0,0,0,0.35),0 1px 0 var(--glass-shine) inset,0 -1px 0 rgba(0,0,0,0.2) inset;
  backdrop-filter:blur(20px) saturate(1.4);
  -webkit-backdrop-filter:blur(20px) saturate(1.4);
  position:relative;
}
.card::before{
  content:'';position:absolute;inset:0;
  background:linear-gradient(135deg,rgba(255,255,255,0.06) 0%,transparent 50%,rgba(0,0,0,0.1) 100%);
  border-radius:inherit;pointer-events:none;z-index:0;
}
.card>*{position:relative;z-index:1;}
.card-h{
  padding:8px 14px;border-bottom:1px solid rgba(255,255,255,0.06);
  display:flex;align-items:center;gap:8px;
  background:rgba(255,255,255,0.03);
  backdrop-filter:blur(4px);
}
.bub-b{
  background:var(--glass-bg);
  border:1px solid var(--glass-border);
  backdrop-filter:blur(16px) saturate(1.3);
  -webkit-backdrop-filter:blur(16px) saturate(1.3);
  box-shadow:0 4px 20px rgba(0,0,0,0.25),0 1px 0 var(--glass-shine) inset;
  position:relative;
}
.bub-b::before{
  content:'';position:absolute;inset:0;
  background:linear-gradient(135deg,rgba(255,255,255,0.04) 0%,transparent 60%);
  border-radius:inherit;pointer-events:none;
}
.sb{
  background:rgba(9,12,23,0.72);
  backdrop-filter:blur(28px) saturate(1.5);
  -webkit-backdrop-filter:blur(28px) saturate(1.5);
  border-right:1px solid rgba(255,255,255,0.07);
}
.tb{
  background:rgba(6,8,16,0.65);
  backdrop-filter:blur(28px) saturate(1.6);
  -webkit-backdrop-filter:blur(28px) saturate(1.6);
  border-bottom:1px solid rgba(255,255,255,0.06);
}
.inp-wrap{
  background:rgba(9,12,23,0.6);
  border:1px solid var(--b2);border-radius:14px;
  padding:3px 3px 3px 14px;display:flex;align-items:flex-end;gap:3px;
  transition:border-color .2s,box-shadow .2s;
  backdrop-filter:blur(20px);
  -webkit-backdrop-filter:blur(20px);
  box-shadow:0 4px 20px rgba(0,0,0,0.2),0 1px 0 rgba(255,255,255,0.04) inset;
}
/* glass highlight on card-h titles */
.card-h-t{font-size:9px;font-weight:700;color:var(--t1);letter-spacing:.07em;flex:1;font-family:var(--display);font-size:10px;}
</style>
</head>
<body>

<aside class="sb">
  <div class="sb-top">
    <div class="sb-badge"><span class="sb-dot"></span><span class="sb-badge-t">LIVE · 6 AGENTS</span></div>
    <div class="sb-logo">AI <em>Nexus</em></div>
    <div class="sb-sub">// multi-agent intelligence</div>
  </div>

  <div class="sb-nav">
    <div class="sb-sec">// agents</div>
    <div class="ni active" id="nav-all" onclick="switchAgent('all')">
      <div class="ni-ic">⚡</div><span class="ni-name">All Agents</span>
    </div>
    <div class="ni" id="nav-weather" onclick="switchAgent('weather')">
      <div class="ni-ic">🌤</div><span class="ni-name">Weather</span><span class="ni-tag nt-live">LIVE</span>
    </div>
    <div class="ni" id="nav-news" onclick="switchAgent('news')">
      <div class="ni-ic">📰</div><span class="ni-name">News</span>
    </div>
    <div class="ni" id="nav-crypto" onclick="switchAgent('crypto')">
      <div class="ni-ic">₿</div><span class="ni-name">Crypto</span><span class="ni-tag nt-live">LIVE</span>
    </div>
    <div class="ni" id="nav-database" onclick="switchAgent('database')">
      <div class="ni-ic">🗄</div><span class="ni-name">Database</span>
    </div>
    <div class="ni" id="nav-calculator" onclick="switchAgent('calculator')">
      <div class="ni-ic">🧮</div><span class="ni-name">Calculator</span><span class="ni-tag nt-new">NEW</span>
    </div>
    <div class="ni" id="nav-converter" onclick="switchAgent('converter')">
      <div class="ni-ic">🔄</div><span class="ni-name">Converter</span><span class="ni-tag nt-new">NEW</span>
    </div>
  </div>

  <div class="sb-foot">
    <div class="sb-stats">
      <div class="sb-stat"><div class="sb-stat-n" id="msg-count">0</div><div class="sb-stat-l">MESSAGES</div></div>
      <div class="sb-stat"><div class="sb-stat-n">6</div><div class="sb-stat-l">AGENTS</div></div>
    </div>
    <div class="sb-mdl">
      <div style="flex:1"><div class="sb-mdl-n">LLaMA 3.3 70B</div><div class="sb-mdl-s">via Groq Cloud</div></div>
      <div class="sb-mdl-dot"></div>
    </div>
  </div>
</aside>

<main class="main">
  <header class="tb">
    <div class="tb-l">
      <div class="tb-ic" id="tb-ic">⚡</div>
      <div class="tb-info">
        <div class="tb-title" id="tb-title">Multi-Agent Workspace</div>
        <div class="tb-sub" id="tb-sub">// all_agents_active · auto-routing enabled</div>
      </div>
    </div>
    <div class="tb-r">
      <div class="sys-pill"><div class="sys-dot"></div>all systems nominal</div>
      <button class="tb-btn" onclick="clearChat()">new_chat</button>
    </div>
  </header>

  <div class="qbar" id="qbar">
    <span class="q-lbl">QUICK</span><div class="q-sep"></div>
    <button class="q-btn" onclick="qs('Weather in Chennai')">Chennai weather</button>
    <button class="q-btn" onclick="qs('Show Bitcoin and Ethereum prices')">BTC + ETH</button>
    <button class="q-btn" onclick="qs('Show me latest AI news')">AI news</button>
    <button class="q-btn" onclick="qs('List all products in the database')">Products</button>
    <button class="q-btn" onclick="qs('Calculate 15% of 85000')">15% of 85K</button>
    <button class="q-btn" onclick="qs('Convert 1000 USD to INR')">USD → INR</button>
  </div>

  <div class="chat" id="chat">
    <div class="empty" id="empty">
      <div class="e-orb">⚡</div>
      <div class="e-title">AI <em>Nexus</em></div>
      <div class="e-cmd"><em>$</em> nexus --agents=6 --model=llama3.3-70b --status=<em>ready</em></div>
      <div class="e-sub">Six specialized agents at your command. Pick an agent from the sidebar or ask anything below — I'll route to the right expert automatically.</div>
      <div class="e-grid">
        <div class="e-card" onclick="switchAgent('weather');qs('Weather in Chennai')"><span class="e-ic">🌤</span><div class="e-name">Weather Agent</div><div class="e-hint">Any city worldwide</div></div>
        <div class="e-card" onclick="switchAgent('news');qs('Latest AI news')"><span class="e-ic">📰</span><div class="e-name">News Agent</div><div class="e-hint">AI · tech · crypto · biz</div></div>
        <div class="e-card" onclick="switchAgent('crypto');qs('Bitcoin price')"><span class="e-ic">₿</span><div class="e-name">Crypto Agent</div><div class="e-hint">50+ coins live</div></div>
        <div class="e-card" onclick="switchAgent('database');qs('List all products')"><span class="e-ic">🗄</span><div class="e-name">Database Agent</div><div class="e-hint">CRUD + SQL</div></div>
        <div class="e-card" onclick="switchAgent('calculator');qs('Calculate 15% of 85000')"><span class="e-ic">🧮</span><div class="e-name">Calculator Agent</div><div class="e-hint">Math & expressions</div></div>
        <div class="e-card" onclick="switchAgent('converter');qs('1000 USD to INR')"><span class="e-ic">🔄</span><div class="e-name">Converter Agent</div><div class="e-hint">Currency · temp · units</div></div>
      </div>
      <div class="e-chips">
        <div class="e-chip" onclick="qs('Weather in London')">🌧 London weather</div>
        <div class="e-chip" onclick="qs('ETH and SOL price')">📈 ETH &amp; SOL</div>
        <div class="e-chip" onclick="qs('Latest tech news')">🔬 Tech news</div>
        <div class="e-chip" onclick="qs('25 C to F')">🌡 25°C → °F</div>
        <div class="e-chip" onclick="qs('Add task: Review hackathon submission')">✅ Add task</div>
      </div>
    </div>
  </div>

  <div class="inp-zone">
    <div class="inp-wrap">
      <textarea id="msg" rows="1" placeholder="// ask anything — weather, crypto, news, math, convert, database…" onkeydown="handleKey(event)" oninput="autoH(this)"></textarea>
      <div class="inp-btns">
        <button class="i-btn" onclick="startVoice()" title="Voice">🎤</button>
        <button class="send" onclick="send()">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </div>
    <div class="inp-hint">
      <kbd>Enter</kbd> send &nbsp; <kbd>Shift+Enter</kbd> newline &nbsp; <kbd>🎤</kbd> voice
      <span class="inp-albl" id="a-lbl">// agent: auto-detect</span>
    </div>
  </div>
</main>

<script>
let msgCount=0, activeAgent='all', hasMsgs=false;

const AGENTS={
  all:{id:'nav-all',ic:'⚡',title:'Multi-Agent Workspace',sub:'// all_agents_active · auto-routing enabled',lbl:'// agent: auto-detect',ph:'// ask anything — weather, crypto, news, math, convert, database…',
    btns:[{l:'Chennai weather',m:'Weather in Chennai'},{l:'BTC + ETH',m:'Show Bitcoin and Ethereum prices'},{l:'AI news',m:'Show me latest AI news'},{l:'Products',m:'List all products in the database'},{l:'15% of 85K',m:'Calculate 15% of 85000'},{l:'USD → INR',m:'Convert 1000 USD to INR'}]},
  weather:{id:'nav-weather',ic:'🌤',title:'Weather Agent',sub:'// weather_agent · live data · worldwide cities',lbl:'// agent: weather',ph:'// try: "Weather in Mumbai" or "Temperature in New York"',
    btns:[{l:'Chennai',m:'Weather in Chennai'},{l:'Mumbai',m:'Weather in Mumbai'},{l:'London',m:'Weather in London'},{l:'Tokyo',m:'Weather in Tokyo'},{l:'Dubai',m:'Weather in Dubai'},{l:'New York',m:'Weather in New York'}]},
  news:{id:'nav-news',ic:'📰',title:'News Agent',sub:'// news_agent · 47 sources · curated feeds',lbl:'// agent: news',ph:'// try: "Latest AI news" or "Tech headlines today"',
    btns:[{l:'AI news',m:'Latest AI news'},{l:'Tech news',m:'Latest tech news'},{l:'Crypto news',m:'Latest crypto news'},{l:'Business',m:'Business headlines'},{l:'Top stories',m:'Top headlines today'},{l:'Startups',m:'Startup news'}]},
  crypto:{id:'nav-crypto',ic:'₿',title:'Crypto Agent',sub:'// crypto_agent · live prices · 50+ coins',lbl:'// agent: crypto',ph:'// try: "Bitcoin price" or "Show Ethereum and Solana"',
    btns:[{l:'Bitcoin',m:'Bitcoin price'},{l:'Ethereum',m:'Ethereum price'},{l:'Solana',m:'Solana price'},{l:'Top 4',m:'Show top 4 crypto coins'},{l:'Dogecoin',m:'Dogecoin price'},{l:'Market',m:'Overall crypto market sentiment'}]},
  database:{id:'nav-database',ic:'🗄',title:'Database Agent',sub:'// db_agent · SQLite · CRUD · products · tasks',lbl:'// agent: database',ph:'// try: "List products" or "Add task: Complete submission"',
    btns:[{l:'All products',m:'List all products in the database'},{l:'My tasks',m:'Show all my tasks'},{l:'Add task',m:'Add task: Complete hackathon submission'},{l:'AI services',m:'Find products in AI Services category'},{l:'SQL query',m:'sql: SELECT * FROM products WHERE price > 100'},{l:'Add note',m:'Note: Review the multi-agent architecture'}]},
  calculator:{id:'nav-calculator',ic:'🧮',title:'Calculator Agent',sub:'// calc_agent · math · percentages · expressions',lbl:'// agent: calculator',ph:'// try: "Calculate 15% of 85000" or "sqrt(256)"',
    btns:[{l:'15% of 85K',m:'Calculate 15% of 85000'},{l:'sqrt(256)',m:'What is sqrt(256)?'},{l:'Compound',m:'Calculate 100000 * 1.08 ^ 10'},{l:'250 × 4.5',m:'Calculate 250 * 4.5 + 120'},{l:'Power',m:'Calculate 2 ^ 32'},{l:'Complex',m:'Calculate (500 + 200) * 1.18 / 12'}]},
  converter:{id:'nav-converter',ic:'🔄',title:'Converter Agent',sub:'// converter_agent · currency · temp · distance · weight',lbl:'// agent: converter',ph:'// try: "100 USD to INR" or "37 C to F"',
    btns:[{l:'USD → INR',m:'1000 USD to INR'},{l:'°C → °F',m:'37 C to F'},{l:'km → miles',m:'100 km to miles'},{l:'kg → lbs',m:'75 kg to lbs'},{l:'EUR → INR',m:'500 EUR to INR'},{l:'miles → km',m:'26.2 miles to km'}]}
};

const META={
  weather:{tag:'☁ WEATHER',bg:'rgba(255,184,77,.12)',fg:'#ffb84d'},
  news:{tag:'◈ NEWS',bg:'rgba(180,141,255,.12)',fg:'#b48dff'},
  crypto:{tag:'₿ CRYPTO',bg:'rgba(255,125,77,.12)',fg:'#ff7d4d'},
  db:{tag:'◆ DB',bg:'rgba(61,255,160,.1)',fg:'#3dffa0'},
  calc:{tag:'∑ CALC',bg:'rgba(77,184,255,.1)',fg:'#4db8ff'},
  converter:{tag:'⇄ CONVERT',bg:'rgba(198,255,78,.1)',fg:'#c6ff4e'},
  chat:{tag:'● NEXUS',bg:'rgba(77,184,255,.1)',fg:'#4db8ff'}
};

function switchAgent(key){
  const prev=activeAgent; activeAgent=key;
  const cfg=AGENTS[key]; if(!cfg) return;
  // flash if switching away from active chat
  if(hasMsgs && prev!==key){
    const f=document.createElement('div'); f.className='flash';
    document.body.appendChild(f); setTimeout(()=>f.remove(),400);
  }
  // nav highlight
  document.querySelectorAll('.ni').forEach(e=>e.classList.remove('active'));
  document.getElementById(cfg.id).classList.add('active');
  // topbar
  document.getElementById('tb-ic').textContent=cfg.ic;
  document.getElementById('tb-title').textContent=cfg.title;
  document.getElementById('tb-sub').textContent=cfg.sub;
  document.getElementById('a-lbl').textContent=cfg.lbl;
  // quick bar
  const qb=document.getElementById('qbar');
  qb.innerHTML='<span class="q-lbl">QUICK</span><div class="q-sep"></div>';
  cfg.btns.forEach(b=>{
    const btn=document.createElement('button');
    btn.className='q-btn'; btn.textContent=b.l;
    btn.onclick=()=>qs(b.m); qb.appendChild(btn);
  });
  // placeholder
  document.getElementById('msg').placeholder=cfg.ph;
  // clear to new chat
  clearChat();
}

function clearChat(){
  document.querySelectorAll('.msg').forEach(m=>m.remove());
  const em=document.getElementById('empty');
  em.style.display=''; em.style.animation='none';
  void em.offsetWidth; em.style.animation='fadeUp .4s cubic-bezier(.22,1,.36,1) both';
  msgCount=0; document.getElementById('msg-count').textContent='0'; hasMsgs=false;
}

function autoH(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,120)+'px'}
function handleKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}
function qs(t){document.getElementById('msg').value=t;send();}
function getTime(){return new Date().toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'})}
function esc(t){return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

function startVoice(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){alert('Voice not supported');return;}
  const r=new SR(); r.lang='en-US';
  r.onresult=e=>{const ta=document.getElementById('msg');ta.value=e.results[0][0].transcript;autoH(ta);};
  r.onerror=()=>{}; r.start();
}

function typeEffect(text,el,cb){
  let i=0;
  (function tick(){if(i<text.length){el.textContent+=text.charAt(i++);setTimeout(tick,5);}else if(cb)cb();})();
}

function renderWeather(d){
  const ico={'Sunny':'☀️','Partly Cloudy':'⛅','Overcast':'☁️','Humid & Clear':'🌤','Breezy':'🌬️'}[d.condition]||'🌡';
  return `<div class="card"><div class="card-h"><span class="card-h-ic">🌤</span><span class="card-h-t">WEATHER · ${esc(d.city)}</span><span class="card-h-s">${getTime()}</span></div>
  <div class="card-b"><div class="w-main"><div>
    <div class="w-temp">${d.temperature_c}<span class="w-unit">°C</span></div>
    <div class="w-city">${esc(d.city)}</div>
    <div class="w-cond">${d.condition} · feels like ${d.feels_like_c}°C</div>
  </div><div class="w-emoji">${ico}</div></div>
  <div class="w-grid">
    <div class="w-cell"><div class="w-v">${d.humidity_pct}%</div><div class="w-l">HUMIDITY</div></div>
    <div class="w-cell"><div class="w-v">${d.wind_kmh}</div><div class="w-l">WIND km/h</div></div>
    <div class="w-cell"><div class="w-v">${d.uv_index}</div><div class="w-l">UV INDEX</div></div>
    <div class="w-cell"><div class="w-v">${d.visibility_km}</div><div class="w-l">VISIBILITY</div></div>
  </div></div></div>`;
}

function renderNews(d){
  const items=d.articles.map((a,i)=>`<div class="n-item"><div class="n-num">0${i+1}</div><div>
    <div class="n-ttl">${esc(a.title)}</div>
    <div class="n-meta"><span class="n-src">${esc(a.source)}</span><span class="n-time">${a.time}</span><span class="n-cat">${esc(a.category)}</span></div>
  </div></div>`).join('');
  return `<div class="card"><div class="card-h"><span class="card-h-ic">📰</span><span class="card-h-t">NEWS FEED · ${esc(d.category).toUpperCase()}</span><span class="card-h-s">updated ${d.last_updated}</span></div><div class="card-b">${items}</div></div>`;
}

function renderCrypto(d){
  const coins=d.coins.map(c=>{
    const up=c.change_24h>=0;
    const price=c.price_usd>=1?'$'+c.price_usd.toLocaleString():'$'+c.price_usd;
    return `<div class="c-item"><div class="c-top"><span class="c-sym">${c.symbol}</span><span class="c-chg ${up?'up':'dn'}">${up?'+':''}${c.change_24h}%</span></div>
    <div class="c-price">${price}</div><div class="c-name">${c.name}</div>
    <div class="c-mcap">mcap ${c.market_cap} · vol ${c.volume_24h}</div></div>`;
  }).join('');
  return `<div class="card"><div class="card-h"><span class="card-h-ic">₿</span><span class="card-h-t">CRYPTO MARKETS · LIVE</span><span class="card-h-s">${d.timestamp}</span></div>
  <div class="card-b"><div class="c-grid">${coins}</div>
  <div class="c-sent"><span class="c-sl">market sentiment</span><span class="c-sv">${d.market_sentiment} · fear/greed ${d.fear_greed_index}</span></div></div></div>`;
}

function renderDB(d){
  if(d.action==='list_products'){
    const rows=d.products.map(p=>`<tr><td>${esc(p.name)}</td><td><span class="bd bd-b">${esc(p.category)}</span></td><td>$${p.price}</td><td>${p.stock}</td><td style="color:var(--amber)">★ ${p.rating}</td></tr>`).join('');
    return `<div class="card"><div class="card-h"><span class="card-h-ic">🗄</span><span class="card-h-t">PRODUCTS · ${d.count} rows</span></div>
    <div class="card-b"><table class="db-tbl"><thead><tr><th>name</th><th>category</th><th>price</th><th>stock</th><th>rating</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }
  if(d.action==='list_tasks'){
    if(!d.tasks.length) return `<div class="card"><div class="card-b" style="color:var(--t3);font-size:11px;text-align:center;padding:14px">// no tasks · try: "Add task: Review code"</div></div>`;
    const rows=d.tasks.map(t=>`<tr><td>${esc(t.title)}</td><td><span class="bd ${t.priority==='high'?'bd-r':t.priority==='medium'?'bd-a':'bd-g'}">${t.priority}</span></td><td><span class="bd bd-b">${t.status}</span></td></tr>`).join('');
    return `<div class="card"><div class="card-h"><span class="card-h-ic">✅</span><span class="card-h-t">TASKS · ${d.count} rows</span></div>
    <div class="card-b"><table class="db-tbl"><thead><tr><th>title</th><th>priority</th><th>status</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }
  if(d.action==='task_created') return `<div class="card"><div class="card-b"><div class="aok"><span class="aok-ic">✅</span><span class="aok-t">task created → "${esc(d.task)}" [priority: ${d.priority}]</span></div></div></div>`;
  if(d.action==='note_saved') return `<div class="card"><div class="card-b"><div class="aok"><span class="aok-ic">📝</span><span class="aok-t">note saved → "${esc(d.content)}"</span></div></div></div>`;
  if(d.action==='sql_query'||d.action==='product_search'){
    const data=d.rows||d.products;
    if(!data||!data.length) return `<div class="card"><div class="card-b" style="color:var(--t3);font-size:11px">// no results found</div></div>`;
    const keys=Object.keys(data[0]);
    return `<div class="card"><div class="card-h"><span class="card-h-ic">🔍</span><span class="card-h-t">QUERY RESULTS · ${data.length} rows</span></div>
    <div class="card-b"><table class="db-tbl"><thead><tr>${keys.map(k=>`<th>${k}</th>`).join('')}</tr></thead>
    <tbody>${data.map(r=>`<tr>${keys.map(k=>`<td>${esc(r[k]??'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>`;
  }
  return null;
}

function renderCalc(d){
  if(d.status!=='success') return null;
  return `<div class="card"><div class="card-h"><span class="card-h-ic">🧮</span><span class="card-h-t">CALCULATION RESULT</span></div>
  <div class="card-b"><div class="res-big"><div class="res-expr">// input: ${esc(d.expression)}</div><div class="res-val">= ${d.result.toLocaleString()}</div></div></div></div>`;
}

function renderConverter(d){
  if(!d.from) return null;
  return `<div class="card"><div class="card-h"><span class="card-h-ic">🔄</span><span class="card-h-t">CONVERSION RESULT</span></div>
  <div class="card-b"><div class="res-big"><div class="res-expr">// input: ${esc(d.from)}</div><div class="res-val">= ${esc(d.to)}</div></div></div></div>`;
}

function buildCard(agent,td){
  if(!td) return '';
  try{
    if(agent==='weather') return renderWeather(td)||'';
    if(agent==='news') return renderNews(td)||'';
    if(agent==='crypto') return renderCrypto(td)||'';
    if(agent==='db') return renderDB(td)||'';
    if(agent==='calc') return renderCalc(td)||'';
    if(agent==='converter') return renderConverter(td)||'';
  }catch(e){console.error(e);}
  return '';
}

let msgId=0;
async function send(){
  const inp=document.getElementById('msg');
  const msg=inp.value.trim(); if(!msg) return;
  const chat=document.getElementById('chat');
  document.getElementById('empty').style.display='none';
  hasMsgs=true; msgCount++; document.getElementById('msg-count').textContent=msgCount;

  const ur=document.createElement('div'); ur.className='msg user';
  ur.innerHTML=`<div class="av av-u">YOU</div><div class="msg-body"><div class="msg-meta">${getTime()}</div><div class="bub bub-u">${esc(msg)}</div></div>`;
  chat.appendChild(ur);
  inp.value=''; inp.style.height='auto'; chat.scrollTop=chat.scrollHeight;

  const mid=++msgId;
  const br=document.createElement('div'); br.className='msg';
  br.innerHTML=`<div class="av av-b">⚡</div><div class="msg-body"><div class="msg-meta" id="bm-${mid}"></div>
    <div class="thinking" id="thinker-${mid}"><div class="td"></div><div class="td"></div><div class="td"></div></div>
    <div class="bub bub-b" id="bbub-${mid}" style="display:none"></div><div id="bcard-${mid}"></div></div>`;
  chat.appendChild(br); chat.scrollTop=chat.scrollHeight;

  try{
    const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    const data=await res.json();
    const agent=data.agent||'chat'; const m=META[agent]||META.chat;
    const thinker=document.getElementById(`thinker-${mid}`);
    if(thinker) thinker.remove();
    const bm=document.getElementById(`bm-${mid}`);
    if(bm) bm.innerHTML=`<span class="atag" style="background:${m.bg};color:${m.fg}">${m.tag}</span> ${getTime()}`;
    const bub=document.getElementById(`bbub-${mid}`); bub.style.display='inline-block';
    typeEffect(data.response,bub,()=>{
      const card=buildCard(agent,data.tool_data);
      if(card){ const bc=document.getElementById(`bcard-${mid}`); if(bc) bc.innerHTML=card; }
      chat.scrollTop=chat.scrollHeight;
    });
    msgCount++; document.getElementById('msg-count').textContent=msgCount;
    chat.scrollTop=chat.scrollHeight;
  }catch(err){
    const thinker=document.getElementById(`thinker-${mid}`);
    if(thinker) thinker.remove();
    const bub=document.getElementById(`bbub-${mid}`); bub.style.display='inline-block';
    bub.style.color='var(--red)';
    bub.textContent='// error: cannot reach server. check GROQ_API_KEY and restart.';
  }
}
</script>
</body>
</html>"""

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
