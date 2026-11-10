# Subagente de geracao de imagem

Workflow: **Subagente - gerar imagem para publicacao**. Sua unica funcao e receber uma descricao e devolver uma imagem JPEG. Nao escreve legendas, nao escolhe redes e nao publica. Usa a API Images da OpenAI no servico editorial interno; nao precisa do sandbox do assistente n8n.

## Usar pelo chatbot

No chat editorial:

```text
SIMULAR IMAGEM: foto de uma cafeteria acolhedora, luz natural, mesa de madeira, sem texto
```

Testa o roteamento sem chamar a OpenAI. Para gerar de verdade:

```text
GERAR IMAGEM: foto de uma cafeteria acolhedora, luz natural, mesa de madeira, sem texto
```

Esse comando solicita uma geracao real pela API. O servico nao exige que a publicacao real esteja habilitada para gerar uma imagem: sao operacoes independentes. Depois da geracao, a publicacao continua exigindo uma nova previa e confirmacao. Comandos simultaneos na mesma sessao nao iniciam duas geracoes enquanto ha um job em andamento.

A chave OpenAI ainda precisa ser preenchida no `.env` para chamadas reais. Os testes desta entrega nao geraram imagens pagas.

## Configuracao exclusivamente no .env

```dotenv
OPENAI_API_KEY=
OPENAI_IMAGE_MODEL=gpt-image-1.5
IMAGE_PUBLIC_BASE_URL=
N8N_IMAGE_AGENT_WORKFLOW_ID=
```

O instalador preenche o ID do workflow. O modelo e configuravel; o padrao desta entrega e `gpt-image-1.5`, com JPEG opaco, tamanho quadrado e qualidade media. Confira acesso ao modelo na conta OpenAI. Esses parametros seguem a [API oficial de geracao de imagens](https://developers.openai.com/api/reference/resources/images/methods/generate).

Aplique somente o servico editorial depois de preencher/configurar o `.env`:

```sh
docker compose up -d --no-deps --build --wait editorial
```

Nao e necessario recriar o n8n nem liberar `$env` para este subagente. A chave fica somente no ambiente do servico editorial; nao entra no JSON dos workflows ou no chat.

## Chamar a partir de outro workflow

Use **Execute Sub-workflow**, selecione o workflow instalado e espere sua conclusao. O node aceita campos diretamente ou dentro de `payload`. Exemplo de entrada:

```json
{
  "description": "Foto de uma cafeteria acolhedora com luz natural, sem texto",
  "dry_run": true,
  "request_id": "image-request-unique-001",
  "size": "1024x1024",
  "quality": "medium"
}
```

- `description`: obrigatoria, de 1 a 12000 caracteres.
- `dry_run`: booleano; omitido significa `true`. Use `false` para uma geracao real.
- `request_id`: identifica uma tentativa. Se omitido no subworkflow, deriva da execucao n8n. Para tentativas do mesmo pedido, mantenha o mesmo ID.
- `size`: `1024x1024`, `1024x1536` ou `1536x1024`.
- `quality`: `low`, `medium` ou `high`.

Saida real: `status=image_generated`, `asset_id`, `file_name`, `mime_type`, `image_url` e o arquivo em **binary.data**. Em simulacao retorna `status=dry_run`, sem arquivo e sem chamada ao provedor. A API retorna base64, mas o servico decodifica e guarda o arquivo: o workflow recebe metadados e binario, sem incluir base64 no JSON.

## URL publica para Facebook/Instagram

O arquivo fica persistido em `editorial_data`, na pasta `/data/generated-images`. O n8n consegue baixa-lo por uma rota **interna** do Docker. Essa rota nao e acessivel pela Meta.

Sem `IMAGE_PUBLIC_BASE_URL`, `image_url` retorna `null`: o arquivo pode ser baixado pela execucao do subagente no n8n, mas ainda nao esta hospedado publicamente. O chatbot nao substitui isso por uma URL inventada nem publica uma imagem anterior como se fosse a nova.

Quando houver dominio/proxy HTTPS para as midias, configure, por exemplo:

```dotenv
IMAGE_PUBLIC_BASE_URL=https://midias.seu-dominio.com/images/files
```

O proxy deve encaminhar **somente** `/images/files/` para `editorial:8080`, em rede Docker compartilhada, mantendo a API editorial privada. O codigo nao cria DNS, certificado, proxy ou hospedagem automaticamente e nao verifica a acessibilidade externa da URL configurada. Confirme que a Meta consegue buscar o arquivo antes de publicar. Os nomes dos arquivos sao aleatorios; nao use essa rota para conteudo confidencial.

Com a URL publica configurada, a imagem gerada e anexada ao rascunho da sessao. O codigo de confirmacao anterior e invalidado. Peca uma nova previa e confira o arquivo antes de confirmar a publicacao. Se a imagem nova nao tiver URL publica, o campo de imagem anterior e limpo para impedir o uso silencioso do arquivo antigo.

## Repeticoes e falhas

O servico registra `request_id` e o hash da descricao/configuracao antes de chamar a API. Repetir o mesmo ID concluido devolve o mesmo resultado; reutilizar o ID para outro pedido e bloqueado. Se houver timeout ou erro, a tentativa fica incerta e nao e repetida automaticamente. O registro reduz cobrancas duplicadas por retries locais; nao garante exactly-once no provedor.

Uma nova mensagem `GERAR IMAGEM:` cria um novo pedido, com novo ID; pode resultar em outra chamada paga. Para investigar um timeout, consulte o registro e a operacao antes de reenviar. O subagente nao cria variantes em lote, nao edita imagens anexadas e nao publica.

## Instalar, testar e manter

```sh
python3 scripts/build_image_workflow.py
python3 scripts/install_image_agent.py
docker compose up -d --no-deps --build --wait editorial
python3 -m unittest discover -s tests
python3 scripts/smoke_image_agent.py
```

O instalador altera somente o subagente de imagem e salva seu ID no `.env`. Publica-o para chamadas internas porque a versao instalada do n8n exige isso; o JSON versionado permanece inativo por padrao. O teste integrado usa simulacao e uma fixture binaria local, sem chamada OpenAI. Troca temporariamente a entrada do chatbot inativo para testar a ligacao e restaura o workflow ao terminar; nao use sobre um chatbot publicado/em uso.

O backup inclui o registro SQLite e `generated-images.tar.gz`. Restaure o banco e os arquivos juntos no volume editorial, com dono 1000:1000 e acesso privado. Arquivos concluidos sao imutaveis; sua retencao e limpeza ainda sao manuais. Nao apague imagens usadas por posts ou pedidos em andamento sem verificar as referencias.

Se configurar o dominio depois de gerar, repetir a chamada com o mesmo request_id concluido e a mesma descricao recupera o arquivo existente e recalcula sua URL com a configuracao atual; nao chama o provedor novamente.

Verificacao desta entrega: testes locais passaram, assim como roteamento pelo chat, simulacao do subagente, retorno binario nativo com fixture e regressao das tres integracoes sociais. A geracao real continua dependente da chave/acesso OpenAI.
