const apiBase = `${window.location.origin}`;

const appLoader = document.getElementById("appLoader");
const flash = document.getElementById("flash");
const loadingOverlay = document.getElementById("loadingOverlay");
const loadingText = document.getElementById("loadingText");

window.addEventListener("load", () => {
  setTimeout(() => {
    document.body.classList.remove("booting");
    if (appLoader) appLoader.classList.add("loaded");
  }, 1800);
});

function notify(msg) {
  flash.textContent = msg;
  flash.classList.remove("hidden");
  setTimeout(() => flash.classList.add("hidden"), 3500);
}

function setLoading(active, text = "Analyse en cours...") {
  if (active) {
    loadingText.textContent = text;
    loadingOverlay.classList.remove("hidden");
  } else {
    loadingOverlay.classList.add("hidden");
  }
}

function setTab(tabId) {
  const tabs = ["Analytics", "Animal", "Theft", "Queue", "Docs", "Access"];
  tabs.forEach((name) => {
    document.getElementById(`tab${name}`)?.classList.remove("active");
    document.getElementById(`view${name}`)?.classList.remove("active");
  });
  document.getElementById(`tab${tabId}`)?.classList.add("active");
  document.getElementById(`view${tabId}`)?.classList.add("active");
  document.querySelector(".workspace")?.scrollTo({ top: 0, behavior: "smooth" });
}

const tabAnimal = document.getElementById("tabAnimal");
const tabTheft = document.getElementById("tabTheft");
const tabQueue = document.getElementById("tabQueue");
const tabDocs = document.getElementById("tabDocs");
const tabAccess = document.getElementById("tabAccess");
const tabAnalytics = document.getElementById("tabAnalytics");
if (tabAnimal) tabAnimal.addEventListener("click", () => setTab("Animal"));
if (tabTheft) tabTheft.addEventListener("click", () => setTab("Theft"));
if (tabQueue) tabQueue.addEventListener("click", () => setTab("Queue"));
if (tabDocs) tabDocs.addEventListener("click", () => setTab("Docs"));
if (tabAccess) tabAccess.addEventListener("click", () => setTab("Access"));
if (tabAnalytics) tabAnalytics.addEventListener("click", () => setTab("Analytics"));

// --- Animal & Bag functionality ---
const btnImage = document.getElementById("btnImage");
const btnVideo = document.getElementById("btnVideo");
const btnYoutube = document.getElementById("btnYoutube");

const imageForm = document.getElementById("imageForm");
const videoForm = document.getElementById("videoForm");
const youtubeForm = document.getElementById("youtubeForm");

const imageInput = document.getElementById("imageInput");
const imgMinConfidenceInput = document.getElementById("imgMinConfidence");
const videoInput = document.getElementById("videoInput");
const sampleSecInput = document.getElementById("sampleSec");
const thresholdInput = document.getElementById("threshold");
const minConfidenceInput = document.getElementById("minConfidence");
const targetLabelInput = document.getElementById("targetLabel");
const youtubeUrlInput = document.getElementById("youtubeUrl");

const imageResult = document.getElementById("imageResult");
const videoSummary = document.getElementById("videoSummary");
const eventsEl = document.getElementById("events");
const eventsTitle = document.getElementById("eventsTitle");

function showSourceForm(form) {
  [imageForm, videoForm, youtubeForm].forEach((f) => f.classList.add("hidden"));
  form.classList.remove("hidden");
}
btnImage.addEventListener("click", () => showSourceForm(imageForm));
btnVideo.addEventListener("click", () => showSourceForm(videoForm));
btnYoutube.addEventListener("click", () => showSourceForm(youtubeForm));
showSourceForm(imageForm);

function clearAnimalResults() {
  imageResult.classList.add("hidden");
  imageResult.innerHTML = "";
  videoSummary.classList.add("hidden");
  videoSummary.innerHTML = "";
  eventsEl.innerHTML = "";
}

imageForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAnimalResults();
  if (!imageInput.files?.length) return notify("Choisissez une image.");
  const fd = new FormData();
  fd.append("image", imageInput.files[0]);
  const minConf = Number(imgMinConfidenceInput.value || 0.6);

  try {
    const submitBtn = imageForm.querySelector("button[type='submit']");
    submitBtn.disabled = true;
    submitBtn.textContent = "Analyse en cours...";
    setLoading(true, "Analyse image en cours...");
    const res = await fetch(`${apiBase}/model3/predict-image?min_confidence=${minConf}`, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur analyse image");
    imageResult.innerHTML = `
      <img class="annotated" src="${data.annotated_image_data_url}" alt="annotated" />
      <p><strong>Label final:</strong> ${data.label}</p>
      <p><strong>Label brut:</strong> ${data.raw_label}</p>
      <p><strong>Confidence:</strong> ${(data.confidence * 100).toFixed(1)}%</p>
    `;
    imageResult.classList.remove("hidden");
  } catch (err) {
    notify(err.message);
  } finally {
    const submitBtn = imageForm.querySelector("button[type='submit']");
    submitBtn.disabled = false;
    submitBtn.textContent = "Analyser l'image";
    setLoading(false);
  }
});

videoForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAnimalResults();
  if (!videoInput.files?.length) return notify("Choisissez une video.");
  const fd = new FormData();
  fd.append("video", videoInput.files[0]);
  const sample = Number(sampleSecInput.value || 1.0);
  const threshold = Number(thresholdInput.value || 0.6);
  const minConfidence = Number(minConfidenceInput.value || 0.6);
  const targetLabel = targetLabelInput.value || "all";

  try {
    const submitBtn = videoForm.querySelector("button[type='submit']");
    submitBtn.disabled = true;
    submitBtn.textContent = "Analyse en cours...";
    setLoading(true, "Analyse video en cours...");
    const url = `${apiBase}/model3/analyze-video?sample_every_sec=${sample}&event_threshold=${threshold}&min_confidence=${minConfidence}&target_label=${targetLabel}`;
    const res = await fetch(url, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur analyse video");
    videoSummary.innerHTML = `
      <p><strong>FPS:</strong> ${data.fps}</p>
      <p><strong>Frames echantillonnees:</strong> ${data.sampled_frames}</p>
      <p><strong>Counts:</strong> animal=${data.class_counts.animal || 0}, bag=${data.class_counts.bag || 0}</p>
      <p><strong>Events:</strong> ${data.events.length}</p>
    `;
    videoSummary.classList.remove("hidden");
    eventsTitle.textContent = `Events detectes (${data.target_label})`;
    eventsEl.innerHTML = data.events.map((ev) => `
      <article class="event ${ev.raw_label === "animal" ? "animal" : "bag"}">
        <img src="${ev.snapshot_data_url}" alt="event" />
        <div class="meta">
          <div><strong>Time:</strong> ${ev.timestamp_sec}s</div>
          <div><strong>Label:</strong> ${ev.label} (raw: ${ev.raw_label})</div>
          <div><strong>Confidence:</strong> ${(ev.confidence * 100).toFixed(1)}%</div>
        </div>
      </article>
    `).join("");
  } catch (err) {
    notify(err.message);
  } finally {
    const submitBtn = videoForm.querySelector("button[type='submit']");
    submitBtn.disabled = false;
    submitBtn.textContent = "Analyser la video";
    setLoading(false);
  }
});

youtubeForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!youtubeUrlInput.value.trim()) return notify("Entrez une URL YouTube.");
  const res = await fetch(`${apiBase}/model3/analyze-youtube`, { method: "POST" });
  const data = await res.json();
  notify(data.message || "Fonction en preparation.");
});

// --- Theft functionality ---
const btnTheftVideo = document.getElementById("btnTheftVideo");
const btnTheftYoutube = document.getElementById("btnTheftYoutube");
const theftVideoForm = document.getElementById("theftVideoForm");
const theftYoutubeForm = document.getElementById("theftYoutubeForm");
const theftVideoInput = document.getElementById("theftVideoInput");
const theftYoutubeUrlInput = document.getElementById("theftYoutubeUrl");
const confPersonInput = document.getElementById("confPerson");
const confTheftInput = document.getElementById("confTheft");
const frameStrideInput = document.getElementById("frameStride");
const confPersonYtInput = document.getElementById("confPersonYt");
const confTheftYtInput = document.getElementById("confTheftYt");
const frameStrideYtInput = document.getElementById("frameStrideYt");
const theftSummary = document.getElementById("theftSummary");
const theftEvents = document.getElementById("theftEvents");
const theftFaceGallery = document.getElementById("theftFaceGallery");
const theftFacesRefreshBtn = document.getElementById("theftFacesRefreshBtn");

function showTheftSource(form) {
  [theftVideoForm, theftYoutubeForm].forEach((f) => f.classList.add("hidden"));
  form.classList.remove("hidden");
}
btnTheftVideo.addEventListener("click", () => showTheftSource(theftVideoForm));
btnTheftYoutube.addEventListener("click", () => showTheftSource(theftYoutubeForm));
showTheftSource(theftVideoForm);

function clearTheftResults() {
  theftSummary.classList.add("hidden");
  theftEvents.innerHTML = "";
}

