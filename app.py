import os
import sys
import time
import subprocess
import requests as req
import re
import traceback
import gradio as gr
from typing import List, Tuple


GROQ_API_KEYS = [
    "Groq API",
    "Groq API",
    "Groq API",
    "Groq API",
]
VALIDATION_API_KEY = "Groq API"

BACKEND_PORT = 5000
BACKEND_URL  = f"http://127.0.0.1:{BACKEND_PORT}"
GRADIO_PORT  = 7866



_backend_process = None

def start_backend():
    """Start local_backend.py if it isn't already running."""
    global _backend_process

    if _backend_process and _backend_process.poll() is None:
        return True

    backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_backend.py")
    if not os.path.exists(backend_path):
        print("❌ local_backend.py not found next to this file!")
        return False

    print("🚀 Starting local backend…")
    _backend_process = subprocess.Popen(
        [sys.executable, backend_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    for _ in range(16):
        time.sleep(0.5)
        if backend_healthy():
            print("✅ Backend is up and healthy.")
            return True

    print("❌ Backend did not start in time.")
    return False


def backend_healthy() -> bool:
    try:
        r = req.get(f"{BACKEND_URL}/api/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False



import time as _time

class GroqAPI:
    def __init__(self, api_key: str, api_id: int, model: str = "openai/gpt-oss-120b"):
        self.api_key  = api_key
        self.api_id   = api_id
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model    = model
        self.last_req = 0

    def generate(self, messages: list, temperature: float = 0.7) -> Tuple[bool, str]:
        elapsed = _time.time() - self.last_req
        if elapsed < 8:
            _time.sleep(8 - elapsed)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 8000,
        }
        try:
            print(f"   API #{self.api_id} generating…")
            resp = req.post(self.base_url, headers=headers, json=payload, timeout=120)
            self.last_req = _time.time()

            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 30))
                print(f"   Rate limited – {wait}s…")
                _time.sleep(wait)
                resp = req.post(self.base_url, headers=headers, json=payload, timeout=120)
                self.last_req = _time.time()
                if resp.status_code == 429:
                    return False, "RATE_LIMITED"

            resp.raise_for_status()
            return True, resp.json()["choices"][0]["message"]["content"]

        except req.exceptions.Timeout:
            return False, "TIMEOUT"
        except Exception as e:
            self.last_req = _time.time()
            return False, str(e)


class APIPool:
    def __init__(self, keys: List[str]):
        self.apis = [GroqAPI(k, i + 1) for i, k in enumerate(keys)]
        self.idx  = 0

    def next(self) -> GroqAPI:
        api      = self.apis[self.idx]
        self.idx = (self.idx + 1) % len(self.apis)
        return api

    def call(self, messages: list, temperature: float = 0.7) -> Tuple[bool, str]:
        for _ in range(len(self.apis)):
            ok, text = self.next().generate(messages, temperature)
            if ok:
                return True, text
        return False, text



class Validator:
    def __init__(self, key: str):
        self.api = GroqAPI(key, 999, model="llama-3.3-70b-versatile")

    def fix(self, html: str, error_info: str = "") -> str:
        error_section = f"\n\nIframe error:\n{error_info}\nFix it.\n" if error_info else ""

        messages = [
            {"role": "system", "content":
                "You are an HTML/CSS/JS fixer. Return ONLY raw corrected HTML. No markdown fences, no explanation."},
            {"role": "user", "content":
                f"Fix this single-file HTML app. It uses fetch() to http://127.0.0.1:5000/api/… — "
                f"those calls are CORRECT, do NOT remove them. Fix syntax, close tags, ensure something "
                f"renders on load.{error_section}\n\n```html\n{html}\n```"}
        ]
        ok, text = self.api.generate(messages, temperature=0.1)
        return self._strip(text) if ok else html

    @staticmethod
    def _strip(code: str) -> str:
        code = code.strip()
        code = re.sub(r"^```(?:html)?\s*\n?", "", code)
        code = re.sub(r"\n?```\s*$",          "", code)
        return code.strip()



