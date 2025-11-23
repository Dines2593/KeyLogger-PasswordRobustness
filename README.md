🔐 Keylogger Password Robustness Lab
1️⃣ Contexte & objectif

Ce projet a été réalisé dans un cadre pédagogique sur deux machines virtuelles Kali Linux isolées (VirtualBox).

🎯 Objectifs :

    comprendre comment un keylogger peut exfiltrer des données ;
    voir comment les logs sont stockés et visualisés ;
    piloter un agent à distance (commande start/stop capture) ;
    gérer la résilience en cas de panne de l’attaquant (tampon local).

    ⚠️ Usage strictement pédagogique
    Ne pas utiliser ce code en dehors d’un environnement de test contrôlé et autorisé.

2️⃣ Architecture générale

Le lab repose sur deux VMs en réseau interne :

Victime (VM1)                         Attaquant + Contrôleur (VM2)
-------------------------------       ---------------------------------------
Flask : app_victim.py                 Flask : server_attacker.py
- Faux "password checker"             - Endpoint /logs (réception JSON)
- Génération d'un UUID                - Stockage JSONL dans logs/<victim_id>/
- Envoi HTTP POST -> /logs            - Interface web de contrôle
- Tampon local en cas de panne        - Commandes start/stop de la capture
🌐 Protocole : HTTP

📦 Format des événements : JSON

🧱 Résilience : tampon local côté victime quand l’attaquant est indisponible

lab_keylogger/
├── attacker/
│   └── server_attacker.py   # Serveur Flask + contrôleur web
└── victim/
    └── app_victim.py        # Appli Flask victime (fake password checker)
Les dossiers logs/, buffer/, commands/ et le fichier uuid.txt sont générés à l’exécution et ne sont pas indispensables dans le dépôt.

4️⃣ Fonctionnement côté victime (victim/app_victim.py)

📍 Application Flask exposée sur : http://127.0.0.1:8000
Interface :
page web “Vérificateur pédagogique de mot de passe” ;
un champ de mot de passe + jauge de robustesse.
À chaque frappe dans le champ :
calcul d’un score de robustesse (strength_score, strength_label) ;
construction d’un événement JSON :
{
  "victim_id": "<UUID>",
  "timestamp": 1730000000.0,
  "password": "Azerty12!",
  "strength_score": 3,
  "strength_label": "Fort"
}
envoi via HTTP POST vers : http://<IP_ATTAQUANT>:5000/logs.

Autres points importants :

🆔 UUID persistant : généré une fois puis stocké dans uuid.txt pour identifier la victime.

💾 Tampon local (buffer/queue.jsonl) :
si l’envoi échoue (attaquant down), l’événement est ajouté au buffer ;
à chaque nouvelle frappe, la fonction send_with_retry() commence par appeler flush_buffer() pour tenter de renvoyer tous les anciens événements.

🎮 Commande de capture :
la victime interroge /api/commands/<victim_id> sur l’attaquant ;
si capture_enabled = false, l’interface continue d’afficher la robustesse mais aucun événement n’est exfiltré (ni via réseau, ni via buffer).


5️⃣ Fonctionnement côté attaquant / contrôleur (attacker/server_attacker.py)

📍 Application Flask exposée sur : http://<IP_ATTAQUANT>:5000
📥 Réception & stockage des logs
Endpoint POST /logs :
lit le JSON envoyé par la victime ;
ajoute chaque événement dans :
logs/<victim_id>/<YYYY-MM-DD>.log   # 1 événement JSON par ligne

🖥 Interface de contrôle
GET /
→ liste des victimes actives (dossiers présents dans logs/).
GET /victim/<victim_id>
→ vue détaillée pour une victime :
historique des événements (timestamp, mot de passe, score, label) ;
rafraîchissement automatique toutes les 5 s ;
affichage de l’état de la capture : 🟢 ACTIVE / 🔴 STOPPÉE ;
deux boutons :
Activer la capture
Stopper la capture

GET /api/commands/<victim_id>
→ renvoie l’état courant des commandes (JSON).

POST /api/commands/<victim_id>
→ met à jour capture_enabled pour la victime ciblée, stocké dans :
commands/<victim_id>.json


6️⃣ Déploiement rapide du lab

Exemple d’IPs :

Victime : 192.168.30.133

Attaquant : 192.168.30.132
Les deux VMs sont en réseau interne dans VirtualBox.

🔧 Pré-requis
Sur les deux VMs :
sudo apt update
sudo apt install -y python3 python3-pip
pip3 install flask requests

🧍‍♂️ Lancer la victime
Sur la VM victime :
cd lab_keylogger/victim
python3 app_victim.py

🧑‍💻 Lancer l’attaquant + contrôleur
Sur la VM attaquante :
cd lab_keylogger/attacker
python3 server_attacker.py
Contrôleur disponible sur : http://127.0.0.1:5000

7️⃣ Scénarios de démonstration
🔹 1. Exfiltration simple
Lancer la victime et l’attaquant.
Sur la victime, ouvrir http://127.0.0.1:8000 et saisir plusieurs mots de passe.

Sur l’attaquant :
observer les événements dans le terminal ;
ouvrir http://127.0.0.1:5000, cliquer sur l’UUID de la victime ;
vérifier que les mots de passe apparaissent dans le tableau.

🔹 2. Résilience (panne de l’attaquant)
Laisser la victime tourner.
Arrêter server_attacker.py (Ctrl+C).
Sur la victime, saisir des mots de passe :
les événements sont ajoutés dans buffer/queue.jsonl.
Relancer server_attacker.py.
Retaper un mot de passe sur la victime :
les anciens événements sont d’abord renvoyés (vidage du buffer),
puis l’événement courant est exfiltré.

🔹 3. Commande à distance (start / stop capture)
Sur le contrôleur /victim/<victim_id>, vérifier que l’état est 🟢 ACTIVE.

Cliquer sur Stopper la capture :
l’état passe à 🔴 STOPPÉE ;
la victime affiche CAPTURE_ENABLED = False et “événement non exfiltré”.
Saisir des mots de passe sur la victime :
aucun nouvel événement n’apparaît côté attaquant.

Cliquer sur Activer la capture :
à la prochaine saisie, les événements sont de nouveau exfiltrés.


8️⃣ Limites & pistes d’amélioration
Keylogger limité au champ de mot de passe de l’application web (pas de hook clavier global).
Pas de chiffrement (HTTP simple, pas de TLS).
Pas encore de moteur d’analyse des logs (statistiques, détection de patterns, corrélation).
Pistes possibles :
ajout d’un mode TCP ou d’un chiffrement simple ;
règles de détection (mots-clés, longueur suspecte, etc.) ;
export CSV / dashboard plus avancé.

9️⃣ Avertissement légal
Ce projet est destiné à l’enseignement et à l’expérimentation encadrée.
Toute utilisation sur des systèmes réels sans accord explicite est susceptible d’être illégale et contraire à l’éthique de la cybersécurité.


A brief description of what this project does and who it's for

