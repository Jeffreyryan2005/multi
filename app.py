import os, sqlite3, random, re, json, datetime, urllib.request, xml.etree.ElementTree as ET
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

# ── WMO weather code → condition/emoji ──
WMO_CODES = {
    0:"Clear Sky",1:"Mainly Clear",2:"Partly Cloudy",3:"Overcast",
    45:"Foggy",48:"Icy Fog",51:"Light Drizzle",53:"Drizzle",55:"Heavy Drizzle",
    61:"Light Rain",63:"Rain",65:"Heavy Rain",
    71:"Light Snow",73:"Snow",75:"Heavy Snow",
    80:"Rain Showers",81:"Heavy Showers",82:"Violent Showers",
    95:"Thunderstorm",96:"Thunderstorm + Hail",99:"Heavy Thunderstorm"
}
WMO_EMOJI = {
    0:"☀️",1:"🌤",2:"⛅",3:"☁️",45:"🌫",48:"🌫",
    51:"🌦",53:"🌧",55:"🌧",61:"🌦",63:"🌧",65:"🌧",
    71:"🌨",73:"❄️",75:"❄️",80:"🌧",81:"🌧",82:"🌧",
    95:"⛈",96:"⛈",99:"⛈"
}

WEATHER_PROFILES = {
    "chennai":{"base":32,"humidity":78,"wind":14},
    "mumbai":{"base":30,"humidity":82,"wind":18},
    "delhi":{"base":28,"humidity":55,"wind":12},
    "bangalore":{"base":24,"humidity":65,"wind":10},
    "bengaluru":{"base":24,"humidity":65,"wind":10},
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

    # ── Try Open-Meteo real-time API ──
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.request.quote(city)}&count=1&language=en&format=json"
        headers = {"User-Agent": "AI-Nexus/1.0"}
        geo_req = urllib.request.Request(geo_url, headers=headers)
        geo_data = json.loads(urllib.request.urlopen(geo_req, timeout=5).read())
        results = geo_data.get("results", [])
        if results:
            lat = results[0]["latitude"]
            lon = results[0]["longitude"]
            display_city = results[0].get("name", city)
            country = results[0].get("country", "")
            wx_url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                      f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
                      f"wind_speed_10m,weather_code,uv_index,visibility"
                      f"&daily=sunrise,sunset&timezone=auto&forecast_days=1")
            wx_req = urllib.request.Request(wx_url, headers=headers)
            wx_data = json.loads(urllib.request.urlopen(wx_req, timeout=5).read())
            cur = wx_data["current"]
            code = int(cur.get("weather_code", 0))
            condition = WMO_CODES.get(code, "Clear Sky")
            emoji = WMO_EMOJI.get(code, "🌡")
            sunrise = wx_data.get("daily", {}).get("sunrise", ["06:12"])[0][-5:]
            sunset  = wx_data.get("daily", {}).get("sunset",  ["18:48"])[0][-5:]
            return {
                "agent":"Weather Agent",
                "city": f"{display_city}, {country}" if country else display_city,
                "temperature_c": round(cur["temperature_2m"]),
                "feels_like_c": round(cur["apparent_temperature"]),
                "condition": condition,
                "emoji": emoji,
                "humidity_pct": int(cur["relative_humidity_2m"]),
                "wind_kmh": round(cur["wind_speed_10m"]),
                "uv_index": round(cur.get("uv_index", 3)),
                "visibility_km": round(cur.get("visibility", 10000) / 1000),
                "sunrise": sunrise,
                "sunset": sunset,
                "live": True,
                "source": "Open-Meteo"
            }
    except Exception:
        pass

    # ── Fallback to static profiles ──
    profile = WEATHER_PROFILES.get(city.lower())
    if profile:
        temp=profile["base"]+random.randint(-2,3); humidity=profile["humidity"]+random.randint(-5,5); wind=profile["wind"]+random.randint(-3,3)
    else:
        temp=random.randint(18,38); humidity=random.randint(45,85); wind=random.randint(8,25)
    condition=random.choice(CONDITIONS)
    return {"agent":"Weather Agent","city":city,"temperature_c":temp,"feels_like_c":temp-random.randint(1,3),"condition":condition,"emoji":"🌡","humidity_pct":humidity,"wind_kmh":wind,"uv_index":random.randint(1,11),"visibility_km":random.randint(5,20),"sunrise":"06:12","sunset":"18:48","live":False,"source":"estimated"}

