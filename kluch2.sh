#!/bin/sh
# Шаг 2: сервер забирает исходники из закрытого репозитория и обновляет панель.
# Запуск: cd /tmp; rm -f kluch2.sh; wget -q kussatayevaa-tech.github.io/lawyer-site-preview/kluch2.sh; sudo sh kluch2.sh
set -e
U=/home/ubuntu
VETKA=bezopasnost-20-11

echo "1/5 Убираю открытый ключ с сайта"
rm -f /var/www/html/dk.txt

echo "2/5 Забираю исходники"
export GIT_SSH_COMMAND="ssh -i $U/.ssh/github -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes"
if ! command -v git >/dev/null 2>&1; then apt-get install -y git >/dev/null; fi
rm -rf $U/src
git clone --quiet --depth 1 -b "$VETKA" git@github.com:kussatayevaa-tech/lawyer-site.git $U/src
echo "   ветка $VETKA, коммит $(cd $U/src && git rev-parse --short HEAD)"

echo "3/5 Обновляю панель"
sh $U/src/backend/deploy/server-setup.sh

echo "4/5 Делаю команду обновления на будущее"
cat > $U/obnovit.sh <<'UPD'
#!/bin/sh
# Обновить панель из закрытого репозитория: sudo sh /home/ubuntu/obnovit.sh [ветка]
set -e
U=/home/ubuntu
VETKA=${1:-admin-v2}
export GIT_SSH_COMMAND="ssh -i $U/.ssh/github -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes"
rm -rf $U/src
git clone --quiet --depth 1 -b "$VETKA" git@github.com:kussatayevaa-tech/lawyer-site.git $U/src
sh $U/src/backend/deploy/server-setup.sh
UPD
chmod +x $U/obnovit.sh

echo "5/5 Проверка"
sleep 3
echo "   панель: $(curl -s -o /dev/null -w '%{http_code}' https://admin.kussatayev.kz/admin/login)"
echo "   сайт:   $(curl -s -o /dev/null -w '%{http_code}' https://kussatayev.kz/)"
echo "   ключ с сайта убран: $(curl -s -o /dev/null -w '%{http_code}' https://kussatayev.kz/dk.txt)"
echo "Готово."
