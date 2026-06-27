const APP_VERSION = "20260627-theme";
const CATALOG_PATH = `data/catalog.json?v=${Date.now()}`;
const THEME_STORAGE_KEY = "pages-library-theme";

function readSavedTheme() {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY);
  } catch (error) {
    return null;
  }
}

function saveTheme(theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (error) {
    // O tema ainda funciona na página atual mesmo se o navegador bloquear storage.
  }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme === "light" ? "light" : "dark";
}

function updateThemeToggle(button) {
  const isLight = document.documentElement.dataset.theme === "light";
  button.textContent = isLight ? "Tema escuro" : "Tema claro";
  button.setAttribute("aria-pressed", String(isLight));
  button.setAttribute("aria-label", isLight ? "Alternar para tema escuro" : "Alternar para tema claro");
}

function initThemeToggle() {
  const savedTheme = readSavedTheme();
  const initialTheme = savedTheme === "light" ? "light" : "dark";
  const button = document.querySelector(".theme-toggle");

  applyTheme(initialTheme);

  if (!button) {
    return;
  }

  updateThemeToggle(button);
  button.addEventListener("click", () => {
    const nextTheme = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    applyTheme(nextTheme);
    saveTheme(nextTheme);
    updateThemeToggle(button);
  });
}

async function loadCatalog() {
  const response = await fetch(CATALOG_PATH, { cache: "no-store" });

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

function formatMissingItemDetails(id, items) {
  const availableIds = (items || []).map((item) => item.id).filter(Boolean);

  return `
    <p>ID procurado: <code>${escapeHtml(id || "(vazio)")}</code></p>
    <p>Itens carregados: ${availableIds.length}</p>
    <p>IDs disponíveis: ${availableIds.length ? escapeHtml(availableIds.join(", ")) : "nenhum"}</p>
  `;
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
  const pdfs = catalog.pdfs || [];
  const pdf = pdfs.find((item) => item.id === id);

  if (!pdf) {
    container.innerHTML = `
      <section class="empty-state">
        <h1>PDF não encontrado</h1>
        <p>Não existe um PDF no catálogo com o id informado.</p>
        ${formatMissingItemDetails(id, pdfs)}
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
  const albums = catalog.albums || [];
  const album = albums.find((item) => item.id === id);

  if (!album) {
    container.innerHTML = `
      <section class="empty-state">
        <h1>Álbum não encontrado</h1>
        <p>Não existe um álbum no catálogo com o id informado.</p>
        ${formatMissingItemDetails(id, albums)}
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
        <div class="player-panel">
          <div class="album-controls">
            <button class="control-button" id="play-album" type="button">Tocar álbum</button>
            <button class="control-button" id="previous-track" type="button">Anterior</button>
            <button class="control-button" id="next-track" type="button">Próxima</button>
            <label class="repeat-control">
              <input id="repeat-album" type="checkbox">
              Repetir álbum
            </label>
          </div>
          <p class="player-status" id="player-status" role="status">Nenhuma faixa selecionada</p>
          <audio class="audio-player" id="audio-player" controls preload="metadata"></audio>
        </div>
        <ol class="track-list" id="track-list">
          ${(album.tracks || []).map((track, index) => `
            <li class="track-item" data-track-index="${index}">
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
  const tracks = album.tracks || [];
  const player = document.querySelector("#audio-player");
  const playAlbumButton = document.querySelector("#play-album");
  const previousButton = document.querySelector("#previous-track");
  const nextButton = document.querySelector("#next-track");
  const repeatCheckbox = document.querySelector("#repeat-album");
  const status = document.querySelector("#player-status");
  const buttons = [...document.querySelectorAll(".track-button")];
  const items = [...document.querySelectorAll(".track-item")];
  let currentIndex = -1;
  let reachedAlbumEnd = false;

  function trackLabel(index) {
    const track = tracks[index];
    return `${index + 1}/${tracks.length}: ${track.title}`;
  }

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle("error", isError);
  }

  function updateActiveTrack() {
    buttons.forEach((button) => {
      button.classList.toggle("active", Number(button.dataset.trackIndex) === currentIndex);
    });
    items.forEach((item) => {
      item.classList.toggle("is-playing", Number(item.dataset.trackIndex) === currentIndex);
    });
  }

  function loadTrack(index, shouldPlay) {
    if (!tracks[index]) {
      return;
    }

    const sources = tracks[index].sources || [];
    if (sources.length === 0) {
      setStatus("Não foi possível reproduzir esta faixa neste navegador.", true);
      return;
    }

    currentIndex = index;
    reachedAlbumEnd = false;
    player.innerHTML = sources
      .map((source) => `<source src="${escapeHtml(source.src)}" type="${escapeHtml(source.type)}">`)
      .join("");
    player.load();
    updateActiveTrack();

    if (!shouldPlay) {
      setStatus(`Pausado: ${tracks[index].title}`);
      return;
    }

    setStatus(`Tocando ${trackLabel(index)}`);
    player.play().catch(() => {
      setStatus("Não foi possível reproduzir esta faixa neste navegador.", true);
    });
  }

  function playTrack(index) {
    loadTrack(index, true);
  }

  function playCurrentOrFirst() {
    playTrack(currentIndex >= 0 ? currentIndex : 0);
  }

  function playPrevious() {
    playTrack(Math.max(currentIndex - 1, 0));
  }

  function playNext() {
    if (currentIndex < tracks.length - 1) {
      playTrack(currentIndex + 1);
      return;
    }

    if (repeatCheckbox.checked && tracks.length > 0) {
      playTrack(0);
      return;
    }

    reachedAlbumEnd = true;
    player.pause();
    setStatus("Fim do álbum");
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      playTrack(Number(button.dataset.trackIndex));
    });
  });

  playAlbumButton.addEventListener("click", playCurrentOrFirst);
  previousButton.addEventListener("click", playPrevious);
  nextButton.addEventListener("click", playNext);

  player.addEventListener("play", () => {
    if (currentIndex >= 0) {
      setStatus(`Tocando ${trackLabel(currentIndex)}`);
    }
  });

  player.addEventListener("pause", () => {
    if (currentIndex >= 0 && !player.ended && !reachedAlbumEnd) {
      setStatus(`Pausado: ${tracks[currentIndex].title}`);
    }
  });

  player.addEventListener("ended", playNext);
  player.addEventListener("error", () => {
    setStatus("Não foi possível reproduzir esta faixa neste navegador.", true);
  });
}

async function init() {
  initThemeToggle();

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
