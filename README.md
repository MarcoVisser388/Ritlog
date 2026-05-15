# 🚛 RitLog

> Een mobiele webapplicatie die het papieren rittenboek vervangt voor vrachtwagenchauffeurs.

![RitLog Login](screenshots/ritlog1.jpeg)

---

## 📖 Wat is RitLog?

RitLog is gebouwd vanuit een echte werkpraktijk. Als vrachtwagenchauffeur bij een distributiecentrum in Zwaagdijk-Oost reed ik dagelijks naar verschillende Action filialen door heel Nederland. Het bijhouden van ritten, werktijden en schades ging altijd op papier — totdat ik dit zelf digitaal heb gebouwd.

De app vervangt het papieren rittenboek volledig en biedt een overzichtelijke, mobielvriendelijke oplossing voor het registreren van alles wat een chauffeur dagelijks bijhoudt.

---

## 📱 Screenshots

| Login | Overzicht | Rit details |
|-------|-----------|-------------|
| ![Login](screenshots/ritlog1.jpeg) | ![Overzicht](screenshots/ritlog4.jpeg) | ![Details](screenshots/ritlog3.jpeg) |

| Schade registratie | Schade rapport |
|-------------------|----------------|
| ![Schade](screenshots/ritlog2.jpeg) | ![Rapport](screenshots/ritlog5.jpeg) |

---

## ✨ Functies

- 🗓️ **Ritten registreren** — datum, voertuig, oplegger, chauffeur en bezochte filialen
- ⏱️ **Werktijden bijhouden** — starttijd, eindtijd, pauze en automatisch berekende gewerkte uren
- 📍 **Kilometerberekening** — automatisch via Google Maps API op basis van bezochte filialen
- 📸 **Schaderegistratie** — foto's uploaden met beschrijving, onderscheid tussen nieuwe en bestaande schades
- 📄 **PDF schaderapportages** — direct deelbaar vanuit de app
- 📊 **Power BI koppeling** — managementdashboard voor overzicht over alle chauffeurs
- 👤 **Accountbeheer** — meerdere chauffeurs kunnen inloggen met eigen account
- 📅 **Overzichten** — dag, week, maand en jaar weergave

---

## 🛠️ Technologie

| Categorie | Technologie |
|-----------|-------------|
| Backend | Python Flask |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript |
| Kaarten & Kilometers | Google Maps API |
| Hosting | Raspberry Pi (thuis) |
| Bereikbaar via | Cloudflare Tunnel |
| Rapportages | PDF generatie |
| Dashboard | Microsoft Power BI |
| Versiebeheer | Git / GitHub |

---

## 🏗️ Architectuur

```
RitLog/
├── app.py              # Flask applicatie & routes
├── ritten.sqbpro       # SQLite database
├── static/             # CSS, JavaScript, afbeeldingen
├── templates/          # HTML templates (Jinja2)
└── uploads/            # Geüploade schadefotos
```

---

## 🚀 Lokaal draaien

### Vereisten
- Python 3.x
- pip

### Installatie

```bash
# Repository klonen
git clone https://github.com/MarcoVisser388/Ritlog.git
cd Ritlog

# Virtuele omgeving aanmaken
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Afhankelijkheden installeren
pip install -r requirements.txt

# Applicatie starten
python app.py
```

De app is dan bereikbaar op `http://localhost:5000`

---

## 💡 Waarom dit project?

Ik studeer HBO-ICT aan de Hogeschool van Amsterdam (deeltijd) en werk naast mijn studie als vrachtwagenchauffeur. Elke dag vulde ik mijn rit in — welke truck, welke oplegger, welke filialen, hoe laat begonnen en gestopt. Dat ging allemaal op papier of in losse notities.

Dit project heb ik gebouwd omdat ik iets wilde maken dat ik zelf écht gebruik. Geen tutorial-project, maar een echte oplossing voor een echt probleem.

---

## 👨‍💻 Over de ontwikkelaar

**Marco Visser**  
HBO-ICT Student @ Hogeschool van Amsterdam  
Vrachtwagenchauffeur @ Distributiecentrum Zwaagdijk-Oost

🌐 [threshold-dev.nl](https://threshold-dev.nl)  
💼 [LinkedIn](https://www.linkedin.com/in/marco-visser-20664b11a/)  
🐙 [GitHub](https://github.com/MarcoVisser388)  
📧 vissermarco@live.nl

---

*Gebouwd met Python Flask, draaiend op een Raspberry Pi thuis.*