SYSTEM_PROMPT = f"""You are an EXPERT full-stack developer and UI/UX designer. You build complete web apps as a
SINGLE self-contained HTML file. The frontend runs in the browser; the backend is already running at {BACKEND_URL}.

═══ BACKEND API (already running — use it) ═══

  GET    {BACKEND_URL}/api/<table>          → returns {{"data": [row, …]}}
  GET    {BACKEND_URL}/api/<table>/<id>     → returns {{"data": {{row}}}}
  POST   {BACKEND_URL}/api/<table>          → insert  body = JSON object  → 201 {{"data": {{row}}}}
  PUT    {BACKEND_URL}/api/<table>/<id>     → update  body = JSON object  → 200 {{"data": {{row}}}}
  DELETE {BACKEND_URL}/api/<table>/<id>     → delete  → 200 {{"message": "Deleted"}}
  GET    {BACKEND_URL}/api/tables           → {{"tables": ["name", …]}}

  • Table name = anything you choose (e.g. "tasks", "expenses", "menu", "reservations").
  • Columns are created automatically from the keys in your first POST body.
  • Every row gets an auto "id" (integer) and "created_at" (ISO timestamp).
  • **IMPORTANT**: New tables are AUTO-POPULATED with 5-10 sample rows of realistic dummy data!
    So when you fetch data on page load, there will already be items to display.
  • Data is stored in SQLite on disk — it persists forever.

═══ TECHNICAL RULES ═══
• Output ONE HTML file. <!DOCTYPE html> … </html>.
• ALL CSS in one <style> block. ALL JS in one <script> block before </body>.
• Use fetch() to call {BACKEND_URL}/api/… for ALL data operations.
• **CRITICAL**: On page load, ALWAYS fetch existing data first and display it immediately.
  Don't show "No items" until after the fetch confirms the table is truly empty.
• Show loading states while fetching. Show error messages on failure.
• Do NOT use localStorage for data that should persist — use the backend.
• You MAY use localStorage only for UI preferences (theme, language, etc.).
• No external CDNs, no frameworks. Vanilla HTML/CSS/JS only.
  Exception: Google Fonts are allowed and encouraged.
• Output ONLY raw HTML. No markdown fences. Start with <!DOCTYPE html>.

═══ FRONTEND DESIGN EXCELLENCE ═══

**TYPOGRAPHY** (Critical - sets the entire tone):
• NEVER use generic fonts (Arial, Helvetica, Inter, Roboto, system fonts)
• Choose DISTINCTIVE Google Fonts that match the app's purpose:
  - Medical/Hospital: DM Sans, Inter, or Karla (clean, professional)
  - Restaurant/Food: Playfair Display + Lato, Cormorant + Open Sans
  - Creative/Portfolio: Space Grotesk, Syne, Outfit
  - Finance/Business: IBM Plex Sans, Work Sans, Manrope
  - E-commerce: Montserrat, Poppins, Raleway
• Pair a distinctive display font (headings) with a refined body font (text)
• Font sizes: Use a scale (12px, 14px, 16px, 20px, 24px, 32px, 48px, 64px)
• Line height: 1.5-1.7 for body text, 1.2-1.3 for headings
• Letter spacing: -0.02em for headings, normal for body

**COLOR & VISUAL IDENTITY** (Define a bold aesthetic):
• COMMIT to a clear aesthetic direction based on the app:
  - Medical: Blues/teals + white (trust, cleanliness) — #1E40AF, #0EA5E9, #F8FAFC
  - Restaurant: Warm earth tones — #D97706, #92400E, #FEF3C7, #1C1917
  - E-commerce: Bold + energetic — #EC4899, #8B5CF6, #F472B6, #1F2937
  - Finance: Professional navy + green — #1E3A8A, #059669, #F3F4F6
  - Creative: Vibrant gradients — #F59E0B → #EF4444 → #8B5CF6
• Use CSS variables for consistency:
  ```css
  :root {{
    --primary: #...;
    --secondary: #...;
    --accent: #...;
    --bg-main: #...;
    --bg-card: #...;
    --text-primary: #...;
    --text-secondary: #...;
    --border: #...;
    --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    --shadow-lg: 0 20px 25px -5px rgb(0 0 0 / 0.1);
  }}
  ```
• Dominant colors with sharp accents > evenly-distributed palettes
• Use gradients intentionally (backgrounds, buttons, cards):
  ```css
  background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
  ```

**LAYOUT & SPATIAL DESIGN** (Create visual interest):
• Modern CSS Grid/Flexbox layouts — no tables for layout
• Generous white space (padding: 2rem-4rem on containers)
• Card-based design with proper elevation:
  ```css
  .card {{
    background: var(--bg-card);
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: var(--shadow);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  .card:hover {{
    transform: translateY(-4px);
    box-shadow: var(--shadow-lg);
  }}
  ```
• Asymmetric layouts where appropriate (not everything centered)
• Visual hierarchy: Size, color, spacing, weight to guide the eye
• Border radius: 8px-16px for modern feel (not 2px, not 50px)

**COMPONENTS & INTERACTIONS** (Polish every detail):
• **Buttons**:
  ```css
  .btn {{
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.875rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    cursor: pointer;
    transition: all 0.2s ease;
    border: none;
    background: var(--primary);
    color: white;
  }}
  .btn:hover {{
    background: var(--primary-dark);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  }}
  .btn:active {{
    transform: translateY(0);
  }}
  ```
• **Forms**:
  ```css
  input, select, textarea {{
    width: 100%;
    padding: 0.75rem 1rem;
    border: 2px solid var(--border);
    border-radius: 8px;
    font-size: 1rem;
    transition: all 0.2s ease;
    background: var(--bg-card);
  }}
  input:focus {{
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(var(--primary-rgb), 0.1);
  }}
  ```
• **Navigation**: Sticky header, smooth scroll, active states
• **Tables/Lists**: Alternating row colors, hover states, proper cell padding
• **Modals/Dialogs**: Backdrop blur, smooth fade-in, proper z-index
• **Loading states**: Skeleton screens or elegant spinners (not just "Loading...")
• **Empty states**: Beautiful illustrations or messages (not harsh "No data")

**ANIMATIONS & MICRO-INTERACTIONS** (Delight users):
• Page load animations (stagger with animation-delay):
  ```css
  @keyframes fadeInUp {{
    from {{
      opacity: 0;
      transform: translateY(20px);
    }}
    to {{
      opacity: 1;
      transform: translateY(0);
    }}
  }}
  .card {{
    animation: fadeInUp 0.6s ease-out;
  }}
  .card:nth-child(1) {{ animation-delay: 0.1s; }}
  .card:nth-child(2) {{ animation-delay: 0.2s; }}
  .card:nth-child(3) {{ animation-delay: 0.3s; }}
  ```
• Smooth transitions on ALL interactive elements (0.2s-0.3s)
• Hover effects: scale, color change, shadow lift
• Click feedback: active states with slight scale down
• Success/error notifications: slide in from top-right
• Form submission: button loading state (spinner + "Saving...")

**RESPONSIVE DESIGN** (Mobile-first):
• Desktop: max-width: 1200px-1400px container
• Tablet: Single column grid below 768px
• Mobile: Stack everything, larger touch targets (min 44px)
• Media queries:
  ```css
  @media (max-width: 768px) {{
    .grid {{ grid-template-columns: 1fr; }}
    .nav {{ flex-direction: column; }}
  }}
  ```

**PROFESSIONAL POLISH** (The 1% that matters):
• Consistent spacing scale: 4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px
• Icon placeholders using Unicode or CSS shapes (→, ✓, ✕, ☰, ⚙)
• Proper form validation (red borders, error messages)
• Disabled states (opacity: 0.5, cursor: not-allowed)
• Focus states for accessibility (outline or box-shadow)
• Status badges with colored backgrounds:
  ```css
  .badge {{
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
  }}
  .badge-success {{ background: #DEF7EC; color: #03543F; }}
  .badge-warning {{ background: #FEF3C7; color: #92400E; }}
  .badge-error {{ background: #FEE2E2; color: #991B1B; }}
  ```

**AVOID AT ALL COSTS**:
❌ Generic system fonts (Arial, Helvetica)
❌ Purple gradients on white (cliché AI aesthetic)
❌ Centered everything (boring, no hierarchy)
❌ Harsh colors (#FF0000 red, #00FF00 green)
❌ No spacing (cramped UI)
❌ Default browser styles (ugly inputs/buttons)
❌ "Loading..." text without spinner
❌ Instant state changes (no transitions)

**REMEMBER**: Every app should look DISTINCTIVE and PURPOSE-BUILT, never generic.
Choose fonts, colors, and layouts that FIT THE CONTEXT. A hospital app should NOT look
like a restaurant app. Be bold, be intentional, be professional."""