# ── RSS feeds for live news ──
RSS_FEEDS = {
    "ai":    [("TechCrunch AI",   "https://techcrunch.com/category/artificial-intelligence/feed/"),
              ("MIT Tech Review", "https://www.technologyreview.com/feed/")],
    "tech":  [("The Verge",       "https://www.theverge.com/rss/index.xml"),
              ("Ars Technica",    "https://feeds.arstechnica.com/arstechnica/technology-lab")],
    "crypto":[("CoinDesk",        "https://www.coindesk.com/arc/outboundfeeds/rss/"),
              ("Decrypt",         "https://decrypt.co/feed")],
    "business":[("Reuters Biz",   "https://feeds.reuters.com/reuters/businessNews"),
                ("BBC Business",  "http://feeds.bbci.co.uk/news/business/rss.xml")],
    "world": [("BBC World",       "http://feeds.bbci.co.uk/news/world/rss.xml"),
              ("Reuters World",   "https://feeds.reuters.com/Reuters/worldNews")],
    "general":[("BBC Top Stories","http://feeds.bbci.co.uk/news/rss.xml"),
               ("Reuters Top",    "https://feeds.reuters.com/reuters/topNews")],
    "sports":[("BBC Sport",       "http://feeds.bbci.co.uk/sport/rss.xml"),
              ("ESPN",            "https://www.espn.com/espn/rss/news")],
    "science":[("NASA",           "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
               ("ScienceDaily",   "https://www.sciencedaily.com/rss/top/science.xml")],
    "india": [("Times of India",  "https://timesofindia.indiatimes.com/rssfeeds/1221656.cms"),
              ("NDTV India",      "https://feeds.feedburner.com/ndtvnews-top-stories")],
}

FALLBACK_NEWS = {
    "ai":     [{"title":"OpenAI releases GPT-5 with advanced reasoning capabilities","source":"TechCrunch","time":"2h ago","category":"AI"},
               {"title":"Google DeepMind achieves breakthrough in protein folding accuracy","source":"Nature","time":"4h ago","category":"AI Research"},
               {"title":"Anthropic Claude scores highest on MMLU benchmark","source":"Bloomberg","time":"6h ago","category":"AI Business"},
               {"title":"Meta Llama 4 open-sourced with 400B parameters","source":"Reuters","time":"8h ago","category":"Open Source"}],
    "tech":   [{"title":"Apple M5 chip unveiled with 40% performance boost","source":"The Verge","time":"3h ago","category":"Hardware"},
               {"title":"NVIDIA Blackwell GPUs break AI training speed records","source":"AnandTech","time":"5h ago","category":"Hardware"},
               {"title":"GitHub Copilot now handles full code review lifecycle","source":"GitHub Blog","time":"7h ago","category":"DevTools"},
               {"title":"Microsoft Azure reaches $100B annual revenue milestone","source":"WSJ","time":"9h ago","category":"Cloud"}],
    "crypto": [{"title":"Bitcoin surges past $90K on institutional demand","source":"CoinDesk","time":"1h ago","category":"Markets"},
               {"title":"Ethereum ETF sees record $2B inflows this week","source":"Decrypt","time":"3h ago","category":"ETH"},
               {"title":"Solana processes 100K TPS in stress test","source":"CoinTelegraph","time":"5h ago","category":"Blockchain"},
               {"title":"SEC approves spot crypto ETFs for major exchanges","source":"Reuters","time":"7h ago","category":"Regulation"}],
    "general":[{"title":"AI models now pass bar exam and medical licensing consistently","source":"WSJ","time":"2h ago","category":"AI"},
               {"title":"Renewable energy surpasses fossil fuels in G7 nations","source":"Guardian","time":"5h ago","category":"Climate"},
               {"title":"India GDP grows at 8.2%, fastest major economy","source":"Mint","time":"8h ago","category":"Economy"},
               {"title":"Tech sector adds 500K jobs globally in Q1 2025","source":"FT","time":"10h ago","category":"Jobs"}],
}

def _fetch_rss(url, source_name, category, limit=4):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AINewsBot/1.0)"}
    req = urllib.request.Request(url, headers=headers)
    xml_data = urllib.request.urlopen(req, timeout=5).read()
    root = ET.fromstring(xml_data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    for item in root.findall(".//item")[:limit]:
        title_el = item.find("title")
        pub_el   = item.find("pubDate")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        if not title: continue
        time_str = "recently"
        if pub_el is not None and pub_el.text:
            try:
                from email.utils import parsedate_to_datetime
                pub_dt = parsedate_to_datetime(pub_el.text)
                diff = datetime.datetime.now(datetime.timezone.utc) - pub_dt
                h = int(diff.total_seconds() // 3600)
                time_str = f"{h}h ago" if h > 0 else "just now"
            except: pass
        items.append({"title": title, "source": source_name, "time": time_str, "category": category})
    if not items:
        for entry in root.findall("atom:entry", ns)[:limit]:
            title_el = entry.find("atom:title", ns)
            updated_el = entry.find("atom:updated", ns)
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            if not title: continue
            time_str = "recently"
            if updated_el is not None and updated_el.text:
                try:
                    pub_dt = datetime.datetime.fromisoformat(updated_el.text.replace("Z","+00:00"))
                    diff = datetime.datetime.now(datetime.timezone.utc) - pub_dt
                    h = int(diff.total_seconds() // 3600)
                    time_str = f"{h}h ago" if h > 0 else "just now"
                except: pass
            items.append({"title": title, "source": source_name, "time": time_str, "category": category})
    return items

def news_agent(msg):
    m = msg.lower()
    if any(w in m for w in ["iran","ukraine","russia","war","conflict","geopolit","world","global","international"]):
        bucket, category = "world", "World News"
    elif any(w in m for w in ["india","indian","delhi","mumbai","modi","bjp","parliament"]):
        bucket, category = "india", "India News"
    elif any(w in m for w in ["sport","cricket","football","ipl","nba","fifa","tennis","f1","formula"]):
        bucket, category = "sports", "Sports"
    elif any(w in m for w in ["science","space","nasa","research","climate","environment","health","covid"]):
        bucket, category = "science", "Science & Space"
    elif any(w in m for w in ["ai","artificial intelligence","machine learning","llm","openai","gemini","claude","gpt","chatgpt"]):
        bucket, category = "ai", "AI & Machine Learning"
    elif any(w in m for w in ["crypto","bitcoin","ethereum","blockchain","defi","nft","web3","btc","eth","solana"]):
        bucket, category = "crypto", "Crypto & Blockchain"
    elif any(w in m for w in ["business","startup","market","economy","invest","finance","stock","gdp"]):
        bucket, category = "business", "Business & Markets"
    elif any(w in m for w in ["tech","software","hardware","apple","google","microsoft","nvidia","samsung","dev"]):
        bucket, category = "tech", "Technology"
    else:
        bucket, category = "general", "Top Headlines"

    articles = []
    feeds = RSS_FEEDS.get(bucket, RSS_FEEDS["general"])
    for source_name, url in feeds:
        try:
            fetched = _fetch_rss(url, source_name, category, limit=3)
            articles.extend(fetched)
            if len(articles) >= 4:
                break
        except Exception:
            continue

    topic_words = [w for w in m.split() if len(w) > 3 and w not in
                   {"news","latest","today","show","tell","give","what","about","articles","headlines","recent","update","current","happening"}]
    if topic_words and articles:
        filtered = [a for a in articles if any(tw in a["title"].lower() for tw in topic_words)]
        if filtered:
            articles = filtered

    if not articles:
        articles = FALLBACK_NEWS.get(bucket, FALLBACK_NEWS["general"])

    return {
        "agent": "News Agent",
        "category": category,
        "articles": articles[:4],
        "total_sources": len(feeds),
        "last_updated": datetime.datetime.now().strftime("%I:%M %p"),
        "live": len(articles) > 0
    }

# ── CoinGecko real-time crypto ──
COIN_IDS = {
    "bitcoin":"bitcoin","btc":"bitcoin",
    "ethereum":"ethereum","eth":"ethereum",
    "solana":"solana","sol":"solana",
    "bnb":"binancecoin","binance":"binancecoin",
    "xrp":"ripple","ripple":"ripple",
    "cardano":"cardano","ada":"cardano",
    "dogecoin":"dogecoin","doge":"dogecoin",
    "polygon":"matic-network","matic":"matic-network",
    "avalanche":"avalanche-2","avax":"avalanche-2",
    "chainlink":"chainlink","link":"chainlink",
    "polkadot":"polkadot","dot":"polkadot",
    "litecoin":"litecoin","ltc":"litecoin",
    "shiba":"shiba-inu","shib":"shiba-inu",
    "tron":"tron","trx":"tron",
    "uniswap":"uniswap","uni":"uniswap",
}

CRYPTO_STATIC = {
    "bitcoin":{"symbol":"BTC","base":87500,"change":2.3,"mcap":"1.72T","vol":"38.2B"},
    "ethereum":{"symbol":"ETH","base":3200,"change":1.8,"mcap":"385B","vol":"18.5B"},
    "solana":{"symbol":"SOL","base":148,"change":4.1,"mcap":"70B","vol":"5.2B"},
    "binancecoin":{"symbol":"BNB","base":590,"change":0.9,"mcap":"88B","vol":"2.1B"},
    "ripple":{"symbol":"XRP","base":0.52,"change":-0.5,"mcap":"29B","vol":"1.8B"},
    "cardano":{"symbol":"ADA","base":0.44,"change":1.2,"mcap":"15B","vol":"0.9B"},
    "dogecoin":{"symbol":"DOGE","base":0.14,"change":3.8,"mcap":"20B","vol":"2.4B"},
    "matic-network":{"symbol":"MATIC","base":0.71,"change":-1.1,"mcap":"7B","vol":"0.6B"},
}

def crypto_agent(msg):
    m = msg.lower()
    # Identify requested coins
    found_ids = []
    for key, cid in COIN_IDS.items():
        if key in m and cid not in found_ids:
            found_ids.append(cid)
    if not found_ids:
        found_ids = ["bitcoin","ethereum","solana","binancecoin"]

    # ── Try CoinGecko real-time ──
    try:
        ids_str = ",".join(found_ids[:4])
        cg_url = (f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}"
                  f"&vs_currencies=usd&include_24hr_change=true"
                  f"&include_market_cap=true&include_24hr_vol=true")
        req = urllib.request.Request(cg_url, headers={"User-Agent":"AI-Nexus/1.0","Accept":"application/json"})
        cg_data = json.loads(urllib.request.urlopen(req, timeout=6).read())
        results = []
        for cid in found_ids[:4]:
            if cid not in cg_data: continue
            d = cg_data[cid]
            price = d.get("usd", 0)
            change = d.get("usd_24h_change", 0) or 0
            mcap = d.get("usd_market_cap", 0)
            vol = d.get("usd_24h_vol", 0)
            # Format large numbers
            def fmt(n):
                if n >= 1e12: return f"{n/1e12:.2f}T"
                if n >= 1e9: return f"{n/1e9:.1f}B"
                if n >= 1e6: return f"{n/1e6:.1f}M"
                return str(round(n,2))
            static = CRYPTO_STATIC.get(cid, {})
            symbol = static.get("symbol", cid[:3].upper())
            name = cid.replace("-"," ").title()
            # Map known names
            name_map = {"Bitcoin":"Bitcoin","Ethereum":"Ethereum","Solana":"Solana",
                        "Binancecoin":"BNB","Ripple":"XRP","Cardano":"Cardano",
                        "Dogecoin":"Dogecoin","Matic-network":"Polygon"}
            name = name_map.get(name, name)
            results.append({
                "name":name,"symbol":symbol,
                "price_usd":round(price,2 if price>10 else 6),
                "change_24h":round(change,2),
                "market_cap":fmt(mcap),"volume_24h":fmt(vol)
            })
        if results:
            fear_greed = random.randint(50,80)
            sentiment = "Bullish 📈" if fear_greed>60 else "Neutral ➡️"
            return {"agent":"Crypto Agent","coins":results,"market_sentiment":sentiment,
                    "fear_greed_index":fear_greed,"live":True,"source":"CoinGecko",
                    "timestamp":datetime.datetime.now().strftime("%H:%M:%S UTC")}
    except Exception:
        pass

    # ── Fallback to static ──
    results = []
    static_list = [(cid, CRYPTO_STATIC.get(cid,{})) for cid in found_ids[:4]]
    for cid, data in static_list:
        if not data: continue
        price=data["base"]*(1+random.uniform(-0.02,0.02))
        change=data["change"]+random.uniform(-0.3,0.3)
        results.append({"name":cid.replace("-"," ").title(),"symbol":data["symbol"],
                        "price_usd":round(price,2 if price>10 else 4),
                        "change_24h":round(change,2),"market_cap":data["mcap"],"volume_24h":data["vol"]})
    return {"agent":"Crypto Agent","coins":results,"market_sentiment":random.choice(["Bullish 📈","Neutral ➡️","Cautiously Bullish 📊"]),
            "fear_greed_index":random.randint(55,80),"live":False,"source":"estimated",
            "timestamp":datetime.datetime.now().strftime("%H:%M:%S UTC")}

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
    cur=re.search(r'([\d.]+)\s*(usd|inr|eur|gbp|jpy|cad|aud|aed|sgd)\s+(?:to|in)\s+(usd|inr|eur|gbp|jpy|cad|aud|aed|sgd)',m)
    if cur:
        rates={"usd":1,"inr":83.5,"eur":0.92,"gbp":0.79,"jpy":154.2,"cad":1.36,"aud":1.52,"aed":3.67,"sgd":1.35}
        val,f,t2=float(cur.group(1)),cur.group(2),cur.group(3)
        if f in rates and t2 in rates:
            return {"agent":"Converter Agent","from":f"{val} {f.upper()}","to":f"{round(val/rates[f]*rates[t2],2)} {t2.upper()}"}
    lbs=re.search(r'([\d.]+)\s*(?:lb|lbs|pounds?)\s+(?:to|in)\s+kg',m)
    if lbs: return {"agent":"Converter Agent","from":f"{lbs.group(1)} lbs","to":f"{round(float(lbs.group(1))*0.453592,3)} kg"}
    return {"agent":"Converter Agent","message":"Try: 100 km to miles, 25 C to F, 1000 USD to INR, 75 kg to lbs"}

def route_message(msg):
    m=msg.lower()
    if any(w in m for w in ["weather","temperature","temp","climate","forecast","humid","rain","sunny"]): return "weather"
    if any(w in m for w in ["news","headline","latest","happening","update","story","article","breaking"]): return "news"
    if any(w in m for w in ["bitcoin","ethereum","crypto","coin","btc","eth","sol","doge","blockchain","price of","value of","crypto market"]): return "crypto"
    if any(w in m for w in ["calculate","compute","×","÷","sqrt"]) or re.search(r'\d+\s*[\+\-\*\/\^]\s*\d+',m): return "calc"
    if any(w in m for w in ["convert","in miles","to km","to usd","to inr","to eur","to gbp","°c","°f","kg to","lbs","miles to"]): return "converter"
    if any(w in m for w in ["database","product","sql","query","task","note","record","stock","rating","add task","save note","list task"]): return "db"
    return "chat"

SYSTEM_PROMPT = """You are AI Nexus, an advanced multi-agent AI assistant with 6 specialized agents AND your own broad general knowledge. You can answer ANY question — not just agent-specific ones.

Specialized agents:
1. Weather Agent — real-time weather via Open-Meteo API for any city worldwide
2. News Agent — live RSS news across AI, tech, crypto, business, sports, science, India, world
3. Crypto Agent — real-time prices via CoinGecko for 50+ coins
4. Database Agent — product catalog, tasks, notes with full CRUD
5. Calculator Agent — math, percentages, expressions
6. Converter Agent — currency, temperature, distance, weight

CRITICAL RULES:
- When [AGENT DATA] is provided, USE IT as ground truth. Present it naturally and clearly.
- For weather: mention city, temperature, condition, humidity, wind, UV index. Note if it's real-time.
- For crypto: show price, 24h change, market cap. Note if from CoinGecko live data.
- For news: present each headline naturally with source and time.
- For database: confirm actions and show results.
- For calculator/converter: state the result directly and clearly.
- For ANY other question (history, science, coding, general knowledge, opinions, etc.) — answer fully from your own knowledge. You are a capable general-purpose assistant.
- NEVER say you cannot access real-time data when [AGENT DATA] is provided.
- NEVER refuse general knowledge questions.
- Be concise, confident, and helpful. No AI disclaimers. Use clear formatting.
- If asked about yourself: you are AI Nexus, powered by LLaMA 3.3 70B via Groq with real-time data agents.
"""

chat_memory = []

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>AI Nexus — Multi-Agent Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Syne:wght@400;500;600;700;800&family=JetBrains+Mono:wght@300;400;500;600;700&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden}

:root{
  --bg:#04060f;
  --surf:rgba(10,13,26,0.8);
  --panel:rgba(14,18,35,0.7);
  --b1:rgba(255,255,255,0.06);
  --b2:rgba(255,255,255,0.1);
  --t1:#eef2ff; --t2:#7889aa; --t3:#2d3a50;
  --a:#c8ff47; --ag:rgba(200,255,71,0.25); --ad:rgba(200,255,71,0.08);
  --blue:#3db8ff; --bdim:rgba(61,184,255,0.12);
  --green:#2dffb0; --gdim:rgba(45,255,176,0.1);
  --red:#ff4466; --rdim:rgba(255,68,102,0.1);
  --amber:#ffa830; --adim2:rgba(255,168,48,0.1);
  --purple:#a78bfa; --pdim:rgba(167,139,250,0.1);
  --mono:'JetBrains Mono',ui-monospace,monospace;
  --display:'Bebas Neue','Impact','Arial Narrow',sans-serif;
  --syne:'Syne','DM Sans',sans-serif;
  --body:'DM Sans','Segoe UI',system-ui,sans-serif;
  --ease:cubic-bezier(.22,1,.36,1);
  --r:18px;
}

body{background:var(--bg);color:var(--t1);font-family:var(--mono);font-size:12.5px;display:flex;line-height:1.6;overflow:hidden}

/* ── ANIMATED BG ── */
body::before{
  content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
  background:
    radial-gradient(ellipse 80% 50% at 20% -10%,rgba(200,255,71,0.06) 0%,transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 110%,rgba(61,184,255,0.05) 0%,transparent 60%),
    radial-gradient(ellipse 40% 40% at 60% 50%,rgba(167,139,250,0.03) 0%,transparent 70%),
    repeating-linear-gradient(0deg,transparent,transparent 39px,rgba(255,255,255,0.012) 40px),
    repeating-linear-gradient(90deg,transparent,transparent 39px,rgba(255,255,255,0.012) 40px);
}

/* ── noise grain texture ── */
body::after{
  content:'';position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.025;
  background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size:128px 128px;
}

::-webkit-scrollbar{width:3px;height:3px}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.07);border-radius:3px}

