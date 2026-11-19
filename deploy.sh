#!/bin/sh
# Выкладка сайта kussatayev.kz на сервер.
# Запуск на сервере (пользователь ubuntu):
#   cd /tmp
#   rm -f deploy.sh
#   wget -q kussatayevaa-tech.github.io/lawyer-site-preview/deploy.sh
#   sh deploy.sh
#
# Берет готовый сайт с тестовой копии, снимает с него запрет индексации
# (он нужен только тестовой копии), кладет рабочий robots.txt и публикует
# в /var/www/html. Перед заменой делает резервную копию всего сайта.

set -e

ROOT=/var/www/html
BACK=/var/www/backup/$(date +%Y%m%d-%H%M)
SRC=https://codeload.github.com/kussatayevaa-tech/lawyer-site-preview/tar.gz/refs/heads/main

TMP=$(mktemp -d)
cd "$TMP"

echo "1/5 Скачиваю сайт"
wget -q -O site.tar.gz "$SRC"
tar xzf site.tar.gz
cd lawyer-site-preview-main
rm -f deploy.sh .nojekyll README.md
rm -rf admin-setup   # установка админки, на сайт не выкладывается

echo "2/5 Снимаю запрет индексации"
find . -name '*.html' -exec sed -i \
  -e 's#<meta name="robots" content="noindex, nofollow">##g' \
  -e 's#<meta content="noindex, nofollow" name="robots"/>##g' {} +

echo "3/5 Проверяю, что скачалось целиком"
test -s index.html || { echo "ОШИБКА: нет главной"; exit 1; }
test -s kk.html || { echo "ОШИБКА: нет казахской версии"; exit 1; }
test -s stati/razdel-imushchestva/index.html || { echo "ОШИБКА: нет страниц статей"; exit 1; }
test -s uslugi/semya/index.html || { echo "ОШИБКА: нет страниц услуг"; exit 1; }
test -s yurist/almaty/index.html || { echo "ОШИБКА: нет городских страниц"; exit 1; }
test -s stati/yurist-ili-advokat/index.html || { echo "ОШИБКА: нет новой статьи"; exit 1; }
test "$(find . -name 'index.html' | wc -l)" -ge 70 || { echo "ОШИБКА: страниц меньше, чем должно быть"; exit 1; }
test -s assets/site.css || { echo "ОШИБКА: нет стилей"; exit 1; }
grep -q 'rel="canonical"' index.html || { echo "ОШИБКА: нет canonical"; exit 1; }
if grep -rl 'name="robots"' --include='*.html' . | grep .; then
  echo "ОШИБКА: запрет индексации остался, ничего не меняю"; exit 1
fi
echo "  страниц: $(find . -name 'index.html' | wc -l), адресов в карте: $(grep -c '<loc>' sitemap.xml)"

cat > robots.txt <<'EOF'
User-agent: *
Allow: /

Sitemap: https://kussatayev.kz/sitemap.xml
EOF

echo "4/5 Делаю резервную копию"
sudo mkdir -p "$BACK"
sudo cp -a "$ROOT/." "$BACK/"

echo "5/5 Публикую"
sudo cp -a ./. "$ROOT/"
sudo chmod -R a+rX "$ROOT"

cd /
rm -rf "$TMP"
echo "Готово. Резервная копия: $BACK"
