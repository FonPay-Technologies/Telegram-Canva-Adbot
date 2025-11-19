# main.py
import os
import time
import logging
import threading
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from flask import Flask, render_template_string, request
from markupsafe import Markup

# -------------------- CONFIG --------------------
TOKEN = "8103309728:AAGKsck7UMUmfjucRRNoEcc3YFazhvz_u3I"
ADMIN_ID = 5236441213
PREMIUM_APPS_LINK = "https://t.me/gsf8mqOl0atkMTM0"
CHEAP_DATA_LINK = "https://play.google.com/store/apps/details?id=fonpaybusiness.aowd"
MONETAG_ZONE = "10089898"
MONETAG_LINK = f"https://libtl.com/zone/{MONETAG_ZONE}"

# Grace and inactivity (seconds)
GRACE_SECONDS = 60            # allow 1 minute after browser close before reset
INACTIVITY_MS = 1 * 60 * 1000  # 1 minute inactivity (client-side)

# -------------------- LOGGING --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------- FILES --------------------
MODE_FILE = "mode.txt"
PROMO_FILE = "promo.txt"
GIFT_FILE = "gift.txt"

# Ensure default files (so missing files won't crash)
if not os.path.exists(MODE_FILE):
    with open(MODE_FILE, "w") as f:
        f.write("monetag")
if not os.path.exists(PROMO_FILE):
    with open(PROMO_FILE, "w") as f:
        f.write(PREMIUM_APPS_LINK)
if not os.path.exists(GIFT_FILE):
    with open(GIFT_FILE, "w") as f:
        f.write("https://www.canva.com/brand/join?token=BrnBqEuFTwf7IgNrKWfy4A&br")

# -------------------- DYNAMIC ADS COUNT --------------------
TOTAL_ADS_FILE = "total_ads.txt"

def get_required_ads():
    try:
        return int(open(TOTAL_ADS_FILE).read().strip())
    except Exception:
        return 5  # default

def set_required_ads(n: int):
    n = int(n)
    with open(TOTAL_ADS_FILE, "w") as f:
        f.write(str(n))

# load at start (keeps backward compatibility)
TOTAL_ADS = get_required_ads()

# -------------------- HELPERS --------------------
def get_mode():
    try:
        return open(MODE_FILE).read().strip()
    except Exception:
        return "monetag"

def set_mode(mode: str):
    with open(MODE_FILE, "w") as f:
        f.write(mode.strip())

def get_promo_link():
    try:
        return open(PROMO_FILE).read().strip()
    except Exception:
        return PREMIUM_APPS_LINK

def update_promo_link(link: str):
    with open(PROMO_FILE, "w") as f:
        f.write(link.strip())

def get_gift_link():
    try:
        return open(GIFT_FILE).read().strip()
    except Exception:
        return "https://www.canva.com/brand/join?token=BrnBqEuFTwf7IgNrKWfy4A&br"

def update_gift_link(link: str):
    with open(GIFT_FILE, "w") as f:
        f.write(link.strip())

# -------------------- STORAGE --------------------
ad_count = {}          # user_id -> verified ads count (0..5)
verified_users = set() # completed users (>=5)
user_list = set()      # seen users (for broadcast / status)

# track browser-close times so reset only after GRACE_SECONDS
close_times = {}       # user_id -> timestamp (time.time())

