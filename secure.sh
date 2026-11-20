#!/bin/sh
# Защита сервера: фаервол, запрет подбора паролей по SSH, заголовки безопасности в nginx.
# Запуск на сервере: cd /tmp; rm -f secure.sh; wget -q kussatayevaa-tech.github.io/lawyer-site-preview/secure.sh; sudo sh secure.sh
# Сеть не трогает: адреса и маршруты остаются как есть (на сервере IPv4 прописан вручную).
set -e

echo "1/4 Фаервол"
if ! command -v ufw >/dev/null 2>&1; then apt-get install -y ufw >/dev/null; fi
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
ufw status | head -8

echo "2/4 Запрет подбора паролей (fail2ban)"
if ! command -v fail2ban-client >/dev/null 2>&1; then apt-get install -y fail2ban >/dev/null; fi
mkdir -p /etc/fail2ban/jail.d
cat > /etc/fail2ban/jail.d/kussatayev.conf <<JAIL
[DEFAULT]
bantime = 1h
findtime = 15m
maxretry = 5

[sshd]
enabled = true
backend = systemd
JAIL
systemctl enable fail2ban >/dev/null 2>&1 || true
systemctl restart fail2ban
sleep 2
fail2ban-client status sshd | head -6 || true

echo "3/4 Заголовки безопасности в nginx"
cat > /etc/nginx/snippets/kussatayev-security.conf <<HDR
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=31536000" always;
HDR
cp -a /etc/nginx/sites-available/default /etc/nginx/sites-available/default.bak.$(date +%Y%m%d-%H%M%S)
python3 - <<'PYEOF'
import io, re
line = "    include snippets/kussatayev-security.conf;\n"
for path in ("/etc/nginx/sites-available/default", "/etc/nginx/sites-available/kussatayev-admin"):
    try:
        src = io.open(path, encoding="utf-8").read()
    except OSError:
        continue
    if "kussatayev-security.conf" in src:
        print("уже стоит:", path)
        continue
    out, depth, done = [], 0, False
    for ln in src.splitlines(True):
        out.append(ln)
        if ln.strip().startswith("server") and "{" in ln:
            depth = 1
            continue
        if depth == 1 and re.match(r"\s*server_name\b", ln) and not done:
            out.append(line)
            done = True
            depth = 0
    if done:
        io.open(path, "w", encoding="utf-8").write("".join(out))
        print("добавлено в", path)
    else:
        print("не нашел server_name, пропускаю:", path)
PYEOF
if nginx -t 2>/tmp/ngx.err; then
  systemctl reload nginx
  echo "   nginx перезагружен"
else
  echo "   ОШИБКА в конфигурации, откатываю:"; cat /tmp/ngx.err
  LAST=$(ls -t /etc/nginx/sites-available/default.bak.* | head -1)
  cp -a "$LAST" /etc/nginx/sites-available/default
  nginx -t && systemctl reload nginx
  exit 1
fi

echo "4/4 Проверка"
for u in https://kussatayev.kz/ https://admin.kussatayev.kz/admin/login; do
  echo "   $u"
  curl -sSI "$u" | grep -iE "^(http/|x-frame|x-content|referrer|strict-transport)" | sed "s/^/      /"
done
echo "Готово."
