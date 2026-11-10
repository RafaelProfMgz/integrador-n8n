# Comentarios da comunidade Alpendre

Implementados adaptadores Instagram, Paginas Facebook e X, com polling limitado a publicacoes recentes das contas configuradas. O ponto de partida e Instagram. O site informado e o Alpendre; os fatos usados nas respostas foram extraidos de sua pagina publica e registrados em `response-skills/book-community/knowledge.md`.

Os textos iniciais sao skills deterministicas em JSON, nao geracao livre por IA. Comentarios nao sao enviados a OpenAI. Uma alteracao nas regras entra na proxima classificacao; alteracao da resposta/regras invalida uma aprovacao anterior.

## Workflows instalados

- **Comunidade livros - monitorar comentarios recentes**: entrada manual e agendamento a cada 15 minutos. Importado inativo. Consulta o servico de comentarios, que so le APIs externas quando a leitura esta habilitada.
- **Comunidade livros - revisar respostas**: lista comentario, contexto do post, skill escolhida, sugestao, motivo e codigo de aprovacao.
- **Comunidade livros - aprovar resposta**: subworkflow interno que recebe `record_id` e `approval_token` da fila. Revalida comentario/conta/historico antes de enviar o texto exato da sugestao.
- **Subagente - skills de resposta comunidade de livros**: recebe `text` e opcionalmente `comment_id`; devolve `skill`, `action` e `reply`. Nao consulta redes nem envia nada. Pode ser usado por outros workflows.

O envio usa APIs de comentario proprias, sem chamar o publicador de posts de topo. Instagram usa `/{comment-id}/replies`, Facebook usa `/{comment-id}/comments` e X usa `/2/tweets` com `reply.in_reply_to_tweet_id`.

## Skills iniciais

| Caso | Tratamento |
|---|---|
| Pergunta pelo site/link | Orientar link na bio, contextualizado ao Alpendre |
| Como ler capitulos | Explicar historias capitulo a capitulo |
| Como publicar historia | Orientar o caminho “Publicar uma historia”, sem prometer aceitacao |
| Avaliar, comentar, guardar livros | Explicar recursos de conta confirmados no site |
| Pedido de indicacao | Perguntar genero/preferencia; nao inventar titulos |
| Conversa sobre leitura | Pergunta curta sem spoilers |
| Agradecimento, elogio, saudacao | Acolher sem inserir propaganda |
| Proximo capitulo/cronograma | Revisao, sem inventar data |
| Preco, gratuidade, direitos, PDF/download | Revisao, sem prometer servicos nao confirmados |
| Reclamacao, conta, dados pessoais, spoilers | Revisao humana |
| Spam, instrucoes para o bot, contexto incerto | Revisao, sem executar instrucoes do comentario |
| Pedido para parar | Nao responder e registrar opt-out para o autor/conta |

Regras e textos: `response-skills/book-community/rules.json`. Orientacoes: `response-skills/book-community/SKILL.md`. O link na bio aparece quando a pessoa pergunta sobre acesso ou um recurso do site, sem ser anexado a todos os comentarios. A marca e o site ficam no `.env`.

## Configurar no .env

```dotenv
COMMUNITY_NAME=Alpendre
COMMUNITY_SITE_URL=
COMMENTS_PLATFORMS=instagram
COMMENTS_READ_ENABLED=false
COMMENTS_SEND_ENABLED=false
COMMENTS_MODE=review
COMMENTS_X_REPLY_ENABLED=false
COMMENTS_POST_DAYS=30
COMMENTS_LOOKBACK_DAYS=7
COMMENTS_MAX_POSTS=10
COMMENTS_MAX_COMMENTS=20
COMMENTS_RUN_REPLY_LIMIT=3
COMMENTS_DAILY_LIMIT=20
COMMENTS_AUTHOR_DAILY_LIMIT=2
```

Nesta instalacao o endereco fornecido pelo usuario ja esta em `COMMUNITY_SITE_URL`. Reutilize os IDs/tokens das contas no mesmo `.env`; nao cole credenciais nos workflows nem nas skills.

1. Configure as permissoes de leitura/moderacao pertinentes e selecione inicialmente `COMMENTS_PLATFORMS=instagram`.
2. Habilite somente `COMMENTS_READ_ENABLED=true`, mantendo `COMMENTS_SEND_ENABLED=false` e `COMMENTS_MODE=review`.
3. Aplique somente o servico: `docker compose up -d --no-deps --build --wait community`.
4. Execute manualmente o monitor e depois a fila de revisao. Confira textos, identidade e permissoes antes de publicar o agendamento.
5. Para envio revisado, `COMMENTS_SEND_ENABLED=true` permite que o subworkflow de aprovacao envie uma sugestao com seu codigo valido. O modo `review` continua sem envios automaticos no monitor.
6. Para responder automaticamente apenas casos simples, configure deliberadamente `COMMENTS_MODE=auto` junto de leitura/envio habilitados e publique o monitor. Casos classificados para revisao nao sao enviados automaticamente.

O parametro de entrada `dry_run: true` do endpoint `/run` impede envios, mas, se a leitura estiver habilitada, ainda consulta APIs sociais. Leitura real nao e uma simulacao sem API e pode consumir limites/custos, especialmente no X. Com `COMMENTS_READ_ENABLED=false`, nem mesmo essas leituras sao feitas.

## Contas e permissoes

### Instagram

Modalidade atual: Instagram profissional vinculado a Pagina, com Facebook Login e Graph versionado. Confira `instagram_basic`, `instagram_manage_comments`, `pages_read_engagement` e demais requisitos do app/ativo. Publicar fotos nao concede automaticamente permissao de ler/moderar comentarios. A autenticacao usa `META_INSTAGRAM_ACCOUNT_ID`, `META_INSTAGRAM_ACCESS_TOKEN` e `META_GRAPH_VERSION` do `.env`.

