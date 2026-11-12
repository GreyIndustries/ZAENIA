# ZAE's phone line: setup guide

This gives ZAE her own phone number that you can **call** and **text**. It also makes her the **answering service for your own number**, and lets her **call people showing your number**. Her brain, voice and memory stay on your PC. A phone company called Twilio provides the number and passes calls and texts to your PC over a secure link.

**Time:** about 30 minutes, plus a few days' wait for US texting approval (step 3).
**Cost** (check twilio.com/pricing for current prices): roughly $1–2 a month for the number, about 1¢ a minute for calls, about 1¢ a text, and a small one-time fee for texting registration.

---

## How it behaves

| Who | What happens |
|---|---|
| **You call ZAE's number** | She says "Hi, it's ZAE. Say your phrase." Your spoken phrase must match **and** your voice must be yours. Then you just talk. Every sentence is voice-checked again, so if someone else takes your phone mid-call, she hangs up. |
| **Bad line** (voice can't be checked) | If you set a phone PIN, the right phrase plus your PIN on the keypad gets you in. |
| **Anyone else calls her number** | She's your answering service: she takes their name and message, then texts it to you and shows it in the app. Callers learn nothing about you. |
| **Calls to *your* number you don't answer** | Your carrier forwards them to her, and she takes a message the same way. |
| **You text her number** | She texts back an answer. Texts can't be voice-checked, so a text can never save, change or do anything; it only gets answers. |
| **Anyone else texts her** | No reply. She forwards the text to you. |
| **You want her to call someone as you** | A command on the PC (step 9). It needs your passkey every time. |

**Privacy:**
- Call audio passes through Twilio.
- She deletes Twilio's copy of every recording right after she's heard it.
- Transcribing, voice checks, thinking and her Kokoro voice all happen on your PC.
- Only the `/phone` path of your PC is reachable from the internet, and it rejects anything not signed by your Twilio account.

---

## Before you start

You need:
- **Your spoken phrase.** You said you'd forgotten it, so reset it first:
  ```powershell
  cd "C:\Projects\ZAENIA"
  .\.venv\Scripts\python.exe -m core.foundation.foundation_main reset-voice-phrase
  .\.venv\Scripts\python.exe -m core.foundation.foundation_main setup-voice-phrase
  ```
- **Phone voice sign-in turned on.** The phone line uses the same voice check as the phone app. If you haven't run it yet: `.\scripts\enable_mobile_voice.ps1`.
- **Tailscale running** on this PC. It already is for the phone app.

---

## 1. Create the Twilio account

1. Go to **twilio.com/try-twilio** and sign up with your email. Verify your email and your mobile number.
2. When it asks what you're building, choose anything close, such as "Voice" and "With code". It doesn't change anything.
3. **Upgrade the account:** click **Upgrade** at the top of the Console and add a payment method. A trial account can only call and text your own verified number and plays a "trial account" message, so upgrade before using it for real. (I can't do this step for you.)

## 2. Buy ZAE's number

1. Console → **Phone Numbers** → **Manage** → **Buy a number**.
2. Country: United States. Tick **Voice** and **SMS**. Optionally type your area code.
3. Pick one and click **Buy**. Write it down. This is ZAE's number.

## 3. Register for texting (US carriers require it)

US carriers block texts from unregistered business numbers. For one person, the easiest route is:
1. Console → **Messaging** → **Regulatory compliance** (or **Trust Hub**) → register as a **Sole Proprietor** (A2P 10DLC).
2. Use your own name. For the use case, choose something like **"Personal assistant notifications to the owner"**. Sample message: *"ZAE here. Missed call from +1 555 123 4567: please call back."*
3. Add ZAE's number to the campaign.

Approval usually takes a few days. **Calls work right away;** texts start working once it's approved.

## 4. Find your Account SID and Auth Token

Console home page → **Account Info**: copy the **Account SID** (starts with `AC`) and the **Auth Token** (click to reveal). Don't put the Auth Token anywhere except the setup prompt in step 5.

## 5. Connect ZAE (on the PC)

```powershell
cd "C:\Projects\ZAENIA"
.\.venv\Scripts\python.exe -m core.telephony setup
```

It asks for:
- the Account SID;
- the Auth Token (hidden as you type);
- ZAE's number;
- your number(s), comma separated, with `+1` or 10 digits;
- the public address. Press Enter to accept the one it suggests (your PC's Tailscale name);
- **your passkey.**

It then:
- seals the token to your Windows account;
- opens **only** the `/phone` path to the internet with Tailscale Funnel;
- points ZAE's number at your PC;
- sends you a test text (once texting is approved).

**If it says Funnel isn't enabled:** Tailscale shows a link the first time. Open it, allow **Funnel** for this PC in the Tailscale admin page, then run:
```powershell
tailscale funnel --bg --set-path=/phone http://127.0.0.1:8766/phone
```

**Then restart her server:**
```powershell
.\scripts\zae.ps1 restart
```

## 6. Test it

1. From your phone, **call ZAE's number**.
2. When she asks, say your phrase.
3. Ask her something, like "What's on my calendar tomorrow?"
4. Say "goodbye" to hang up.
5. **Text her number** "what's the weather?". She should text back (after step 3 is approved).
6. From another phone, call her: she should take a message and text it to you.

## 7. Optional: phone PIN (for bad lines)

```powershell
.\.venv\Scripts\python.exe -m core.telephony pin
```

It must be 6–8 digits and not something simple like 123456. Only a hash is stored. You get one try per call.

## 8. Answering service for your own number

Ask your carrier to forward calls you **don't answer** to ZAE's number. Don't use the iPhone's Call Forwarding setting, because that forwards **all** calls.

Dial these on your iPhone's keypad and press call:

| Carrier | Forward when unanswered | Turn it off |
|---|---|---|
| T-Mobile / AT&T | `**61*1ZAENUMBER#` (e.g. `**61*15551234567#`) | `##61#` |
| Verizon | `*71` then ZAE's 10-digit number | `*73` |

Also forward when busy (`**67*1ZAENUMBER#`) and when unreachable (`**62*1ZAENUMBER#`) on T-Mobile/AT&T. Your phone still rings first. ZAE only answers after it would have gone to voicemail.

## 9. Calling and texting as you

- **Calls showing your number:** Console → **Phone Numbers** → **Manage** → **Verified Caller IDs** → **Add a new Caller ID** → enter your number. Twilio calls you with a code. Then:
  ```powershell
  .\.venv\Scripts\python.exe -m core.telephony call +15551234567 "Hi, this is Zack's assistant. Zack is running ten minutes late." --as-me
  ```
  Without `--as-me`, the call comes from ZAE's number.
- **Texts:** Twilio can't send texts *from* your personal number, so texts always come from ZAE's number:
  ```powershell
  .\.venv\Scripts\python.exe -m core.telephony text +15551234567 "Running ten minutes late."
  ```
- Both show you the message and ask before sending, and both need your passkey.
- Replying from your real number through Windows Phone Link is a possible later add-on.

## 10. Check, turn off, or change

```powershell
.\.venv\Scripts\python.exe -m core.telephony status     # what's set up (no secrets)
.\.venv\Scripts\python.exe -m core.telephony disable    # stop answering and close the /phone path (passkey)
.\.venv\Scripts\python.exe -m core.telephony setup      # run again to change numbers or the token
```

To stop being charged for the number, release it in the Twilio Console (Phone Numbers → your number → Release).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| The call says "an application error has occurred" | Her server isn't reachable. Run `.\scripts\zae.ps1 status`, then `.\scripts\zae.ps1 restart`. Check `tailscale funnel status` lists `/phone`. |
| She never accepts your phrase | Reset it (see "Before you start"). Say it clearly; she hears it over a phone line. |
| The phrase is accepted but the voice check always fails | Phone audio is lower quality than your mic. Set a phone PIN (step 7) and run voice training ("train my voice"). |
| Texts don't arrive | Texting registration (step 3) isn't approved yet. Check its status in the Console. |
| Calls cost more than expected | Twilio Console → **Monitor** → **Logs** shows every call and text. |
| You want to see what happened | The Security tab's activity log shows every phone event: verified, rejected, message taken, bad signature. |
