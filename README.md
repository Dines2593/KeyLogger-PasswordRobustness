Keylogger pédagogique – Victime / Attaquant / Contrôleur

⚠️ Avertissement
Ce projet est réalisé exclusivement dans un cadre pédagogique, sur deux machines virtuelles isolées, pour comprendre les mécanismes d’exfiltration de données et de détection.
Il ne doit en aucun cas être utilisé sur des systèmes réels sans autorisation explicite.

🧩 Objectif du projet

Ce dépôt contient un mini-lab de keylogger “pédagogique” composé de :

une machine victime : faux vérificateur de robustesse de mot de passe en Flask ;

une machine attaquante : serveur Flask recevant les événements en JSON et les stockant ;

un contrôleur web : interface pour visualiser les logs et activer/désactiver la capture à distance.

L’infrastructure reproduit un scénario typique :

La victime saisit un mot de passe dans une application apparemment légitime.

Chaque saisie est envoyée à l’attaquant sous forme d’événement JSON.

L’attaquant stocke les logs, les affiche dans une interface web et peut envoyer des commandes à la victime.

Le tout est déployé sur 2 VMs Kali Linux en réseau interne (VirtualBox).

🏗 Architecture générale

Victime (VM1) Attaquant + Contrôleur (VM2)

Flask : app_victim.py Flask : server_attacker.py
• Faux "password checker" • Endpoint /logs pour recevoir les JSON
• Génération d'un UUID • Stockage des logs en JSONL
• Envoi JSON via HTTP POST ---> • Interface web :
• Tampon local (buffer) - liste des victimes
- vue détaillée des événements
- boutons Activer / Stopper la capture

Protocole : HTTP

Format des événements : JSON (1 event = 1 objet JSON)

Résilience : tampon local côté victime si l’attaquant est indisponible

📁 Arborescence du dépôt

lab_keylogger/
├── attacker/
│ └── server_attacker.py # Serveur Flask + contrôleur web
└── victim/
└── app_victim.py # Appli Flask sur la victime (fake password checker)

Les dossiers logs/, buffer/, commands/ et le fichier uuid.txt sont générés au runtime et ne sont pas nécessaires pour lancer le projet.

✅ Fonctionnalités principales
Côté victime (victim/app_victim.py)

Application Flask exposée sur http://127.0.0.1:8000.

Interface web : “vérificateur pédagogique de mot de passe”.

À chaque frappe dans le champ mot de passe :

calcul d’un score de robustesse (strength_score, strength_label) ;

construction d’un événement JSON :

{
"victim_id": "<UUID>",
"timestamp": <epoch>,
"password": "<mot de passe saisi>",
"strength_score": 0..4,
"strength_label": "Très faible" | "Faible" | "Moyen" | "Fort" | "Très fort"
}

envoi via HTTP POST à http://<IP_ATTAQUANT>:5000/logs.

Génération et persistance d’un UUID dans uuid.txt (identifie la victime).

Tampon local (buffer/queue.jsonl) :

si l’envoi échoue (attaquant down), l’événement est écrit dans le buffer ;

à chaque nouvelle frappe, la victime tente de vider le buffer (flush_buffer()).

Prise en compte des commandes du contrôleur :

la victime interroge /api/commands/<victim_id> sur l’attaquant ;

si capture_enabled = false, l’UI continue à fonctionner mais aucun événement n’est exfiltré.

Côté attaquant / contrôleur (attacker/server_attacker.py)

Serveur Flask exposé sur http://<IP_ATTAQUANT>:5000.

Endpoint /logs :

reçoit les événements JSON depuis la victime ;

stocke chaque event dans : logs/<victim_id>/<YYYY-MM-DD>.log (format JSONL).

Contrôleur web :

GET / :

liste des victimes actives (dossiers présents dans logs/) ;

GET /victim/<victim_id> :

affiche l’historique des événements pour une victime ;

rafraîchissement automatique toutes les 5 secondes ;

indique l’état de la capture (ACTIVE / STOPPÉE) ;

propose 2 boutons :

Activer la capture

Stopper la capture

GET /api/commands/<victim_id> :

renvoie l’état courant des commandes (JSON) ;

POST /api/commands/<victim_id> :

met à jour capture_enabled pour la victime ciblée.

Les commandes sont stockées dans commands/<victim_id>.json.

🧪 Déploiement du lab (résumé)

Exemple :
Victime = 192.168.30.133
Attaquant = 192.168.30.132
Les deux VMs sont en réseau interne dans VirtualBox.

1. Pré-requis

Sur les deux VMs :

sudo apt update
sudo apt install -y python3 python3-pip
pip3 install flask requests

2. Lancer la victime

Sur la VM victime :

cd lab_keylogger/victim
python3 app_victim.py

L’appli écoute sur http://127.0.0.1:8000.

Ouvrir un navigateur sur la victime : http://127.0.0.1:8000.

3. Lancer l’attaquant + contrôleur

Sur la VM attaquante :

cd lab_keylogger/attacker
python3 server_attacker.py

L’API et le contrôleur sont accessibles sur :

http://127.0.0.1:5000 (depuis l’attaquant)

http://192.168.30.132:5000 (depuis la victime, si besoin)

🔍 Scénarios de démonstration
1. Exfiltration simple

Lancer la victime et l’attaquant.

Sur la victime, saisir plusieurs mots de passe.

Sur l’attaquant :

observer dans le terminal les événements reçus ;

ouvrir http://127.0.0.1:5000 puis cliquer sur l’UUID de la victime ;

vérifier que les mots de passe apparaissent dans le tableau.

2. Résilience (panne de l’attaquant)

Laisser la victime tourner.

Arrêter server_attacker.py sur l’attaquant (Ctrl+C).

Saisir des mots de passe sur la victime :

les événements sont ajoutés au buffer (buffer/queue.jsonl).

Relancer server_attacker.py.

Saisir un nouveau mot de passe sur la victime :

la victime vide d’abord le buffer (renvoi des anciens events),

puis envoie l’événement courant.

3. Commande à distance (start / stop capture)

Sur le contrôleur (/victim/<victim_id>), vérifier que l’état est ACTIVE.

Cliquer sur Stopper la capture :

l’état passe à STOPPÉE ;

la victime affiche CAPTURE_ENABLED = False et “événement non exfiltré”.

Tapoter des mots de passe :

aucun nouvel event n’apparaît côté attaquant.

Cliquer sur Activer la capture :

l’exfiltration reprend dès la prochaine saisie.

🚧 Limites et pistes d’amélioration

Le keylogger est limité au champ de mot de passe de l’application web (pas de hook global du clavier).

Les communications HTTP ne sont pas chiffrées (pas de TLS).

Les logs ne sont pas encore enrichis d’analyses (statistiques, détection de patterns, règles de corrélation).

Des commandes supplémentaires pourraient être ajoutées :

changement de mode d’exfiltration (HTTP / TCP) ;

suppression remote des logs ;

déclenchement de captures ponctuelles, etc.

⚠️ Usage responsable

Ce projet a été développé dans le cadre d’un TP de sécurité sur deux machines virtuelles isolées.
Il est destiné à illustrer les concepts de :

keylogging,

exfiltration de données,

résilience en présence de pannes,

contrôle à distance d’un agent compromis.

Toute utilisation en dehors d’un environnement contrôlé et autorisé serait contraire à l’éthique et potentiellement illégale.
