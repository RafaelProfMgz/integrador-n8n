# Chatbot editorial

O workflow **Editorial - chatbot de publicacoes** recebe a conversa pelo chat do n8n. Um servico interno prepara o rascunho com OpenAI Responses API e guarda sessoes/revisoes em SQLite num volume separado. O modelo nao recebe ferramentas de publicacao nem tokens das redes. O fluxo n8n chama publicadores independentes somente depois da confirmacao deterministica.

## Usar nesta instalacao

1. Preencha somente o `.env` na raiz:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
CHATBOT_PUBLISH_ENABLED=false
```

2. Para aplicar somente a chave/modelo do chatbot, sem recriar n8n: `docker compose up -d --no-deps --build --wait editorial`.
3. Em <http://localhost:5680>, abra **Editorial - chatbot de publicacoes** e use **Open chat** no editor. O workflow fica inativo e o chat fica privado durante a configuracao.
4. Converse sobre assunto, objetivo, publico, tom e texto. Escolha Facebook, Instagram, X ou varias redes. Facebook e Instagram precisam de uma imagem JPEG em URL HTTPS publica; o X recebe somente texto nesta versao.
5. Confira a previa. Responda `SIMULAR codigo` usando o codigo apresentado: o n8n chama os publicadores reais em modo dry-run, sem acessar as APIs sociais. A chave OpenAI e necessaria para escrever/revisar, mas a saudacao, status e os comandos sao locais.

Os IDs de roteamento tambem ficam no `.env`, preenchidos pelo instalador:

```dotenv
N8N_EDITORIAL_CHAT_WORKFLOW_ID=
N8N_PUBLISH_FACEBOOK_WORKFLOW_ID=
N8N_PUBLISH_INSTAGRAM_WORKFLOW_ID=
N8N_PUBLISH_X_WORKFLOW_ID=
```

Nao coloque esses IDs em mensagens do chat. Nao e preciso trocar os IDs das contas Meta/X para IDs de workflow: sao configuracoes diferentes. O servico retorna ao n8n apenas o ID de um publicador da lista configurada, nunca um ID escolhido pelo modelo.

## Exemplo de conversa

- Usuario: "Monte uma publicacao sobre a inauguracao da loja. Tom acolhedor."
- Bot: pede os detalhes que faltam e propoe um texto.
- Usuario: "Quero Instagram e Facebook. Use esta imagem: https://meu-dominio.com/loja.jpg"
- Bot: mostra os textos por rede, a foto, os destinos e um codigo de confirmacao.
- Usuario: "Deixe o texto mais curto."
- Bot: cria uma nova revisao e outra previa; o codigo anterior deixa de valer.
- Usuario: "SIMULAR codigo-da-previa"
- Bot: informa o resultado separado de cada rede, sem publicar.

Uma URL de imagem nao presente no historico do usuario ou no rascunho anterior e descartada. O texto editorial nao gera imagens por conta propria. Para isso, use o subagente dedicado com `GERAR IMAGEM: descricao` ou `SIMULAR IMAGEM: descricao`; ele guarda o JPEG no volume editorial. A URL publica depende da configuracao de hospedagem descrita em `docs/image-agent.md`. Links no texto nao sao baixados automaticamente.

## Publicacao real

O padrao `CHATBOT_PUBLISH_ENABLED=false` bloqueia publicacao real no servico, mesmo se a mensagem pedir para ignorar as regras. Quando as contas e o ambiente estiverem preparados e a publicacao real estiver autorizada, `CHATBOT_PUBLISH_ENABLED=true` permite apresentar tambem `CONFIRMAR codigo` na previa. Esse comando confirma apenas a revisao e os destinos exibidos. Depois de confirmar, o envio e consumido e nao se repete automaticamente.

O acesso `$env` dos publicadores continua dependente da configuracao e aprovacao descritas nos guias Meta/X. O servico editorial foi separado justamente para nao precisar dessa mudanca para conversar e simular: ele recebe somente chave OpenAI, modelo, flag de publicacao e IDs dos publicadores. O n8n em execucao nao foi recriado para habilitar acesso ao ambiente nesta entrega.

Nenhuma publicacao real ou chamada OpenAI paga faz parte dos testes automatizados. A chave da API precisa ser valida e ter acesso/saldo para o modelo configurado; ela permanece no `.env` e e injetada somente no servico editorial. A conversa e o rascunho sao enviados a OpenAI para composicao, com `store: false`; a persistencia local fica no volume `editorial_data`. Isso nao equivale a uma garantia geral de retencao zero do provedor.

## Confirmacao e registro

- Rascunho e historico separados por `sessionId`, com ate 20 mensagens enviadas ao modelo por turno.
- Previa expira em 30 minutos. Uma nova mensagem editorial invalida o codigo anterior, mesmo se o modelo mantiver o texto.
- Transacao SQLite registra todos os destinos antes de despachar; confirmacoes simultaneas consomem o codigo uma unica vez.
- A chave unica e `(sessao, revisao, plataforma, modo)`. A mesma revisao nao e reenviada no mesmo modo depois de uma tentativa registrada. Uma simulacao anterior nao impede a primeira confirmacao real daquela revisao.
- Erros, timeout e resultados invalidos ficam como incertos. O bot nao copia erros de requisicao para o chat nem refaz automaticamente o POST.
- Um processo interrompido pode deixar o estado `dispatching`. Confira as execucoes e as plataformas antes de qualquer recuperacao manual. Nao apague o registro para simplesmente tentar outra vez.
- `status` consulta os resultados. `previa` mostra o rascunho atual. `cancelar` ou `novo` inicia um novo rascunho; nao desfaz publicacoes existentes.

Esse registro impede repeticoes comuns do chatbot, mas nao garante exactly-once na API remota. Nao substitui uma fila editorial agendada, auditoria por usuario ou reconciliacao automatica. Publicadores manuais fora do chatbot mantem seus limites anteriores.

## Instalar e desenvolver

```sh
python3 scripts/build_workflows.py
python3 scripts/build_chat_workflows.py
python3 scripts/install_chatbot.py
docker compose up -d --no-deps --build --wait editorial
python3 -m unittest discover -s tests
python3 scripts/smoke_chatbot.py
```

O instalador importa o chatbot inativo e publica os tres subworkflows, que possuem exclusivamente um trigger de chamada interna. Esta versao do n8n exige publicacao dos subworkflows para que possam ser chamados. Os JSON versionados continuam inativos por padrao. Salva os IDs no `.env`; rodar novamente atualiza esses workflows editoriais, incluindo alteracoes feitas neles pelo editor. Nao altera os modelos manuais preexistentes. Ao editar a logica compartilhada de publicacao, regenere tambem os subworkflows para mante-los alinhados.

O smoke test usa uma sessao de teste e troca temporariamente o trigger do chatbot inativo por uma entrada manual. Exercita o servico, as confirmacoes e as tres chamadas reais de subworkflow em dry-run; restaura o Chat Trigger em `finally`. Nao execute esse teste sobre um chatbot publicado/em uso. Ele nao testa a qualidade da resposta real da OpenAI nem a permissao de publicacao das contas.

## Operacao e acesso

O servico editorial nao tem porta publicada no host. Sua API e interna a rede Compose e presume containers confiaveis. O chat fica disponivel somente no editor por padrao. Para oferecer uma URL hospedada, configure autenticacao **n8n User Auth**, mantenha a exigencia de permissao de execucao e publique deliberadamente o workflow. Nao exponha diretamente a API do servico editorial.

Esta versao atende um operador/equipe de confianca com contas sociais globais no `.env`; nao e um SaaS multiempresa. O `sessionId` separa conversas, mas nao representa identidade autenticada nem autorizacao por tenant. Um produto para varios clientes precisa vincular sessao a usuario verificado, isolar credenciais e aplicar autorizacao por conta.

O backup inclui `editorial.sqlite` quando o servico esta em execucao. Para restaurar, mantenha o servico parado, restaure o arquivo no volume `/data/editorial.sqlite` com dono 1000:1000 e restaure o mesmo `.env` e o banco n8n correspondente; nao descarte estados de envio incertos. Consulte o guia de operacao.

## Fontes

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Chat Trigger n8n](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-langchain.chattrigger/)
- [Execute Sub-workflow n8n](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executeworkflow/)

## Verificacao desta entrega

Passaram 40 testes locais de validacao, conversa, isolamento, confirmacao concorrente, expiracao, edicao, retorno parcial, persistencia e bloqueio de reenvios. O teste integrado executou o n8n, o servico editorial e os tres publicadores em dry-run; todos retornaram simulated. A chave OpenAI ainda nao foi preenchida nesta instalacao; a chamada real do modelo e a qualidade dos textos permanecem para validacao com a chave do usuario.

## Subagente de imagem

O chatbot pode chamar um quarto tipo de subworkflow, dedicado exclusivamente a imagem. Use `GERAR IMAGEM: descricao` ou `SIMULAR IMAGEM: descricao`. Essa chamada invalida a previa anterior e nao publica nada. Para configurar modelo, retorno binario e URL publica, veja [geracao de imagem](image-agent.md).
