# Operacao

## Comandos

```sh
docker compose ps
docker compose logs --tail=100 n8n
docker compose restart n8n
docker compose stop
```

`stop` preserva dados. `down` remove containers/rede e preserva volumes, salvo uso de `-v`, que apaga os dados. Nao use `down -v` para manutencao. Logs e execucoes podem conter conteudo privado; nao os compartilhe sem revisar. As execucoes sao podadas apos 168 horas e logs Docker tem rotacao.

## Backup

```sh
bash scripts/backup.sh
```

O script para brevemente o n8n, exporta PostgreSQL em formato customizado e arquiva o volume n8n_data. Se o servico editorial estiver em execucao, inclui tambem uma copia consistente de `editorial.sqlite`. Inclui copia privada do `.env` porque sem a chave as credenciais podem ser irrecuperaveis. Reinicia o servico ao finalizar ou falhar. Confirme os tres arquivos, criptografe e copie para armazenamento externo. Backups locais isoladamente nao protegem contra perda do host.

## Restaurar

Teste inicialmente numa maquina/instancia isolada, sem agendamentos nem saida de publicacao. Restaure usando a mesma versao e o conjunto de arquivos do mesmo backup. Os comandos abaixo substituem o estado do destino: escolha somente uma instancia de recuperacao preparada para receber esses dados.

1. Copie `env.secret` para `.env` na raiz e aplique `chmod 600 .env`.
2. Inicie somente o banco: `docker compose up -d postgres`; aguarde ficar healthy.
3. Com n8n parado: `docker compose exec -T postgres pg_restore -U n8n -d n8n --clean --if-exists --no-owner < backups/SEU_BACKUP/postgres.dump`.
4. No volume vazio de recuperacao: `docker compose run --rm --no-deps -T --user root --entrypoint tar n8n -C /home/node/.n8n -xzf - < backups/SEU_BACKUP/n8n-data.tar.gz`.
5. Inicie n8n, confirme login, credenciais e workflows antes de habilitar qualquer publicacao. Nunca repita publicacoes em estado ambiguo apenas porque houve restauracao.

## Atualizar

Faca e confira backup, consulte release notes/migracoes e altere N8N_VERSION no `.env` e no exemplo versionado apos validacao. Execute `docker compose pull` e `docker compose up -d --wait`. Verifique healthchecks, login, credenciais e simulacao. Downgrade apos migracao de banco exige restaurar o backup compativel; trocar apenas a tag nao basta.

## Expor em producao

Configure dominio e proxy reverso com TLS, mantendo o binding local se o proxy estiver no host. Ajuste N8N_HOST, N8N_PROTOCOL=https, N8N_EDITOR_BASE_URL, WEBHOOK_URL, N8N_SECURE_COOKIE=true e N8N_PROXY_HOPS ao numero real de proxies confiaveis. Se o proxy estiver em outro container, use rede Docker compartilhada em vez de publicar todas as interfaces. Teste callbacks OAuth e MCP. Nao exponha PostgreSQL.

O modo local usa cookie sem Secure exclusivamente para HTTP em localhost. O template nao instala proxy nem abre portas no firewall.

## Volumes desta instalacao

O volume ativo PostgreSQL e `n8n-social_postgres17_data`. Durante a validacao inicial, foi criado um volume PostgreSQL 16, preservado sem uso apos migracao para 17. Nao o monte em um PostgreSQL 17 nem remova volumes sem confirmar seus dados.

Os modelos usam somente Code JavaScript. A imagem pode registrar aviso de ausencia de Python no runner interno; isso nao impediu as simulacoes JS. Para executar Python ou codigo de terceiros em producao, configure task runners externos e isolamento apropriado conforme a documentacao oficial.

Para o chatbot, preserve tambem o volume `n8n-social_editorial_data` e o arquivo `editorial.sqlite` do backup. O banco guarda rascunhos e tentativas para impedir repeticoes. Restaure com o servico parado, dono 1000:1000 e permissoes privadas; verifique estados `dispatching`/`unknown` antes de retomar. Backups anteriores a instalacao do chatbot nao incluem esse arquivo.

O subagente de imagem guarda JPEGs em `/data/generated-images`, no mesmo volume editorial. O backup inclui `generated-images.tar.gz` junto do SQLite. Restaure os dois com o servico parado; aponte o mesmo dominio de midias para o volume restaurado. A limpeza de arquivos ainda e manual.

O monitor de comentarios usa `community_data` com `/data/community.sqlite`. O backup inclui esse banco e as skills quando o servico esta em execucao. Restaure-os juntos, com `community` parado; preserve registros de envio incerto e opt-outs para nao repetir respostas. O monitor e importado inativo; nao o publique antes de configurar permissoes e revisar a fila.