class Engine:
    def __init__(self, api_keys: List[str], val_key: str):
        self.pool      = APIPool(api_keys)
        self.validator = Validator(val_key)

    def create(self, description: str) -> Tuple[bool, str]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content":
                f'Build a complete, beautiful, fully-functional single-page web app for:\n\n'
                f'"{description}"\n\n'
                f'Use the backend at {BACKEND_URL} for all data storage. '
                f'Fetch and display existing data on load. '
                f'Make the UI stunning and mobile-responsive.\n\n'
                f'Output ONLY raw HTML. No code fences. Start with <!DOCTYPE html>.'}
        ]
        ok, raw = self.pool.call(messages, temperature=0.72)
        if not ok:
            return False, raw
        html = self._strip(raw)
        html = self.validator.fix(html)
        return True, html

    def edit(self, current_html: str, user_request: str, history: list) -> Tuple[bool, str]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content":
            f'Current app:\n\n```html\n{current_html}\n```\n\n'
            f'User wants: "{user_request}"\n\n'
            f'Apply ONLY that change. Keep everything else. '
            f'Keep all fetch() calls to {BACKEND_URL}. '
            f'Output the FULL updated HTML. No code fences.'})

        ok, raw = self.pool.call(messages, temperature=0.5)
        if not ok:
            return False, raw
        html = self._strip(raw)
        html = self.validator.fix(html)
        return True, html

    @staticmethod
    def _strip(code: str) -> str:
        code = code.strip()
        code = re.sub(r"^```(?:html)?\s*\n?", "", code)
        code = re.sub(r"\n?```\s*$",          "", code)
        return code.strip()


