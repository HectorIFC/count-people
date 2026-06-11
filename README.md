# People counter for photos and videos (Telegram bot)

<img src="assets/logo.png" alt="Bot logo" width="160" align="right">

**[Project site →](https://hectorifc.github.io/count-people/)**


Telegram bot that receives photos and videos, counts the people in the scene
with [MiVOLO](https://github.com/WildChlamydia/MiVOLO) (age and gender estimated
from body + face) and stores only aggregated numbers in a CSV history.
Runs on Mac (Apple Silicon/MPS), CPU-only VPS or NVIDIA GPU machines, detecting
the device automatically.

- **Photo**: scene count within seconds
- **Video**: slow 20-30s pan; counts **unique** people via tracking
- **History**: total + age group / gender distribution, per event
- **Multi-language**: replies in Portuguese, English or Spanish, following each
  sender's Telegram client language (fallback: English)

## 1) Create the bot on Telegram

1. Open Telegram and talk to **@BotFather**
2. Send `/newbot`, pick a name and a username
3. Save the **token** it gives you (it is a secret: do not commit it or paste it in chats)
4. Find your user id by talking to **@userinfobot** (needed for the allowlist)

## 2) Install

> The project path must not contain spaces (`PIP_CONSTRAINT` below does not
> accept paths with spaces).

### Mac (Apple Silicon)

```bash
git clone <your-repository> && cd count-people
python3.12 -m venv .venv && source .venv/bin/activate
PIP_CONSTRAINT=$PWD/constraints.txt pip install -r requirements.txt
```

Use Python 3.12 (`brew install python@3.12`); newer versions may lack wheels
for some dependencies.

### VPS (CPU, Ubuntu/Debian)

```bash
python3 -m venv .venv && source .venv/bin/activate
# CPU-only torch: ~10x smaller than the default CUDA package
pip install torch --index-url https://download.pytorch.org/whl/cpu
PIP_CONSTRAINT=$PWD/constraints.txt pip install -r requirements.txt
```

## 3) Configure

```bash
cp .env.example .env
chmod 600 .env          # only your user can read the token
$EDITOR .env            # fill in TELEGRAM_BOT_TOKEN and ALLOWED_USER_IDS
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | - | token from @BotFather |
| `ALLOWED_USER_IDS` | yes | - | authorized ids, comma-separated |
| `SEND_ANNOTATED_PREVIEW` | no | `false` | `true` replies with the annotated photo |
| `HISTORY_FILE` | no | `counts.csv` | history CSV path |
| `MODELS_DIR` | no | `models` | model weights cache |

## 4) Run

```bash
set -a && source .env && set +a
python3 bot.py
```

On the first run the weights (~250 MB) are downloaded to `./models` and their
SHA256 is verified. Send `/start` to the bot, then a photo or a video.

- Photo: 2-5 s (Mac M1/M2), 15-40 s (CPU VPS)
- Video: minutes on Mac, tens of minutes on a CPU VPS
- Telegram limit: bots can only download files up to **20 MB** — record short
  clips (20-30s) at 720p
- Tip: write the event name in the photo/video caption (e.g. "Sunday meeting")
  to organize the history

## 5) Keep the bot running

### Mac (occasional use)

```bash
set -a && source .env && set +a
nohup python3 bot.py > bot.log 2>&1 &
```

### VPS (always on, via systemd)

Create the dedicated user and the secrets file (outside the repository, root-only):

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin peoplebot
sudo mkdir -p /etc/people-counter
sudo install -m 600 -o root -g root /dev/null /etc/people-counter/env
sudoedit /etc/people-counter/env   # TELEGRAM_BOT_TOKEN=... and ALLOWED_USER_IDS=...
```

Create `/etc/systemd/system/people-counter.service`:

```ini
[Unit]
Description=People counting Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
User=peoplebot
Group=peoplebot
WorkingDirectory=/opt/count-people
# Secrets via EnvironmentFile (inline Environment= would leak in `systemctl show`)
EnvironmentFile=/etc/people-counter/env
ExecStart=/opt/count-people/.venv/bin/python3 bot.py
Restart=on-failure
RestartSec=5

# Sandbox: the process can only write to its own data directory
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/opt/count-people

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now people-counter
```

## Security

**Bot itself:**

- **Mandatory allowlist**: the bot does not start without `ALLOWED_USER_IDS`
  and **silently ignores** messages from anyone else (without confirming the
  bot exists); attempts are logged
- **Long polling**: the bot only opens **outbound** TLS connections to
  `api.telegram.org`. No inbound port is opened, no webhook, no exposed endpoint
- **Model integrity**: downloaded weights have their SHA256 verified on every
  startup (they are deserialized via pickle; a tampered file could execute
  code). Wrong hash = file deleted + bot aborts
- **Data**: photos/videos are processed in a temporary directory and deleted
  right after; only aggregated numbers go to the CSV (created with mode `600`)
- **User input**: captions are truncated and sanitized before reaching the CSV
  (mitigates CSV/formula injection)
- **Secrets**: token only via environment variable; `.env` is in `.gitignore`,
  and the noisy `httpx` logger (which prints URLs containing the token) is
  silenced

**VPS (recommended):**

```bash
# SSH with keys only, no passwords, no root login
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# Firewall: deny all inbound except SSH (the bot needs no open port)
sudo apt install -y ufw fail2ban unattended-upgrades
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw enable
```

- `fail2ban` blocks SSH brute force; `unattended-upgrades` keeps security
  patches current
- Run the bot as the dedicated no-shell user (unit above), never as root

## Privacy

- Photos and videos are processed in a temporary directory and **deleted right
  after**; no media is ever stored
- Only aggregated numbers (no identification of any kind) go to the CSV
- Recommended: let the people present know that counting is done by image
- Do not commit real photos/videos to the repository (`.gitignore` already
  blocks them)

## Tests

```bash
pip install -r requirements-dev.txt
pytest                        # unit tests + coverage (fails under 80%)
RUN_INTEGRATION=1 pytest      # also runs the real-model tests (slow)
```

Unit tests mock Telegram and the models, so they run in seconds. The
integration tests load the real MiVOLO weights and analyze the local sample
photo/video, which takes minutes — hence the opt-in flag.

## Alternative: Colab notebook

`count-people.ipynb` runs the same flow on Google Colab (free T4 GPU), with
manual photo/video upload and history saved to your Google Drive. Useful when
you do not want to keep a bot running.

## Project layout

```
bot.py               # Telegram bot (long polling, allowlist, limits)
messages.py          # localized replies (pt/en/es)
analysis.py          # counting and demographics (MiVOLO), photo and video
history.py           # CSV history persistence
count-people.ipynb  # Google Colab alternative
requirements.txt     # dependencies (MiVOLO pinned by commit)
constraints.txt      # build constraint (setuptools < 81)
.env.example         # configuration template
```