/* ══════════════════════════════════
   LIQUID GLASS SYSTEM (Magnetto-style)
══════════════════════════════════ */
.glass{
  background:rgba(10,14,30,0.42);
  backdrop-filter:blur(28px) saturate(1.8) brightness(1.06);
  -webkit-backdrop-filter:blur(28px) saturate(1.8) brightness(1.06);
  border:1px solid rgba(255,255,255,0.1);
  box-shadow:
    0 1px 0 rgba(255,255,255,0.09) inset,
    0 -1px 0 rgba(0,0,0,0.35) inset,
    0 24px 64px rgba(0,0,0,0.45),
    0 2px 12px rgba(0,0,0,0.2);
  position:relative;overflow:hidden;
}
.glass::after{
  content:'';position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(135deg,rgba(255,255,255,0.055) 0%,rgba(255,255,255,0) 45%,rgba(0,0,0,0.06) 100%);
  border-radius:inherit;
}
.glass-edge{
  position:absolute;top:0;left:15%;right:15%;height:1px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,0.18),transparent);
  pointer-events:none;z-index:1;
}

/* ══════════════════════════════════
   SIDEBAR
══════════════════════════════════ */
.sb{
  width:240px;min-width:240px;
  background:rgba(5,8,18,0.78);
  backdrop-filter:blur(40px) saturate(2);
  -webkit-backdrop-filter:blur(40px) saturate(2);
  border-right:1px solid rgba(255,255,255,0.07);
  display:flex;flex-direction:column;position:relative;z-index:20;overflow:hidden;
}
.sb::before{content:'';position:absolute;top:-80px;left:-60px;width:280px;height:280px;background:radial-gradient(circle,rgba(200,255,71,0.09) 0%,transparent 65%);pointer-events:none;z-index:0}
.sb::after{content:'';position:absolute;bottom:-60px;right:-40px;width:200px;height:200px;background:radial-gradient(circle,rgba(61,184,255,0.05) 0%,transparent 65%);pointer-events:none;z-index:0}
.sb>*{position:relative;z-index:1}

.sb-top{padding:22px 18px 16px;border-bottom:1px solid rgba(255,255,255,0.05)}
.sb-live{display:inline-flex;align-items:center;gap:5px;background:rgba(200,255,71,0.09);border:1px solid rgba(200,255,71,0.22);border-radius:20px;padding:3px 9px;margin-bottom:14px}
.sb-dot{width:5px;height:5px;border-radius:50%;background:var(--a);box-shadow:0 0 8px var(--a);animation:pulse 2s ease infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.8)}}
.sb-live-t{font-size:8px;letter-spacing:.18em;color:var(--a);font-weight:600;font-family:var(--mono)}

