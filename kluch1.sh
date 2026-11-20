#!/bin/sh
# Шаг 1: сервер заводит себе ключ для чтения закрытого репозитория
# и кладет открытую половину туда, откуда ее можно прочитать.
# Запуск: cd /tmp; rm -f kluch1.sh; wget -q kussatayevaa-tech.github.io/lawyer-site-preview/kluch1.sh; sudo sh kluch1.sh
set -e
U=/home/ubuntu
mkdir -p $U/.ssh
chmod 700 $U/.ssh
chown ubuntu:ubuntu $U/.ssh
if [ ! -f $U/.ssh/github ]; then
  ssh-keygen -t ed25519 -f $U/.ssh/github -q -N "" -C "kussatayev-server"
  chown ubuntu:ubuntu $U/.ssh/github $U/.ssh/github.pub
  chmod 600 $U/.ssh/github
  echo "Ключ сервера создан."
else
  echo "Ключ сервера уже был."
fi
cp $U/.ssh/github.pub /var/www/html/dk.txt
chmod 644 /var/www/html/dk.txt
echo "Открытая половина выложена по адресу kussatayev.kz/dk.txt"
echo "Шаг 1 готов."
