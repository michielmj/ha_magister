# Magister login flow (discovery notes)

Verified against a live Magister tenant on **2026-11-09** (without credentials:
everything up to and including the username challenge). The school is written as
`school.magister.net` in this document. The flow is undocumented and can change; the
implementation is isolated in `custom_components/magister/api/auth.py` and
`api/login_page.py`.

Legend: **[live]** observed against the real service, **[bundle]** read from the
shipped JavaScript but not exercised, **[unverified]** assumed / community knowledge.

## 1. Where the client settings come from

`GET https://school.magister.net/oidc_config.js` **[live]** is a small JavaScript file
that returns the settings of the OpenID Connect client (oidc-client.js):

| Setting | Value |
|---|---|
| `authority` | `https://accounts.magister.net` |
| `client_id` | `M6-` + host name, e.g. `M6-school.magister.net` |
| `redirect_uri` | `https://school.magister.net/oidc/redirect_callback.html` |
| `silent_redirect_uri` | `https://school.magister.net/oidc/silent.html` |
| `response_type` | `id_token token` (implicit flow, no refresh token) |
| `scope` | `openid profile opp.read opp.manage attendance.overview attendance.administration calendar.user calendar.ical.user calendar.to-do.user grades.read grades.manage oso.administration registration.admin lockers.administration exams.administration enrollment.admin privacyportal.administration learningmaterials.user` |
| `acr_values` | `tenant:` + host name |

Everything but the scope follows from the host name; the implementation fetches
`oidc_config.js` and takes the `scope` from it (regex `scope:\s*'...'`), with the list
above as fallback. `https://school.magister.net/magister/settings.js` additionally holds
`apiKey: '4AF1'` / `apiKeyHeader: 'API-Client-ID'` for the web app; the data API worked
for the reference script without it, so we do not send it **[unverified for the new
flow, the reference script does not use it]**.

## 2. Request sequence

```
 1  GET  https://school.magister.net/oidc_config.js                  (once per MagisterAuth)

 2  GET  https://accounts.magister.net/connect/authorize
          ?client_id=M6-school.magister.net
          &redirect_uri=https%3A%2F%2Fschool.magister.net%2Foidc%2Fredirect_callback.html
          &response_type=id_token%20token
          &scope=<scope from step 1, space separated>
          &state=<random hex>&nonce=<random hex>
          &acr_values=tenant%3Aschool.magister.net
      -> 303 Location: https://accounts.magister.net/Account/Login?ReturnUrl=<enc>      [live]

 3  GET  that URL
      -> 302 Location: /account/login?sessionId=<32 hex>&returnUrl=<enc>               [live]
         Set-Cookie: XSRF-TOKEN=...           (secure, samesite=lax, readable by JS)
         Set-Cookie: Magister.Identities.XSRF=... (httponly)
         Set-Cookie: Magister.PresentationSessionCookie=... (httponly)

 4  GET  https://accounts.magister.net/account/login?sessionId=...&returnUrl=...
      -> 200 text/html: a tiny SPA shell with
         <base href="/"> and <script defer src="js/account-<hash>.js">                 [live]
         (a refreshed XSRF-TOKEN cookie is set again)

 5  GET  https://accounts.magister.net/js/account-<hash>.js          (~325 kB, cacheable)
      -> contains the authCode (see 3)

 6  POST https://accounts.magister.net/challenges/current            body = base         [live]
      -> 200 {"action":"username","tenantname":"<school name>","fidoAssertionOptions":{...},
              "expiresIn":900,"externalIdPs":[], ...}

 7  POST /challenges/username   body = base + {"action":"username","username":"..."}    [live: error shape]
      -> 200 {"action":"password",...}
      -> 400 {"error":"InvalidUsername", ...}                  (dummy user, observed)

 8  POST /challenges/password   body = base + {"action":"password","password":"...",
                                   "userWantsToPairSoftToken":false,"userSkippedFido":true}  [bundle]
      -> 200 {"redirectURL":"/connect/authorize/callback?..."}            (no 2FA)
      -> 200 {"action":"soft-token",...}                                  (2FA with TOTP)
      -> 400 {"error":"InvalidPassword"} (and others, see 5)

 9  POST /challenges/soft-token body = base + {"action":"soft-token","code":"123456"}   [bundle]
      -> 200 {"redirectURL":"..."}  |  400 {"error":"InvalidCode"|"IncorrectToken"|...}

10  GET  https://accounts.magister.net<redirectURL>
      -> 302 ... -> 302 Location:
         https://school.magister.net/oidc/redirect_callback.html
             #access_token=<jwt>&token_type=Bearer&expires_in=3600&scope=...&state=...
                                                                                       [bundle/community]
```

`base` is the JSON object `{"sessionId": <from step 3>, "returnUrl": <from step 3>,
"authCode": <see below>}` that the login SPA adds to **every** challenge POST. Headers
on the POSTs: `Content-Type: application/json`, `Accept: application/json` and
`X-XSRF-TOKEN: <value of the XSRF-TOKEN cookie>` **[live]** (without a valid code the
server answers `400 {"error":"AuthCodeValidation"}`).