.sb-logo{font-family:'Syne','Bebas Neue',sans-serif;font-size:28px;font-weight:800;color:#fff;line-height:1;letter-spacing:-.01em}
.sb-logo span{color:var(--a)}
.sb-sub{font-size:9px;color:var(--t3);letter-spacing:.1em;margin-top:5px;font-family:var(--mono)}

.sb-nav{padding:14px 10px;flex:1;overflow-y:auto}
.sb-sec{font-size:8px;letter-spacing:.22em;color:var(--t3);padding:0 8px;margin:0 0 8px 0;text-transform:uppercase;font-weight:700;font-family:var(--mono)}

.ni{
  display:flex;align-items:center;gap:9px;padding:9px 10px;
  border-radius:10px;cursor:pointer;color:var(--t2);font-size:12px;font-weight:500;
  border:1px solid transparent;margin-bottom:3px;
  transition:all .18s var(--ease);position:relative;overflow:hidden;user-select:none;
  font-family:var(--body);
}
.ni::before{content:'';position:absolute;left:0;top:20%;bottom:20%;width:2px;background:var(--a);transform:scaleX(0);transform-origin:left;border-radius:2px;transition:transform .2s var(--ease)}
.ni:hover{background:rgba(255,255,255,0.04);color:var(--t1);border-color:rgba(255,255,255,0.05)}
.ni:hover::before{transform:scaleX(1)}
.ni.active{background:rgba(200,255,71,0.07);border-color:rgba(200,255,71,0.18);color:var(--a);box-shadow:0 0 20px rgba(200,255,71,0.05)}
.ni.active::before{transform:scaleX(1)}
.ni-ic{width:28px;height:28px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:13px;background:rgba(255,255,255,0.04);flex-shrink:0;transition:background .18s}
.ni.active .ni-ic{background:rgba(200,255,71,0.1)}
.ni-name{flex:1;font-weight:600;letter-spacing:-.01em}
.ni-tag{font-size:7px;padding:2px 6px;border-radius:3px;font-weight:700;letter-spacing:.08em;font-family:var(--mono)}
.nt-live{background:rgba(61,184,255,0.12);color:var(--blue)}
.nt-new{background:rgba(167,139,250,0.12);color:var(--purple)}

.sb-foot{padding:10px;border-top:1px solid rgba(255,255,255,0.05)}
.sb-stats{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:7px}
.sb-stat{
  background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);
  border-radius:10px;padding:8px 11px;
  backdrop-filter:blur(10px);
}
.sb-stat-n{font-family:'Syne',sans-serif;font-size:28px;font-weight:800;color:#fff;line-height:1}
.sb-stat-l{font-size:7px;color:var(--t3);letter-spacing:.12em;margin-top:1px;font-family:var(--mono)}
.sb-mdl{
  background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);
  border-radius:10px;padding:9px 12px;display:flex;align-items:center;gap:9px;
}
.sb-mdl-n{font-size:11.5px;font-weight:600;color:var(--t1);font-family:var(--body)}
.sb-mdl-s{font-size:8px;color:var(--t3);margin-top:1px;font-family:var(--mono)}
.sb-mdl-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 10px var(--green);animation:pulse 2.5s ease infinite}

/* ══════════════════════════════════
   MAIN
══════════════════════════════════ */
.main{flex:1;display:flex;flex-direction:column;min-width:0;background:transparent;position:relative;z-index:1}

/* TOPBAR */
.tb{
  height:54px;padding:0 24px;
  display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid rgba(255,255,255,0.06);
  background:rgba(4,6,15,0.55);
  backdrop-filter:blur(32px) saturate(1.6);
  -webkit-backdrop-filter:blur(32px) saturate(1.6);
  flex-shrink:0;position:relative;
}
.tb::after{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.08),transparent);pointer-events:none}
.tb-l{display:flex;align-items:center;gap:12px}
.tb-ic{
  width:34px;height:34px;border-radius:9px;
  display:flex;align-items:center;justify-content:center;font-size:16px;
  background:rgba(200,255,71,0.08);border:1px solid rgba(200,255,71,0.2);
  transition:all .25s var(--ease);box-shadow:0 0 16px rgba(200,255,71,0.07);
}
.tb-title{font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#fff;letter-spacing:-.01em;line-height:1;transition:all .2s}
.tb-sub{font-size:8px;color:var(--a);letter-spacing:.1em;margin-top:2px;opacity:.65;font-family:var(--mono);transition:all .2s}
.tb-r{display:flex;align-items:center;gap:8px}
.sys-pill{
  display:flex;align-items:center;gap:5px;padding:5px 12px;
  border-radius:20px;border:1px solid rgba(255,255,255,0.07);
  background:rgba(255,255,255,0.03);font-size:8px;color:var(--t2);letter-spacing:.05em;
  backdrop-filter:blur(10px);font-family:var(--mono);
}
.sys-dot{width:5px;height:5px;border-radius:50%;background:var(--green);box-shadow:0 0 7px var(--green)}
.tb-btn{
  padding:6px 14px;border-radius:8px;border:1px solid rgba(255,255,255,0.08);
  background:rgba(255,255,255,0.04);color:var(--t2);
  font-size:9px;font-family:var(--mono);cursor:pointer;
  transition:all .15s;letter-spacing:.04em;backdrop-filter:blur(10px);
}
.tb-btn:hover{border-color:rgba(255,255,255,0.14);color:var(--t1);background:rgba(255,255,255,0.07)}

/* QUICK BAR */
.qbar{
  padding:8px 24px;border-bottom:1px solid rgba(255,255,255,0.045);
  display:flex;align-items:center;gap:7px;
  background:rgba(4,6,15,0.38);backdrop-filter:blur(20px);
  flex-shrink:0;overflow-x:auto;
}
.qbar::-webkit-scrollbar{height:0}
.q-lbl{font-size:7.5px;color:var(--t3);letter-spacing:.18em;white-space:nowrap;flex-shrink:0;font-weight:700;font-family:var(--mono)}
.q-sep{width:1px;height:14px;background:rgba(255,255,255,0.06);flex-shrink:0;margin:0 2px}
.q-btn{
  padding:5px 13px;border-radius:20px;border:1px solid rgba(255,255,255,0.07);
  background:rgba(255,255,255,0.025);color:var(--t2);
  font-size:10px;font-family:var(--mono);cursor:pointer;
  transition:all .15s;white-space:nowrap;flex-shrink:0;backdrop-filter:blur(8px);
}
.q-btn:hover{border-color:rgba(200,255,71,0.3);color:var(--a);background:rgba(200,255,71,0.07);transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,0.2)}

/* CHAT */
.chat{flex:1;overflow-y:auto;padding:24px 28px;display:flex;flex-direction:column;gap:4px;scroll-behavior:smooth}

/* EMPTY STATE */
@keyframes fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
.empty{margin:auto;text-align:center;max-width:560px;padding:24px 20px;animation:fadeUp .5s var(--ease) both}
.e-orb{
  width:72px;height:72px;border-radius:20px;
  background:rgba(200,255,71,0.07);border:1px solid rgba(200,255,71,0.18);
  display:flex;align-items:center;justify-content:center;font-size:28px;
  margin:0 auto 18px;
  box-shadow:0 0 60px rgba(200,255,71,0.08),0 0 120px rgba(200,255,71,0.03);
  position:relative;
}
.e-orb::before{content:'';position:absolute;inset:-10px;border-radius:28px;border:1px solid rgba(200,255,71,0.06)}
.e-title{font-family:'Syne',sans-serif;font-size:60px;font-weight:800;color:#fff;letter-spacing:-.02em;line-height:.9;margin-bottom:4px}
.e-title span{color:var(--a)}
.e-cmd{
  font-size:9px;color:var(--t3);
  background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
  border-radius:6px;padding:5px 14px;display:inline-block;margin-bottom:16px;
  letter-spacing:.06em;font-family:var(--mono);
}
.e-cmd em{color:var(--a);font-style:normal}
.e-sub{font-size:12px;color:var(--t2);line-height:1.8;margin-bottom:24px;font-family:var(--body)}
.e-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px}
.e-card{
  background:rgba(255,255,255,0.025);
  border:1px solid rgba(255,255,255,0.07);
  border-radius:14px;padding:14px 12px;text-align:left;cursor:pointer;
  transition:all .22s var(--ease);position:relative;overflow:hidden;
  backdrop-filter:blur(12px);
}
.e-card::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--a),transparent);opacity:0;transition:opacity .2s}
.e-card:hover{border-color:rgba(200,255,71,0.22);background:rgba(200,255,71,0.05);transform:translateY(-3px);box-shadow:0 12px 32px rgba(0,0,0,0.3)}
.e-card:hover::before{opacity:1}
.e-ic{font-size:20px;margin-bottom:8px;display:block}
.e-name{font-size:10.5px;font-weight:700;color:var(--t1);font-family:var(--body)}
.e-hint{font-size:8.5px;color:var(--t3);margin-top:3px;font-family:var(--mono)}
.e-chips{display:flex;flex-wrap:wrap;gap:7px;justify-content:center}
.e-chip{
  padding:6px 14px;border-radius:20px;border:1px solid rgba(255,255,255,0.07);
  background:rgba(255,255,255,0.025);font-size:10.5px;color:var(--t1);cursor:pointer;
  transition:all .15s;font-family:var(--body);backdrop-filter:blur(8px);
}
.e-chip:hover{border-color:rgba(200,255,71,0.28);color:var(--a);background:rgba(200,255,71,0.07);transform:translateY(-1px)}

