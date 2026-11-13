# Magister voor Home Assistant

Nederlands | [English](README.md)

Toon de schoolagenda van je kind uit [Magister](https://www.magister.nl/) in Home Assistant: een
agenda per kind, plus optionele sensoren met de starttijd van de eerste afspraak van een dag
(handig voor een wekker).

> **Onofficieel.** Dit project is niet verbonden aan, goedgekeurd door of ondersteund door Iddink
> of Magister. Het meldt zich aan zoals een browser dat doet en kan dus stoppen met werken als
> Magister de aanmelding wijzigt. Gebruik op eigen risico.

## Wat je krijgt

- Een agenda **Agenda** per kind (apparaat `Kind (myschool)`), met lessen, huiswerk, toetsen,
  vervallen lessen en schoolactiviteiten. Standaard van een week terug tot drie weken vooruit,
  elke 30 minuten ververst (beide instelbaar).
- Optionele **sensoren voor de eerste afspraak** (een tijdstempel) voor automatiseringen.
- De titels komen uit Magister met deze labels:

| Titel | Betekenis |
|---|---|
| `[Vervallen] wiskunde` | les vervalt |
| `[Huiswerk] wiskunde` | les met huiswerk |
| `[Proefwerk]`, `[Tentamen]`, `[SO]`, `[MO]`, `[Informatie]` | proefwerk, tentamen, schriftelijke/mondelinge overhoring, informatie |

Labels worden gecombineerd, bijvoorbeeld `[Vervallen] [Huiswerk] scheikunde`. Geeft Magister geen vak, dan wordt het
eerste deel van de omschrijving als titel gebruikt (en `Afspraak` als die leeg is). De beschrijving van een afspraak toont het lesuur, een
opmerking bij verplaatste of vervallen lessen, de docenten en de huiswerktekst.

## Vereisten

- Home Assistant **2026.10.4** of nieuwer.
- Een Magister-account van een ouder of leerling met **gebruikersnaam en wachtwoord**. Accounts
  die alleen via school-SSO (Entree, Microsoft, Google) of een passkey kunnen inloggen worden niet
  ondersteund.
- Alleen bij een account met tweestapsverificatie (authenticator-app): het **authenticator-
  geheim**. Dat is de base32-tekst (letters en cijfers) die Magister naast de QR-code toont bij
  het instellen van de authenticator-app. Magister toont die alleen tijdens het instellen, dus
  waarschijnlijk moet je de authenticator opnieuw koppelen (nieuwe QR-code en geheim) en het
  geheim noteren. Het nieuwe geheim vervangt de oude koppeling: voeg het ook toe aan je eigen
  authenticator-app.

## Installatie

### Met HACS (aanbevolen)

1. Installeer eerst HACS als je dat nog niet hebt gedaan, volgens de officiële handleiding:
   <https://hacs.xyz/docs/use/download/download/> (in Home Assistant 2026.2 en nieuwer heten
   add-ons *apps*).
2. Open in HACS het drie-puntjesmenu en kies **Aangepaste repositories**.
3. Vul `https://github.com/michielmj/ha_magister` in, kies het type **Integratie** en dan
   **Toevoegen**.
4. Zoek in HACS naar **Magister**, kies **Downloaden** en herstart Home Assistant.
5. Ververs je browser (harde verversing) zodat de nieuwe integratie en het icoon verschijnen.

### Handmatig

Kopieer de map `custom_components/magister` uit deze repository naar
`config/custom_components/magister` in Home Assistant, herstart Home Assistant en ververs de browser.

## Instellen

1. Ga naar **Instellingen > Apparaten & services > Integratie toevoegen** en kies **Magister**.
2. Vul de school in (`myschool`, `myschool.magister.net` of het webadres), de gebruikersnaam en het
   wachtwoord. Bij tweestapsverificatie vul je ook het authenticator-geheim in.
3. Kies bij een ouderaccount de kinderen die een agenda moeten krijgen.

