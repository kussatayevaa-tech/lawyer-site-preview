#!/bin/sh
# Установка или обновление админ-панели на admin.kussatayev.kz.
# Запуск на сервере (пользователь ubuntu), только строчные буквы:
#   cd /tmp
#   rm -f install.sh
#   wget -q kussatayevaa-tech.github.io/lawyer-site-preview/admin-setup/install.sh
#   sh install.sh
# Исходники панели лежат в pkg.enc зашифрованными; скрипт спросит пароль архива.
set -e
W=/tmp/kadmin
rm -rf "$W"; mkdir -p "$W"; cd "$W"
echo "Скачиваю архив панели"
wget -q -O pkg.enc "https://kussatayevaa-tech.github.io/lawyer-site-preview/admin-setup/pkg.enc?t=$(date +%s)"
printf "Пароль архива: "
stty -echo; read P; stty echo; echo
openssl enc -d -aes-256-cbc -pbkdf2 -iter 300000 -pass "pass:$P" -in pkg.enc -out pkg.tgz || { echo "ОШИБКА: неверный пароль архива"; exit 1; }
unset P
tar xzf pkg.tgz
sudo sh backend/deploy/server-setup.sh
cd /tmp; rm -rf "$W"
