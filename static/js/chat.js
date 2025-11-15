const CURRENT_CHAT = document.body.dataset.chatId || "";

let lbOverlay = null;
let lbImg = null;
let lbPrev = null;
let lbNext = null;
let lbCaption = null;
let lbJump = null;
let lbOcrLayer = null;
let lbImages = [];
let lbFilenameToIndex = {};
let lbIndex = 0;
let lbRecordFound = null;
let lbRecorded = null;
let lbNotFound = null;
let lbPaymentRecord = null;
let lbNote = null;
let lbSave = null;
let lbStatus = null;

let matchEls = [];
let matchIndex = -1;
let btnPrev = null;
let btnNext = null;
let counterEl = null;

function initLightbox() {
  lbOverlay = document.getElementById("lightbox-overlay");
  if (!lbOverlay) return; // not on chat page

  lbImg = document.getElementById("lightbox-img");
  lbPrev = document.getElementById("lightbox-prev");
  lbNext = document.getElementById("lightbox-next");
  lbCaption = document.getElementById("lightbox-caption");
  lbJump = document.getElementById("lightbox-jump");
  lbOcrLayer = document.getElementById("lightbox-ocr-layer");
  lbRecordFound = document.getElementById("lb-record-found");
  lbRecorded = document.getElementById("lb-recorded");
  lbNotFound = document.getElementById("lb-not-found");
  lbPaymentRecord = document.getElementById("lb-payment-record");
  lbNote = document.getElementById("lightbox-note");
  lbSave = document.getElementById("lightbox-save");
  lbStatus = document.getElementById("lightbox-status");

  lbImages = Array.from(document.querySelectorAll("img.chat-image"));
  lbFilenameToIndex = {};
  lbImages.forEach((img, idx) => {
    img.dataset.lbIndex = idx;
    const filename = img.dataset.filename;
    if (filename) lbFilenameToIndex[filename] = idx;
    img.addEventListener("click", (e) => {
      e.stopPropagation();
      openLightbox(idx);
    });
  });

  const autoSaveCheckbox = () => {
    saveImageMeta();
  };
  lbRecordFound.addEventListener("change", autoSaveCheckbox);
  lbRecorded.addEventListener("change", autoSaveCheckbox);
  lbNotFound.addEventListener("change", autoSaveCheckbox);
  lbPaymentRecord.addEventListener("change", autoSaveCheckbox);

  lbOverlay.addEventListener("click", (e) => {
    if (e.target === lbOverlay) {
      closeLightbox();
    }
  });

  lbPrev.addEventListener("click", (e) => {
    e.stopPropagation();
    showDelta(-1);
  });
  lbNext.addEventListener("click", (e) => {
    e.stopPropagation();
    showDelta(1);
  });

  lbJump.addEventListener("click", (e) => {
    e.stopPropagation();
    const msgId = lbJump.dataset.msgId;
    closeLightbox();
    if (msgId) {
      const el = document.getElementById(msgId);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("msg-highlight");
        setTimeout(() => el.classList.remove("msg-highlight"), 1500);
      }
    }
  });

  lbImg.addEventListener("load", () => {
    renderOcrHighlights();
  });

  lbSave.addEventListener("click", (e) => {
    e.stopPropagation();
    saveImageMeta();
  });

  document.addEventListener("keydown", (e) => {
    if (lbOverlay.style.display === "flex") {
      if (e.key === "Escape") closeLightbox();
      else if (e.key === "ArrowRight") showDelta(1);
      else if (e.key === "ArrowLeft") showDelta(-1);
    }
  });
}

function openLightbox(index) {
  if (!lbImages.length) return;
  lbIndex = index;
  updateLightboxFromCurrent();
  lbOverlay.style.display = "flex";
}

function closeLightbox() {
  lbOverlay.style.display = "none";
  // Keep ?img= in URL so refresh can reopen same image
}

function showDelta(delta) {
  if (!lbImages.length) return;
  lbIndex = (lbIndex + delta + lbImages.length) % lbImages.length;
  updateLightboxFromCurrent();
}

function updateLightboxUrl(filename) {
  if (!filename) return;
  const url = new URL(window.location.href);
  url.searchParams.set("img", filename);
  window.history.replaceState({}, "", url);
}

function updateLightboxFromCurrent() {
  const imgEl = lbImages[lbIndex];
  lbImg.src = imgEl.src;
  const sender = imgEl.dataset.sender || "";
  const dt = imgEl.dataset.datetime || "";
  const msgId = imgEl.dataset.msgId || "";
  const ocrBoxes = imgEl.dataset.ocrBoxes || "[]";
  const filename = imgEl.dataset.filename || "";

  let captionText = "";
  if (sender) captionText += sender;
  if (dt) captionText += (captionText ? " · " : "") + dt;
  lbCaption.textContent = captionText;
  lbJump.dataset.msgId = msgId;

  lbImg.dataset.ocrBoxes = ocrBoxes;
  lbImg.dataset.filename = filename;

  updateLightboxUrl(filename);
  clearOcrLayer();
  loadImageMeta(filename);
}