/* MESSAGES */
@keyframes msgIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg{display:flex;gap:11px;padding:10px 0;animation:msgIn .3s var(--ease) both}
.msg.user{flex-direction:row-reverse}
.av{width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px;font-size:10px;font-weight:700;font-family:var(--mono)}
.av-u{background:rgba(200,255,71,0.1);border:1px solid rgba(200,255,71,0.22);color:var(--a)}
.av-b{background:rgba(61,184,255,0.1);border:1px solid rgba(61,184,255,0.18);font-size:14px}
.msg-body{flex:1;min-width:0;max-width:82%;display:flex;flex-direction:column}
.msg.user .msg-body{align-items:flex-end}
.msg-meta{font-size:8px;color:var(--t3);margin-bottom:5px;display:flex;align-items:center;gap:7px;font-family:var(--mono)}
.atag{padding:2px 7px;border-radius:4px;font-size:7.5px;letter-spacing:.1em;font-weight:700;font-family:var(--mono)}
.bub{
  display:inline-block;padding:12px 16px;border-radius:14px;
  font-size:12.5px;line-height:1.75;max-width:100%;word-break:break-word;
  text-align:left;white-space:pre-wrap;font-family:var(--mono);
}
.bub-u{
  background:rgba(200,255,71,0.06);border:1px solid rgba(200,255,71,0.1);
  border-bottom-right-radius:4px;color:var(--t1);
}
.bub-b{
  background:rgba(10,14,28,0.5);border:1px solid rgba(255,255,255,0.08);
  border-bottom-left-radius:4px;color:var(--t1);
  backdrop-filter:blur(20px) saturate(1.4);
  box-shadow:0 8px 32px rgba(0,0,0,0.25),0 1px 0 rgba(255,255,255,0.05) inset;
  position:relative;overflow:hidden;
}
.bub-b::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.08),transparent)}
.thinking{
  display:inline-flex;align-items:center;gap:5px;padding:12px 16px;
  background:rgba(10,14,28,0.5);border:1px solid rgba(255,255,255,0.07);
  border-radius:14px;border-bottom-left-radius:4px;backdrop-filter:blur(16px);
}
.td{width:6px;height:6px;border-radius:50%;animation:td 1.4s infinite ease-in-out}
.td:nth-child(1){background:var(--a);animation-delay:0s}
.td:nth-child(2){background:var(--blue);animation-delay:.2s}
.td:nth-child(3){background:var(--purple);animation-delay:.4s}
@keyframes td{0%,60%,100%{transform:translateY(0);opacity:.2}30%{transform:translateY(-6px);opacity:1}}

/* ══════════════════════════════════
   DATA CARDS — LIQUID GLASS
══════════════════════════════════ */
.card{
  background:rgba(8,12,26,0.52);
  border:1px solid rgba(255,255,255,0.09);
  border-radius:18px;overflow:hidden;margin-top:10px;
  animation:msgIn .4s var(--ease) both;
  backdrop-filter:blur(32px) saturate(1.7);
  -webkit-backdrop-filter:blur(32px) saturate(1.7);
  box-shadow:
    0 1px 0 rgba(255,255,255,0.09) inset,
    0 -1px 0 rgba(0,0,0,0.3) inset,
    0 28px 70px rgba(0,0,0,0.45);
  position:relative;
}
.card::before{
  content:'';position:absolute;top:0;left:15%;right:15%;height:1px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,0.14),transparent);
  z-index:1;pointer-events:none;
}
.card-h{
  padding:10px 16px;border-bottom:1px solid rgba(255,255,255,0.06);
  display:flex;align-items:center;gap:9px;
  background:rgba(255,255,255,0.02);
}
.card-h-ic{font-size:13px}
.card-h-t{font-family:'Syne',sans-serif;font-size:14px;font-weight:700;color:var(--t1);letter-spacing:-.01em;flex:1}
.card-h-s{font-size:8px;color:var(--t3);font-family:var(--mono)}
.card-b{padding:14px 16px}

/* Weather card */
.w-main{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px}
.w-temp{font-family:'Syne',sans-serif;font-size:68px;font-weight:800;color:#fff;line-height:1;text-shadow:0 0 40px rgba(200,255,71,0.2)}
.w-unit{font-size:22px;color:var(--t3)}
.w-city{font-size:13px;font-weight:600;color:var(--t1);margin-top:5px;font-family:var(--body)}
.w-cond{font-size:9.5px;color:var(--t2);margin-top:3px;font-family:var(--mono)}
.w-emoji{font-size:50px;filter:drop-shadow(0 0 20px rgba(255,220,100,0.3))}
.w-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.w-cell{
  background:rgba(255,255,255,0.035);border:1px solid rgba(255,255,255,0.065);
  border-radius:10px;padding:9px 8px;text-align:center;backdrop-filter:blur(8px);
}
.w-v{font-size:13px;font-weight:700;color:var(--t1);font-family:var(--body)}
.w-l{font-size:7.5px;color:var(--t3);letter-spacing:.1em;margin-top:3px;font-family:var(--mono)}

/* News card */
.n-item{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.04)}
.n-item:last-child{border:none;padding-bottom:0}
.n-num{font-family:'Syne',sans-serif;font-size:24px;font-weight:800;color:rgba(255,255,255,0.1);min-width:28px;line-height:1;margin-top:1px}
.n-ttl{font-size:11.5px;font-weight:500;color:var(--t1);line-height:1.55;font-family:var(--body)}
.n-meta{display:flex;gap:6px;margin-top:4px;align-items:center;flex-wrap:wrap}
.n-src{font-size:8.5px;color:var(--a);font-weight:700;font-family:var(--mono)}
.n-time{font-size:8px;color:var(--t3);font-family:var(--mono)}
.n-cat{font-size:7.5px;padding:2px 6px;border-radius:4px;background:rgba(61,184,255,0.1);color:var(--blue);font-weight:700;letter-spacing:.05em;font-family:var(--mono)}

/* Crypto card */
.c-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}
.c-item{
  background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.065);
  border-radius:12px;padding:12px 14px;backdrop-filter:blur(10px);
}
.c-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.c-sym{font-size:9px;font-weight:700;color:var(--t3);letter-spacing:.1em;font-family:var(--mono)}
.c-chg{font-size:10px;font-weight:700;padding:2px 7px;border-radius:5px;font-family:var(--mono)}
.up{background:rgba(45,255,176,0.1);color:var(--green)}
.dn{background:rgba(255,68,102,0.1);color:var(--red)}
.c-price{font-family:'Syne',sans-serif;font-size:24px;font-weight:800;color:#fff;line-height:1}
.c-name{font-size:10px;color:var(--t2);margin-top:2px;font-family:var(--body)}
.c-mcap{font-size:8.5px;color:var(--t3);margin-top:5px;font-family:var(--mono)}
.c-sent{
  margin-top:10px;padding:8px 14px;
  background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
  border-radius:10px;display:flex;align-items:center;justify-content:space-between;
}
.c-sl{font-size:9.5px;color:var(--t2);font-family:var(--mono)}
.c-sv{font-size:10.5px;color:var(--a);font-weight:700;font-family:var(--mono)}

/* DB */
.db-tbl{width:100%;border-collapse:collapse;font-size:11.5px}
.db-tbl th{text-align:left;font-size:7.5px;letter-spacing:.15em;color:var(--t3);padding:0 0 8px;border-bottom:1px solid rgba(255,255,255,0.06);font-weight:700;font-family:var(--mono)}
.db-tbl td{padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.03);color:var(--t1);vertical-align:top;font-family:var(--body);font-size:11px}
.db-tbl tr:last-child td{border:none}
.bd{display:inline-block;padding:2px 7px;border-radius:4px;font-size:7.5px;font-weight:700;letter-spacing:.06em;font-family:var(--mono)}
.bd-g{background:var(--gdim);color:var(--green)}
.bd-a{background:var(--adim2);color:var(--amber)}
.bd-r{background:var(--rdim);color:var(--red)}
.bd-b{background:var(--bdim);color:var(--blue)}
.aok{
  display:flex;align-items:center;gap:10px;padding:12px 14px;
  background:rgba(45,255,176,0.05);border:1px solid rgba(45,255,176,0.14);
  border-radius:10px;margin-top:5px;backdrop-filter:blur(10px);
}
.aok-ic{font-size:16px}
.aok-t{font-size:11.5px;color:var(--green);font-weight:500;font-family:var(--body)}

/* Calc / Converter */
.res-big{text-align:center;padding:18px 14px}
.res-expr{font-size:10px;color:var(--t3);margin-bottom:10px;letter-spacing:.05em;font-family:var(--mono)}
.res-val{font-family:'Syne',sans-serif;font-size:56px;font-weight:800;color:var(--a);text-shadow:0 0 30px rgba(200,255,71,0.3);line-height:1}

/* ══════════════════════════════════
   INPUT ZONE — Magnetto glass style
══════════════════════════════════ */
.inp-zone{padding:12px 28px 20px;flex-shrink:0}
.inp-wrap{
  background:rgba(8,12,26,0.55);
  border:1px solid rgba(255,255,255,0.1);
  border-radius:18px;padding:4px 4px 4px 18px;
  display:flex;align-items:flex-end;gap:4px;
  transition:border-color .2s,box-shadow .2s;
  backdrop-filter:blur(28px) saturate(1.6);
  -webkit-backdrop-filter:blur(28px) saturate(1.6);
  box-shadow:
    0 8px 32px rgba(0,0,0,0.35),
    0 1px 0 rgba(255,255,255,0.07) inset,
    0 -1px 0 rgba(0,0,0,0.25) inset;
  position:relative;
}
.inp-wrap::before{
  content:'';position:absolute;top:0;left:18%;right:18%;height:1px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,0.12),transparent);
  border-radius:1px;
}
.inp-wrap:focus-within{
  border-color:rgba(200,255,71,0.3);
  box-shadow:0 0 0 3px rgba(200,255,71,0.07),0 8px 32px rgba(0,0,0,0.35),0 1px 0 rgba(255,255,255,0.07) inset;
}
.inp-wrap textarea{
  flex:1;background:transparent;border:none;outline:none;
  color:var(--t1);font-family:var(--mono);font-size:12.5px;
  resize:none;min-height:22px;max-height:120px;padding:11px 0;line-height:1.65;
}
.inp-wrap textarea::placeholder{color:var(--t3)}

