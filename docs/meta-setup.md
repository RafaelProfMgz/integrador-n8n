# Configuracao inicial Meta

A modalidade escolhida e Instagram API com Facebook Login para compartilhar a configuracao com Paginas. Necessita Instagram profissional (Business ou Creator) vinculado a uma Pagina Facebook e acesso suficiente a ambos. Perfil pessoal Facebook e Instagram comum nao sao destinos destes modelos.

## Preparar acesso

1. Crie/configure um app em Meta for Developers para os casos de uso pertinentes a Paginas e Instagram. Vincule os ativos e adicione os usuarios de teste conforme o modo do app.
2. Confirme no painel e na documentacao atual os escopos: descoberta de Paginas `pages_show_list`, leitura `pages_read_engagement`, publicacao na Pagina `pages_manage_posts`; Instagram `instagram_basic` e `instagram_content_publish`. Solicite apenas o necessario. Permissoes e revisao dependem de quem usa o app e quais ativos acessa.
3. Obtenha o ID da Pagina e o ID da conta Instagram profissional, distinguindo os dois. Selecione explicitamente uma versao Graph suportada pelo app; preencha `META_GRAPH_VERSION=vNN.N` no `.env` conforme o painel. Nao copiar uma versao antiga de exemplos.
4. Gere o token apropriado para cada API/ativo e confirme escopos, expiracao e acesso. Para Facebook, use o Page Access Token pertinente. Documente um responsavel por renovacao/revogacao.
5. Preencha exclusivamente o `.env` na raiz do projeto:

```dotenv
META_APP_ID=
META_APP_SECRET=
META_GRAPH_VERSION=
META_FACEBOOK_PAGE_ID=
META_FACEBOOK_PAGE_ACCESS_TOKEN=
META_INSTAGRAM_ACCOUNT_ID=
META_INSTAGRAM_ACCESS_TOKEN=
```

Use a versao Graph suportada e os IDs/tokens do seu app. App ID/Secret ficam reservados para obtencao/renovacao dos tokens; os modelos atuais usam Access Tokens e nao fazem OAuth automaticamente. O Compose nao injeta App ID/Secret, pois os modelos nao precisam deles. Os headers usam referencias `$env`, sem gravar o valor do token no JSON do workflow. Nao e necessario criar Credentials no editor para estes modelos.

Apos salvar o `.env`, aplique com `docker compose up -d --wait n8n`; apenas `restart` nao recarrega as variaveis do Compose. Importe os modelos atualizados para substituir os anteriores. Legenda e imagem continuam no bloco Conteudo; IDs, versao e tokens vem exclusivamente do ambiente.

A aprovacao do app, niveis de acesso e eventual verificacao comercial precisam ser conferidos na Meta para o caso real. Esta entrega nao registra app nem consegue obter tokens automaticamente.

## Executar

Importe os JSON pelo editor. Em **Conteudo**, informe somente `caption`, `image_url` e as flags de simulacao/aprovacao. IDs e versao Graph sao lidos do `.env`. Use uma imagem JPEG compativel, em URL HTTPS publica acessivel sem cookies; confirme requisitos atuais de tamanho/proporcao. A URL example.com e apenas demonstrativa.

Execute primeiro com `dry_run: true`: deve sair em **Previa sem publicar**, sem chamada HTTP. Depois de autorizar o conteudo e destino reais, mude para `approved: true` e `dry_run: false` e execute manualmente. A flag e uma protecao do modelo local, nao um sistema de aprovacao com identidade/auditoria.

Facebook: `POST /{page-id}/photos` com `url`, `caption` e `published=true`. Guarde a resposta e o identificador remoto.

Instagram: `POST /{ig-user-id}/media` com `image_url` e `caption`; esperar 15 segundos; consultar o container com `fields=status_code,status`; `POST /{ig-user-id}/media_publish` com `creation_id` somente se FINISHED.

O modelo faz uma consulta de status. Caso ainda esteja IN_PROGRESS ou haja erro, encerra com o ID do container na mensagem. Consulte esse mesmo ID e reconcilie antes de retomar a etapa de publicacao. Executar novamente desde o inicio cria outro container; repetir o POST final pode duplicar conteudo. Nao existe retry automatico nem deduplicacao duravel nesta etapa.

Em erro de autenticacao/permissao, corrija acesso. Em rate limit, respeite o tempo indicado pela Meta. Em timeout de POST, confira o destino antes de qualquer tentativa. Nao use os templates para agendamento recorrente ate implementar a fila descrita na arquitetura.

As paginas developers.facebook.com retornaram limitacao de acesso durante a consulta desta entrega. Confirme no painel Meta os requisitos da versao selecionada antes de executar o primeiro post real.

## Referencias

- [Publicacao Instagram com Facebook Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/content-publishing/)
- [Publicacao em Paginas](https://developers.facebook.com/docs/pages-api/posts/)
- [Colecao oficial Meta no Postman](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)

## Aplicacao pendente

Os arquivos foram atualizados e os testes locais passaram. A aplicacao no Docker foi bloqueada pela revisao automatica porque liberar `$env` permite a editores ler segredos do ambiente. A instancia e os workflows ja importados continuam com a configuracao anterior. A ativacao desta alteracao depende de aprovacao explicita desse acesso e nova aplicacao/importacao; nenhuma publicacao foi feita.

## Acesso ao ambiente

O Compose define `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` para permitir `$env` nos workflows. Quem pode editar workflows pode acessar variaveis do processo; mantenha a edicao restrita a pessoas confiaveis. Os tokens nao sao retornados pelos nodes nem entram na previa; headers sao resolvidos em tempo de execucao. Erros HTTP podem conter detalhes de requisicoes: revise-os antes de compartilhar. Fonte: [configuracao de seguranca n8n](https://github.com/n8n-io/n8n-docs/blob/main/docs/deploy/host-n8n/configure-n8n/basic-configuration/use-environment-variables/security.md).