PREVIEW_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nefercode_preview")
PREVIEW_FILE = os.path.join(PREVIEW_DIR, "index.html")

def write_preview(html: str):
    """Write the current app HTML to the preview directory."""
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    with open(PREVIEW_FILE, "w", encoding="utf-8") as f:
        f.write(html)


def preview_url() -> str:
    """
    The backend also serves static files from nefercode_preview/.
    We add a simple static route in local_backend.py for this.
    URL: http://127.0.0.1:5000/preview/index.html
    """
    return f"{BACKEND_URL}/preview/index.html"


def make_preview_iframe() -> str:
    return (
        f"<iframe src='{preview_url()}' "
        f"style='width:100%;height:620px;border:none;border-radius:10px;' "
        f"sandbox='allow-scripts allow-forms allow-same-origin allow-modals allow-popups'>"
        f"</iframe>"
    )



def create_ui(api_keys: List[str], val_key: str):
    engine = Engine(api_keys, val_key)

    css = """
    .preview-container iframe {
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    .msg-user  { background:#667eea; color:#fff; padding:10px 14px; border-radius:8px 8px 8px 2px; margin:6px 0; max-width:90%; word-break:break-word; }
    .msg-bot   { background:#f0f0f5; color:#222; padding:10px 14px; border-radius:8px 8px 2px 8px; margin:6px 0; max-width:90%; align-self:flex-end; word-break:break-word; }
    .chat-wrap { display:flex; flex-direction:column; gap:4px; padding:12px; max-height:360px; overflow-y:auto; }
    .db-badge  { display:inline-block; background:#2ecc71; color:#fff; padding:3px 10px; border-radius:12px; font-size:13px; margin-left:8px; }
    """

    with gr.Blocks(title="Nefercode", head=f"<style>{css}</style>") as app:

        gr.HTML("""
        <div style="padding:18px 0 4px;">
          <h2 style="margin:0;">🚀 Nefercode <span class="db-badge">🗄️ SQLite Local DB</span></h2>
          <p style="margin:6px 0 0; color:#555;">
            Describe an app → see it live with <strong>real data persistence</strong>.<br>
            Then keep chatting to change it. Data survives refreshes &amp; restarts.
        </div>
        """)

        with gr.Row():
            with gr.Column(scale=1):
                chat_history = gr.HTML(value="<div class='chat-wrap'>👋 Describe your app to get started.</div>")
                user_input   = gr.Textbox(label="", placeholder="Describe your app… or ask for changes", lines=3)

                with gr.Row():
                    send_btn  = gr.Button("🚀 Send", variant="primary", size="lg", scale=2)
                    clear_btn = gr.Button("🗑️ New", scale=1)

                status_box = gr.Textbox(label="Status", lines=2, interactive=False)

                with gr.Row():
                    save_name   = gr.Textbox(label="Save as", value="app.html", scale=3)
                    save_btn    = gr.Button("💾 Save", scale=1)
                save_status = gr.Textbox(label="", lines=1, interactive=False)

                gr.HTML("""<div style="margin-top:12px;padding:10px;background:#f8f9fa;border-radius:8px;border:1px solid #e9ecef;font-size:13px;color:#555;">
                  🗄️ <strong>Database:</strong> <code>nefercode_db.sqlite</code> (local file)<br>
                  📦 Tables auto-created on first write<br>
                  ♻️ Data persists across sessions
                </div>""")

            with gr.Column(scale=2):
                gr.Markdown("### 👁️ Live Preview")
                preview   = gr.HTML(
                    value="<div style='padding:60px;text-align:center;color:#999;font-size:18px;'>"
                          "Your app will appear here…</div>",
                    elem_classes=["preview-container"],
                )
                gr.Markdown("### 📝 Source Code")
                code_view = gr.Code(label="HTML", language="html", lines=28)

        current_html = gr.State("")
        msg_history  = gr.State([])
        chat_msgs    = gr.State([])

        def render_chat(msgs: list) -> str:
            parts = []
            for role, text in msgs:
                cls     = "msg-user" if role == "user" else "msg-bot"
                display = text if role == "user" else "✅ App updated — see preview →"
                parts.append(f'<div class="{cls}">{display}</div>')
            return f'<div class="chat-wrap">{"".join(parts) or "👋 Describe your app to get started."}</div>'

        def on_send(user_text, cur_html, hist, chat):
            if not user_text.strip():
                return ("", cur_html, hist, chat,
                        render_chat(chat),
                        make_preview_iframe() if cur_html else "<div style='padding:40px;text-align:center;color:#999;'>…</div>",
                        cur_html,
                        "Type something first.")

            chat = chat + [("user", user_text.strip())]

            if cur_html == "":
                ok, html = engine.create(user_text.strip())
                status   = "✅ App created with local DB!" if ok else f"❌ {html}"
            else:
                ok, html = engine.edit(cur_html, user_text.strip(), hist)
                status   = "✅ App updated!" if ok else f"❌ {html}"

            if not ok:
                chat = chat + [("bot", f"Error: {html}")]
                return ("", cur_html, hist, chat,
                        render_chat(chat),
                        make_preview_iframe() if cur_html else "<div style='padding:40px;color:red;'>Failed</div>",
                        cur_html,
                        status)

            write_preview(html)

            hist = hist + [
                {"role": "user",      "content": user_text.strip()},
                {"role": "assistant", "content": html},
            ]
            if len(hist) > 8:
                hist = hist[-8:]

            chat = chat + [("bot", html)]

            return ("",                          
                    html,                        
                    hist,                        
                    chat,                        
                    render_chat(chat),           
                    make_preview_iframe(),       
                    html,                        
                    status)

        def on_clear():
            return ("", "", [], [],
                    render_chat([]),
                    "<div style='padding:60px;text-align:center;color:#999;font-size:18px;'>Your app will appear here…</div>",
                    "",
                    "🗑️ Cleared. (DB data is kept — use DELETE in the app to remove rows.)")

        def on_save(html, fname):
            if not html.strip():
                return "❌ Nothing to save."
            try:
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(html)
                return f"✅ Saved → {fname}"
            except Exception as e:
                return f"❌ {e}"

        outputs = [user_input, current_html, msg_history, chat_msgs,
                   chat_history, preview, code_view, status_box]

        send_btn.click(fn=on_send,
                       inputs =[user_input, current_html, msg_history, chat_msgs],
                       outputs=outputs)
        user_input.submit(fn=on_send,
                          inputs =[user_input, current_html, msg_history, chat_msgs],
                          outputs=outputs)
        clear_btn.click(fn=on_clear, outputs=outputs)
        save_btn.click(fn=on_save,
                       inputs =[current_html, save_name],
                       outputs=[save_status])

    return app



