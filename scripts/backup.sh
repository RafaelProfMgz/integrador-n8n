#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
backup_dir="backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
# Parada curta garante consistencia entre banco e arquivos binarios.
docker compose stop n8n
trap 'docker compose start n8n >/dev/null' EXIT
docker compose exec -T postgres pg_dump -U n8n -d n8n -Fc > "$backup_dir/postgres.dump"
docker compose run --rm --no-deps -T --user root --entrypoint tar n8n -C /home/node/.n8n -czf - . > "$backup_dir/n8n-data.tar.gz"
if [ -n "$(docker compose ps -q --status running editorial)" ]; then
  docker compose exec -T editorial python -c 'import sqlite3,sys; source=sqlite3.connect("/data/editorial.sqlite"); target=sqlite3.connect(":memory:"); source.backup(target); sys.stdout.buffer.write(target.serialize()); source.close(); target.close()' > "$backup_dir/editorial.sqlite"
  docker compose exec -T editorial tar -C /data -czf - generated-images > "$backup_dir/generated-images.tar.gz"
fi
if [ -n "$(docker compose ps -q --status running community)" ]; then
  docker compose exec -T community python -c 'import sqlite3,sys; source=sqlite3.connect("/data/community.sqlite"); target=sqlite3.connect(":memory:"); source.backup(target); sys.stdout.buffer.write(target.serialize()); source.close(); target.close()' > "$backup_dir/community.sqlite"
  cp -R response-skills "$backup_dir/response-skills"
fi
cp .env "$backup_dir/env.secret"
echo "Backup privado criado em $backup_dir; copie para armazenamento criptografado externo."
