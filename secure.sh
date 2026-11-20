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
ufw status

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
fail2ban-client status sshd >/dev/null 2>&1 && echo "   sshd под охраной: 5 попыток за 15 минут, блокировка на час"

echo "3/4 Заголовки безопасности в nginx"
mkdir -p /etc/nginx/snippets
cat > /etc/nginx/snippets/kussatayev-security.conf <<HDR
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=31536000" always;
HDR
for f in /etc/nginx/sites-available/default /etc/nginx/sites-available/kussatayev-admin; do
  if [ -f "$f" ]; then cp -a "$f" "$f.bak.$(date +%Y%m%d-%H%M%S)"; fi
done
python3 - <<'PYEOF'
import io
line = "    include snippets/kussatayev-security.conf;\n"
for path in ("/etc/nginx/sites-available/default", "/etc/nginx/sites-available/kussatayev-admin"):
    try:
        src = io.open(path, encoding="utf-8").read().splitlines(True)
    except OSError:
        continue
    out, done, n = [], False, 0
    for ln in src:
        if "kussatayev-security.conf" in ln:   # прежняя вставка, в том числе неудачная
            continue
        out.append(ln)
        t = ln.strip()
        if t.startswith("server") and "{" in t:
            done = False
        elif (not done) and t.startswith("listen") and "443" in t:
            out.append(line)   # внутрь блока HTTPS, один раз на блок
            done, n = True, n + 1
    io.open(path, "w", encoding="utf-8").write("".join(out))
    print("   %s: вставок в блоки HTTPS: %d" % (path, n))
PYEOF
if nginx -t 2>/tmp/ngx.err; then
  systemctl reload nginx
  echo "   nginx перезагружен"
else
  echo "   ОШИБКА в конфигурации, откатываю:"; cat /tmp/ngx.err
  for f in /etc/nginx/sites-available/default /etc/nginx/sites-available/kussatayev-admin; do
    LAST=$(ls -t $f.bak.* 2>/dev/null | head -1)
    if [ -n "$LAST" ]; then cp -a "$LAST" "$f"; fi
  done
  nginx -t && systemctl reload nginx
  exit 1
fi

echo "4/4 Проверка"
for u in https://kussatayev.kz/ https://admin.kussatayev.kz/admin/login; do
  echo "   $u"
  curl -sSI "$u" | grep -iE "^(http/|x-frame|x-content|referrer|strict-transport)" | sed "s/^/      /"
done
echo "Готово."