Elke Magister-login is één vermelding. Je kunt meer logins toevoegen, ook voor dezelfde school
(bijvoorbeeld beide ouders), en logins voor andere scholen. Hetzelfde account kan niet twee keer
worden toegevoegd.

### Opties

**Configureren** op de integratiepagina wijzigt de kinderen (voegt ook hun agenda's en sensoren
toe of verwijdert ze), de weken terug (0 tot 8), de weken vooruit (1 tot 12) en het
verversingsinterval (15 tot 360 minuten). Opslaan laadt de integratie opnieuw, zonder opnieuw in
te loggen.

## Sensoren voor de eerste afspraak

Er wordt niets automatisch aangemaakt. Kies op de integratiepagina **Sensor voor eerste afspraak
toevoegen** (naast **Configureren**):

1. Kies het kind en de dagverschuiving (0 = vandaag, 1 = morgen, ...). De dag moet binnen het
   opgehaalde venster liggen: hooguit `7 x weken vooruit - 1` dagen vooruit (20 bij de standaard
   van 3 weken).
2. Kies de vakken die niet meetellen, bijvoorbeeld `Franse taal`. De lijst toont vakken uit de
   huidige agenda van het kind en je kunt ook andere namen typen. Een vak komt overeen als de hele
   naam gelijk is, zonder onderscheid tussen hoofd- en kleine letters.

De sensor (apparaatklasse `timestamp`, op het apparaat van het kind, bijvoorbeeld
`sensor.kind_myschool_eerste_afspraak_vandaag`) toont de start van de eerste afspraak met een
tijd op die dag die niet vervalt en niet is uitgesloten. Lessen, schooltoetsen en
schoolactiviteiten tellen mee; afspraken voor de hele dag niet. Attributen: `date`, `end`,
`subject`, `summary`, `location`, `lesson_hours` en `skipped` (het aantal vervallen of
uitgesloten afspraken ervoor).

De status is **`unknown`** (onbekend) als er zo'n afspraak niet is (weekend, vakantie, alles
vervalt of is uitgesloten) of als de dagverschuiving niet meer in het venster past (een
reparatiemelding legt dat uit). De verschuiving telt kalenderdagen, dus op vrijdag is 1 zaterdag.
De sensor wordt bij elke verversing en om middernacht bijgewerkt, zonder extra verzoeken aan
Magister. Elke sensor kun je apart wijzigen (opnieuw configureren) en verwijderen.

### Voorbeelden voor automatiseringen

De sensor is een tijdstempel, dus de trigger **Tijd** kan er relatief aan vuren. Een wekker 1,5
uur voor de eerste les van vandaag (sensor met verschuiving 0):

```yaml
triggers:
  - trigger: time
    at:
      entity_id: sensor.kind_myschool_eerste_afspraak_vandaag
      offset: "-01:30:00"
actions:
  - action: script.wake_up
```

Bij een vroege les wil je misschien de avond ervoor een wekker: gebruik de sensor "morgen"
(verschuiving 1) met een grote negatieve offset, bijvoorbeeld `"-14:00:00"` (14 uur voor de
eerste les van morgen).

Vuistregel: kies de sensor waarvan de dag de doeldag is op het moment dat de trigger vuurt. Een
sensor "vandaag" schuift om middernacht door naar de volgende dag, dus een wekker om 06:45 voor
de les van vandaag hoort bij de sensor met verschuiving 0 en een wekker de avond ervoor bij de
sensor met verschuiving 1.

**Voeg voor belangrijke wekkers een reserve toe.** De sensoren en agenda's houden de laatste goede
gegevens tot 24 uur vast als Magister of je internet uitvalt, dus een korte storing annuleert een
geplande wekker niet. Na 24 uur zonder geslaagde verversing worden ze niet beschikbaar. Voor een
eerste les die je niet mag missen: zet er ook een wekker op een vaste tijd naast.

## Gedrag

