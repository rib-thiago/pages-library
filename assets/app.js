const CATALOG_PATH = "data/catalog.json";

async function loadCatalog() {
  const response = await fetch(CATALOG_PATH);

  if (!response.ok) {
    throw new Error(`Falha ao carregar ${CATALOG_PATH}`);
  }

  return response.json();
}

function normalizeSearchText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function getPageId() {
  return new URLSearchParams(window.location.search).get("id") || "";
}

function itemSearchText(item) {
  return normalizeSearchText([
    item.title,
    item.author,
    item.artist,
    item.year,
    item.collection,
    ...(item.tags || [])
  ].join(" "));
}

function formatTags(tags) {
  if (!tags || tags.length === 0) {
    return "";
  }

  return `
    <ul class="tag-list">
      ${tags.map((tag) => `<li class="tag">${escapeHtml(tag)}</li>`).join("")}
    </ul>
  `;
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderCard(item, type) {
  const href = type === "pdf" ? `pdf.html?id=${encodeURIComponent(item.id)}` : `album.html?id=${encodeURIComponent(item.id)}`;
  const creator = type === "pdf" ? item.author : item.artist;
  const kicker = type === "pdf" ? "PDF" : "Album";

  return `
    <a class="card" href="${href}">
      <article class="card-body">
        <span class="card-kicker">${kicker}</span>
        <h3 class="card-title">${escapeHtml(item.title)}</h3>
        <div class="meta-list">${escapeHtml(creator)} · ${escapeHtml(item.year)} · ${escapeHtml(item.collection)}</div>
        <p class="card-description">${escapeHtml(item.description)}</p>
        ${formatTags(item.tags)}
      </article>
    </a>
  `;
}

function renderHome(catalog) {
  const searchInput = document.querySelector("#search-input");
  const pdfList = document.querySelector("#pdf-list");
  const albumList = document.querySelector("#album-list");
  const pdfCount = document.querySelector("#pdf-count");
  const albumCount = document.querySelector("#album-count");
  const status = document.querySelector("#home-status");

  function update() {
    const query = normalizeSearchText(searchInput.value);
    const pdfs = (catalog.pdfs || []).filter((item) => itemSearchText(item).includes(query));
    const albums = (catalog.albums || []).filter((item) => itemSearchText(item).includes(query));

    pdfList.innerHTML = pdfs.map((item) => renderCard(item, "pdf")).join("") || '<p class="empty-state">Nenhum PDF encontrado.</p>';
    albumList.innerHTML = albums.map((item) => renderCard(item, "album")).join("") || '<p class="empty-state">Nenhum álbum encontrado.</p>';
    pdfCount.textContent = `${pdfs.length} item${pdfs.length === 1 ? "" : "s"}`;
    albumCount.textContent = `${albums.length} item${albums.length === 1 ? "" : "s"}`;
    status.textContent = query ? `Resultados para "${searchInput.value}"` : "";
  }

  searchInput.addEventListener("input", update);
  update();
}

function renderPdfPage(catalog) {
  const container = document.querySelector("#pdf-page");
  const id = getPageId();
  const pdf = (catalog.pdfs || []).find((item) => item.id === id);

  if (!pdf) {
    container.innerHTML = `
      <section class="empty-state">
        <h1>PDF não encontrado</h1>
        <p>Não existe um PDF no catálogo com o id informado.</p>
        <a href="index.html">Voltar para a home</a>
      </section>
    `;
    return;
  }

  document.title = `${pdf.title} - Pages Library`;
  container.innerHTML = `
    <section class="detail-header">
      <h1>${escapeHtml(pdf.title)}</h1>
      <div class="meta-list">${escapeHtml(pdf.author)} · ${escapeHtml(pdf.year)} · ${escapeHtml(pdf.collection)}</div>
      ${formatTags(pdf.tags)}
      <p class="detail-description">${escapeHtml(pdf.description)}</p>
      <div class="actions">
        <a class="button-link" href="${escapeHtml(pdf.file)}" target="_blank" rel="noopener">Abrir PDF em nova aba</a>
      </div>
    </section>
    <iframe class="pdf-frame" src="${escapeHtml(pdf.file)}" title="${escapeHtml(pdf.title)}"></iframe>
  `;
}

function renderAlbumPage(catalog) {
  const container = document.querySelector("#album-page");
  const id = getPageId();
  const album = (catalog.albums || []).find((item) => item.id === id);

  if (!album) {
    container.innerHTML = `
      <section class="empty-state">
        <h1>Álbum não encontrado</h1>
        <p>Não existe um álbum no catálogo com o id informado.</p>
        <a href="index.html">Voltar para a home</a>
      </section>
    `;
    return;
  }

  document.title = `${album.artist} - ${album.title} - Pages Library`;
  container.innerHTML = `
    <section class="album-layout">
      <div class="cover">
        ${album.cover ? `<img src="${escapeHtml(album.cover)}" alt="Capa de ${escapeHtml(album.title)}">` : "Sem capa"}
      </div>
      <div>
        <div class="detail-header">
          <h1>${escapeHtml(album.title)}</h1>
          <div class="meta-list">${escapeHtml(album.artist)} · ${escapeHtml(album.year)} · ${escapeHtml(album.collection)}</div>
          ${formatTags(album.tags)}
          <p class="detail-description">${escapeHtml(album.description)}</p>
        </div>
        <audio class="audio-player" id="audio-player" controls preload="metadata"></audio>
        <ol class="track-list" id="track-list">
          ${(album.tracks || []).map((track, index) => `
            <li>
              <button class="track-button" type="button" data-track-index="${index}">
                ${index + 1}. ${escapeHtml(track.title)}
              </button>
            </li>
          `).join("")}
        </ol>
      </div>
    </section>
  `;

  setupTrackPlayer(album);
}

function setupTrackPlayer(album) {
  const player = document.querySelector("#audio-player");
  const buttons = [...document.querySelectorAll(".track-button")];

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const track = album.tracks[Number(button.dataset.trackIndex)];
      player.innerHTML = (track.sources || [])
        .map((source) => `<source src="${escapeHtml(source.src)}" type="${escapeHtml(source.type)}">`)
        .join("");
      player.load();
      player.play().catch(() => {
        // Alguns navegadores bloqueiam autoplay; o usuário ainda pode acionar o player.
      });
      buttons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
    });
  });
}

async function init() {
  const page = document.body.dataset.page;

  try {
    const catalog = await loadCatalog();

    if (page === "home") {
      renderHome(catalog);
    } else if (page === "pdf") {
      renderPdfPage(catalog);
    } else if (page === "album") {
      renderAlbumPage(catalog);
    }
  } catch (error) {
    const message = "Não foi possível carregar o catálogo. Confira se data/catalog.json existe e se o site está sendo servido por HTTP.";
    const status = document.querySelector(".status-message");

    if (status) {
      status.textContent = message;
      status.classList.add("error");
    }

    console.error(error);
  }
}

init();
