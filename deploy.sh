#!/bin/sh
# Выкладка сайта kussatayev.kz на сервер.
# Запуск на сервере (пользователь ubuntu):
#   cd /tmp
#   rm -f deploy.sh
#   wget -q kussatayevaa-tech.github.io/lawyer-site-preview/deploy.sh
#   sh deploy.sh
#
# Берет готовые файлы с тестовой копии, снимает с них запрет индексации
# (он нужен только тестовой копии) и кладет на боевой сайт вместе с
# robots.txt и картой сайта.

set -e

BASE=https://kussatayevaa-tech.github.io/lawyer-site-preview
ROOT=/var/www/html

TMP=$(mktemp -d)
cd "$TMP"
mkdir assets

echo "1/4 Скачиваю страницы"
for f in index.html kk.html; do
  wget -q -O "$f" "$BASE/$f"
done
for f in site.css site.js engine.js site.kk.js engine.kk.js logo.svg logo-light.svg; do
  wget -q -O "assets/$f" "$BASE/assets/$f"
done

echo "2/4 Снимаю запрет индексации"
sed -i -e 's#<meta name="robots" content="noindex, nofollow">##g' \
       -e 's#<meta content="noindex, nofollow" name="robots"/>##g' index.html kk.html
if grep -q noindex index.html kk.html; then
  echo "ОШИБКА: запрет индексации остался, ничего не меняю"
  exit 1
fi

echo "3/4 Готовлю robots.txt и карту сайта"
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

echo "4/4 Кладу на сайт"
for f in index.html kk.html robots.txt sitemap.xml; do
  sudo install -m 644 "$f" "$ROOT/$f"
done
for f in assets/*; do
  sudo install -m 644 "$f" "$ROOT/assets/$(basename "$f")"
done

cd /
rm -rf "$TMP"
echo "Готово. Проверьте https://kussatayev.kz/robots.txt"