- Standaard elke 30 minuten verversen; het hele venster wordt in één keer opgehaald.
- Bij een storing blijven de gegevens tot 24 uur beschikbaar, daarna worden ze niet beschikbaar.
- Vervallen lessen blijven zichtbaar met `[Vervallen]` en worden door de sensoren overgeslagen.
- Verplaatste lessen krijgen een opmerking in de beschrijving.
- Alleen de schoolagenda wordt gelezen. Er wordt niets naar Magister geschreven.

## Problemen oplossen

- **Opnieuw inloggen bij Magister** (kaart op de integratiepagina): de login werkt niet meer,
  meestal na een wachtwoordwijziging. Vul het nieuwe wachtwoord in (en alleen een nieuw
  authenticator-geheim als dat veranderd is). De integratie logt dan precies één keer in. Wil je
  bewust de gebruikersnaam of het geheim wijzigen, gebruik dan **Opnieuw configureren** in het
  drie-puntjesmenu van de vermelding. Beide accepteren alleen hetzelfde Magister-account.
- **Inloggen geblokkeerd / "Inloggen bij Magister is geblokkeerd na herhaalde fouten"**: om te
  voorkomen dat je account op slot gaat, stopt de integratie na herhaalde fouten met proberen.
  Los de oorzaak op (wachtwoord, netwerk) en **laad de integratie opnieuw** (drie-puntjesmenu):
  dat probeert het nog één keer. Klopt het wachtwoord niet, gebruik dan Opnieuw configureren of de
  kaart voor opnieuw inloggen.
- **Reparatie "Magister heeft de loginpagina gewijzigd"**: Magister heeft de loginpagina's
  aangepast. Werk de integratie bij in HACS; blijft het probleem, meld het dan als issue.
- **Reparatie "Sensor voor eerste afspraak buiten het venster"**: een sensor kijkt verder vooruit
  dan de weken vooruit toelaten. Verhoog **Weken vooruit** of wijzig de sensor.
- **Logs**: Instellingen > Systeem > Logs, filter op `magister`. Voor meer detail zet je dit in
  `configuration.yaml` en herstart je:

  ```yaml
  logger:
    logs:
      custom_components.magister: debug
  ```

- **Diagnostiek**: op de integratiepagina, drie-puntjesmenu, **Diagnostiek downloaden**. Het
  bestand bevat opties, aantallen en de loginstatus; gebruikersnamen, wachtwoorden, geheimen,
  tokens, namen, id's en de schoolhost zijn verwijderd.

**Plaats nooit namen, schermafbeeldingen met namen of wachtwoorden in een issue.** Voeg het
diagnostiekbestand toe en haal persoonlijke gegevens uit logs zelf weg.

### Controle vanaf de opdrachtregel

[`tools/magister_cli.py`](tools/README.md) test de login en agenda vanaf je eigen computer, zonder
Home Assistant, en kan een geanonimiseerde dump schrijven. Lees eerst
[`tools/README.md`](tools/README.md) (in het Engels); het wachtwoord wordt met verborgen invoer
gevraagd.

## Privacy en beveiliging

- Je gebruikersnaam, wachtwoord en authenticator-geheim staan in de config entry van Home
  Assistant (`config/.storage`), net als bij andere integraties. Bescherm je back-ups.
- Ze worden nooit in logs geschreven; diagnostiek verbergt ze.
- Gegevens gaan alleen tussen je Home Assistant en Magister (de Magister-server en de loginservice
  van je school). Er is geen andere server en er is geen analyse.
- Bescherming tegen blokkade: na een mislukte login of herhaalde serverfouten wacht de integratie
  en probeert niet opnieuw met het wachtwoord; ze stopt helemaal als een poging kan meetellen voor
  een blokkade, tot je de integratie opnieuw laadt of opnieuw verifieert.

Meld beveiligingsproblemen privé, zie [SECURITY.md](SECURITY.md).

## Ontwikkeling

Ontwerp- en planningsdocumenten staan in [`docs/`](docs/) (Engels). Beheerder: `michielmj`.
Licentie: MIT.