async function loadTheftFaces() {
  if (!theftFaceGallery) return;
  try {
    const res = await fetch(`${apiBase}/theft/suspect-faces?limit=80`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur chargement visages suspects");
    const items = data.items || [];
    if (!items.length) {
      theftFaceGallery.innerHTML = `<p class="small-muted">Aucun visage suspect sauvegarde pour le moment.</p>`;
      return;
    }
    theftFaceGallery.innerHTML = items.map((item) => {
      const date = item.created_at_unix_ms ? new Date(item.created_at_unix_ms).toLocaleString() : "-";
      const statusClass = item.status === "THEFT" ? "face-theft" : "face-suspect";
      return `
        <article class="face-card ${statusClass}">
          <img src="${item.image_data_url}" alt="visage ${item.status}" />
          <div class="meta">
            <strong>${item.status}</strong>
            <span>${date}</span>
          </div>
        </article>
      `;
    }).join("");
  } catch (err) {
    theftFaceGallery.innerHTML = `<p class="small-muted">Impossible de charger les visages: ${err.message}</p>`;
  }
}

if (theftFacesRefreshBtn) theftFacesRefreshBtn.addEventListener("click", loadTheftFaces);
loadTheftFaces();

function renderTheftResult(data) {
  theftSummary.innerHTML = `
    <p><strong>Frames:</strong> ${data.processed_frames}</p>
    <p><strong>FPS:</strong> ${data.fps}</p>
    <p><strong>Status:</strong> NORMAL=${data.status_counts.NORMAL || 0}, SUSPECT=${data.status_counts.SUSPECT || 0}, THEFT=${data.status_counts.THEFT || 0}</p>
    <p><strong>Events:</strong> ${data.events.length}</p>
  `;
  theftSummary.classList.remove("hidden");
  if (!data.events.length) {
    theftEvents.innerHTML = `<p class="small-muted">Aucun evenement suspect detecte pour cette video.</p>`;
    notify("Analyse terminee: aucun evenement suspect.");
    return;
  }
  theftEvents.innerHTML = data.events.map((ev) => `
    <article class="event ${ev.status === "THEFT" ? "bag" : "animal"}">
      <img src="${ev.saved_image_data_url || ev.snapshot_data_url}" alt="theft event" />
      <div class="meta">
        <div><strong>ID:</strong> ${ev.track_id}</div>
        <div><strong>Status:</strong> ${ev.status}</div>
        <div><strong>Capture auto:</strong> ${ev.saved_source}</div>
        <div><strong>Saved path:</strong> ${ev.saved_image_path}</div>
        <div><strong>Time:</strong> ${ev.timestamp_sec}s</div>
      </div>
    </article>
  `).join("");
}

theftVideoForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearTheftResults();
  if (!theftVideoInput.files?.length) return notify("Choisissez une video locale.");
  const fd = new FormData();
  const confPerson = Number(confPersonInput.value || 0.3);
  const confTheft = Number(confTheftInput.value || 0.4);
  const frameStride = Number(frameStrideInput.value || 2);
  fd.append("video", theftVideoInput.files[0]);

  try {
    const submitBtn = theftVideoForm.querySelector("button[type='submit']");
    submitBtn.disabled = true;
    submitBtn.textContent = "Surveillance en cours...";
    setLoading(true, "Surveillance vol en cours...");
    const url = `${apiBase}/theft/analyze-video?conf_person=${confPerson}&conf_theft=${confTheft}&frame_stride=${frameStride}`;
    const res = await fetch(url, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur surveillance");
    renderTheftResult(data);
    await loadTheftFaces();
  } catch (err) {
    notify(err.message);
  } finally {
    const submitBtn = theftVideoForm.querySelector("button[type='submit']");
    submitBtn.disabled = false;
    submitBtn.textContent = "Lancer surveillance";
    setLoading(false);
  }
});

theftYoutubeForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearTheftResults();
  const youtubeUrl = (theftYoutubeUrlInput.value || "").trim();
  if (!youtubeUrl) return notify("Entrez une URL YouTube.");

  const confPerson = Number(confPersonYtInput.value || 0.3);
  const confTheft = Number(confTheftYtInput.value || 0.4);
  const frameStride = Number(frameStrideYtInput.value || 2);

  try {
    const submitBtn = theftYoutubeForm.querySelector("button[type='submit']");
    submitBtn.disabled = true;
    submitBtn.textContent = "Surveillance YouTube...";
    setLoading(true, "Surveillance YouTube en cours...");
    const url = `${apiBase}/theft/analyze-youtube?youtube_url=${encodeURIComponent(youtubeUrl)}&conf_person=${confPerson}&conf_theft=${confTheft}&frame_stride=${frameStride}`;
    const res = await fetch(url, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "YouTube indisponible sur cet environnement.");
    renderTheftResult(data);
    await loadTheftFaces();
  } catch (err) {
    notify(err.message);
  } finally {
    const submitBtn = theftYoutubeForm.querySelector("button[type='submit']");
    submitBtn.disabled = false;
    submitBtn.textContent = "Lancer surveillance YouTube";
    setLoading(false);
  }
});

// --- Queue recommendation functionality ---
const queueVideoForm = document.getElementById("queueVideoForm");
const queueVideoInput = document.getElementById("queueVideoInput");
const queueConfPersonInput = document.getElementById("queueConfPerson");
const queueIouInput = document.getElementById("queueIou");
const queueImgszInput = document.getElementById("queueImgsz");
const queueStrideInput = document.getElementById("queueStride");
const queueMinOverlapInput = document.getElementById("queueMinOverlap");
const queueMinValidCountInput = document.getElementById("queueMinValidCount");
const queueSummary = document.getElementById("queueSummary");
const queueJobStatus = document.getElementById("queueJobStatus");
const queueRefreshBtn = document.getElementById("queueRefreshBtn");

