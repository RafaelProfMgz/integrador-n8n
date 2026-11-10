# Formatos Instagram e musica

Abra o [formulario Instagram](http://localhost:5680/form/publicar-instagram) com seu login n8n. Os novos formatos pertencem ao formulario Instagram; Facebook continua com uma foto e X com texto.

| Formato | Entrada | Resultado |
| --- | --- | --- |
| Automatico | Uma foto, um video ou varias midias | Foto, Reel ou carrossel conforme a entrada |
| Foto no feed | Uma imagem | Foto no feed |
| Story | Uma imagem ou um video | Video vertical de Story |
| Reels | Um video | Reel vertical |
| Carrossel | De 2 a 10 fotos/videos | Carrossel preservando a ordem |
| Carrossel em video (Reels) | De 1 a 10 imagens | Um Reel com as imagens na ordem |
| Carrossel em video (Story) | De 1 a 10 imagens | Um Story em video com as imagens na ordem |

A ordem pode ser informada como `2,1,3`; ela conta somente fotos/videos, nunca o arquivo de musica. Em branco, preserva a ordem da selecao. Para juntar varias imagens em um unico Story ou Reel, escolha explicitamente a opcao Carrossel em video.

## Duracao e audio

**Segundos por imagem** aceita de 1 a 30, com padrao 5. A duracao total deve ficar entre 3 e 900 segundos para Reel; esta implementacao limita Story de 3 a 60 segundos. Um Story de foto e convertido em video. Os arquivos montados usam H.264, MP4, 720x1280, 30 fps e margens para preservar a imagem inteira, sem recorte. O limite local do resultado e 100 MB. A Meta pode aplicar validacoes adicionais.

Em **Audio**:

- **Manter audio original** preserva o audio do video enviado; sequencias de fotos ficam sem som.
- **Sem som** remove o audio do video final.
- **Musica enviada** incorpora a faixa escolhida no campo Musica e substitui o audio original.

Aceita MP3, WAV, M4A, AAC ou OGG. Escolha um arquivo que voce tenha direito de usar. Pode informar o volume de 0 a 100 e o ponto de inicio em segundos. Se a faixa for menor que o video, ela e repetida para preencher a duracao. O resultado usa AAC 48 kHz. Musica em foto/carrossel estatico exige escolher a conversao para video; nao e descartada silenciosamente.

O catalogo de musicas do Instagram nao esta conectado. Esta implementacao usa o arquivo enviado e nao promete pesquisar ou selecionar faixas desse catalogo. As musicas originais nao sao servidas pelo tunel publico; somente o JPEG/MP4 final pode ser buscado pela Meta.

## Stories

Na modalidade Facebook Login usada no projeto, Stories exigem conta Instagram Business e acesso/permissoes pertinentes. A descricao, hashtags e mencoes do formulario nao viram texto ou stickers no Story. Inclua o texto no proprio arquivo antes de enviar. O adaptador usa `media_type=STORIES`, com o MP4 preparado, e nao envia `caption` nem `share_to_feed` nesse caso.

## Aplicar atualizacoes

```sh
python3 scripts/build_manual_forms.py
docker compose config --quiet
docker compose up -d --build --wait editorial instagram-media
python3 scripts/install_manual_forms.py --publish
python3 -m unittest discover -s tests
```

Os JSON ficam inativos; o instalador publica os formularios apenas com `--publish`. Os modos continuam Simular/Publicar, com confirmacao CONFIRMO e flag CHATBOT_PUBLISH_ENABLED para envio real. Simular monta o arquivo local quando ha conversao, mas nao chama OpenAI nem a API social.

As montagens ficam em uploaded-media, no volume editorial_data. SQLite guarda formato, origem, ordem e estado da montagem, separados do modelo. Backup/restauracao precisam manter esses arquivos e editorial.sqlite juntos, alem dos registros do publicador. Timeout de POST social continua incerto e sem retry automatico; nao confunda conversao concluida com post publicado.

Referencias oficiais: [publicacao Instagram](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/content-publishing/), [colecao Meta no Postman](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api). A consulta automatizada a pagina Meta e ao guia de Audio API retornou limitacao de acesso; o catalogo de audio nao foi implementado nem validado nesta entrega.
