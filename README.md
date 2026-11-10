# Integrador n8n — publicações sociais

Aplicativo local em Docker para preparar publicações, selecionar fotos/vídeos e confirmar o envio às contas configuradas. Inclui chat editorial com OpenAI, Instagram (foto, Reel e carrossel de até 10 itens), foto em Página Facebook, texto no X e revisão de comentários da comunidade.

**Instalação nova:** siga as etapas 1 a 7. **Transferir a instalação atual com seus dados:** use a seção [Migrar para outro computador](#migrar-para-outro-computador).

## 1. Preparar o computador

Precisa de Git, Python 3 e Docker com os plugins Compose v2 e Buildx. Bash é usado nos comandos abaixo; no Windows, execute no WSL 2 com integração do Docker Desktop. No macOS, instale [Docker Desktop](https://docs.docker.com/desktop/) e use `python3`. Não é necessário instalar n8n, PostgreSQL ou dependências Python manualmente: os serviços rodam em containers.

### Ubuntu sem Docker instalado

Em uma instalação nova do Ubuntu, instale pelo [repositório oficial do Docker](https://docs.docker.com/engine/install/ubuntu/):

```bash
sudo apt update
sudo apt install -y ca-certificates curl git python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Saia e entre novamente na sessão para aplicar o grupo Docker. Esse grupo dá acesso administrativo ao Docker. Se já tem Docker instalado, confira as instruções oficiais para eventuais conflitos de pacotes; não reinstale por cima sem verificar. Para Debian, siga a [instalação específica do Debian](https://docs.docker.com/engine/install/debian/).

### Conferir as ferramentas

```bash
git --version
python3 --version
docker version
docker compose version
docker buildx version
docker run --rm hello-world
```

Se aparecer `permission denied` no socket Docker, confirme que entrou novamente na sessão e que seu usuário tem acesso ao daemon antes de continuar.

## 2. Baixar o projeto e criar o ambiente

```bash
git clone https://github.com/RafaelProfMgz/integrador-n8n.git
cd integrador-n8n
python3 scripts/setup.py
mkdir -p media-library
chmod 600 .env
```

Se o repositório exigir acesso privado, autentique-se no GitHub antes do clone. Execute os próximos comandos **sempre dentro desta pasta**, onde está `compose.yaml`.

`setup.py` cria `.env` a partir de `.env.example`, com senha do banco e chave de criptografia aleatórias. Se `.env` já existir, ele é preservado. A chave `N8N_ENCRYPTION_KEY` e a senha `POSTGRES_PASSWORD` não devem ser regeneradas ao reutilizar volumes existentes.

Edite o arquivo local no seu editor:

```bash
nano .env
```

Preencha apenas as integrações que vai usar. Valores reais, IDs e tokens ficam exclusivamente nesse arquivo; não entram no README, nos workflows nem no Git.

| Uso | Variáveis no `.env` |
| --- | --- |
| Escrever/revisar legendas com IA | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Instagram profissional vinculado a Página | `META_GRAPH_VERSION`, `META_INSTAGRAM_ACCOUNT_ID`, `META_INSTAGRAM_ACCESS_TOKEN` |
| Página Facebook | `META_GRAPH_VERSION`, `META_FACEBOOK_PAGE_ID`, `META_FACEBOOK_PAGE_ACCESS_TOKEN` |
| X | `X_USER_ID`, `X_OAUTH2_ACCESS_TOKEN` de usuário |
| Gerar imagem com IA, opcional | `OPENAI_IMAGE_MODEL`; hospedagem descrita em [geração de imagem](docs/image-agent.md) |
| Importar arquivos por caminho local, opcional | `MEDIA_LIBRARY_HOST_PATH`, caminho absoluto de uma pasta existente neste computador |
| Servir anexos à Meta por HTTPS | `MEDIA_PUBLIC_BASE_URL`; configuração na etapa 6 |

A versão Graph deve ser suportada pelo seu aplicativo Meta. App ID e App Secret são reservados para obtenção/renovação de tokens; os publicadores atuais não executam OAuth automaticamente. Consulte [Meta](docs/meta-setup.md) e [X](docs/x-setup.md) para obter as credenciais corretas.

Mantenha inicialmente `CHATBOT_PUBLISH_ENABLED=false`, `COMMENTS_READ_ENABLED=false`, `COMMENTS_SEND_ENABLED=false`, `COMMENTS_MODE=review` e `COMMENTS_X_REPLY_ENABLED=false`. Isso permite preparar e simular antes de habilitar envios.

## 3. Construir e iniciar os serviços

```bash
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 300
docker compose ps
```

O primeiro build baixa imagens e instala FFmpeg nos containers; pode demorar. O n8n usa a versão fixada no `.env`. PostgreSQL, editorial, adaptador Instagram, servidor de mídias e comunidade sobem junto. O túnel ngrok é opcional e fica fora desse comando inicial.

Abra **<http://localhost:5680>** e crie seu usuário proprietário. Não existe login ou senha universal: use o acesso que você cadastrar nesta instalação.

| Endereço/serviço | Finalidade |
| --- | --- |
| `http://localhost:5680` | Editor e login n8n |
| `http://localhost:5681` | Seletor de mídias; abra pelo link privado recebido com `MIDIAS` no chat |
| PostgreSQL e APIs dos serviços | Internos à rede Docker, sem porta pública no host |

As portas locais podem ser alteradas no `.env`. Ao mudar `N8N_PORT`, ajuste também `N8N_EDITOR_BASE_URL` e `WEBHOOK_URL`. Ao mudar `MEDIA_EDITOR_PORT`, ajuste `MEDIA_EDITOR_BASE_URL`.

## 4. Importar os workflows

**Montar a pasta `workflows/` no Docker não importa os JSON automaticamente.** Depois de criar o proprietário, execute:

```bash
python3 scripts/install_chatbot.py
python3 scripts/install_image_agent.py
python3 scripts/install_comment_workflows.py
```

Os instaladores registram os IDs da nova instância no `.env`. Eles publicam somente os subworkflows internos necessários; chatbot, monitor e revisão começam inativos. Não preencha esses campos com IDs de contas sociais.

Importe também os quatro modelos manuais, se quiser usá-los pelo editor:

```bash
docker compose exec -T n8n n8n import:workflow --input=/opt/workflows/facebook-photo.json
docker compose exec -T n8n n8n import:workflow --input=/opt/workflows/instagram-photo.json
docker compose exec -T n8n n8n import:workflow --input=/opt/workflows/x-check-account.json
docker compose exec -T n8n n8n import:workflow --input=/opt/workflows/x-text.json
```

Esses quatro comandos são para a primeira instalação; repeti-los pode criar cópias dos modelos. Também é possível usar **Import from File** no editor. Os modelos manuais entram inativos e em dry-run.

## 5. Liberar o chat para usar o app

Recarregue os IDs agora gravados no `.env` e publique o chat com autenticação n8n:

```bash
docker compose up -d --no-deps --wait editorial
python3 scripts/install_media_support.py --publish-chat
```

Entre no n8n e abra **[o chat do aplicativo](http://localhost:5680/webhook/editorial-social-chat/chat)**. Essa publicação disponibiliza a interface; o envio às redes continua bloqueado enquanto `CHATBOT_PUBLISH_ENABLED=false`.

Para usar:

1. Diga o assunto, a legenda desejada e o destino, por exemplo Instagram.
2. Use o botão de anexo ou envie `MIDIAS` para abrir o seletor: selecione arquivos do computador, remova itens e organize a ordem com as setas.
3. Clique em **Usar esta sequência no rascunho**, volte ao chat e peça a legenda ou envie `PREVIA`.
4. Use `SIMULAR` com o código apresentado para validar sem publicar. O chatbot chama os publicadores em dry-run, sem APIs sociais; conversar com a IA usa a chave OpenAI.

JPEG/PNG são normalizados para JPEG. MP4/MOV precisam de vídeo H.264 e áudio AAC quando presente. Limites locais: 10 itens e 100 MB por arquivo; a Meta ainda verifica seus próprios requisitos. Um vídeo sozinho vira Reel; várias mídias viram carrossel. Anexos são suportados inicialmente no Instagram; Facebook mantém foto por URL pública e X mantém texto.

Para importar uma pasta do host, configure `MEDIA_LIBRARY_HOST_PATH` no `.env` e recrie `editorial`. Depois envie `IMPORTAR: caminho relativo` ou um `file:///...` sozinho no chat. A biblioteca é montada somente para leitura. Em outro computador, ajuste o caminho para uma pasta que exista lá; caminhos de uma máquina não dão acesso aos arquivos de outra. Você pode simplesmente usar o botão de upload, sem configurar biblioteca.

## 6. Disponibilizar fotos e vídeos por HTTPS

O Instagram precisa buscar os anexos por uma URL HTTPS pública. O seletor e o dry-run funcionam sem isso, mas o envio real de anexos precisa dessa configuração.

### Opção A: ngrok

No `.env`, preencha `NGROK_AUTHTOKEN` e `NGROK_DOMAIN`. O domínio deve estar sem `https://` e sem caminhos. Configure `MEDIA_PUBLIC_BASE_URL` como a URL HTTPS desse mesmo domínio seguida de `/media/files`. Use os dados da sua própria conta ngrok; não há valores de conta incluídos no repositório.

```bash
nano .env
docker compose config --quiet
docker compose up -d --no-deps --wait editorial instagram-media media-public
docker compose --profile media-public up -d --wait media-tunnel
docker compose --profile media-public ps
```

O túnel encaminha somente para `media-public`, que entrega arquivos em `/media/files/`. Ele não expõe o chat, o painel de seleção nem a API editorial. Não mantenha o mesmo domínio em uso no computador antigo e no novo simultaneamente.

### Opção B: domínio e proxy próprios

Configure HTTPS e encaminhe somente `/media/files/` para `media-public:8083`, numa rede Docker compartilhada. Preencha `MEDIA_PUBLIC_BASE_URL` no `.env` e reaplique `editorial` e `instagram-media` com o comando acima. Confirme que um anexo é acessível externamente antes de tentar publicar. Uma URL interna Docker não funciona para a Meta.

`IMAGE_PUBLIC_BASE_URL` é outra configuração: atende as imagens geradas pelo subagente de IA. O túnel de anexos acima não expõe automaticamente essa rota. Veja [geração de imagem](docs/image-agent.md).

## 7. Habilitar publicação real

Depois de conferir conta, permissões, conteúdo e HTTPS, altere **somente** `CHATBOT_PUBLISH_ENABLED=true` no `.env`:

```bash
nano .env
docker compose config --quiet
docker compose up -d --no-deps --wait editorial instagram-media
```

Peça uma nova `PREVIA`, confira mídias, ordem, legenda e destino e envie `CONFIRMAR` com o código exibido. A IA não aprova nem publica sozinha. Alterações invalidam a confirmação anterior. `restart` não recarrega o `.env`; use `up -d` para aplicar variáveis.

Comentários têm controles separados. Habilitar o chatbot não habilita respostas automáticas: mantenha os controles de comentários desligados até seguir o [guia de comentários](docs/comment-workflows.md).

Se houver timeout ou resultado incerto, confira o Instagram e os registros antes de repetir. Não apague tentativas nem recrie um post incerto automaticamente.

## Rotina: iniciar, parar e atualizar

Depois da instalação, não precisa importar os workflows a cada inicialização:

```bash
# Iniciar os serviços já configurados
docker compose up -d --wait --wait-timeout 300

# Iniciar também o túnel, caso você o tenha configurado
docker compose --profile media-public up -d --wait media-tunnel

# Conferir estado e logs locais
docker compose ps
docker compose logs --tail=50 n8n editorial instagram-media

# Parar preservando volumes e cadastros
docker compose --profile media-public stop
```

Não use `docker compose down -v`: ele apaga os volumes. Não compartilhe logs sem revisá-los. `docker compose config --quiet` valida sem imprimir as credenciais.

Para atualizar o código, faça backup e revise as alterações antes de aplicar:

```bash
bash scripts/backup.sh
git pull --ff-only
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 300
```

Se o chatbot/adaptador de mídia mudou e você quer instalar a definição atual do repositório:

```bash
python3 scripts/install_media_support.py --publish-chat
```

Instaladores substituem as definições correspondentes, incluindo alterações feitas pelo editor; use-os deliberadamente. Uma atualização da versão n8n exige leitura de release notes, backup e validação, conforme [operação](docs/operations.md).

## Migrar para outro computador

Clonar o Git transfere o código e os modelos, mas **não** transfere usuários, workflows instalados, conversas, credenciais, arquivos enviados ou tentativas de publicação. Para manter tudo isso, faça backup/restauração.

### No computador de origem

Finalize os envios em andamento, não inicie novos envios durante o backup e execute na pasta do projeto:

```bash
bash scripts/backup.sh
docker compose --profile media-public stop
```

Copie de forma privada a pasta de backup criada em `backups/` e os arquivos originais da sua biblioteca para o novo computador. O backup contém `.env` e segredos: mantenha-o privado e criptografado no transporte/armazenamento. A chave de criptografia deve acompanhar os dados.

### No computador de destino

Instale as ferramentas da etapa 1 e clone a **mesma revisão do projeto e versão n8n** do backup. Restaure apenas em volumes novos de uma instalação dedicada à recuperação; não execute os comandos sobre outra instalação com dados que precisa preservar.

Coloque a pasta de backup dentro de `backups/`. Ajuste a variável abaixo para o nome real da pasta recebida:

```bash
backup_origem="backups/PASTA_DO_BACKUP"
cp "$backup_origem/env.secret" .env
chmod 600 .env
mkdir -p media-library
nano .env
```

No `.env`, ajuste `MEDIA_LIBRARY_HOST_PATH` para o caminho do novo computador e confira portas/domínios. Preserve `N8N_ENCRYPTION_KEY`, `POSTGRES_PASSWORD` e os IDs de workflows do backup. Na primeira validação, deixe `CHATBOT_PUBLISH_ENABLED=false`, `COMMENTS_READ_ENABLED=false` e `COMMENTS_SEND_ENABLED=false`; não publique o monitor nem inicie o túnel antes de conferir os dados restaurados.

```bash
docker compose config --quiet
docker compose build editorial instagram-media media-public community
docker compose up -d --wait postgres

# Restaurar banco n8n; serviços de aplicação permanecem parados
docker compose exec -T postgres pg_restore -U n8n -d n8n --clean --if-exists --no-owner < "$backup_origem/postgres.dump"

# Restaurar configurações e binários n8n
docker compose run --rm --no-deps -T --user root --entrypoint sh n8n -c 'tar -xzf - -C /home/node/.n8n && chown -R node:node /home/node/.n8n' < "$backup_origem/n8n-data.tar.gz"

# Restaurar conversas e anexos editoriais, se presentes no backup
if [ -f "$backup_origem/editorial.sqlite" ]; then
  docker compose run --rm --no-deps -T --user root --entrypoint sh editorial -c 'cat > /data/editorial.sqlite && chown 1000:1000 /data/editorial.sqlite' < "$backup_origem/editorial.sqlite"
fi
for arquivo in generated-images uploaded-media; do
  if [ -f "$backup_origem/$arquivo.tar.gz" ]; then
    docker compose run --rm --no-deps -T --user root --entrypoint sh editorial -c 'tar -xzf - -C /data && chown -R 1000:1000 /data' < "$backup_origem/$arquivo.tar.gz"
  fi
done

# Restaurar o registro de tentativas de publicação de mídias
if [ -f "$backup_origem/media-publisher.sqlite" ]; then
  docker compose run --rm --no-deps -T --user root --entrypoint sh instagram-media -c 'cat > /data/media-publisher.sqlite && chown 1000:1000 /data/media-publisher.sqlite' < "$backup_origem/media-publisher.sqlite"
fi

# Restaurar opt-outs e histórico de respostas da comunidade
if [ -f "$backup_origem/community.sqlite" ]; then
  docker compose run --rm --no-deps -T --user root --entrypoint sh community -c 'cat > /data/community.sqlite && chown 1000:1000 /data/community.sqlite' < "$backup_origem/community.sqlite"
fi
if [ -d "$backup_origem/response-skills" ]; then
  cp -a "$backup_origem/response-skills/." response-skills/
fi

docker compose up -d --wait --wait-timeout 300
docker compose ps
```

Abra <http://localhost:5680> com o usuário e a senha da instalação original. Os workflows e seus IDs vieram do banco: **não rode novamente os instaladores da primeira instalação**. Confira conversas, anexos e estados incertos antes de reabilitar envios pela etapa 7 e o túnel pela etapa 6. Para voltar ao computador antigo, primeiro pare a instalação nova; não mantenha as duas operando as mesmas contas em paralelo.

## Desenvolvimento e verificações opcionais

Para rodar a suíte no host, instale também Node.js e FFmpeg (usados pelos testes). No Ubuntu:

```bash
sudo apt install -y nodejs ffmpeg
python3 -m compileall -q scripts services/editorial
python3 -m unittest discover -s tests
docker compose config --quiet
```

Para regenerar os JSON a partir dos geradores versionados:

```bash
python3 scripts/build_workflows.py
python3 scripts/build_chat_workflows.py
python3 scripts/build_image_workflow.py
python3 scripts/build_comment_workflows.py
```

Gerar arquivos não atualiza a instância n8n automaticamente. Exporte alterações sem credenciais e sem pinData. Não execute `smoke_chatbot.py` sobre chatbot publicado/em uso, nem smoke de comentários com leitura/envio reais habilitados.

## Documentação e limites

- [Chatbot, anexos e confirmação](docs/chatbot.md)
- [Configurar Meta](docs/meta-setup.md) e [X](docs/x-setup.md)
- [Subagente de geração de imagem](docs/image-agent.md)
- [Comentários da comunidade](docs/comment-workflows.md)
- [Operação, backup e restauração](docs/operations.md)
- [Arquitetura](docs/architecture.md)
- [MCP e skill](docs/mcp.md)
- [Regras do projeto](AGENTS.md) e [skill de publicação](skills/n8n-social-publishing/SKILL.md)
- [Fontes e licenciamento](docs/sources-and-license.md)

Agendamento editorial, reconciliação automática, stories e conectores YouTube/TikTok continuam fora do escopo implementado. No X, upload de mídia e renovação OAuth não estão implementados. O sistema registra tentativas, mas não promete envio único na API remota.