function renderQueueSummary(data) {
  const queueCounts = data.queue_counts || {};
  const queueLines = Object.keys(queueCounts).length
    ? Object.entries(queueCounts)
        .map(([name, count]) => `<li><strong>${name}:</strong> ${count}</li>`)
        .join("")
    : "<li>Aucune file detectee.</li>";
  queueSummary.innerHTML = `
    <p><strong>BEST QUEUE:</strong> <span class="best-queue">${data.best_queue || "N/A"}</span></p>
    <p><strong>Processed frames:</strong> ${data.processed_frames ?? 0}</p>
    <p><strong>FPS:</strong> ${data.fps ?? 0}</p>
    <p><strong>Min valid count:</strong> ${data.min_valid_count ?? 1}</p>
    <p><strong>Output video:</strong> ${data.output_video_path || "-"}</p>
    <p><strong>Queue counts:</strong></p>
    <ul class="queue-list">${queueLines}</ul>
  `;
  queueSummary.classList.remove("hidden");
}

async function refreshQueueLatest(silent = false) {
  try {
    const res = await fetch(`${apiBase}/queue-recommendation/latest`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur latest queue");
    renderQueueSummary(data);
  } catch (err) {
    if (!silent) notify(err.message);
  }
}

function renderQueueJobStatus(job) {
  queueJobStatus.innerHTML = `
    <p><strong>Job status:</strong> ${job.status}</p>
    <p><strong>Job ID:</strong> ${job.job_id || "-"}</p>
    <p><strong>Message:</strong> ${job.message || "-"}</p>
  `;
  queueJobStatus.classList.remove("hidden");
}

async function refreshQueueJobStatus(silent = true) {
  try {
    const res = await fetch(`${apiBase}/queue-recommendation/job-latest`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur status job queue");
    renderQueueJobStatus(data);
  } catch (err) {
    if (!silent) notify(err.message);
  }
}

queueVideoForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!queueVideoInput.files?.length) return notify("Choisissez une video CCTV.");
  const fd = new FormData();
  fd.append("video", queueVideoInput.files[0]);

  const confPerson = Number(queueConfPersonInput.value || 0.25);
  const iou = Number(queueIouInput.value || 0.5);
  const imgsz = Number(queueImgszInput.value || 1280);
  const stride = Number(queueStrideInput.value || 1);
  const minOverlap = Number(queueMinOverlapInput.value || 0.2);
  const minValidCount = Number(queueMinValidCountInput.value || 1);

  try {
    const submitBtn = queueVideoForm.querySelector("button[type='submit']");
    submitBtn.disabled = true;
    submitBtn.textContent = "Analyse files en cours...";
    setLoading(true, "Soumission job files caisse...");
    const url = `${apiBase}/queue-recommendation/submit-video?conf_person=${confPerson}&iou=${iou}&imgsz=${imgsz}&frame_stride=${stride}&min_overlap=${minOverlap}&min_valid_count=${minValidCount}`;
    const res = await fetch(url, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur queue recommendation");
    renderQueueJobStatus(data);
    notify("Job queue lance en arriere-plan. La decision va se mettre a jour automatiquement.");
    await refreshQueueLatest(true);
  } catch (err) {
    notify(err.message);
  } finally {
    const submitBtn = queueVideoForm.querySelector("button[type='submit']");
    submitBtn.disabled = false;
    submitBtn.textContent = "Lancer recommandation caisse";
    setLoading(false);
  }
});

queueRefreshBtn.addEventListener("click", async () => {
  await refreshQueueJobStatus(false);
  await refreshQueueLatest(false);
});

// Poll latest recommendation every second for near real-time queue display.
setInterval(() => {
  refreshQueueJobStatus(true);
  refreshQueueLatest(true);
}, 1000);

// --- Forged docs functionality ---
const docsForm = document.getElementById("docsForm");
const docsImageInput = document.getElementById("docsImageInput");
const docsSummary = document.getElementById("docsSummary");
const docsVisuals = document.getElementById("docsVisuals");

function clearDocsResult() {
  docsSummary.classList.add("hidden");
  docsSummary.innerHTML = "";
  docsVisuals.innerHTML = "";
}

docsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearDocsResult();
  if (!docsImageInput.files?.length) return notify("Choisissez une image document.");
  const fd = new FormData();
  fd.append("image", docsImageInput.files[0]);

  try {
    const submitBtn = docsForm.querySelector("button[type='submit']");
    submitBtn.disabled = true;
    submitBtn.textContent = "Verification en cours...";
    setLoading(true, "Analyse falsification document...");

    const res = await fetch(`${apiBase}/model8/verify-doc`, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur model8");

    const verdictClass = data.is_forged ? "verdict-forged" : "verdict-authentic";
    const verdictText = data.is_forged ? "FORGED" : "AUTHENTIC";
    docsSummary.innerHTML = `
      <p><strong>Verdict:</strong> <span class="${verdictClass}">${verdictText}</span></p>
      <p><strong>Score:</strong> ${Number(data.score).toFixed(5)}</p>
      <p><strong>Threshold:</strong> ${Number(data.threshold).toFixed(5)}</p>
      <p><strong>Message:</strong> ${data.message || "-"}</p>
    `;
    docsSummary.classList.remove("hidden");

    docsVisuals.innerHTML = `
      <article class="event">
        <img src="${data.original_data_url}" alt="original document" />
        <div class="meta"><strong>Original</strong></div>
      </article>
      <article class="event ${data.is_forged ? "bag" : "animal"}">
        <img src="${data.mask_data_url}" alt="forgery mask" />
        <div class="meta"><strong>Forgery Mask</strong></div>
      </article>
      <article class="event ${data.is_forged ? "bag" : "animal"}">
        <img src="${data.heatmap_data_url}" alt="forgery heatmap" />
        <div class="meta"><strong>Heatmap</strong></div>
      </article>
    `;
  } catch (err) {
    notify(err.message);
  } finally {
    const submitBtn = docsForm.querySelector("button[type='submit']");
    submitBtn.disabled = false;
    submitBtn.textContent = "Verifier document";
    setLoading(false);
  }
});

