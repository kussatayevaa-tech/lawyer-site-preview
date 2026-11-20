#!/bin/sh
# Уборка старых резервных копий на сервере и ежедневная автоматическая чистка.
# Запуск: cd /tmp; rm -f chistka.sh; wget -q kussatayevaa-tech.github.io/lawyer-site-preview/chistka.sh; sudo sh chistka.sh
set -e

echo "1/6 Сколько занято сейчас"
df -h / | tail -1
du -sh /var/www/backup /var/backups/kussatayev-admin 2>/dev/null || true

echo "2/6 Копии сайта: оставляю 3 последние"
if [ -d /var/www/backup ]; then
  ls -1dt /var/www/backup/*/ 2>/dev/null | tail -n +4 | xargs -r rm -rf
  echo "   осталось: $(ls -1dt /var/www/backup/*/ 2>/dev/null | wc -l)"
fi

echo "3/6 Копии настроек nginx: оставляю 3 последние"
ls -1t /etc/nginx/sites-available/*.bak.* 2>/dev/null | tail -n +4 | xargs -r rm -f
echo "   осталось: $(ls -1t /etc/nginx/sites-available/*.bak.* 2>/dev/null | wc -l)"

echo "4/6 Копии базы панели: оставляю 14 последних"
ls -1t /var/backups/kussatayev-admin/app-*.db 2>/dev/null | tail -n +15 | xargs -r rm -f
ls -1t /var/backups/kussatayev-admin/files-*.tgz 2>/dev/null | tail -n +15 | xargs -r rm -f
echo "   копий базы: $(ls -1 /var/backups/kussatayev-admin/app-*.db 2>/dev/null | wc -l), копий файлов: $(ls -1 /var/backups/kussatayev-admin/files-*.tgz 2>/dev/null | wc -l)"

echo "5/6 Ставлю ежедневную чистку в 04:15"
cat > /etc/cron.d/kussatayev-chistka <<CRON
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
15 4 * * * root ls -1dt /var/www/backup/*/ 2>/dev/null | tail -n +4 | xargs -r rm -rf; ls -1t /etc/nginx/sites-available/*.bak.* 2>/dev/null | tail -n +4 | xargs -r rm -f; ls -1t /var/backups/kussatayev-admin/app-*.db 2>/dev/null | tail -n +15 | xargs -r rm -f; ls -1t /var/backups/kussatayev-admin/files-*.tgz 2>/dev/null | tail -n +15 | xargs -r rm -f
CRON
chmod 644 /etc/cron.d/kussatayev-chistka
echo "   поставлено"

echo "6/6 Ставлю сторожа диска (каждые 6 часов)"
cat > /usr/local/bin/kussatayev-disk.sh <<'DISK'
#!/bin/sh
# Следит за местом на диске. Выше 80 процентов чистит копии жестче и пишет в журнал.
LOG=/var/log/kussatayev-disk.log
P=$(df / | awk 'NR==2{gsub("%","",$5); print $5}')
D=$(date "+%Y-%m-%d %H:%M")
if [ "$P" -ge 80 ]; then
  echo "$D диск занят на $P процентов, чищу" >> $LOG
  ls -1dt /var/www/backup/*/ 2>/dev/null | tail -n +2 | xargs -r rm -rf
  ls -1t /var/backups/kussatayev-admin/app-*.db 2>/dev/null | tail -n +8 | xargs -r rm -f
  ls -1t /var/backups/kussatayev-admin/files-*.tgz 2>/dev/null | tail -n +8 | xargs -r rm -f
  journalctl --vacuum-size=100M >/dev/null 2>&1
  apt-get clean >/dev/null 2>&1
  P2=$(df / | awk 'NR==2{gsub("%","",$5); print $5}')
  echo "$D после чистки $P2 процентов" >> $LOG
else
  echo "$D диск занят на $P процентов" >> $LOG
fi
tail -n 200 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
DISK
chmod +x /usr/local/bin/kussatayev-disk.sh
cat > /etc/cron.d/kussatayev-disk <<CRON2
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
7 */6 * * * root /usr/local/bin/kussatayev-disk.sh
CRON2
chmod 644 /etc/cron.d/kussatayev-disk
/usr/local/bin/kussatayev-disk.sh
echo "   журнал: /var/log/kussatayev-disk.log"
tail -2 /var/log/kussatayev-disk.log

echo "Проверка, что копии базы вообще делаются:"
if [ -f /etc/cron.d/kussatayev-admin-backup ]; then echo "   ежедневная копия базы в 03:30: настроена"; else echo "   ВНИМАНИЕ: ежедневная копия базы не настроена"; fi
df -h / | tail -1
echo "Готово."