function clearOcrLayer() {
  if (!lbOcrLayer) return;
  while (lbOcrLayer.firstChild) {
    lbOcrLayer.removeChild(lbOcrLayer.firstChild);
  }
}

function renderOcrHighlights() {
  clearOcrLayer();
  if (!lbImg || !lbOcrLayer) return;

  const raw = lbImg.dataset.ocrBoxes;
  if (!raw) return;

  let boxes = [];
  try {
    boxes = JSON.parse(raw);
  } catch {
    return;
  }
  if (!boxes || !boxes.length) return;

  const layerWidth = lbImg.clientWidth;
  const layerHeight = lbImg.clientHeight;

  boxes.forEach((b) => {
    const div = document.createElement("div");
    div.className = "ocr-box";
    div.style.left = b.x * layerWidth + "px";
    div.style.top = b.y * layerHeight + "px";
    div.style.width = b.w * layerWidth + "px";
    div.style.height = b.h * layerHeight + "px";
    lbOcrLayer.appendChild(div);
  });
}

function loadImageMeta(filename) {
  if (!filename || !CURRENT_CHAT) return;
  fetch(
    "/image_meta/" +
      encodeURIComponent(CURRENT_CHAT) +
      "/" +
      encodeURIComponent(filename)
  )
    .then((r) => r.json())
    .then((data) => {
      lbRecordFound.checked = !!data.record_found;
      lbRecorded.checked = !!data.recorded;
      lbNotFound.checked = !!data.not_found;
      lbPaymentRecord.checked = !!data.payment_record;
      lbNote.value = data.note || "";
      lbStatus.textContent = "";
    })
    .catch(() => {
      lbStatus.textContent = "Failed to load meta";
    });
}

function saveImageMeta() {
  const filename = lbImg.dataset.filename;
  if (!filename || !CURRENT_CHAT) return;
  const payload = {
    record_found: lbRecordFound.checked,
    recorded: lbRecorded.checked,
    not_found: lbNotFound.checked,
    payment_record: lbPaymentRecord.checked,
    note: lbNote.value || "",
  };
  lbStatus.textContent = "Saving...";
  fetch(
    "/image_meta/" +
      encodeURIComponent(CURRENT_CHAT) +
      "/" +
      encodeURIComponent(filename),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  )
    .then((r) => r.json())
    .then(() => {
      lbStatus.textContent = "Saved";
      setTimeout(() => {
        lbStatus.textContent = "";
      }, 1500);
    })
    .catch(() => {
      lbStatus.textContent = "Error saving";
    });
}

function initSearchNav() {
  btnPrev = document.getElementById("search-prev");
  btnNext = document.getElementById("search-next");
  counterEl = document.getElementById("search-counter");
  if (!btnPrev || !btnNext || !counterEl) return;

  matchEls = Array.from(
    document.querySelectorAll('.bubble[data-has-match="1"]')
  );
  const hasMatches = matchEls.length > 0;

  btnPrev.disabled = !hasMatches;
  btnNext.disabled = !hasMatches;

  btnPrev.addEventListener("click", () => gotoMatch(-1));
  btnNext.addEventListener("click", () => gotoMatch(1));

  updateCounter();

  if (hasMatches) {
    gotoMatch(1); // auto-jump first
  }
}

function updateCounter() {
  if (!counterEl) return;
  if (!matchEls.length) {
    counterEl.textContent = "0 / 0";
    return;
  }
  if (matchIndex === -1) {
    counterEl.textContent = "0 / " + matchEls.length;
  } else {
    counterEl.textContent = matchIndex + 1 + " / " + matchEls.length;
  }
}

function gotoMatch(delta) {
  if (!matchEls.length) return;

  document.querySelectorAll(".bubble.match-focus").forEach((el) => {
    el.classList.remove("match-focus");
  });

  if (matchIndex === -1) {
    matchIndex = delta > 0 ? 0 : matchEls.length - 1;
  } else {
    matchIndex = (matchIndex + delta + matchEls.length) % matchEls.length;
  }

  const el = matchEls[matchIndex];
  el.classList.add("match-focus");
  el.scrollIntoView({ behavior: "smooth", block: "center" });

  updateCounter();
}

function initImageJumpPanel() {
  const buttons = document.querySelectorAll(".image-jump");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const msgId = btn.dataset.msgId;
      if (!msgId) return;
      const el = document.getElementById(msgId);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("msg-highlight");
        setTimeout(() => el.classList.remove("msg-highlight"), 1500);
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (!document.querySelector(".chat-container")) {
    // not on chat page (probably picker)
    return;
  }

  initLightbox();
  initSearchNav();
  initImageJumpPanel();

  // reopen image from URL if ?img= is present
  const url = new URL(window.location.href);
  const imgParam = url.searchParams.get("img");
  if (imgParam && lbFilenameToIndex[imgParam] !== undefined) {
    openLightbox(lbFilenameToIndex[imgParam]);
  }
});