// --- Employee access functionality ---
const accessForm = document.getElementById("accessForm");
const accessSummary = document.getElementById("accessSummary");
const accessCamera = document.getElementById("accessCamera");
const accessCanvas = document.getElementById("accessCanvas");
const accessStartCameraBtn = document.getElementById("accessStartCameraBtn");
const accessStopCameraBtn = document.getElementById("accessStopCameraBtn");
const accessRegisterBtn = document.getElementById("accessRegisterBtn");
const accessEmployeeName = document.getElementById("accessEmployeeName");
let accessCameraStream = null;

function clearAccessResult() {
  accessSummary.classList.add("hidden");
  accessSummary.innerHTML = "";
}

async function startAccessCamera() {
  if (!accessCamera) return;
  try {
    accessCameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    accessCamera.srcObject = accessCameraStream;
  } catch (err) {
    notify("Impossible d'acceder a la camera.");
  }
}

function stopAccessCamera() {
  if (accessCameraStream) {
    accessCameraStream.getTracks().forEach((t) => t.stop());
    accessCameraStream = null;
  }
  if (accessCamera) accessCamera.srcObject = null;
}

if (accessStartCameraBtn) {
  accessStartCameraBtn.addEventListener("click", async () => {
    await startAccessCamera();
  });
}

if (accessStopCameraBtn) {
  accessStopCameraBtn.addEventListener("click", () => {
    stopAccessCamera();
  });
}