.inp-btns{display:flex;align-items:center;gap:3px;padding:5px}

/* ══════════════════════════════════
   MIC BUTTON — clean SVG animated
══════════════════════════════════ */
.mic-btn{
  width:36px;height:36px;border-radius:10px;border:1px solid rgba(255,255,255,0.08);
  background:rgba(255,255,255,0.04);color:var(--t2);cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:all .2s var(--ease);position:relative;overflow:visible;
  flex-shrink:0;
}
.mic-btn:hover{
  background:rgba(61,184,255,0.1);
  border-color:rgba(61,184,255,0.3);
  color:var(--blue);
  transform:scale(1.05);
  box-shadow:0 4px 16px rgba(61,184,255,0.15);
}
.mic-btn.listening{
  background:rgba(255,68,102,0.12) !important;
  border-color:rgba(255,68,102,0.4) !important;
  color:var(--red) !important;
  box-shadow:0 0 0 0 rgba(255,68,102,0.4);
  animation:mic-pulse 1.2s ease-out infinite;
}
@keyframes mic-pulse{
  0%{box-shadow:0 0 0 0 rgba(255,68,102,0.5)}
  70%{box-shadow:0 0 0 8px rgba(255,68,102,0)}
  100%{box-shadow:0 0 0 0 rgba(255,68,102,0)}
}
.mic-btn svg{transition:all .2s}
.mic-btn.listening svg{transform:scale(1.1)}

/* Listening indicator */
.mic-indicator{
  position:absolute;top:-28px;left:50%;transform:translateX(-50%);
  background:rgba(255,68,102,0.9);backdrop-filter:blur(12px);
  border:1px solid rgba(255,68,102,0.5);
  border-radius:20px;padding:3px 9px;
  font-size:7.5px;color:#fff;font-weight:700;letter-spacing:.1em;font-family:var(--mono);
  white-space:nowrap;display:none;z-index:10;
  animation:fadeUp .2s var(--ease) both;
}
.mic-btn.listening .mic-indicator{display:block}

/* Mic sound waves (shown when listening) */
.mic-waves{
  position:absolute;inset:-4px;border-radius:14px;pointer-events:none;
  display:none;
}
.mic-btn.listening .mic-waves{display:block}
.mic-wave{
  position:absolute;inset:0;border-radius:12px;
  border:1.5px solid rgba(255,68,102,0.4);
  animation:wave-expand 1.4s ease-out infinite;
}
.mic-wave:nth-child(2){animation-delay:.35s}
.mic-wave:nth-child(3){animation-delay:.7s}
@keyframes wave-expand{
  0%{transform:scale(1);opacity:.6}
  100%{transform:scale(1.7);opacity:0}
}

