# ZÆNIA — Module 1: rules, authentication and moral code

This update implements the foundation backend and a nested moral-code module. It is built from the source review you supplied. It contains complete replacement files and an offline Scripture corpus. The separate UI chat continues to own layout and animation.

## Install once

1. Stop ZÆNIA and its API process so they can reload the new modules.
2. Extract this ZIP to a separate folder. Keep the `payload` folder beside `install_module1.py`.
3. Open PowerShell in that extracted folder and run:

```powershell
py -3.11 .\install_module1.py --project "C:\Projects\ZAENIA"
```

The installer selects the existing `.venv` or `venv`, or your active virtual environment. If none exists, it creates a project `.venv`. An optional `--python` argument can select your project interpreter explicitly. It installs the listed free dependencies, backs up every source file it replaces, and runs **one combined confirmation check**. Enter your passkey only in the local terminal. Existing installations receive one hidden passkey prompt during activation. First-time setup asks you to create and confirm a private phrase before activation.

Successful completion prints `Module 1 installed and verified.` Share only the outcome or error text. Keep passphrases, client tokens and biometric records private.

## What changed

| Component | Behavior |
|---|---|
| Owner authentication | Argon2 passkey verification, persistent attempt limiting, hidden local input, no password-echo fallback |
| Sessions | Expiring owner sessions; changing the credential or logging out revokes them |
| Sensitive operations | One-use fresh authentication bound to the exact action and parameters |
| Rules | Exact operation scopes, actual deny/reauth enforcement, protected hard rules; unknown actions fail closed |
| Permanent file deletion | A registered executor needs fresh authentication and two owner confirmation proofs |
| API clients | Existing token hash remains compatible; explicit create, rotation and revocation; fixed conversation/CarPlay capabilities |
| Moral code | Your original statement, clarifications and ten protected principles; owner notes are editable after fresh authentication |
| Scripture | Offline original-language words, transliterations, glosses, lexical/morphology fields, witnesses and variant information; ASV/WEB comparisons and surrounding chapters |
| Context | Historical time, situation, culture and people remain explicit fields; missing evidence is disclosed and documented review can be saved encrypted |
| Storage | Atomic encrypted writes, scoped encryption keys, private OS permissions, logs containing safe metadata rather than raw messages |
| Recovery | Encrypted portable policy backup and validated restore; versioned encrypted policies before migration |
| Launchers | `main.py`, `start.py` and `foundation_main.py` use the same working CLI |

Soft `allow` rules never create permissions or override denials. Rule descriptions and model prose do not create executable commands. A moral `ALLOW` never authenticates the owner or authorizes a tool.

## Complete installed layout

The update supplies these files. Existing project files outside this list remain part of your original project.

```text
C:\Projects\ZAENIA\
  main.py
  start.py
  foundation_main.py
  requirements-module1.txt
  build_scripture_corpus.py
  core\
    api\
      auth.py
      chat_routes.py
      server.py
    foundation\
      foundation_main.py
      lifecycle.py
      client_gate.py
      self_test.py
      auth\
        passkey.py
        session.py
        voice_passkey.py
      rules\
        models.py
        vault.py
        policy.py
        engine.py
      security\
        io.py
        crypto.py
        audit.py
      storage\
        paths.py
      moral_code\
        __init__.py
        charter.json
        engine.py
        vault.py
        scripture_context.py
  data\
    scripture\
      corpus.sqlite3
      corpus_manifest.json
      STEPBible_README.md
      CC-BY-4.0.txt
      eng-asv_about.htm
      eng-web_about.htm
  docs\module1\
    README.md
    PROGRESS.md
    INTEGRATION.md
    THIRD_PARTY_NOTICES.md
```

Activation adds encrypted `moral_code.vault` to `data\secure`. Context notes use `scripture_context.vault`. Attempt limiting uses `auth_attempts.sqlite3`. Existing passkey hashes, master salt, API token hash and speaker enrollment data are retained. Encrypted policy snapshots are kept under `data\secure\policy_versions`; source backups are kept under `module1_backups`.

## Your moral compass

The protected charter preserves your words and clarifications. God's love and Christ's example are central. Humans retain dignity as God's image, can grow together despite imperfection, and must protect life and relationships, including care for animals and nature. Accountability serves protection. The assistant cannot pronounce final spiritual condemnation, claim divine authority, or impose atonement.

The deterministic evaluator rejects proposed coercion, exploitation, manipulation, vengeance, dehumanization, concealment of abuse, forced reconciliation/contact with an abuser, needless harm and final spiritual punishment. Undefined labels need context. Evidence and protective, proportionate purposes are required for accountability. Urgent protective guidance can be evaluated without a loaded corpus; urgency never bypasses execution permissions.

The evaluator checks structured, reviewed assessments. It is not a semantic detector for every sentence. A model's claim that facts are confirmed is insufficient: consequential registered actions require a fresh, exact owner moral-review grant. Chat generation receives the compass as guidance; generated prose is advisory and remains capable of mistakes.