if __name__ == "__main__":
    print("=" * 60)
    print(" 🚀  NEFERCODE")
    print(" 🗄️  Local Backend + SQLite")
    print("=" * 60)

    print("📦 Checking dependencies…")
    for pkg in ["flask", "flask-cors", "gradio", "requests"]:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            print(f"   Installing {pkg}…")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"   ❌ Failed to install {pkg}: {result.stderr[:200]}")
                sys.exit(1)
            print(f"   ✅ {pkg} installed")
    
    print("✅ All dependencies ready")
    print("=" * 60)

    if not start_backend():
        print("⚠️  Backend failed to start. Check if port 5000 is already in use.")
        print("   Try: netstat -ano | findstr :5000  (Windows)")
        print("   Try: lsof -i :5000  (Mac/Linux)")
        print("\n   App will still launch but data won't persist.")
    else:
        print(f" 🗄️  DB:      nefercode_db.sqlite")
        print(f" 🌐  Backend: {BACKEND_URL}")

    print(f" 🌐  Gradio:  http://127.0.0.1:{GRADIO_PORT}")
    print("=" * 60)

    ui = create_ui(GROQ_API_KEYS, VALIDATION_API_KEY)
    ui.launch(
        server_name="127.0.0.1",
        server_port=GRADIO_PORT,
        share=False,
        show_error=True,
        inbrowser=True,
        theme=gr.themes.Soft(),
    )