.send{
  width:36px;height:36px;border-radius:10px;border:none;
  background:var(--a);color:#010b01;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:all .18s;font-size:12px;font-weight:700;
  box-shadow:0 4px 16px rgba(200,255,71,0.28),0 1px 0 rgba(255,255,255,0.3) inset;
}
.send:hover{background:#d4ff5a;box-shadow:0 6px 24px rgba(200,255,71,0.4),0 1px 0 rgba(255,255,255,0.3) inset;transform:scale(1.06)}
.send:active{transform:scale(.93)}

.inp-hint{font-size:8.5px;color:var(--t3);margin-top:7px;padding:0 4px;display:flex;align-items:center;gap:9px;font-family:var(--mono)}
kbd{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:4px;padding:1px 5px;font-size:7.5px;font-family:var(--mono);color:var(--t2)}
.inp-albl{margin-left:auto;color:var(--a);opacity:.65;font-size:8.5px;transition:all .2s}

/* FLASH */
@keyframes agentFlash{0%{opacity:0}40%{opacity:.04}100%{opacity:0}}
.flash{position:fixed;inset:0;background:var(--a);pointer-events:none;z-index:9999;animation:agentFlash .4s var(--ease) both}

/* LIVE badge */
.live-badge{font-size:7px;padding:2px 6px;border-radius:3px;background:rgba(45,255,176,0.12);color:var(--green);font-weight:700;letter-spacing:.08em;font-family:var(--mono)}
.est-badge{font-size:7px;padding:2px 6px;border-radius:3px;background:rgba(255,168,48,0.12);color:var(--amber);font-weight:700;letter-spacing:.08em;font-family:var(--mono)}
</style>
</head>
<body>

<aside class="sb">
  <div class="sb-top">
    <div class="sb-live"><span class="sb-dot"></span><span class="sb-live-t">LIVE · 6 AGENTS</span></div>
    <div class="sb-logo">AI <span>NEXUS</span></div>
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
      <div class="ni-ic">📰</div><span class="ni-name">News</span><span class="ni-tag nt-live">RSS</span>
    </div>
    <div class="ni" id="nav-crypto" onclick="switchAgent('crypto')">
      <div class="ni-ic">₿</div><span class="ni-name">Crypto</span><span class="ni-tag nt-live">LIVE</span>
    </div>
    <div class="ni" id="nav-database" onclick="switchAgent('database')">
      <div class="ni-ic">🗄</div><span class="ni-name">Database</span>
    </div>
    <div class="ni" id="nav-calculator" onclick="switchAgent('calculator')">
      <div class="ni-ic">🧮</div><span class="ni-name">Calculator</span>
    </div>
    <div class="ni" id="nav-converter" onclick="switchAgent('converter')">
      <div class="ni-ic">🔄</div><span class="ni-name">Converter</span>
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
      <div>
        <div class="tb-title" id="tb-title">MULTI-AGENT WORKSPACE</div>
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
    <button class="q-btn" onclick="qs('Weather in Chennai')">Chennai</button>
    <button class="q-btn" onclick="qs('Weather in Mumbai')">Mumbai</button>
    <button class="q-btn" onclick="qs('Weather in London')">London</button>
    <button class="q-btn" onclick="qs('Weather in Tokyo')">Tokyo</button>
    <button class="q-btn" onclick="qs('Weather in Dubai')">Dubai</button>
    <button class="q-btn" onclick="qs('Weather in New York')">New York</button>
  </div>

  <div class="chat" id="chat">
    <div class="empty" id="empty">
      <div class="e-orb">⚡</div>
      <div class="e-title">AI <span>NEXUS</span></div>
      <div class="e-cmd"><em>$</em> nexus --agents=6 --model=llama3.3-70b --status=<em>ready</em></div>
      <div class="e-sub">Six specialized agents at your command. Ask anything and I'll route it to the right expert — or pick an agent from the sidebar.</div>
      <div class="e-grid">
        <div class="e-card" onclick="switchAgent('weather');qs('Weather in Chennai')"><span class="e-ic">🌤</span><div class="e-name">Weather Agent</div><div class="e-hint">Live · Open-Meteo API</div></div>
        <div class="e-card" onclick="switchAgent('news');qs('Latest AI news')"><span class="e-ic">📰</span><div class="e-name">News Agent</div><div class="e-hint">Live RSS · 8 categories</div></div>
        <div class="e-card" onclick="switchAgent('crypto');qs('Bitcoin price')"><span class="e-ic">₿</span><div class="e-name">Crypto Agent</div><div class="e-hint">Live · CoinGecko API</div></div>
        <div class="e-card" onclick="switchAgent('database');qs('List all products')"><span class="e-ic">🗄</span><div class="e-name">Database Agent</div><div class="e-hint">CRUD + SQL</div></div>
        <div class="e-card" onclick="switchAgent('calculator');qs('Calculate 15% of 85000')"><span class="e-ic">🧮</span><div class="e-name">Calculator Agent</div><div class="e-hint">Math & expressions</div></div>
        <div class="e-card" onclick="switchAgent('converter');qs('1000 USD to INR')"><span class="e-ic">🔄</span><div class="e-name">Converter Agent</div><div class="e-hint">Currency · temp · units</div></div>
      </div>
      <div class="e-chips">
        <div class="e-chip" onclick="qs('What is artificial intelligence?')">🤖 What is AI?</div>
        <div class="e-chip" onclick="qs('ETH and SOL price')">📈 ETH &amp; SOL</div>
        <div class="e-chip" onclick="qs('Latest tech news today')">🔬 Tech news</div>
        <div class="e-chip" onclick="qs('25 C to F')">🌡 25°C → °F</div>
        <div class="e-chip" onclick="qs('Add task: Review hackathon submission')">✅ Add task</div>
      </div>
    </div>
  </div>

  <div class="inp-zone">
    <div class="inp-wrap">
      <textarea id="msg" rows="1" placeholder="// ask anything — weather, crypto, news, math, convert, database, or any question…" onkeydown="handleKey(event)" oninput="autoH(this)"></textarea>
      <div class="inp-btns">
        <!-- CLEAN MIC BUTTON -->
        <button class="mic-btn" id="micBtn" onclick="startVoice()" title="Voice search">
          <div class="mic-indicator">LISTENING</div>
          <div class="mic-waves">
            <div class="mic-wave"></div>
            <div class="mic-wave"></div>
            <div class="mic-wave"></div>
          </div>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <!-- Mic body -->
            <rect x="9" y="2" width="6" height="11" rx="3" fill="currentColor" opacity="0.9"/>
            <!-- Arc -->
            <path d="M5 10C5 14.418 8.134 18 12 18C15.866 18 19 14.418 19 10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            <!-- Stem -->
            <line x1="12" y1="18" x2="12" y2="22" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            <!-- Base -->
            <line x1="8" y1="22" x2="16" y2="22" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </button>
        <button class="send" onclick="send()" title="Send">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </div>
    <div class="inp-hint">
      <kbd>Enter</kbd> send &nbsp; <kbd>Shift+Enter</kbd> newline
      <span style="display:flex;align-items:center;gap:4px;color:var(--blue);opacity:.6;font-size:8.5px">
        <svg width="9" height="9" viewBox="0 0 24 24" fill="currentColor"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10C5 14.418 8.134 18 12 18C15.866 18 19 14.418 19 10" stroke="currentColor" stroke-width="2.5" fill="none"/><line x1="12" y1="18" x2="12" y2="22" stroke="currentColor" stroke-width="2.5"/></svg>
        voice
      </span>
      <span class="inp-albl" id="a-lbl">// agent: auto-detect</span>
    </div>
  </div>
</main>

<script>
let msgCount=0, activeAgent='all', hasMsgs=false, msgId=0;

const AGENTS={
  all:{id:'nav-all',ic:'⚡',title:'MULTI-AGENT WORKSPACE',sub:'// all_agents_active · auto-routing enabled',lbl:'// agent: auto-detect',ph:'// ask anything — weather, crypto, news, math, convert, database, or any question…',
    btns:[{l:'Chennai',m:'Weather in Chennai'},{l:'Mumbai',m:'Weather in Mumbai'},{l:'London',m:'Weather in London'},{l:'Tokyo',m:'Weather in Tokyo'},{l:'Dubai',m:'Weather in Dubai'},{l:'New York',m:'Weather in New York'}]},
  weather:{id:'nav-weather',ic:'🌤',title:'WEATHER AGENT',sub:'// weather_agent · live Open-Meteo API · worldwide',lbl:'// agent: weather',ph:'// try: "Weather in Mumbai" or "Temperature in Paris"',
    btns:[{l:'Chennai',m:'Weather in Chennai'},{l:'Mumbai',m:'Weather in Mumbai'},{l:'London',m:'Weather in London'},{l:'Tokyo',m:'Weather in Tokyo'},{l:'Dubai',m:'Weather in Dubai'},{l:'New York',m:'Weather in New York'}]},
  news:{id:'nav-news',ic:'📰',title:'NEWS AGENT',sub:'// news_agent · live RSS · 8 categories',lbl:'// agent: news',ph:'// try: "Latest AI news" or "India news today"',
    btns:[{l:'AI news',m:'Latest AI news'},{l:'Tech news',m:'Latest tech news'},{l:'Crypto news',m:'Latest crypto news'},{l:'India',m:'India news today'},{l:'World',m:'World news today'},{l:'Science',m:'Science news today'}]},
  crypto:{id:'nav-crypto',ic:'₿',title:'CRYPTO AGENT',sub:'// crypto_agent · live CoinGecko API · 50+ coins',lbl:'// agent: crypto',ph:'// try: "Bitcoin price" or "ETH and SOL"',
    btns:[{l:'Bitcoin',m:'Bitcoin price'},{l:'Ethereum',m:'Ethereum price'},{l:'Solana',m:'Solana price'},{l:'Top 4',m:'Show top 4 crypto coins'},{l:'Dogecoin',m:'Dogecoin price'},{l:'Market',m:'Crypto market overview'}]},
  database:{id:'nav-database',ic:'🗄',title:'DATABASE AGENT',sub:'// db_agent · SQLite · CRUD · products · tasks',lbl:'// agent: database',ph:'// try: "List products" or "Add task: Complete submission"',
    btns:[{l:'All products',m:'List all products'},{l:'My tasks',m:'Show all my tasks'},{l:'Add task',m:'Add task: Complete hackathon'},{l:'AI services',m:'Find products in AI Services'},{l:'SQL',m:'sql: SELECT * FROM products WHERE price > 100'},{l:'Add note',m:'Note: Review the architecture'}]},
  calculator:{id:'nav-calculator',ic:'🧮',title:'CALCULATOR AGENT',sub:'// calc_agent · math · percentages · expressions',lbl:'// agent: calculator',ph:'// try: "Calculate 15% of 85000" or "sqrt(256)"',
    btns:[{l:'15% of 85K',m:'Calculate 15% of 85000'},{l:'sqrt(256)',m:'What is sqrt(256)?'},{l:'Compound',m:'Calculate 100000 * 1.08 ^ 10'},{l:'250 × 4.5',m:'Calculate 250 * 4.5 + 120'},{l:'2^32',m:'Calculate 2 ^ 32'},{l:'Complex',m:'Calculate (500 + 200) * 1.18 / 12'}]},
  converter:{id:'nav-converter',ic:'🔄',title:'CONVERTER AGENT',sub:'// converter_agent · currency · temp · distance · weight',lbl:'// agent: converter',ph:'// try: "100 USD to INR" or "37 C to F"',
    btns:[{l:'USD → INR',m:'1000 USD to INR'},{l:'°C → °F',m:'37 C to F'},{l:'km → miles',m:'100 km to miles'},{l:'kg → lbs',m:'75 kg to lbs'},{l:'EUR → INR',m:'500 EUR to INR'},{l:'miles → km',m:'26.2 miles to km'}]}
};

const META={
  weather:{tag:'🌤 WEATHER',bg:'rgba(255,168,48,.12)',fg:'#ffa830'},
  news:{tag:'📰 NEWS',bg:'rgba(157,124,255,.12)',fg:'#a78bfa'},
  crypto:{tag:'₿ CRYPTO',bg:'rgba(255,100,60,.12)',fg:'#ff6e3c'},
  db:{tag:'🗄 DATABASE',bg:'rgba(45,255,176,.1)',fg:'#2dffb0'},
  calc:{tag:'🧮 CALC',bg:'rgba(61,184,255,.1)',fg:'#3db8ff'},
  converter:{tag:'🔄 CONVERT',bg:'rgba(200,255,71,.1)',fg:'#c8ff47'},
  chat:{tag:'⚡ NEXUS',bg:'rgba(61,184,255,.1)',fg:'#3db8ff'}
};

function switchAgent(key){
  const prev=activeAgent; activeAgent=key;
  const cfg=AGENTS[key]; if(!cfg) return;
  if(hasMsgs && prev!==key){
    const f=document.createElement('div'); f.className='flash';
    document.body.appendChild(f); setTimeout(()=>f.remove(),450);
  }
  document.querySelectorAll('.ni').forEach(e=>e.classList.remove('active'));
  document.getElementById(cfg.id).classList.add('active');
  document.getElementById('tb-ic').textContent=cfg.ic;
  document.getElementById('tb-title').textContent=cfg.title;
  document.getElementById('tb-sub').textContent=cfg.sub;
  document.getElementById('a-lbl').textContent=cfg.lbl;
  const qb=document.getElementById('qbar');
  qb.innerHTML='<span class="q-lbl">QUICK</span><div class="q-sep"></div>';
  cfg.btns.forEach(b=>{
    const btn=document.createElement('button');
    btn.className='q-btn'; btn.textContent=b.l;
    btn.onclick=()=>qs(b.m); qb.appendChild(btn);
  });
  document.getElementById('msg').placeholder=cfg.ph;
  clearChat();
}

function clearChat(){
  document.querySelectorAll('.msg').forEach(m=>m.remove());
  const em=document.getElementById('empty');
  em.style.display=''; em.style.animation='none';
  void em.offsetWidth; em.style.animation='fadeUp .5s cubic-bezier(.22,1,.36,1) both';
  msgCount=0; document.getElementById('msg-count').textContent='0'; hasMsgs=false;
}

function autoH(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,120)+'px'}
function handleKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}
function qs(t){document.getElementById('msg').value=t;send();}
function getTime(){return new Date().toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'})}
function esc(t){return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

// ── VOICE SEARCH ──
let voiceActive = false;
function startVoice(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  const btn=document.getElementById('micBtn');
  if(!SR){
    btn.style.borderColor='rgba(255,68,102,0.4)';
    setTimeout(()=>btn.style.borderColor='',1500);
    return;
  }
  if(voiceActive) return;
  voiceActive=true;
  btn.classList.add('listening');
  const r=new SR();
  r.lang='en-US'; r.interimResults=false; r.maxAlternatives=1;
  r.onresult=e=>{
    const ta=document.getElementById('msg');
    ta.value=e.results[0][0].transcript;
    autoH(ta);
    stopListening();
    setTimeout(()=>send(),150);
  };
  r.onerror=()=>stopListening();
  r.onend=()=>stopListening();
  r.start();
  function stopListening(){
    voiceActive=false;
    btn.classList.remove('listening');
  }
}

function typeEffect(text,el,cb){
  let i=0;
  (function tick(){if(i<text.length){el.textContent+=text.charAt(i++);setTimeout(tick,6);}else if(cb)cb();})();
}

function renderWeather(d){
  const em=d.emoji||'🌡';
  const srcTag=d.live ? `<span class="live-badge">● LIVE</span>` : `<span class="est-badge">EST</span>`;
  return `<div class="card">
  <div class="card-h"><span class="card-h-ic">🌤</span><span class="card-h-t">WEATHER · ${esc(d.city)}</span><div style="display:flex;gap:6px;align-items:center">${srcTag}<span class="card-h-s">${getTime()}</span></div></div>
  <div class="card-b"><div class="w-main"><div>
    <div class="w-temp">${d.temperature_c}<span class="w-unit">°C</span></div>
    <div class="w-city">${esc(d.city)}</div>
    <div class="w-cond">${d.condition} · feels like ${d.feels_like_c}°C</div>
  </div><div class="w-emoji">${em}</div></div>
  <div class="w-grid">
    <div class="w-cell"><div class="w-v">${d.humidity_pct}%</div><div class="w-l">HUMIDITY</div></div>
    <div class="w-cell"><div class="w-v">${d.wind_kmh}</div><div class="w-l">WIND km/h</div></div>
    <div class="w-cell"><div class="w-v">${d.uv_index}</div><div class="w-l">UV INDEX</div></div>
    <div class="w-cell"><div class="w-v">${d.visibility_km}</div><div class="w-l">VISIBILITY</div></div>
  </div></div></div>`;
}

function renderNews(d){
  const liveTag=d.live ? `<span class="live-badge">● LIVE RSS</span>` : `<span class="est-badge">CACHED</span>`;
  const items=d.articles.map((a,i)=>`<div class="n-item"><div class="n-num">0${i+1}</div><div>
    <div class="n-ttl">${esc(a.title)}</div>
    <div class="n-meta"><span class="n-src">${esc(a.source)}</span><span class="n-time">${a.time}</span><span class="n-cat">${esc(a.category)}</span></div>
  </div></div>`).join('');
  return `<div class="card"><div class="card-h"><span class="card-h-ic">📰</span><span class="card-h-t">NEWS · ${esc(d.category)}</span><div style="display:flex;gap:6px;align-items:center">${liveTag}<span class="card-h-s">updated ${d.last_updated}</span></div></div><div class="card-b">${items}</div></div>`;
}

function renderCrypto(d){
  const srcTag=d.live ? `<span class="live-badge">● COINGECKO</span>` : `<span class="est-badge">EST</span>`;
  const coins=d.coins.map(c=>{
    const up=c.change_24h>=0;
    const price=c.price_usd>=1?'$'+c.price_usd.toLocaleString():'$'+c.price_usd;
    return `<div class="c-item"><div class="c-top"><span class="c-sym">${c.symbol}</span><span class="c-chg ${up?'up':'dn'}">${up?'+':''}${c.change_24h}%</span></div>
    <div class="c-price">${price}</div><div class="c-name">${c.name}</div>
    <div class="c-mcap">mcap ${c.market_cap} · vol ${c.volume_24h}</div></div>`;
  }).join('');
  return `<div class="card"><div class="card-h"><span class="card-h-ic">₿</span><span class="card-h-t">CRYPTO MARKETS</span><div style="display:flex;gap:6px;align-items:center">${srcTag}<span class="card-h-s">${d.timestamp}</span></div></div>
  <div class="card-b"><div class="c-grid">${coins}</div>
  <div class="c-sent"><span class="c-sl">market sentiment</span><span class="c-sv">${d.market_sentiment} · fear/greed ${d.fear_greed_index}</span></div></div></div>`;
}

function renderDB(d){
  if(d.action==='list_products'){
    const rows=d.products.map(p=>`<tr><td>${esc(p.name)}</td><td><span class="bd bd-b">${esc(p.category)}</span></td><td>$${p.price}</td><td>${p.stock}</td><td style="color:var(--amber)">★ ${p.rating}</td></tr>`).join('');
    return `<div class="card"><div class="card-h"><span class="card-h-ic">🗄</span><span class="card-h-t">PRODUCTS · ${d.count} rows</span></div>
    <div class="card-b"><table class="db-tbl"><thead><tr><th>NAME</th><th>CATEGORY</th><th>PRICE</th><th>STOCK</th><th>RATING</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }
  if(d.action==='list_tasks'){
    if(!d.tasks.length) return `<div class="card"><div class="card-b" style="color:var(--t3);font-size:11px;text-align:center;padding:16px">// no tasks · try: "Add task: Review code"</div></div>`;
    const rows=d.tasks.map(t=>`<tr><td>${esc(t.title)}</td><td><span class="bd ${t.priority==='high'?'bd-r':t.priority==='medium'?'bd-a':'bd-g'}">${t.priority}</span></td><td><span class="bd bd-b">${t.status}</span></td></tr>`).join('');
    return `<div class="card"><div class="card-h"><span class="card-h-ic">✅</span><span class="card-h-t">TASKS · ${d.count} rows</span></div>
    <div class="card-b"><table class="db-tbl"><thead><tr><th>TITLE</th><th>PRIORITY</th><th>STATUS</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }
  if(d.action==='task_created') return `<div class="card"><div class="card-b"><div class="aok"><span class="aok-ic">✅</span><span class="aok-t">Task created → "${esc(d.task)}" [priority: ${d.priority}]</span></div></div></div>`;
  if(d.action==='note_saved') return `<div class="card"><div class="card-b"><div class="aok"><span class="aok-ic">📝</span><span class="aok-t">Note saved → "${esc(d.content)}"</span></div></div></div>`;
  if(d.action==='sql_query'||d.action==='product_search'){
    const data=d.rows||d.products;
    if(!data||!data.length) return `<div class="card"><div class="card-b" style="color:var(--t3);font-size:11px">// no results found</div></div>`;
    const keys=Object.keys(data[0]);
    return `<div class="card"><div class="card-h"><span class="card-h-ic">🔍</span><span class="card-h-t">QUERY · ${data.length} rows</span></div>
    <div class="card-b"><table class="db-tbl"><thead><tr>${keys.map(k=>`<th>${k.toUpperCase()}</th>`).join('')}</tr></thead>
    <tbody>${data.map(r=>`<tr>${keys.map(k=>`<td>${esc(r[k]??'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>`;
  }
  return null;
}

function renderCalc(d){
  if(d.status!=='success') return null;
  return `<div class="card"><div class="card-h"><span class="card-h-ic">🧮</span><span class="card-h-t">CALCULATION</span></div>
  <div class="card-b"><div class="res-big"><div class="res-expr">// input: ${esc(d.expression)}</div><div class="res-val">= ${d.result.toLocaleString()}</div></div></div></div>`;
}

function renderConverter(d){
  if(!d.from) return null;
  return `<div class="card"><div class="card-h"><span class="card-h-ic">🔄</span><span class="card-h-t">CONVERSION</span></div>
  <div class="card-b"><div class="res-big"><div class="res-expr">// input: ${esc(d.from)}</div><div class="res-val">${esc(d.to)}</div></div></div></div>`;
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
        context_injection = f"\n[AGENT DATA]: {json.dumps(tool_data)}"
    elif agent == "news":
        tool_data = news_agent(msg)
        context_injection = f"\n[AGENT DATA]: {json.dumps(tool_data)}"
    elif agent == "crypto":
        tool_data = crypto_agent(msg)
        context_injection = f"\n[AGENT DATA]: {json.dumps(tool_data)}"
    elif agent == "db":
        tool_data = db_agent(msg)
        context_injection = f"\n[AGENT DATA]: {json.dumps(tool_data)}"
    elif agent == "calc":
        tool_data = calc_agent(msg)
        context_injection = f"\n[AGENT DATA]: {json.dumps(tool_data)}"
    elif agent == "converter":
        tool_data = converter_agent(msg)
        context_injection = f"\n[AGENT DATA]: {json.dumps(tool_data)}"
    full_msg = msg + context_injection
    chat_memory.append({"role": "user", "content": full_msg})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_memory[-10:]
    groq_res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1024,
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
    return jsonify({"status": "ok", "agents": 6, "products": p,
                    "real_time": {"weather": "Open-Meteo API", "crypto": "CoinGecko API", "news": "RSS Feeds"}})

if __name__ == "__main__":
    init_db()
    app.run(debug=False)