## Scripture coverage

The declared corpus contains the 39 Hebrew/Aramaic Old Testament books and all 27 New Testament books. This includes the complete Psalms, Proverbs, Ecclesiastes and Song of Songs within that corpus. It holds **447,744 word records** and compares **American Standard Version 1901** with **World English Bible Classic**. Textual variant and alternate reference information is retained instead of silently merging witnesses into one supposedly definitive original text.

Original-language coverage for deuterocanonical books is not included. The source WEB download includes additional books; their omission from this declared 66-book corpus is recorded explicitly in the manifest. This is a source collection with named editions, not a claim to possess the original autographs or every Christian canon.

Scripture retrieval returns the requested words, both translations and the preceding, current and following chapters. Historical/cultural interpretations are not invented. Those fields report missing context until sourced review is recorded. The full corpus is available for searching; no exhaustive automatic classification of every passage about God's love is claimed.

## Everyday commands

Run commands from the project root with your project Python interpreter. These are management/reference commands, not additional confirmation tests:

```powershell
python .\foundation_main.py rules
python .\foundation_main.py moral-code
python .\foundation_main.py scripture 1Jn.4.8
python .\foundation_main.py scripture-search "God is love"
python .\foundation_main.py add-soft-rule --name "Calendar review" --description "Require a fresh owner decision" --action require_reauth --operation calendar.write
python .\foundation_main.py backup "D:\PrivateBackups\ZAENIA-policy.zaebackup"
python .\foundation_main.py api-token status
```

`moral-notes --file notes.json` accepts a JSON array of notes. `scripture-context --file context.json` accepts `reference`, `passage_context`, `historical_time`, `situation`, `culture`, `people` and a nonempty `sources` array. Each field must state evidence or uncertainty. The notes are encrypted after exact owner authentication. Use STEP references such as `Gen.1.27`, `Psa.103.1`, `Pro.18.13`, `Luk.6.36` and `1Jn.4.8`.

API token commands support `create`, `rotate`, `revoke` and `status`. Rotation shows a new token once locally and invalidates the old token. Revocation blocks future requests using it. Pair the client with the new token locally when rotating; do not paste tokens into chat.

Start the API with `python -m core.api.server server`. The owner authenticates the service at startup. Token clients can converse and use the existing CarPlay endpoints; they cannot change rules, morals or credentials, delete files, or acquire an owner session. Policy changes stop protected requests until the service is restarted and approved again. A direct unconfigured ASGI launch fails closed for protected operations.

## Backup and recovery

Policy backups contain encrypted rules/moral/context files and their original master salt inside a second, independently salted encrypted envelope. They contain no raw passphrase, API token, recording, speaker embedding or primary passkey hash. Keep your passphrase and other subsystem recovery material available separately. The backup file can be copied to your preferred cloud storage after creation; this package does not connect a cloud account.

`restore` verifies the envelope and protected policy before writing, keeps current owner authentication in force, and rejects a conflicting master salt that could damage other encrypted modules. Restore is an explicit owner recovery operation: editable denials do not lock you out of restoring a known-good protected policy. It does not reset or recover a forgotten passphrase. Primary passphrase rotation across unknown encrypted subsystems is intentionally not exposed here.

## Verification and remaining integration

The package passed **42 isolated security checks**, including legacy cipher compatibility, fresh-auth forgery/replay/expiry, rule mutation, policy tampering, token rotation/revocation, scoped HTTP guards, corpus coverage and encrypted recovery. Python 3.11 syntax and Windows x64 dependency availability were checked. Windows ACL application and physical voice/device behavior are checked on your actual installation, not claimed from the development container.

The installer checks payload hashes, backs up changed source, and restores copied files if a copy fails. It never installs a file into `data\secure`. The combined activation validates existing encrypted rules, adds protected moral policy, and applies private OS permissions. Hashes detect corruption; they are not an independent publisher signature.

The provided foundation and API entry points are integrated. Source for the full brain, voice listener, scheduler and file/calendar executors was not in the review ZIP. Their future tool calls must register trusted handlers with `RuleEngine` as described in `INTEGRATION.md`. Existing speaker profiles are preserved; live biometric acceptance, replay resistance and audio-device calibration remain part of the existing voice workflow. This foundation does not claim to sandbox arbitrary trusted Python code or a compromised operating-system account.

## Dependencies and cost

Argon2-cffi, cryptography, FastAPI, Pydantic, Starlette, Uvicorn and HTTPX are free open-source libraries. Python's standard library handles storage, SQLite, the installer and backups. The corpus sources are openly licensed/public-domain material with attribution in `THIRD_PARTY_NOTICES.md`. No paid API or cloud subscription is required for this module. Your existing optional Vosk, SoundDevice and speaker-verification libraries continue to handle voice hardware and models.
