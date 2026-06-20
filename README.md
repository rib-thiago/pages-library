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

## GitHub Pages

GitHub Pages é uma hospedagem estática. Este projeto não possui backend, banco de dados, login, API própria ou processamento no servidor.

O catálogo inicial é manual e fica em `data/catalog.json`. Para atualizar o conteúdo publicado, edite esse arquivo e adicione os arquivos correspondentes nas pastas `pdfs/` e `music/`.
