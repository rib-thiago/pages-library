# Pages Library

Prova de conceito de uma biblioteca estática para publicar PDFs e álbuns selecionados em um GitHub Pages project site.

O projeto usa somente HTML, CSS e JavaScript puro. Não há framework, dependências externas, CDN, build step, backend, Node, Vite, React, Vue, Svelte, Astro, Next ou Jekyll.

## Estrutura

- `index.html`: home com busca, seção de PDFs e seção de música.
- `pdf.html`: página de detalhe e leitura de um PDF.
- `album.html`: página de detalhe de um álbum com lista de faixas e player.
- `assets/style.css`: tema escuro e layout responsivo.
- `assets/app.js`: carregamento do catálogo, busca e renderização das páginas.
- `data/catalog.json`: catálogo manual inicial.
- `pdfs/`: pasta prevista para arquivos PDF.
- `music/`: pasta prevista para capas e faixas de áudio.
- `scripts/`: pasta reservada para scripts auxiliares futuros.

## Testar localmente

Na raiz do repositório, rode:

```bash
python3 -m http.server 8000
```

Depois acesse:

```text
http://localhost:8000/
```

O site precisa ser servido por HTTP porque o JavaScript carrega `data/catalog.json` com `fetch`.

Se o servidor estiver rodando em outra máquina acessível por SSH, crie um túnel local:

```bash
ssh -L 8000:localhost:8000 homelab
```

Com o túnel ativo, acesse no navegador local:

```text
http://localhost:8000/
```

## Publicar no GitHub Pages

Este repositório foi preparado para funcionar como um GitHub Pages project site em:

```text
https://rib-thiago.github.io/pages-library/
```

Para publicar:

1. Envie os arquivos para o repositório `pages-library` no GitHub.
2. Abra as configurações do repositório.
3. Em Pages, publique a partir da branch desejada e da raiz do projeto.
4. Aguarde a conclusão do deploy e acesse a URL esperada.

Todos os caminhos usados pelo site são relativos, como `assets/app.js`, `data/catalog.json`, `pdf.html?id=...`, `album.html?id=...`, `pdfs/...` e `music/...`. Por isso, o site funciona dentro do prefixo `/pages-library/` sem configuração adicional.

## Adicionar um PDF

1. Coloque o arquivo PDF dentro de `pdfs/`, por exemplo `pdfs/meu-documento.pdf`.
2. Edite `data/catalog.json`.
3. Adicione um item no array `pdfs`:

```json
{
  "id": "meu-documento",
  "title": "Meu Documento",
  "author": "Nome do Autor",
  "year": "2026",
  "collection": "Minha Coleção",
  "tags": ["tag1", "tag2"],
  "description": "Descrição curta do PDF.",
  "file": "pdfs/meu-documento.pdf"
}
```

O campo `id` deve ser único. A página será aberta em `pdf.html?id=meu-documento`.

Em produção, o link correspondente será:

```text
https://rib-thiago.github.io/pages-library/pdf.html?id=meu-documento
```

## Adicionar um álbum FLAC

1. Crie uma pasta para o álbum dentro de `music/`, por exemplo `music/meu-album/`.
2. Coloque a capa e as faixas nessa pasta, por exemplo `cover.jpg` e `01-faixa.flac`.
3. Edite `data/catalog.json`.
4. Adicione um item no array `albums`:

```json
{
  "id": "meu-album",
  "title": "Meu Álbum",
  "artist": "Nome do Artista",
  "year": "2026",
  "collection": "Minha Coleção",
  "tags": ["flac", "ao-vivo"],
  "description": "Descrição curta do álbum.",
  "cover": "music/meu-album/cover.jpg",
  "tracks": [
    {
      "title": "Primeira Faixa",
      "sources": [
        {
          "src": "music/meu-album/01-faixa.flac",
          "type": "audio/flac"
        }
      ]
    }
  ]
}
```

Cada faixa aceita um array `sources`, permitindo adicionar formatos alternativos no futuro, como `audio/mpeg`.

Em produção, o link correspondente será:

```text
https://rib-thiago.github.io/pages-library/album.html?id=meu-album
```

O player usa um único elemento `<audio controls>` e cria elementos `<source>` a partir de `tracks[].sources`. Arquivos FLAC devem ser cadastrados com `type` igual a `audio/flac`. O suporte de reprodução depende do navegador do visitante; manter uma fonte alternativa `audio/mpeg` é opcional, mas recomendado quando compatibilidade ampla for necessária.

## Adicionar materiais com o importador interativo

Rode o importador a partir da raiz do repositório:

```bash
python3 scripts/library-importer.py
```

Ele busca PDFs em `/srv/media/calibre-library` e álbuns em `/srv/media/music`. É possível buscar por termo ou navegar pelas pastas de autores/artistas até escolher um PDF ou álbum. O script copia os arquivos escolhidos para dentro deste repositório e atualiza `data/catalog.json`.

Antes de aplicar, o importador mostra um resumo e oferece dry-run. Ele também permite remover PDFs ou álbuns do catálogo e, com confirmação explícita, apagar os arquivos associados dentro do repositório. Depois de uma alteração, o menu pode validar o catálogo, mostrar `git status`, fazer commit e fazer push. Commit e push sempre pedem confirmação explícita.

Fluxo recomendado:

1. Rode `python3 scripts/library-importer.py`.
2. Navegue ou busque e importe o material escolhido.
3. Valide o catálogo pelo menu.
4. Teste localmente com `python3 -m http.server 8000`.
5. Faça commit e push pelo script ou manualmente.

Depois do deploy no GitHub Pages, se o navegador ainda mostrar conteúdo antigo, abra a home com um parâmetro novo de cache busting, por exemplo:

```text
https://rib-thiago.github.io/pages-library/?v=force3
```

Depois de importar, teste localmente:

```bash
python3 -m http.server 8000
```

Em seguida, revise e publique manualmente:

```bash
git status
git add .
git commit -m "Add selected library materials"
git push
```

## GitHub Pages

GitHub Pages é uma hospedagem estática. Este projeto não possui backend, banco de dados, login, API própria ou processamento no servidor.

O catálogo inicial é manual e fica em `data/catalog.json`. Para atualizar o conteúdo publicado, edite esse arquivo e adicione os arquivos correspondentes nas pastas `pdfs/` e `music/`.
