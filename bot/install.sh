#!/bin/sh
# Установка Телеграм-бота kussatayev.kz на сервер.
# Запуск:  sudo sh install.sh <токен от BotFather>
# Повторный запуск обновляет код и не трогает данные.
set -e

TOKEN="$1"
APP_DIR=/opt/kussatayev-bot
STATE_DIR=/var/lib/kussatayev-bot
ENV_FILE=/etc/kussatayev-bot.env
UNIT=/etc/systemd/system/kussatayev-bot.service
SRC_DIR=$(cd "$(dirname "$0")" && pwd)
RUN_USER=lawadmin

if [ ! -f "$SRC_DIR/bot.py" ]; then
  echo "Рядом со скриптом нет файла bot.py. Положи оба файла в одну папку."
  exit 1
fi

if ! id "$RUN_USER" >/dev/null 2>&1; then
  echo "Пользователя $RUN_USER нет, создаю системного пользователя kussbot."
  RUN_USER=kussbot
  id "$RUN_USER" >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin "$RUN_USER"
fi

mkdir -p "$APP_DIR" "$STATE_DIR"
install -m 0644 "$SRC_DIR/bot.py" "$APP_DIR/bot.py"
chown -R "$RUN_USER":"$RUN_USER" "$STATE_DIR"

if [ -n "$TOKEN" ] || [ ! -f "$ENV_FILE" ]; then
  PAIR=$(tr -dc 'a-z0-9' </dev/urandom | head -c 10)
  OLD_PAIR=""
  if [ -f "$ENV_FILE" ]; then
    OLD_PAIR=$(grep '^BOT_PAIR_CODE=' "$ENV_FILE" | cut -d= -f2)
    OLD_TOKEN=$(grep '^BOT_TOKEN=' "$ENV_FILE" | cut -d= -f2)
    [ -n "$OLD_PAIR" ] && PAIR="$OLD_PAIR"
    [ -z "$TOKEN" ] && TOKEN="$OLD_TOKEN"
  fi
  umask 077
  cat > "$ENV_FILE" <<ENV
BOT_TOKEN=$TOKEN
BOT_PAIR_CODE=$PAIR
BOT_STATE_DIR=$STATE_DIR
BOT_NAMES=full
PANEL_DB=
SITE_URL=https://kussatayev.kz/
PANEL_URL=https://admin.kussatayev.kz/admin/login
DISK_URL=
ENV
  chown "$RUN_USER":"$RUN_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

RW_PATHS="$STATE_DIR"
for d in /var/lib/kussatayev-admin /opt/kussatayev-admin; do
  [ -d "$d" ] && RW_PATHS="$RW_PATHS $d"
done

cat > "$UNIT" <<UNITEOF
[Unit]
Description=Telegram bot kussatayev.kz
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_USER
EnvironmentFile=$ENV_FILE
ExecStart=/usr/bin/python3 $APP_DIR/bot.py
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$RW_PATHS
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNITEOF

systemctl daemon-reload
systemctl enable kussatayev-bot >/dev/null 2>&1 || true

if ! grep -q '^BOT_TOKEN=.\+' "$ENV_FILE"; then
  echo "Токен не задан. Впиши его в $ENV_FILE и выполни: sudo systemctl restart kussatayev-bot"
  exit 0
fi

systemctl restart kussatayev-bot
sleep 4
if systemctl is-active --quiet kussatayev-bot; then
  echo "-----------------------------------------------"
  echo "Бот запущен."
  echo "Пользователь службы: $RUN_USER"
  echo "Код привязки: $(grep '^BOT_PAIR_CODE=' "$ENV_FILE" | cut -d= -f2)"
  echo "Открой своего бота в Телеграме и отправь ему:  /start <код выше>"
  echo "-----------------------------------------------"
else
  echo "Служба не поднялась. Последние строки журнала:"
  journalctl -u kussatayev-bot -n 20 --no-pager || true
  exit 1
fi
