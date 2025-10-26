# -:𝐈𝐓'𝐬𝐆𝐎𝐋𝐔.™®:-
Telegram bot that generates Classplus tokens via email OTP.

## Commands
- /cp: send email → OTP → token
- /auto: Gmail alias → auto-detect 4-digit OTP from `info@ce.classplus.co`

## Setup (local)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Fill USER_* values at top of main.py (bot token, Gmail + app password)
python main.py
```

## Notes
- Polling-only.