`returnUrl` in the body is the query value after `decodeURI()` (so `%20` becomes a space
while escaped reserved characters such as `%3A` / `%2F` stay escaped). The
implementation mirrors this (`_decode_uri`).

Other `action` values seen in the bundle: `tenant`, `select-user`, `external-idp`,
`fido`, `pair-fido`, `skip-pair-fido-promo`, `pair-soft-token`, `hard-token`,
`recovery-code`, `change-password`, `reset-password`, `activate-user`,
`forgot-password`. The implementation supports `username`, `password` and `soft-token`;
anything else raises `MagisterAuthError("unsupported_login")`.

### Unverified in the live run (no credentials were available)
* the password and TOTP responses and the final redirect chain (steps 8 to 10);
* the TOTP step requires the account to have a "soft token" (authenticator app) paired;
* whether the password step ever returns a passkey promo (`pair-fido`) action. The code
  sends `userSkippedFido: true` to avoid that, which is an educated guess from the
  bundle (**open question for PM verification**).

## 3. The `authCode`

Magister sends an `authCode` with every challenge request. It is **not** in the HTML
page and **not** a server-generated nonce: it is a constant inside the login bundle
(`js/account-<hash>.js`), but deliberately obfuscated. Observed on 2026-11-09 (the
snippet is saved in `tests/api/fixtures/login_bundle_excerpt.js`):

```js
$c = ["authCode"], ...
(o = this.session.getSessionData())[$c[0]] =
  (a = ["49", "b701434d", "1d0a1a08", "e602"],
   ["2", "1"].map(function (t) { return a[parseInt(t) || 0]; }).join(""))
```

That is: take a string array, pick the entries named by an index list, concatenate.
Here the result is `a[2] + a[1]` (a 16-character hex string; two of the four fragments
are decoys). The value was accepted by the live service **[live]**: `challenges/current`
with it returned the username challenge, while a wrong value returned
`{"error":"AuthCodeValidation"}`.

**Extractor** (`login_page.extract_auth_code`): regex for

```
<var>=[ "str", "str", ... ] , [ "n", "n", ... ] .map( ... parseInt( ... ) ... ) .join("")
```

independent of variable names and quote style; fragments and index order are read from
the bundle, nothing is hard-coded. Fallback: a literal `authCode: "<hex>"`. If neither
matches, `MagisterApiError("Could not extract authCode ...")` is raised; this is the
first thing to look at when Magister changes the login page. If the server answers
`AuthCodeValidation` anyway, the code is re-scraped once and the login retried once.

The bundle URL contains a content hash, so the code is cached per bundle URL for the
lifetime of the `MagisterAuth` object and re-downloaded when the hash changes.

## 4. Silent renew

`GET /connect/authorize?...&prompt=none` (same parameters, new `state`/`nonce`) with the
`accounts.magister.net` session cookies:

* no session: `303 Location: https://school.magister.net/oidc/redirect_callback.html#error=login_required&state=...` **[live]**
* valid session: expected to redirect (possibly via `/connect/authorize/callback`) to the
  same URL with `#access_token=...` in the fragment **[unverified, needs PM check]**.

Redirects are followed manually (`allow_redirects=False`) because the token is in the
URL *fragment*, which HTTP clients drop on redirects.

## 5. Error codes (JSON `error` field, from the bundle)

| `error` | Mapped to |
|---|---|
| `InvalidUsername`, `InvalidPassword`, `InvalidUsernameOrPassword`, `UserHasNoAccess`, `NoUsername`, `NoPassword`, `UserBlocked`, `UserExpired`, `UserNotActivated`, `UserLockedOut`, `DeviceLockedOut`, `UserHasNoChallenges` | `MagisterAuthError("invalid_auth")` |
| `InvalidCode`, `IncorrectToken`, `TotpExpired`, `NoCode` | `invalid_totp` |
| `NoRedirectUrl`, `InvalidIdPSelected`, `IdPDisabled`, `SsoDisabled`, `NoPasswordChallenge` | `unsupported_login` |
| `AuthCodeValidation` | re-scrape the code once, then `MagisterApiError` |
| anything else | `MagisterApiError` |

SSO detection: a redirect (from authorize or from a challenge `redirectURL`) to a host
other than `accounts.magister.net` / the school host, or an unsupported `action`
(`external-idp`, `fido`, ...), raises `unsupported_login`.

## 6. Other observations

* The challenge response includes the school's display name as `tenantname`; we do not
  store or log it.
* `GET https://school.magister.net/api/account` without a token answers `403`.
* Only `accounts.magister.net` and the school host were needed. The JS bundle is served
  from `accounts.magister.net` itself (no CDN host). Third-party hosts referenced by the
  pages (fonts, analytics) are irrelevant to the flow.
* Request volume of this discovery: about 25 requests, no password was ever submitted.
