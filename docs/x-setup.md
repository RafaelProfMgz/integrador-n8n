# Workflows X

Implementados dois modelos manuais, inativos e em dry-run:

- `workflows/x-check-account.json`: consultar a conta autenticada, sem criar posts.
- `workflows/x-text.json`: validar texto, conferir a conta e publicar um post de texto.

O modelo de publicacao chama `GET https://api.x.com/2/users/me`, confere o ID com `X_USER_ID` e so entao faz `POST https://api.x.com/2/tweets` com JSON `text`. A resposta final inclui `post_id` e o link. Tokens nunca sao retornados pelos nodes Code.

## Configuracao no .env

```dotenv
X_USER_ID=
X_OAUTH2_ACCESS_TOKEN=
```

Preencha somente o `.env` local. `X_USER_ID` e o ID numerico da conta, nao o @username. `X_OAUTH2_ACCESS_TOKEN` e um token OAuth 2.0 **de usuario**, obtido apos o usuario autorizar o app pelo fluxo Authorization Code com PKCE. O app-only Bearer Token do painel nao permite publicar em nome da conta. Client ID e Client Secret nao substituem esse token.

Configure o app no Developer Console, callback e autorizacao com `tweet.read`, `tweet.write`, `users.read`. Se optar por renovacao, solicite tambem `offline.access` para obter refresh token. A obtencao/renovacao automatica ainda nao esta implementada: este modelo consome um token de usuario valido fornecido no `.env`. Quando expirar, obtenha/renove fora do workflow e atualize o arquivo. Apenas preencher o ID e a chave de app nao realiza login OAuth.

Confira acesso aos endpoints e condicoes de cobranca vigentes no painel do X. Nenhum credito/plano foi contratado por este projeto. Nem mesmo a verificacao real de conta deve ser tratada como simulacao: ela acessa a API.

## Executar

1. Importe os JSON e execute cada um como esta, com `dry_run: true`. A saida deve ser **Previa sem publicar**, sem chamadas externas e sem exigir token.
2. Configure o ambiente a partir do `.env` quando o acesso ao ambiente estiver liberado. `docker compose up -d --wait n8n` recria o servico com as variaveis; `restart` nao recarrega o Compose.
3. No workflow de verificacao, mude somente `dry_run` para `false`. A chamada GET retorna `user_id` e `username`. Se `X_USER_ID` estiver preenchido e divergir, o fluxo para; se vazio, permite descobrir o ID para preencher no `.env` e reaplicar.
4. No workflow de texto, edite o bloco **Conteudo** com o texto final, execute em simulacao e confira. Para publicar um conteudo autorizado, use `approved: true` e `dry_run: false`.
5. Guarde o ID/link retornado. O destino precisa corresponder ao token e ao `X_USER_ID`.

O texto e normalizado em NFC. Ha estimativa local de comprimento com pesos Unicode v3 e limite 280. Nao e o parser completo twitter-text: URLs encurtadas e sequencias de emojis podem produzir contagem diferente; um texto aceito localmente ainda pode ser rejeitado pela API. Nao suporta posts longos Premium. O JSON de entrada limita-se a `operation`, `dry_run`, `approved` e `text`; campos extras nao sao enviados ao X.

## Falhas e limites atuais

- 401: confira tipo, validade e renovacao do token.
- 403: confira permissoes, acesso ao endpoint e restricoes da conta/app.
- 429: aguarde a janela indicada pelo X. Nao ha retry automatico.
- Timeout/erro ambiguo apos o POST: confira o perfil e reconciliacao antes de repetir; um erro pode ocorrer depois de o post ter sido criado.
- Resposta sem ID valido ou com erros parciais nao e anunciada como sucesso.

Estes modelos nao oferecem deduplicacao duravel, cron, threads, replies, upload de imagens/videos, renovacao de OAuth nem rollback. Nao reconstrua um envio ambiguo como tentativa automatica. O fluxo de verificacao nao comprova permissoes de escrita nem saldo de API; so confirma a identidade acessivel ao token.

## Estado da entrega

Os arquivos e testes do X estao implementados. A aplicacao do Compose com leitura `$env` ficou pendente na etapa anterior por bloqueio da revisao automatica. Os dois workflows foram importados e suas simulacoes passaram dentro do n8n, terminando em Previa sem publicar sem chamadas ao X. Os 17 testes locais tambem passaram. Isso foi feito sem reaplicar o Compose; publicacao real exige as variaveis no container e permissao de acesso ao ambiente. Nao foram realizadas chamadas autenticadas ao X nem publicacoes reais.

## Fontes oficiais

- [Criar post](https://docs.x.com/x-api/posts/create-post)
- [Consultar usuario autenticado](https://docs.x.com/x-api/users/get-my-user)
- [OAuth 2.0 PKCE e renovacao](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code)
- [Pesos Unicode twitter-text v3](https://github.com/twitter/twitter-text/blob/master/config/v3.json)
