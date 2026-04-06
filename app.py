import os, sqlite3, random
from flask import Flask, request, jsonify, render_template_string
from groq import Groq

app = Flask(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DB = "data.db"
chat_memory = []

# ---------- INIT DB ----------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY, name TEXT, price REAL)""")
    if c.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        c.executemany("INSERT INTO products(name,price) VALUES(?,?)",
                      [("AI API",99),("Cloud DB",49),("Analytics Tool",120)])
    conn.commit()
    conn.close()

# ---------- TOOLS ----------
def get_weather():
    return {"city":"Chennai","temp":random.randint(25,35)}

def get_news():
    return {"news":["AI breakthrough","Tech innovation","Market trends"]}

def get_crypto():
    return {"bitcoin":random.randint(30000,60000)}

# ---------- ROUTER ----------
def detect_task(msg):
    m = msg.lower()
    if "weather" in m: return "weather"
    if "news" in m: return "news"
    if "bitcoin" in m or "crypto" in m: return "crypto"
    if "database" in m or "sql" in m or "products" in m: return "db"
    return "chat"

# ---------- HTML ----------
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>AI Nexus</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
body {
  margin:0;
  font-family:'Segoe UI';
  background: radial-gradient(circle at top,#0f172a,#020617);
  color:white;
  display:flex;
  height:100vh;
}

.sidebar {
  width:250px;
  background:rgba(255,255,255,0.03);
  backdrop-filter:blur(12px);
  padding:20px;
}

.logo {font-size:20px;margin-bottom:20px;}

.menu {
  padding:12px;
  border-radius:10px;
  margin:5px;
  cursor:pointer;
  transition:0.3s;
}

.menu:hover {
  background:#1e293b;
  transform:scale(1.05);
}

.main {flex:1;display:flex;flex-direction:column;}

.header {
  padding:20px;
  border-bottom:1px solid #1e293b;
}

.chat {
  flex:1;
  overflow:auto;
  padding:20px;
}

.msg {
  margin:10px;
  padding:12px;
  border-radius:12px;
  max-width:70%;
  animation:fade 0.3s;
}

.user {
  background:#6366f1;
  margin-left:auto;
}

.bot {
  background:#1e293b;
}

.input {
  display:flex;
  padding:20px;
  gap:10px;
}

textarea {
  flex:1;
  padding:12px;
  border-radius:10px;
  background:#020617;
  color:white;
  border:1px solid #334155;
  resize:none;
}

button {
  padding:12px;
  background:#6366f1;
  border:none;
  border-radius:10px;
  color:white;
  cursor:pointer;
}

button:hover {
  box-shadow:0 0 10px #6366f1;
}

@keyframes fade {
  from {opacity:0; transform:translateY(10px);}
  to {opacity:1;}
}
</style>
</head>

<body>

<div class="sidebar">
<div class="logo">✨ AI Nexus</div>
<div class="menu">💬 Chat</div>
<div class="menu">🌤 Weather</div>
<div class="menu">📰 News</div>
<div class="menu">💰 Crypto</div>
<div class="menu">🗄 Database</div>
</div>

<div class="main">

<div class="header">Unified Multi-Agent AI System</div>

<div class="chat" id="chat"></div>

<div class="input">
<textarea id="msg" placeholder="Ask anything..."></textarea>
<button onclick="startVoice()">🎤</button>
<button onclick="send()">Send</button>
</div>

</div>

<script>

document.getElementById("msg").addEventListener("input", function(){
  this.style.height = "auto";
  this.style.height = this.scrollHeight + "px";
});

function startVoice(){
  const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
  recognition.lang = "en-US";
  recognition.onresult = function(event){
    document.getElementById("msg").value = event.results[0][0].transcript;
  };
  recognition.start();
}

function typeEffect(text, el){
 let i=0;
 function typing(){
   if(i<text.length){
     el.innerHTML += text.charAt(i);
     i++;
     setTimeout(typing,8);
   }
 }
 typing();
}

async function send(){
 let msg=document.getElementById("msg").value.trim();
 if(!msg) return;

 let chat=document.getElementById("chat");

 chat.innerHTML+=`<div class="msg user">${msg}</div>`;
 document.getElementById("msg").value="";

 let bot=document.createElement("div");
 bot.className="msg bot";
 bot.innerHTML="⚡ AI is thinking...";
 chat.appendChild(bot);

 let res=await fetch("/chat",{
   method:"POST",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify({message:msg})
 });

 let data=await res.json();

 bot.innerHTML="";
 typeEffect(data.response,bot);

 if(msg.toLowerCase().includes("product") || msg.toLowerCase().includes("price")){
   let canvas=document.createElement("canvas");
   chat.appendChild(canvas);

   new Chart(canvas,{
     type:'bar',
     data:{
       labels:["AI API","Cloud DB","Analytics"],
       datasets:[{
         label:'Prices',
         data:[99,49,120]
       }]
     }
   });
 }

 chat.scrollTop=chat.scrollHeight;
}

</script>

</body>
</html>
"""

# ---------- ROUTES ----------
@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/chat", methods=["POST"])
def chat():
    msg = request.json["message"]
    task = detect_task(msg)

    context = msg

    if task == "weather":
        context += f"\nWeather:{get_weather()}"
    elif task == "news":
        context += f"\nNews:{get_news()}"
    elif task == "crypto":
        context += f"\nCrypto:{get_crypto()}"
    elif task == "db":
        conn = sqlite3.connect(DB)
        rows = conn.execute("SELECT * FROM products").fetchall()
        conn.close()
        context += f"\nDatabase:{rows}"

    chat_memory.append({"role":"user","content":context})

    messages = [{"role":"system","content":"You are an advanced AI assistant with tools and database."}] + chat_memory[-6:]

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )

    reply = res.choices[0].message.content
    chat_memory.append({"role":"assistant","content":reply})

    return jsonify({"response":reply})

@app.route("/health")
def health():
    return {"status":"ok"}

if __name__ == "__main__":
    init_db()
    app.run()