if (accessForm && accessSummary && accessCamera && accessCanvas) {
  async function captureAccessBlob() {
    if (!accessCameraStream) {
      notify("Activez la camera d'abord.");
      return null;
    }
    if (!accessCamera.videoWidth || !accessCamera.videoHeight) {
      notify("Camera non prete.");
      return null;
    }
    accessCanvas.width = accessCamera.videoWidth;
    accessCanvas.height = accessCamera.videoHeight;
    const ctx = accessCanvas.getContext("2d");
    ctx.drawImage(accessCamera, 0, 0, accessCanvas.width, accessCanvas.height);
    const blob = await new Promise((resolve) => accessCanvas.toBlob(resolve, "image/jpeg", 0.95));
    if (!blob) notify("Echec capture camera.");
    return blob;
  }

  if (accessRegisterBtn && accessEmployeeName) {
    accessRegisterBtn.addEventListener("click", async () => {
      const employeeName = (accessEmployeeName.value || "").trim();
      if (!employeeName) return notify("Entrez le nom employe.");
      const blob = await captureAccessBlob();
      if (!blob) return;
      const fd = new FormData();
      fd.append("image", blob, "employee_register.jpg");
      try {
        accessRegisterBtn.disabled = true;
        accessRegisterBtn.textContent = "Enregistrement...";
        setLoading(true, "Enregistrement visage...");
        const res = await fetch(`${apiBase}/model9/register-face?employee_name=${encodeURIComponent(employeeName)}`, {
          method: "POST",
          body: fd,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Erreur enregistrement visage");
        notify(data.message || "Visage enregistre.");
      } catch (err) {
        notify(err.message);
      } finally {
        accessRegisterBtn.disabled = false;
        accessRegisterBtn.textContent = "Enregistrer visage";
        setLoading(false);
      }
    });
  }

  accessForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAccessResult();
    const blob = await captureAccessBlob();
    if (!blob) return notify("Echec capture camera.");

    const fd = new FormData();
    fd.append("image", blob, "employee_camera.jpg");

    try {
      const submitBtn = accessForm.querySelector("button[type='submit']");
      submitBtn.disabled = true;
      submitBtn.textContent = "Verification en cours...";
      setLoading(true, "Verification access employee...");

      const res = await fetch(`${apiBase}/model9/verify-access`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erreur model9");

      const verdictClass = data.access_granted ? "verdict-authentic" : "verdict-forged";
      const verdictText = data.access_granted ? "ACCESS GRANTED" : "ACCESS DENIED";
      const badgeFaceDistance = data.debug?.badge_face_distance;
      const badgeFaceMatch = data.debug?.badge_face_match;
      accessSummary.innerHTML = `
        <p><strong>Verdict:</strong> <span class="${verdictClass}">${verdictText}</span></p>
        <p><strong>Liveness score:</strong> ${Number(data.liveness_score).toFixed(5)}</p>
        <p><strong>Liveness threshold:</strong> ${Number(data.liveness_threshold).toFixed(2)}</p>
        <p><strong>Face detected:</strong> ${data.face_detected ? "YES" : "NO"}</p>
        <p><strong>Badge face match:</strong> ${badgeFaceMatch === undefined ? "-" : badgeFaceMatch ? "YES" : "NO"}${badgeFaceDistance === undefined ? "" : ` (distance=${Number(badgeFaceDistance).toFixed(4)})`}</p>
        <p><strong>Face registered:</strong> ${data.face_registered ? "YES" : "NO"}</p>
        <p><strong>Employee:</strong> ${data.employee_name || "-"}</p>
        <p><strong>Badge check:</strong> ${data.badge_ok ? "OK" : "NOT FOUND"} (${data.expected_badge_text})</p>
        <p><strong>Badge text:</strong> ${data.badge_text || "-"}</p>
        <p><strong>Message:</strong> ${data.message || "-"}</p>
      `;
      accessSummary.classList.remove("hidden");
    } catch (err) {
      notify(err.message);
    } finally {
      const submitBtn = accessForm.querySelector("button[type='submit']");
      submitBtn.disabled = false;
      submitBtn.textContent = "Verifier acces";
      setLoading(false);
    }
  });
}

// --- Store analytics functionality ---
const analyticsForm = document.getElementById("analyticsForm");
const analyticsDaysInput = document.getElementById("analyticsDays");
const analyticsTopKInput = document.getElementById("analyticsTopK");
const analyticsKpis = document.getElementById("analyticsKpis");
const analyticsCandles = document.getElementById("analyticsCandles");
const analyticsTopProducts = document.getElementById("analyticsTopProducts");
const analyticsAgents = document.getElementById("analyticsAgents");
let biTooltip = document.getElementById("biTooltip");
if (!biTooltip) {
  biTooltip = document.createElement("div");
  biTooltip.id = "biTooltip";
  biTooltip.className = "bi-tooltip hidden";
  document.body.appendChild(biTooltip);
}

function clearAnalytics() {
  [analyticsKpis, analyticsCandles, analyticsTopProducts, analyticsAgents].forEach((el) => {
    if (!el) return;
    el.classList.add("hidden");
    el.innerHTML = "";
  });
}

function renderLineChart(points, width = 740, height = 220) {
  if (!points?.length) return "<p>Aucune donnee revenue.</p>";
  const vals = points.map((p) => Number(p.value || 0));
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = Math.max(1, max - min);
  const pad = 28;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const pts = vals.map((v, i) => {
    const x = pad + (i / Math.max(1, vals.length - 1)) * innerW;
    const y = pad + (1 - (v - min) / span) * innerH;
    return { x, y, v };
  });
  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
  const areaPath = `${path} L${pts[pts.length - 1].x.toFixed(2)},${height - pad} L${pts[0].x.toFixed(2)},${height - pad} Z`;
  const dots = pts
    .map((p, i) => {
      const date = points[i]?.date || "-";
      return `<circle class="tip-target" data-tip="${date} | Revenue: ${p.v.toFixed(2)} TND" cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="3.2"><title>${date} | Revenue: ${p.v.toFixed(2)} TND</title></circle>`;
    })
    .join("");
  return `
    <svg class="bi-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Revenue trend">
      <path class="line-area" d="${areaPath}" />
      <line class="axis" x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" />
      <line class="axis" x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" />
      <path class="line-path" d="${path}" />
      <g class="line-dots">${dots}</g>
      <text class="chart-label" x="${pad}" y="18">Revenue min ${min.toFixed(2)} TND</text>
      <text class="chart-label" x="${width - pad - 180}" y="18">Revenue max ${max.toFixed(2)} TND</text>
    </svg>
  `;
}

function renderCandles(candles, width = 740, height = 260) {
  if (!candles?.length) return "<p>Aucune donnee chandelle.</p>";
  const rows = candles.slice(-24);
  const hi = Math.max(...rows.map((c) => Number(c.high || 0)));
  const lo = Math.min(...rows.map((c) => Number(c.low || 0)));
  const span = Math.max(1, hi - lo);
  const pad = 28;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const barW = Math.max(4, Math.floor(innerW / (rows.length * 1.7)));
  const body = rows
    .map((c, i) => {
      const x = pad + ((i + 0.5) / rows.length) * innerW;
      const open = Number(c.open || 0);
      const close = Number(c.close || 0);
      const high = Number(c.high || 0);
      const low = Number(c.low || 0);
      const y = (v) => pad + (1 - (v - lo) / span) * innerH;
      const yo = y(open);
      const yc = y(close);
      const yh = y(high);
      const yl = y(low);
      const top = Math.min(yo, yc);
      const h = Math.max(2, Math.abs(yc - yo));
      const cls = close >= open ? "candle-up" : "candle-down";
      return `
        <line x1="${x.toFixed(2)}" y1="${yh.toFixed(2)}" x2="${x.toFixed(2)}" y2="${yl.toFixed(2)}" class="candle-wick ${cls} tip-target" data-tip="${c.date} | High ${high.toFixed(2)} | Low ${low.toFixed(2)}"><title>${c.date} | High ${high.toFixed(2)} | Low ${low.toFixed(2)}</title></line>
        <rect x="${(x - barW / 2).toFixed(2)}" y="${top.toFixed(2)}" width="${barW}" height="${h.toFixed(2)}" class="candle-body ${cls} tip-target" data-tip="${c.date} | Open ${open.toFixed(2)} | Close ${close.toFixed(2)} | Volume ${c.volume}"><title>${c.date} | Open ${open.toFixed(2)} | Close ${close.toFixed(2)} | Volume ${c.volume}</title></rect>
      `;
    })
    .join("");
  return `
    <svg class="bi-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Candlestick revenue">
      <line class="axis" x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" />
      <line class="axis" x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" />
      ${body}
      <text class="chart-label" x="${pad}" y="18">Low ${lo.toFixed(2)}</text>
      <text class="chart-label" x="${width - pad - 120}" y="18">High ${hi.toFixed(2)}</text>
    </svg>
  `;
}

function renderDonut(distribution, size = 220) {
  const entries = Object.entries(distribution || {});
  if (!entries.length) return "<p>Aucune donnee caisse.</p>";
  const total = entries.reduce((s, [, v]) => s + Number(v || 0), 0) || 1;
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.34;
  const stroke = size * 0.18;
  let offset = 0;
  const colors = ["#e30613", "#071a44", "#098a4b", "#d89b16", "#6b4fd8"];
  const rings = entries
    .map(([name, value], i) => {
      const v = Number(value || 0);
      const dash = (v / total) * (2 * Math.PI * r);
      const seg = `
        <circle class="tip-target" data-tip="${name} | Clients: ${v} | Part: ${((v / total) * 100).toFixed(1)}%" cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${colors[i % colors.length]}"
          stroke-width="${stroke}" stroke-dasharray="${dash.toFixed(2)} ${(2 * Math.PI * r).toFixed(2)}"
          stroke-dashoffset="${(-offset).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"></circle>
      `;
      offset += dash;
      return seg;
    })
    .join("");
  const legend = entries
    .map(([name, value], i) => `<li class="legend-item"><span class="legend-swatch" style="background:${colors[i % colors.length]}"></span>${name}: ${value}</li>`)
    .join("");
  return `
    <div class="donut-wrap">
      <svg class="donut-chart" viewBox="0 0 ${size} ${size}" preserveAspectRatio="xMidYMid meet">
        ${rings}
        <text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="middle" class="donut-center">${total}</text>
      </svg>
      <ul class="donut-legend">${legend}</ul>
    </div>
  `;
}

function renderQueueRevenueBars(queueRevenue, width = 740, height = 230) {
  const entries = Object.entries(queueRevenue || {});
  if (!entries.length) return "<p>Aucune donnee revenue par caisse.</p>";
  const sorted = [...entries].sort((a, b) => Number(b[1]) - Number(a[1]));
  const maxVal = Math.max(...sorted.map(([, v]) => Number(v || 0)), 1);
  const pad = 30;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const barW = Math.max(24, Math.floor(innerW / (sorted.length * 1.8)));
  const bars = sorted
    .map(([name, raw], i) => {
      const v = Number(raw || 0);
      const h = (v / maxVal) * innerH;
      const x = pad + ((i + 0.5) / sorted.length) * innerW - barW / 2;
      const y = height - pad - h;
      return `
        <rect class="queue-revenue-bar tip-target" x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barW}" height="${h.toFixed(2)}" data-tip="${name} | Revenue: ${v.toFixed(2)} TND"><title>${name} | Revenue: ${v.toFixed(2)} TND</title></rect>
        <text class="chart-label" x="${(x + barW / 2).toFixed(2)}" y="${height - 10}" text-anchor="middle">${name}</text>
      `;
    })
    .join("");
  return `
    <svg class="bi-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Revenue par caisse">
      <line class="axis" x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" />
      <line class="axis" x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" />
      ${bars}
      <text class="chart-label" x="${pad}" y="18">Max ${maxVal.toFixed(2)} TND</text>
    </svg>
  `;
}

async function fetchAndRenderAnalytics(showSpinner = false) {
  if (!(analyticsKpis && analyticsCandles && analyticsTopProducts && analyticsAgents && analyticsDaysInput && analyticsTopKInput)) return;
  const days = Number(analyticsDaysInput.value || 30);
  const topK = Number(analyticsTopKInput.value || 8);
  try {
    if (showSpinner) setLoading(true, "Mise a jour analytics BI...");
    const res = await fetch(`${apiBase}/analytics/store?days=${days}&top_k=${topK}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur analytics");

    analyticsKpis.innerHTML = `
      <div class="kpi-grid">
        <article class="kpi"><span>Sessions</span><strong>${data.kpis.sessions}</strong></article>
        <article class="kpi"><span>CA total</span><strong>${Number(data.kpis.revenue_total).toFixed(2)} TND</strong></article>
        <article class="kpi"><span>Panier moyen</span><strong>${Number(data.kpis.avg_basket).toFixed(2)} TND</strong></article>
        <article class="kpi"><span>Items vendus</span><strong>${data.kpis.items_sold}</strong></article>
        <article class="kpi"><span>Temps moyen magasin</span><strong>${Number(data.avg_time_in_store_sec).toFixed(1)} sec</strong></article>
        <article class="kpi"><span>Prediction J+1</span><strong>${Number(data.predicted_next_day_revenue).toFixed(2)} TND</strong></article>
      </div>
      <p class="small-muted">Source: ${data.kpis.source} | Refresh auto active (20s)</p>
    `;
    analyticsKpis.classList.remove("hidden");

    const candleRows = (data.revenue_candles || [])
      .slice(-10)
      .map(
        (c) =>
          `<tr><td>${c.date}</td><td>${Number(c.open).toFixed(2)}</td><td>${Number(c.high).toFixed(2)}</td><td>${Number(c.low).toFixed(2)}</td><td>${Number(c.close).toFixed(2)}</td><td>${c.volume}</td></tr>`
      )
      .join("");
    analyticsCandles.innerHTML = `
      <p><strong>Courbe Revenue</strong></p>
      ${renderLineChart(data.revenue_trend || [])}
      <p><strong>Chandelles Revenue</strong></p>
      ${renderCandles(data.revenue_candles || [])}
      <div class="table-wrap">
        <table class="analytics-table">
          <thead><tr><th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr></thead>
          <tbody>${candleRows || "<tr><td colspan='6'>Aucune donnee</td></tr>"}</tbody>
        </table>
      </div>
    `;
    analyticsCandles.classList.remove("hidden");

    const topRows = (data.top_products || [])
      .map(
        (p) =>
          `<tr><td>${p.name}</td><td>${p.brand || "-"}</td><td>${p.quantity}</td><td>${Number(p.revenue).toFixed(2)}</td><td>${Number(p.avg_price).toFixed(2)}</td></tr>`
      )
      .join("");
    const stockRows = (data.stock_risk || [])
      .slice(0, 8)
      .map(
        (s) =>
          `<tr><td>${s.name}</td><td>${s.risk_level}</td><td>${Number(s.estimated_days_left).toFixed(1)}</td><td>${Number(s.avg_daily_qty).toFixed(2)}</td></tr>`
      )
      .join("");
    analyticsTopProducts.innerHTML = `
      <p><strong>Distribution des caisses</strong></p>
      ${renderDonut(data.queue_distribution || {})}
      <p><strong>Revenue par caisse</strong></p>
      ${renderQueueRevenueBars(data.queue_revenue || {})}
      <p><strong>Meilleurs Produits</strong></p>
      <div class="table-wrap">
        <table class="analytics-table">
          <thead><tr><th>Produit</th><th>Brand</th><th>Qte</th><th>Revenue</th><th>Prix moyen</th></tr></thead>
          <tbody>${topRows || "<tr><td colspan='5'>Aucune donnee</td></tr>"}</tbody>
        </table>
      </div>
      <p><strong>Risque Stock</strong></p>
      <div class="table-wrap">
        <table class="analytics-table">
          <thead><tr><th>Produit</th><th>Risque</th><th>Jours restants</th><th>Qte/jour</th></tr></thead>
          <tbody>${stockRows || "<tr><td colspan='4'>Aucune donnee</td></tr>"}</tbody>
        </table>
      </div>
    `;
    analyticsTopProducts.classList.remove("hidden");

    const agentCards = (data.agent_insights || [])
      .map((a) => {
        const recs = (a.recommendations || []).map((r) => `<li>${r}</li>`).join("");
        const details = (a.details || []).map((d) => `<li>${d}</li>`).join("");
        return `
          <article class="result-card">
            <p><strong>${a.title}</strong> <span class="small-muted">(${a.agent})</span></p>
            <p>${a.summary}</p>
            <p><strong>Details analyse:</strong></p>
            <ul class="queue-list">${details || "<li>Aucun detail.</li>"}</ul>
            <p><strong>Actions recommandees:</strong></p>
            <ul class="queue-list">${recs || "<li>Aucune reco.</li>"}</ul>
          </article>
        `;
      })
      .join("");
    analyticsAgents.innerHTML = `<p><strong>Agents d'analyse & recommandations</strong></p>${agentCards}`;
    analyticsAgents.classList.remove("hidden");
    bindBiTooltips();
  } catch (err) {
    notify(err.message);
  } finally {
    if (showSpinner) setLoading(false);
  }
}

function bindBiTooltips() {
  const targets = document.querySelectorAll(".tip-target");
  targets.forEach((el) => {
    if (el.dataset.tipBound === "1") return;
    el.dataset.tipBound = "1";
    el.addEventListener("mouseenter", () => {
      const txt = el.getAttribute("data-tip") || "";
      biTooltip.textContent = txt;
      biTooltip.classList.remove("hidden");
    });
    el.addEventListener("mousemove", (ev) => {
      biTooltip.style.left = `${ev.clientX + 14}px`;
      biTooltip.style.top = `${ev.clientY + 14}px`;
    });
    el.addEventListener("mouseleave", () => {
      biTooltip.classList.add("hidden");
    });
  });
}

if (analyticsForm && analyticsKpis && analyticsCandles && analyticsTopProducts && analyticsAgents) {
  analyticsForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAnalytics();
    await fetchAndRenderAnalytics(true);
  });
}

// Auto-load analytics at page load and refresh each 20s.
fetchAndRenderAnalytics(false);
setInterval(() => {
  fetchAndRenderAnalytics(false);
}, 20000);
