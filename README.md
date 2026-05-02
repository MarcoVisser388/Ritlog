# RitLog

RitLog is een webapplicatie die ik heb gebouwd om ritten bij te houden als vrachtwagenchauffeur. Ik werk bij een distributiecentrum en rij dagelijks naar verschillende filialen door heel Nederland. We hadden geen goede manier om dit digitaal bij te houden, dus heb ik dit zelf gebouwd.

## Waarom dit project?

Ik studeer HBO-ICT aan de Hogeschool van Amsterdam (deeltijd) en werk naast mijn studie als vrachtwagenchauffeur. Dit project heb ik gebouwd omdat ik iets wilde maken wat ik zelf echt gebruik. Elke dag vul ik mijn rit in — welke truck ik had, welke oplegger, welke filialen ik heb bezocht en hoe lang ik gewerkt heb.

De app draait op een Raspberry Pi die thuis staat. Via Cloudflare Tunnel is hij bereikbaar vanaf mijn telefoon, ook als ik onderweg ben.

## Wat kan de app?

- Rit invoeren met truck, oplegger, start- en eindtijd en pauze
- Meerdere filialen per rit toevoegen (in volgorde van bezoek)
- Schadefoto's uploaden met een omschrijving
- Overzicht van alle ritten, met statistieken per dag, week, maand of jaar
- Gewerkte uren worden automatisch berekend
- Beheerpagina voor trucks, opleggers, chauffeurs en filialen

## Hoe is het gebouwd?

**Backend:** Python met Flask  
**Database:** SQLite met 6 tabellen die via foreign keys aan elkaar gekoppeld zijn  
**Frontend:** HTML, CSS en JavaScript — mobile-first, want ik gebruik het op mijn iPhone  
**Hosting:** Raspberry Pi 4 thuis, bereikbaar via Cloudflare Tunnel  

De app valideert alle invoer — opleggernummers moeten beginnen met DD, ED, CDD of CED, postcodes moeten het juiste formaat hebben, enzovoort. Alle database queries gebruiken parameterized statements tegen SQL injection.

Beide services (Flask en Cloudflare) starten automatisch op als de Pi opstart via systemd.

## Lokaal draaien

```bash
git clone https://github.com/MarcoVisser388/Ritlog.git
cd Ritlog
pip install flask werkzeug
python3 app.py
```

Ga daarna naar `http://localhost:5000`.

## Over mij

Ik ben Marco Visser, deeltijdstudent HBO-ICT aan de Hogeschool van Amsterdam. Naast mijn studie werk ik als vrachtwagenchauffeur. Dit project is één van de eerste dingen die ik volledig zelf heb gebouwd en ook echt dagelijks gebruik.