# -------------------- HTML TEMPLATE --------------------
HTML_PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Canva Pro Tips - Watch Ads</title>
<style>
  :root{
    --bg:#0d0d0d; --card:#121213; --muted:#bdbdbd;
    --accent1:#7b2ff7; --accent2:#f107a3;
  }
  body{font-family:Inter, "Segoe UI", Arial, sans-serif;background:var(--bg);color:#fff;margin:0;padding:20px;display:flex;justify-content:center}
  .card{width:100%;max-width:560px;background:var(--card);border-radius:14px;padding:22px;box-shadow:0 10px 30px rgba(0,0,0,0.5);text-align:center}
  .title{font-size:24px;font-weight:800;margin:0 0 6px;background:linear-gradient(90deg,var(--accent1),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
  .subtitle{color:var(--muted);font-size:14px;margin-bottom:14px}
  .steps{display:flex;gap:8px;justify-content:center;margin:14px 0}
  .step{width:40px;height:40px;border-radius:10px;background:#222;display:flex;align-items:center;justify-content:center;font-weight:700;color:#999}
  .step.done{background:linear-gradient(90deg,var(--accent1),var(--accent2));color:#fff}
  .actions{display:flex;flex-direction:column;gap:12px;margin-top:8px;align-items:center}
  .btn{border:none;border-radius:10px;padding:12px;font-weight:700;cursor:pointer;font-size:15px;width:92%;max-width:420px}
  .btn-primary{background:linear-gradient(90deg,var(--accent1),var(--accent2));color:#fff}
  .btn-secondary{background:#1b1b1b;color:#fff;border:1px solid #2a2a2a;padding:10px;width:92%;}
  .small{font-size:12px;color:var(--muted);margin-top:12px}
  .credit{width:100%;background:#0f0f0f;border-radius:10px;padding:12px;margin-top:16px;color:var(--muted);font-size:13px;line-height:1.35;text-align:center}
  .credit b{color:#fff}
  .stacked-buttons{display:flex;flex-direction:column;gap:8px;width:92%;max-width:420px;margin:auto}
  iframe#adFrame{width:100%;height:420px;border-radius:10px;border:none;margin-top:12px}
  a{color:inherit;text-decoration:none}
  #inactiveMsg{display:none;background:#2a2a2a;padding:10px;border-radius:8px;margin-top:10px}
</style>
</head>
<body>
  <div class="card" role="main">
    <div class="title">Canva Pro Tips</div>
    <div class="subtitle">Watch {{ total }} short ads to unlock Canva Pro access — fast and easy.</div>

    <div class="steps" aria-hidden="true">
      {% for i in range(1,6) %}
        <div class="step {% if i <= watched %}done{% endif %}">{{i}}</div>
      {% endfor %}
    </div>

    <div class="actions" id="actionArea">
      {{monetag_script|safe}}
      {{watch_button|safe}}

      <!-- stacked vertical buttons (Premium Apps + Download Cheap Data App) -->
      <div class="stacked-buttons" id="stackedButtons">
        {{premium_button|safe}}
        {{cheapdata_button|safe}}
      </div>

      <div id="inactiveMsg">⏳ You’ve been inactive for a while, please start again.</div>
    </div>

    <div class="small">After completing all {{ total }} Ads, the <strong>Access Canva Pro</strong> button will appear above.</div>

    <div class="credit">
      💎 <b>Developed by Ejimurphy</b><br>
      📣 Promotion / Contact: <b>@ejimurphy</b><br>
      🤖 Want a bot like this? Order it for just <b>$100</b>
    </div>
  </div>

<script>
/*
 Inactivity handling:
 - Listen for user activity (mousemove, keydown, touchstart, click)
 - Reset a 1-minute timer on activity
 - When timer fires: show message, call server to reset user's progress, then reload page
 Also, on beforeunload we attempt to notify server via navigator.sendBeacon to mark close (server will only reset after GRACE_SECONDS)
*/
(function(){
  const INACTIVITY_MS = {{ inactivity_ms }};
  let timer = null;
  const userId = {{user_id}};
  const inactiveMsg = document.getElementById('inactiveMsg');

  function showInactiveAndReset() {
    inactiveMsg.style.display = 'block';
    // notify server and reload after short delay
    fetch(`/reset_progress/${userId}`, { method: 'POST' })
      .finally(()=> setTimeout(()=> location.reload(), 1200));
  }

  function resetTimer() {
    if (timer) clearTimeout(timer);
    inactiveMsg.style.display = 'none';
    timer = setTimeout(showInactiveAndReset, INACTIVITY_MS);
  }

  // activity events
  ['mousemove', 'keydown', 'click', 'touchstart'].forEach(ev=>{
    window.addEventListener(ev, resetTimer, { passive: true });
  });

  // start timer
  resetTimer();

  // beforeunload - mark closed with timestamp (server will wait GRACE_SECONDS before resetting)
  window.addEventListener('beforeunload', function(){
    try {
      const url = `/mark_closed/${userId}`;
      if (navigator.sendBeacon) {
        navigator.sendBeacon(url);
      } else {
        // fallback synchronous XHR (best-effort)
        var xhr = new XMLHttpRequest();
        xhr.open("POST", url, false);
        try { xhr.send(); } catch(e) {}
      }
    } catch(e){}
  });
})();
</script>
</body>
</html>
"""

# -------------------- FLASK APP --------------------
app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Telegram Canva Pro bot is running."

@app.route("/user/<int:user_id>")
def user_page(user_id):
    # If user had closed previously, check grace period and reset only after GRACE_SECONDS passed.
    ct = close_times.get(user_id)
    now_ts = time.time()
    if ct is not None:
        # If close timestamp is older than GRACE_SECONDS, reset the progress
        if now_ts - ct >= GRACE_SECONDS:
            logger.info("Grace expired for user %s — resetting progress", user_id)
            if user_id in ad_count:
                ad_count[user_id] = 0
            if user_id in verified_users:
                verified_users.discard(user_id)
            # remove recorded close time after reset
            close_times.pop(user_id, None)
        else:
            # still within grace period: keep progress (do not reset yet)
            logger.info("User %s within close grace (%.1fs left)", user_id, GRACE_SECONDS - (now_ts - ct))

    mode = get_mode()
    promo_link = get_promo_link()
    watched = ad_count.get(user_id, 0)
    total = get_required_ads()

    # Monetag SDK script (insert once)
    monetag_script = f"<script src='//libtl.com/sdk.js' data-zone='{MONETAG_ZONE}' data-sdk='show_{MONETAG_ZONE}'></script>"

    if watched < total:
        next_idx = watched + 1

        # Build watch button JS safely using percent-style formatting to avoid f-string brace issues
        # It first tries to call SDK function window['show_<ZONE>'](), else opens zone link and falls back to timed verify.
        watch_button = (
            "<button class='btn btn-primary' id='watchBtn' onclick=\"(function(){"
            "var sdkFn = window['show_%s'];"
            "if (typeof sdkFn === 'function') {"
            "  sdkFn().then(function(){"
            "    fetch('/verify_ad/%s/%s', { method: 'POST' })"
            "      .then(function(){ setTimeout(function(){ location.reload(); }, 700); });"
            "  }).catch(function(e){ console.error(e); alert('Ad failed to load. Try again.'); });"
            "} else {"
            "  var w = window.open('%s','_blank');"
            "  setTimeout(function(){"
            "    fetch('/verify_ad/%s/%s', { method: 'POST' })"
            "      .then(function(){ setTimeout(function(){ location.reload(); }, 700); });"
            "  }, 12000);"
            "}"
            "})()\">🎬 Watch Ads to Unlock Canva Pro</button>"
        ) % (MONETAG_ZONE, user_id, next_idx, MONETAG_LINK, user_id, next_idx)
    else:
        # completed - show gift + stacked buttons
        gift = get_gift_link()
        watch_button = f"<a href='{gift}' target='_blank'><button class='btn btn-primary'>🎁 Access Canva Pro</button></a>"

    # stacked (vertical) buttons
    premium_button = f"<a href='{PREMIUM_APPS_LINK}' target='_blank'><button class='btn btn-secondary'>Premium Apps</button></a>"
    cheapdata_button = f"<a href='{CHEAP_DATA_LINK}' target='_blank'><button class='btn btn-secondary'>📱 Download Cheap Data App</button></a>"

    return render_template_string(
        HTML_PAGE,
        watched=watched,
        monetag_script=monetag_script,
        watch_button=watch_button,
        premium_button=premium_button,
        cheapdata_button=cheapdata_button,
        user_id=user_id,
        inactivity_ms=INACTIVITY_MS
    )

@app.route("/verify_ad/<int:user_id>/<int:count>", methods=["POST"])
def verify_ad(user_id, count):
    prev = ad_count.get(user_id, 0)
    total = get_required_ads()
    # Accept only sequential verifies to prevent skipping
    if count == prev + 1 and count <= total:
        ad_count[user_id] = count
        user_list.add(user_id)
        logger.info("User %s verified ad %d (now %d)", user_id, count, ad_count[user_id])
        if ad_count[user_id] >= total:
            verified_users.add(user_id)
    else:
        logger.info("Ignored verify for user %s: count=%s prev=%s total=%s", user_id, count, prev, total)
    return "ok"

@app.route("/reset_progress/<int:user_id>", methods=["POST"])
def reset_progress(user_id):
    # Immediate reset used by inactivity timer (client)
    if user_id in ad_count:
        ad_count[user_id] = 0
    if user_id in verified_users:
        verified_users.discard(user_id)
    # also clear any recorded close time (we treat inactivity as immediate reset)
    close_times.pop(user_id, None)
    logger.info("Reset progress for user %s via reset endpoint", user_id)
    return "ok"

@app.route("/get_ads_count", methods=["GET"])
def get_ads_count():
    return {"status":"ok", "required_ads": get_required_ads()}

@app.route("/set_ads_count", methods=["POST"])
def set_ads_count():
    # expects JSON { "admin_id": 5236441213, "count": 10 }
    data = request.get_json(silent=True) or {}
    admin_id = data.get("admin_id")
    if admin_id != ADMIN_ID:
        return {"status":"error", "message":"Unauthorized"}, 403
    try:
        cnt = int(data.get("count", 0))
        if cnt < 1 or cnt > 100:
            return {"status":"error", "message":"count must be 1..100"}, 400
        set_required_ads(cnt)
        return {"status":"ok", "required_ads": cnt}
    except Exception as e:
        return {"status":"error", "message": str(e)}, 400
        

@app.route("/mark_closed/<int:user_id>", methods=["POST"])
def mark_closed(user_id):
    # Called by beforeunload (sendBeacon). We record timestamp and only reset after GRACE_SECONDS.
    close_times[user_id] = time.time()
    logger.info("Marked closed time for user %s at %s", user_id, datetime.utcfromtimestamp(close_times[user_id]).isoformat())
    return "ok"

# -------------------- TELEGRAM COMMANDS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ad_count.setdefault(user_id, 0)
    user_list.add(user_id)
    web = os.environ.get("RENDER_EXTERNAL_URL", f"http://localhost:{os.environ.get('PORT', 5000)}")
    keyboard = [[InlineKeyboardButton("🎬 Start Watching Ads", url=f"{web}/user/{user_id}")]]
    await update.message.reply_text(
        f"Welcome! Current Mode: *{get_mode()}*\n\nWatch 5 ads to unlock Canva Pro 🎁",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def setads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("🚫 Admin only.")
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Usage: /setads <number>")
    n = int(context.args[0])
    if n < 1 or n > 100:
        return await update.message.reply_text("⚠️ Choose a number between 1 and 100.")
    set_required_ads(n)
    await update.message.reply_text(f"✅ Required ads updated to {n}")

async def getads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🎯 Current required ads: {get_required_ads()}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 Bot Commands\n"
        "/start - Open your ad page\n"
        "/help - Show this help\n\n"
        "Admin commands:\n"
        "/updategift <link>\n"
        "/getgift\n"
        "/resetads\n"
        "/broadcast <msg>\n"
        "/setmode <monetag|promo>\n"
        "/switchmode\n"
        "/setpromo <link>\n"
        "/currentmode\n"
        "/status\n"
    )
    await update.message.reply_text(text)

def is_admin(uid):
    return uid == ADMIN_ID

async def updategift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("🚫 Admin only.")
    if not context.args:
        return await update.message.reply_text("Usage: /updategift <link>")
    new = context.args[0]
    update_gift_link(new)
    await update.message.reply_text(f"✅ Gift link updated to:\n{new}")

async def getgift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("🚫 Admin only.")
    await update.message.reply_text(f"🎁 Gift link:\n{get_gift_link()}")

async def resetads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("🚫 Admin only.")
    ad_count.clear()
    verified_users.clear()
    close_times.clear()
    await update.message.reply_text("✅ All ad progress reset.")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("🚫 Admin only.")
    if not context.args:
        return await update.message.reply_text("Usage: /broadcast <message>")
    message = " ".join(context.args)
    sent = 0
    for uid in list(user_list):
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            sent += 1
        except Exception as e:
            logger.info("Broadcast to %s failed: %s", uid, e)
    await update.message.reply_text(f"✅ Sent to {sent} users.")

async def setmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("🚫 Admin only.")
    if not context.args:
        return await update.message.reply_text("Usage: /setmode <monetag|promo>")
    mode = context.args[0].lower()
    if mode not in ("monetag", "promo"):
        return await update.message.reply_text("⚠️ Invalid mode.")
    set_mode(mode)
    await update.message.reply_text(f"✅ Mode set to: {mode}")

async def switchmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("🚫 Admin only.")
    current = get_mode()
    new = "promo" if current == "monetag" else "monetag"
    set_mode(new)
    await update.message.reply_text(f"🔁 Switched from *{current}* to *{new}*", parse_mode="Markdown")

async def setpromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("🚫 Admin only.")
    if not context.args:
        return await update.message.reply_text("Usage: /setpromo <link>")
    update_promo_link(context.args[0])
    await update.message.reply_text("✅ Promo link updated.")

async def currentmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🧭 Current mode: {get_mode()}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("🚫 Admin only.")
    total_users = len(user_list)
    total_completed = len(verified_users)
    top = sorted(ad_count.items(), key=lambda x: x[1], reverse=True)[:20]
    top_lines = "\n".join([f"{uid}: {cnt}" for uid, cnt in top]) or "No data yet."
    msg = f"📊 Users seen: {total_users}\nCompleted (>=5): {total_completed}\n\nTop users:\n{top_lines}"
    await update.message.reply_text(msg)

# lightweight logger for normal messages
async def echo_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "")[:240]
    uid = update.effective_user.id
    logger.info("Msg from %s: %s", uid, text)
    await update.message.reply_text("✅ Received.")

# -------------------- RUN & START --------------------
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting Flask on port %s", port)
    app.run(host="0.0.0.0", port=port)

def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()

    # Register commands (all required commands included)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("updategift", updategift))
    application.add_handler(CommandHandler("getgift", getgift))
    application.add_handler(CommandHandler("resetads", resetads))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("setmode", setmode))
    application.add_handler(CommandHandler("switchmode", switchmode))
    application.add_handler(CommandHandler("setpromo", setpromo))
    application.add_handler(CommandHandler("currentmode", currentmode))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("setads", setads))
    application.add_handler(CommandHandler("getads", getads))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_logger))

    logger.info("Starting Telegram polling...")
    application.run_polling()

if __name__ == "__main__":
    # start Flask in background thread then run bot polling
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()