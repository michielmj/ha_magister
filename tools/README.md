# Verification tool: `magister_cli.py`

Checks on your own computer that the Magister login and agenda access work for your
account, and can write an **anonymized** dump of the data that developers need for
fixtures. Nothing is sent anywhere except to your school's Magister servers.

## 1. Get the code

Either clone the branch:

```
git clone --branch claude/jolly-mayer-i2h3oo https://github.com/michielmj/ha_magister.git
cd ha_magister
```

or on GitHub choose branch `claude/jolly-mayer-i2h3oo`, then Code > Download ZIP, unzip it
and open a terminal in the unzipped folder.

## 2. Install (once)

You need Python 3.12 or newer (3.14 preferred). Use **Terminal** (macOS/Linux) or
**PowerShell / cmd** (Windows). Do **not** use Git Bash or mintty: the hidden password
prompt does not work there.

macOS / Linux:

```
python3 -m venv .venv-magister
.venv-magister/bin/pip install aiohttp pyotp
```

Windows (PowerShell):

```
py -m venv .venv-magister
.venv-magister\Scripts\pip install aiohttp pyotp tzdata
```

## 3. Run

macOS / Linux:

```
.venv-magister/bin/python tools/magister_cli.py --tenant <school> --username <login> --dump dump-school1
```

Windows (PowerShell):

```
.venv-magister\Scripts\python tools\magister_cli.py --tenant <school> --username <login> --dump dump-school1
```

`<school>` is the first part of your Magister address (`myschool` for
`myschool.magister.net`). The password is asked with hidden input (nothing appears while
you type). It is never taken from the command line and never printed. Add `-v` for
more diagnostics (still without secrets).

### Accounts with 2FA (authenticator app)

The tool needs the **base32 secret** of the authenticator app, the text you can copy or
the QR code's "manual entry key" when you (re)pair the app in Magister (looks like
`JBSW Y3DP EHPK 3PXP`). It cannot use a 6-digit code.

* `--totp-prompt`: asks for the secret with hidden input (recommended).
* `--totp-secret-env VAR`: reads it from environment variable `VAR`. Be careful: typing
  `export VAR=...` or `$env:VAR="..."` puts the secret in your shell history.
  Prefer `--totp-prompt`.

## 4. What the output means

1. `[1/4] Logging in ... OK via login`: username, password (and TOTP) were accepted.
   If it fails you see `LOGIN FAILED (code)` and Magister's own error name, e.g.
   `UserLockedOut`. Do not retry many times: repeated wrong passwords can lock the
   account. The tool itself never retries a failed password.
2. `[2/4] Account and children`: the account type (`Ouder` = parent) and the children.
3. `[3/4] This week's agenda`: each lesson/appointment of this week per child, followed
   by `<status=.. info=.. type=..>`, Magister's raw codes. Please check that the week
   is correct (compare with the Magister website).
4. `[4/4] Second token fetch`: `Silent renew WORKED` is the best case. `did NOT work`
   means a full login was needed instead (not an error, but please report the reason).

## 5. The dump

With `--dump DIR` these files appear in `DIR`:

* `account.json`, `children.json`
* `appointments-kind-a.json` (and `-kind-b`, ...): the data for one week back to three weeks ahead
* `appointments-kind-a-without-status-filter.json`: the same without the `status=1` filter
  (shows whether cancelled lessons are hidden by it)
* `observed-codes.json`: counts of the Status/InfoType/Type codes

Names are replaced (`Ouder`, `Kind A`), IDs are fake numbers, teachers are `Docent N`,
the school becomes `school.example`, e-mail addresses and links are removed.
**Before sharing, open the files and skim `Omschrijving`, `Inhoud` and `Opmerking` for
names of people** (pupils, teachers, parents) that the tool could not recognize, and
edit them out. Then send the folder to the developer.
