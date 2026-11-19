#!/bin/sh
# Выкладка сайта kussatayev.kz на сервер.
# Запуск на сервере (пользователь ubuntu):
#   cd /tmp
#   rm -f deploy.sh
#   wget -q kussatayevaa-tech.github.io/lawyer-site-preview/deploy.sh
#   sh deploy.sh
#
# Публикует только четыре файла: index.html, kk.html, robots.txt, sitemap.xml.
# Картинки, стили и скрипты не трогает.
# Прежние версии этих файлов складывает в /var/www/backup/<дата-время>/

set -e

BASE=https://kussatayevaa-tech.github.io/lawyer-site-preview
ROOT=/var/www/html
BACK=/var/www/backup/$(date +%Y%m%d-%H%M)

TMP=$(mktemp -d)
cd "$TMP"

echo "1/5 Скачиваю страницы"
for f in index.html kk.html; do
  wget -q -O "$f" "$BASE/$f"
done
test -s index.html
test -s kk.html

echo "2/5 Снимаю запрет индексации (он нужен только тестовой копии)"
sed -i -e 's#<meta name="robots" content="noindex, nofollow">##g' \
       -e 's#<meta content="noindex, nofollow" name="robots"/>##g' index.html kk.html
if grep -q noindex index.html kk.html; then
  echo "ОШИБКА: запрет индексации остался, ничего не меняю"
  exit 1
fi
grep -q 'rel="canonical"' index.html || { echo "ОШИБКА: нет canonical"; exit 1; }

echo "3/5 Готовлю robots.txt и карту сайта"
cat > robots.txt <<'EOF'
User-agent: *
Allow: /

Sitemap: https://kussatayev.kz/sitemap.xml
EOF
cat > sitemap.xml <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://kussatayev.kz/</loc></url>
  <url><loc>https://kussatayev.kz/kk.html</loc></url>
</urlset>
EOF

echo "4/5 Делаю резервную копию"
sudo mkdir -p "$BACK"
for f in index.html kk.html robots.txt sitemap.xml; do
  if [ -f "$ROOT/$f" ]; then
    sudo cp -p "$ROOT/$f" "$BACK/$f"
  fi
done

echo "5/5 Публикую"
for f in index.html kk.html robots.txt sitemap.xml; do
  sudo install -m 644 "$f" "$ROOT/$f"
done

cd /
rm -rf "$TMP"
echo "Готово. Резервная копия: $BACK"
