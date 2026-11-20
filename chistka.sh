#!/bin/sh
# Уборка старых резервных копий на сервере и ежедневная автоматическая чистка.
# Запуск: cd /tmp; rm -f chistka.sh; wget -q kussatayevaa-tech.github.io/lawyer-site-preview/chistka.sh; sudo sh chistka.sh
set -e

echo "1/5 Сколько занято сейчас"
df -h / | tail -1
du -sh /var/www/backup /var/backups/kussatayev-admin 2>/dev/null || true

echo "2/5 Копии сайта: оставляю 3 последние"
if [ -d /var/www/backup ]; then
  ls -1dt /var/www/backup/*/ 2>/dev/null | tail -n +4 | xargs -r rm -rf
  echo "   осталось: $(ls -1dt /var/www/backup/*/ 2>/dev/null | wc -l)"
fi

echo "3/5 Копии настроек nginx: оставляю 3 последние"
ls -1t /etc/nginx/sites-available/*.bak.* 2>/dev/null | tail -n +4 | xargs -r rm -f
echo "   осталось: $(ls -1t /etc/nginx/sites-available/*.bak.* 2>/dev/null | wc -l)"

echo "4/5 Копии базы панели: оставляю 14 последних"
ls -1t /var/backups/kussatayev-admin/app-*.db 2>/dev/null | tail -n +15 | xargs -r rm -f
ls -1t /var/backups/kussatayev-admin/files-*.tgz 2>/dev/null | tail -n +15 | xargs -r rm -f
echo "   копий базы: $(ls -1 /var/backups/kussatayev-admin/app-*.db 2>/dev/null | wc -l), копий файлов: $(ls -1 /var/backups/kussatayev-admin/files-*.tgz 2>/dev/null | wc -l)"

echo "5/5 Ставлю ежедневную чистку в 04:15"
cat > /etc/cron.d/kussatayev-chistka <<CRON
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
15 4 * * * root ls -1dt /var/www/backup/*/ 2>/dev/null | tail -n +4 | xargs -r rm -rf; ls -1t /etc/nginx/sites-available/*.bak.* 2>/dev/null | tail -n +4 | xargs -r rm -f; ls -1t /var/backups/kussatayev-admin/app-*.db 2>/dev/null | tail -n +15 | xargs -r rm -f; ls -1t /var/backups/kussatayev-admin/files-*.tgz 2>/dev/null | tail -n +15 | xargs -r rm -f
CRON
chmod 644 /etc/cron.d/kussatayev-chistka
echo "   поставлено"

echo "Проверка, что копии базы вообще делаются:"
if [ -f /etc/cron.d/kussatayev-admin-backup ]; then echo "   ежедневная копия базы в 03:30: настроена"; else echo "   ВНИМАНИЕ: ежедневная копия базы не настроена"; fi
df -h / | tail -1
echo "Готово."
