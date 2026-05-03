# RitLog

RitLog is een webapplicatie die ik heb gebouwd om ritten bij te houden als vrachtwagenchauffeur. Ik werk bij een distributiecentrum in Zwaagdijk-Oost en rij dagelijks naar verschillende Action filialen door heel Nederland. We hadden geen goede manier om dit digitaal bij te houden, dus heb ik dit zelf gebouwd.

## Waarom dit project?

Ik studeer HBO-ICT aan de Hogeschool van Amsterdam (deeltijd) en werk naast mijn studie als vrachtwagenchauffeur. Dit project heb ik gebouwd omdat ik iets wilde maken wat ik zelf echt gebruik. Elke dag vul ik mijn rit in — welke truck ik had, welke oplegger, welke filialen ik heb bezocht en hoe lang ik gewerkt heb.

De app draait op een Raspberry Pi die thuis staat. Via Cloudflare Tunnel is hij bereikbaar vanaf mijn telefoon, ook als ik onderweg ben.

## Wat kan de app?

- Rit invoeren met truck, oplegger, start- en eindtijd en pauze
- Meerdere filialen per rit toevoegen in volgorde van bezoek
- Schadefoto's uploaden met omschrijving
- Kilometerberekening via Google Directions API — de app berekent automatisch de rijafstand van het DC naar alle filialen en terug
- Overzicht van alle ritten met statistieken per dag, week, maand of jaar, inclusief pijltjes om terug te bladeren naar eerdere periodes
- Schade-indicator op ritkaarten zodat ritten met schade direct zichtbaar zijn
- Gewerkte uren worden automatisch berekend
- Drie rollen: admin, chauffeur en demo-account
- Beheerpagina voor trucks, opleggers, chauffeurs, filialen en gebruikers
- REST API endpoints zodat de data ook in Power BI te gebruiken is

## Hoe is het gebouwd?

**Backend:** Python met Flask

**Database:** SQLite met 7 tabellen die via foreign keys aan elkaar gekoppeld zijn: gebruikers, chauffeurs, trucks, opleggers, ritten, rit_filialen, schades en filialen

**Frontend:** HTML, CSS en JavaScript — mobile-first, want ik gebruik het dagelijks op mijn iPhone

**Hosting:** Raspberry Pi 4 thuis, bereikbaar via Cloudflare Tunnel. Beide services (Flask en Cloudflare) starten automatisch op als de Pi opstart via systemd

**Externe API:** Google Directions API voor de kilometerberekening. De API key staat in een .env bestand en komt niet in de code terecht

**BI:** Power BI Desktop gekoppeld via REST API endpoints (/api/ritten, /api/filialen, etc.)

De app valideert alle invoer — opleggernummers moeten beginnen met DD, ED, CDD of CED, postcodes moeten het juiste formaat hebben, eindtijd moet na de starttijd liggen, enzovoort. Alle database queries gebruiken parameterized statements tegen SQL injection. Wachtwoorden worden opgeslagen als bcrypt hash.

## Lokaal draaien

```bash
git clone https://github.com/MarcoVisser388/Ritlog.git
cd Ritlog
pip install flask werkzeug bcrypt python-dotenv requests
```

Maak een `.env` bestand aan in de projectmap met:

```
GOOGLE_API_KEY=jouw_key_hier
```

Start daarna de app:

```bash
python app.py
```

Ga naar `http://localhost:5000`. Standaard inloggegevens: admin / Mvisser1.

## Over mij

Ik ben Marco Visser, deeltijdstudent HBO-ICT aan de Hogeschool van Amsterdam. Naast mijn studie werk ik als vrachtwagenchauffeur bij een distributiecentrum. Dit project is één van de eerste dingen die ik volledig zelf heb gebouwd en ook echt dagelijks gebruik.