O adaptador verifica ID/username, busca `/{ig-id}/media`, filtra posts recentes e consulta comentarios de primeiro nivel e suas respostas. Se nao conseguir identificar o autor ou conferir o historico de respostas, nao envia automaticamente. Comentarios de anuncios ou outros formatos nao retornados por essa colecao nao estao cobertos.

### Facebook

Use Page Access Token correspondente a `META_FACEBOOK_PAGE_ID`. Confira `pages_read_engagement`, `pages_read_user_content`, `pages_manage_engagement` e o papel de moderacao do operador. O token precisa ser da Pagina configurada; o servico confere `/me` antes de consultar `published_posts`.

### X

Para incluir: `COMMENTS_PLATFORMS=instagram,facebook,x`. Use token OAuth de usuario com acesso de leitura/escrita apropriado. O adaptador combina posts recentes proprios com mencoes e considera somente respostas diretas a esses posts. Mencoes soltas, busca por palavras-chave em posts de terceiros e quotes nao sao respondidas.

A verificacao de resposta anterior usa busca recente; sem acesso a ela, o historico fica incompleto e a interacao segue para revisao. O envio X permanece bloqueado por `COMMENTS_X_REPLY_ENABLED=false`, inclusive para aprovacao via helper, ate validar o acesso e as condicoes de resposta do app. Endpoints/permissoes podem limitar respostas mesmo quando publicar posts simples ja funciona.

As regras oficiais do X exigem interacao iniciada pelo usuario, limite por interacao e respeito ao opt-out; se futuramente trocar os templates por um bot de respostas geradas por IA, o X exige aprovacao previa especifica. Veja [regras de automacao](https://help.x.com/en/rules-and-policies/x-automation) e [guia de desenvolvimento](https://docs.x.com/developer-guidelines). Esta entrega usa regras locais e nao envia comentarios a um LLM.

YouTube e TikTok ainda nao possuem adaptadores de comentarios neste projeto. Exigem configuracao OAuth e verificacao de disponibilidade/permissoes propria; nao sao tratados como integracoes prontas.

As paginas Meta retornaram limitacao de consulta durante esta entrega. Os endpoints/campos precisam ser validados na Graph version escolhida com suas contas antes de habilitar envio. Nenhum teste foi feito em comentarios reais.

## Revisao e seguranca de envio

A fila retorna `record_id` e `approval_token`. Passe exatamente esses dois campos ao subworkflow **aprovar resposta**, usando Execute Sub-workflow. O codigo vale por uma hora. O servico relê o comentario e suas respostas antes do POST; se o texto, autor/conta ou a skill mudaram, bloqueia o envio e exige nova revisao.

Estados do registro: `suggested`, `review`, `skipped`, `replying`, `replied`, `unknown`. A chave unica e `(plataforma, conta, comentario)`. Respostas proprias e comentarios ja respondidos pelo perfil sao ignorados. Ha tambem limite de uma resposta por autor/post, limites diarios e por ciclo. Tentativas incertas contam para esses limites.

O estado `replying` e persistido antes do POST. Timeout, resposta ambigua ou interrupcao apos o envio deixam o registro bloqueado para repeticao automatica. Confira a plataforma e a execucao antes de reconciliar; nao apague o banco para tentar de novo. Isso reduz duplicacoes locais, sem prometer exactly-once na API remota.

Cada pagina/API e lida com limite e cursor. O servico nunca segue uma URL `paging.next` recebida da rede; usa o cursor no host oficial fixo. A coleta e uma amostra limitada: posts antigos fora da janela, paginas alem dos limites e replies aninhadas nao sao cobertos. `partial_scan` informa truncamento. Historico de respostas incompleto impede envio naquele comentario.

A API `community` fica somente na rede Docker, sem porta publicada, e presume containers/operadores confiaveis. Seu endpoint de envio nao e publico. Os tokens ficam no ambiente desse servico e nao sao expostos aos nodes n8n. Este modulo nao depende de liberar `$env` no n8n. Nao ha DMs, curtidas, ocultacao ou exclusao de comentarios.

## Instalacao e validacao

```sh
python3 scripts/build_comment_workflows.py
python3 scripts/install_comment_workflows.py
docker compose up -d --no-deps --build --wait community
python3 -m unittest discover -s tests
python3 scripts/smoke_comment_workflows.py
```

O instalador atualiza somente os quatro workflows de comentarios. Monitor/revisao ficam inativos; apenas os helpers com trigger interno sao publicados. Os IDs ficam no `.env`. O smoke test exige leitura/envio desligados, usa comentario ficticio e restaura o monitor inativo ao final. Nao rode sobre um monitor publicado/em uso.

O backup inclui `community.sqlite` e a pasta `response-skills` quando o servico esta em execucao. Restaure regras e banco do mesmo conjunto, com o servico parado e dono 1000:1000. Nao descarte tentativas incertas ou opt-outs. A retencao/limpeza do historico ainda e manual; planeje preservacao da deduplicacao antes de remover registros.

## Fontes primarias

- [Alpendre](https://alpendre.lotmhub.com.br/) — recursos e voz da comunidade, confirmados por consulta publica.
- [Moderacao de comentarios Instagram](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/comment-moderation/)
- [Graph API Comment](https://developers.facebook.com/docs/graph-api/reference/comment/)
- [Pages API](https://developers.facebook.com/docs/pages-api/posts/)
- [X: mencoes](https://docs.x.com/x-api/users/get-mentions)
- [X: criar post/resposta](https://docs.x.com/x-api/posts/create-post)
