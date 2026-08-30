'use strict';

const themeInput        = document.getElementById('themeInput');
const themeError        = document.getElementById('themeError');
const symmetrySelect    = document.getElementById('symmetrySelect');
const complexitySelect  = document.getElementById('complexitySelect');
const styleSelect       = document.getElementById('styleSelect');
const generateBtn       = document.getElementById('generateBtn');
const generateMsg       = document.getElementById('generateMsg');
const designsSection    = document.getElementById('designsSection');
const designsGrid       = document.getElementById('designsGrid');
const previewInfoSection= document.getElementById('previewInfoSection');
const previewSvgWrap    = document.getElementById('previewSvgWrap');
const previewTheme      = document.getElementById('previewTheme');
const previewName       = document.getElementById('previewName');
const previewSymmetry   = document.getElementById('previewSymmetry');
const previewComplexity = document.getElementById('previewComplexity');
const continueBtn       = document.getElementById('continueBtn');
const continueBtn2      = document.getElementById('continueBtn2');
const continueTodo      = document.getElementById('continueTodo');
const previewDefaultBox = document.getElementById('previewDefaultBox');
const previewInfoBox    = document.getElementById('previewInfoBox');
const previewInfoText   = document.getElementById('previewInfoText');
const canvasDots        = document.getElementById('canvasDots');
const canvasPlaceholder = document.getElementById('canvasPlaceholder');
const sidebarToggle     = document.getElementById('sidebarToggle');
const sidebar           = document.getElementById('sidebar');
const footerYear        = document.getElementById('footerYear');

footerYear.textContent = new Date().getFullYear();

// ── Sidebar toggle ────────────────────────────────────────────────────────────
sidebarToggle.addEventListener('click', (e) => { e.stopPropagation(); sidebar.classList.toggle('open'); });
document.addEventListener('click', (e) => {
  if (!sidebar.contains(e.target) && e.target !== sidebarToggle) sidebar.classList.remove('open');
});

// ── Section switching ─────────────────────────────────────────────────────────
// Sections that live inside col-left and can be shown/hidden
const CAMERA_SECTION   = document.getElementById('cameraSection');
const DASHBOARD_CARDS  = document.querySelectorAll(
  '.designer-card, .designs-card, .preview-info-card, .status-card, .workflow-card'
);

function showSection(section) {
  // Hide camera, show dashboard cards
  if (section === 'camera') {
    DASHBOARD_CARDS.forEach(c => c.classList.add('hidden'));
    CAMERA_SECTION.classList.remove('hidden');
  } else {
    // For all other sections restore dashboard view (camera off handled by camera module)
    CAMERA_SECTION.classList.add('hidden');
    DASHBOARD_CARDS.forEach(c => {
      // Restore visibility except cards that were explicitly hidden by user interaction
      if (!c.classList.contains('user-hidden')) c.classList.remove('hidden');
    });
    // Restore the sections that should stay hidden until generated
    if (!window._designsGenerated) {
      document.querySelector('.designs-card')?.classList.add('hidden');
      document.querySelector('.preview-info-card')?.classList.add('hidden');
    }
    if (section !== 'dashboard') {
      // Other sections (path, robot, history, settings) just show dashboard for now
    }
  }
}

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    item.classList.add('active');
    const sec = item.dataset.section;
    showSection(sec);
    // Stop camera stream when navigating away
    if (sec !== 'camera') { if (typeof camStop === 'function') camStop(); }
  });
});

// ── Orbit dots ────────────────────────────────────────────────────────────────
for (let i = 0; i < 2; i++) {
  const dot = document.createElement('div');
  dot.className = 'orbit-dot';
  canvasDots.appendChild(dot);
}

// ── SVG Designs — warm light palette ─────────────────────────────────────────
const DESIGNS = [
  { id: 'lotus-harmony', name: 'Lotus Harmony',  description: 'Eight lotus petals radiating from a central disc — classic Kerala motif.', symmetry: '8-fold',  complexity: 'Simple',   svg: buildLotusSVG()    },
  { id: 'kerala-mandala', name: 'Kerala Mandala', description: 'Layered rings with diamond accents inspired by Thrissur Pooram.',           symmetry: '12-fold', complexity: 'Medium',   svg: buildMandalaSVG()  },
  { id: 'floral-star',   name: 'Floral Star',     description: 'Interlocking triangles and petal arcs forming a six-pointed star.',          symmetry: '6-fold',  complexity: 'Detailed', svg: buildFloralStarSVG()},
];

function buildLotusSVG() {
  const cx = 120, cy = 120;
  let p = '';
  for (let i = 0; i < 8; i++) {
    const a = (i/8)*2*Math.PI;
    const a1=a-Math.PI/8*.6, a2=a+Math.PI/8*.6, tip=90, ctrl=58;
    const tx=cx+tip*Math.cos(a), ty=cy+tip*Math.sin(a);
    const c1x=cx+ctrl*Math.cos(a1),c1y=cy+ctrl*Math.sin(a1);
    const c2x=cx+ctrl*Math.cos(a2),c2y=cy+ctrl*Math.sin(a2);
    p += `<path d="M${cx},${cy} Q${c1x},${c1y} ${tx},${ty} Q${c2x},${c2y} ${cx},${cy}Z" fill="rgba(200,134,10,.1)" stroke="#c8860a" stroke-width="1.4"/>`;
  }
  for (let i = 0; i < 8; i++) {
    const a=(i/8)*2*Math.PI+Math.PI/8;
    const a1=a-Math.PI/8*.5,a2=a+Math.PI/8*.5,tip=52,ctrl=34;
    const tx=cx+tip*Math.cos(a),ty=cy+tip*Math.sin(a);
    const c1x=cx+ctrl*Math.cos(a1),c1y=cy+ctrl*Math.sin(a1);
    const c2x=cx+ctrl*Math.cos(a2),c2y=cy+ctrl*Math.sin(a2);
    p += `<path d="M${cx},${cy} Q${c1x},${c1y} ${tx},${ty} Q${c2x},${c2y} ${cx},${cy}Z" fill="rgba(46,125,50,.08)" stroke="#2e7d32" stroke-width="1.1"/>`;
  }
  return `<svg viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
    <circle cx="${cx}" cy="${cy}" r="108" fill="none" stroke="#e8d9c0" stroke-width="1"/>
    <circle cx="${cx}" cy="${cy}" r="72"  fill="none" stroke="#e8d9c0" stroke-width=".8"/>
    <circle cx="${cx}" cy="${cy}" r="36"  fill="none" stroke="#e8d9c0" stroke-width=".8"/>
    ${p}
    <circle cx="${cx}" cy="${cy}" r="10" fill="#c8860a" fill-opacity=".5"/>
    <circle cx="${cx}" cy="${cy}" r="4"  fill="#e65100"/>
  </svg>`;
}

function buildMandalaSVG() {
  const cx=120,cy=120; let m='';
  [[90,12,'#2e7d32'],[68,12,'#c8860a'],[46,6,'#7b1fa2']].forEach(([r,n,col])=>{
    for(let i=0;i<n;i++){
      const a=(i/n)*2*Math.PI;
      const ix=cx+(r-7)*Math.cos(a),iy=cy+(r-7)*Math.sin(a);
      const ox=cx+(r+7)*Math.cos(a),oy=cy+(r+7)*Math.sin(a);
      const lx=cx+r*Math.cos(a-.16),ly=cy+r*Math.sin(a-.16);
      const rx2=cx+r*Math.cos(a+.16),ry2=cy+r*Math.sin(a+.16);
      m += `<path d="M${ix},${iy} L${lx},${ly} L${ox},${oy} L${rx2},${ry2}Z" fill="${col}18" stroke="${col}" stroke-width="1"/>`;
    }
  });
  return `<svg viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
    <circle cx="${cx}" cy="${cy}" r="108" fill="none" stroke="#e8d9c0" stroke-width="1"/>
    <circle cx="${cx}" cy="${cy}" r="90"  fill="none" stroke="#2e7d32" stroke-width="1.5"/>
    <circle cx="${cx}" cy="${cy}" r="68"  fill="none" stroke="#c8860a" stroke-width="1.5"/>
    <circle cx="${cx}" cy="${cy}" r="46"  fill="none" stroke="#7b1fa2" stroke-width="1.2"/>
    <circle cx="${cx}" cy="${cy}" r="24"  fill="none" stroke="#c8860a" stroke-width="1"/>
    ${m}
    <circle cx="${cx}" cy="${cy}" r="10" fill="#c8860a" fill-opacity=".5"/>
    <circle cx="${cx}" cy="${cy}" r="4"  fill="#2e7d32"/>
  </svg>`;
}

function buildFloralStarSVG() {
  const cx=120,cy=120; let a2='';
  for(let i=0;i<6;i++){
    const a=(i/6)*2*Math.PI;
    const a1=a-Math.PI/6*.7,a3=a+Math.PI/6*.7,tip=85,ctrl=55;
    const tx=cx+tip*Math.cos(a),ty=cy+tip*Math.sin(a);
    const c1x=cx+ctrl*Math.cos(a1),c1y=cy+ctrl*Math.sin(a1);
    const c2x=cx+ctrl*Math.cos(a3),c2y=cy+ctrl*Math.sin(a3);
    a2+=`<path d="M${cx},${cy} Q${c1x},${c1y} ${tx},${ty} Q${c2x},${c2y} ${cx},${cy}Z" fill="rgba(46,125,50,.08)" stroke="#2e7d32" stroke-width="1.5"/>`;
  }
  const triR=62; let t1='',t2='';
  for(let i=0;i<3;i++){
    const a=(i/3)*2*Math.PI-Math.PI/2,b=a+(2*Math.PI)/3;
    t1+=`${cx+triR*Math.cos(a)},${cy+triR*Math.sin(a)} `;
    t2+=`${cx+triR*Math.cos(b+Math.PI/3)},${cy+triR*Math.sin(b+Math.PI/3)} `;
  }
  return `<svg viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
    <circle cx="${cx}" cy="${cy}" r="108" fill="none" stroke="#e8d9c0" stroke-width="1"/>
    ${a2}
    <polygon points="${t1.trim()}" fill="rgba(200,134,10,.08)" stroke="#c8860a" stroke-width="1.3"/>
    <polygon points="${t2.trim()}" fill="rgba(123,31,162,.06)" stroke="#7b1fa2" stroke-width="1.3"/>
    <circle cx="${cx}" cy="${cy}" r="18" fill="none" stroke="#2e7d32" stroke-width="1.2"/>
    <circle cx="${cx}" cy="${cy}" r="8"  fill="#c8860a" fill-opacity=".5"/>
    <circle cx="${cx}" cy="${cy}" r="3"  fill="#e65100"/>
  </svg>`;
}

// ── State ─────────────────────────────────────────────────────────────────────
let selectedDesignId = null, lastParams = {};
let currentDesigns   = [];   // filled by the real API — never hardcoded

// ── Generate — real API call ──────────────────────────────────────────────────
generateBtn.addEventListener('click', async () => {
  const theme      = themeInput.value.trim();
  const symmetry   = symmetrySelect.options[symmetrySelect.selectedIndex].text;
  const complexity = complexitySelect.value;
  const style      = styleSelect.value;

  if (!theme) {
    themeError.textContent = 'Please enter a theme before generating.';
    themeInput.focus();
    return;
  }
  themeError.textContent = '';
  lastParams = { theme, symmetry, complexity, style };

  generateBtn.disabled = true;
  generateBtn.classList.add('loading');
  generateMsg.textContent = `Asking Gemini AI to create designs for "${theme}"…`;
  // Hide any previous results while generating
  designsSection.classList.add('hidden');
  previewInfoSection.classList.add('hidden');

  try {
    const resp = await fetch('/api/generate-design', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ theme, symmetry, complexity, style }),
    });

    const data = await resp.json();

    if (!resp.ok || !data.ok) {
      const msg = data.error || `Server returned ${resp.status}`;
      throw new Error(msg);
    }

    if (!Array.isArray(data.designs) || data.designs.length === 0) {
      throw new Error('AI returned no designs. Try a different theme.');
    }

    currentDesigns = data.designs;
    generateMsg.textContent = `${currentDesigns.length} AI designs generated for "${theme}".`;
    window._designsGenerated = true;
    showDesigns(currentDesigns);

  } catch (err) {
    generateMsg.textContent = '';
    // Show a visible error — never silently fall back
    themeError.textContent  = `Generation failed: ${err.message}`;
    themeError.style.color  = '#c62828';
    console.error('Design generation error:', err);
  } finally {
    generateBtn.disabled = false;
    generateBtn.classList.remove('loading');
  }
});

function showDesigns(designs) {
  designsGrid.innerHTML = '';
  selectedDesignId = null;

  designs.forEach(design => {
    const card = document.createElement('article');
    card.className = 'design-card';
    card.setAttribute('role', 'listitem');
    card.dataset.id = design.id;

    // Build motif tags
    const motifTags = (design.motifs || [])
      .slice(0, 3)
      .map(m => `<span class="tag">${m}</span>`)
      .join('');

    card.innerHTML = `
      <div class="design-card-preview">${design.svg}</div>
      <div class="design-card-body">
        <div class="design-card-name">${design.name}</div>
        <div class="design-card-desc">${design.description}</div>
        <div class="design-card-meta">
          <span class="tag">${design.symmetry}</span>
          <span class="tag">${design.complexity}</span>
          ${motifTags}
        </div>
      </div>
      <button class="btn btn-outline" aria-label="Select ${design.name}">Select Design</button>`;

    card.querySelector('button').addEventListener('click', () => selectDesign(design.id));
    card.addEventListener('click', e => { if (e.target.tagName !== 'BUTTON') selectDesign(design.id); });
    designsGrid.appendChild(card);
  });

  designsSection.classList.remove('hidden');
  previewDefaultBox.classList.add('hidden');
  previewInfoBox.classList.remove('hidden');
  previewInfoText.textContent = 'Select a design below to preview it here.';
  designsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function selectDesign(id) {
  selectedDesignId = id;
  const design = currentDesigns.find(d => d.id === id);
  if (!design) return;

  designsGrid.querySelectorAll('.design-card').forEach(card => {
    const btn = card.querySelector('button'), sel = card.dataset.id === id;
    card.classList.toggle('selected', sel);
    btn.textContent = sel ? 'Selected ✓' : 'Select Design';
    btn.classList.toggle('selected', sel);
  });

  previewSvgWrap.innerHTML = design.svg;
  previewSvgWrap.classList.add('has-design');
  if (canvasPlaceholder) canvasPlaceholder.style.display = 'none';

  previewInfoBox.classList.remove('hidden');
  previewDefaultBox.classList.add('hidden');
  previewInfoText.textContent = `"${design.name}" — ${design.symmetry} symmetry, ${design.complexity}.`;
  continueBtn2.classList.remove('hidden');

  previewTheme.textContent      = lastParams.theme || '—';
  previewName.textContent       = design.name;
  previewSymmetry.textContent   = design.symmetry;
  previewComplexity.textContent = design.complexity;
  continueTodo.classList.add('hidden');
  previewInfoSection.classList.remove('hidden');
  previewInfoSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

[continueBtn, continueBtn2].forEach(btn => {
  btn?.addEventListener('click', async () => {
    if (!selectedDesignId) {
      alert('Please select a design first.');
      return;
    }
    continueTodo.classList.remove('hidden');
    continueTodo.textContent = 'Generating polar plotter waypoints and vector path…';
    btn.disabled = true;

    try {
      const resp = await fetch('/api/designs/vectorize', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ design_id: selectedDesignId, canvas_cm: 60 }),
      });
      const data = await resp.json();
      if (data.status === 'ok') {
        continueTodo.textContent = `✓ Vectorized ${data.waypoints.length} waypoints. Est. drawing time: ${Math.round(data.estimated_drawing_time_sec/60)}m. Ready for robot!`;
        continueTodo.style.background = '#e8f5e9';
        continueTodo.style.color = '#2e7d32';
        continueTodo.style.borderColor = '#c8e6c9';
      } else {
        continueTodo.textContent = `Vectorization note: ${data.error?.message || 'Ready'}`;
      }
    } catch (err) {
      continueTodo.textContent = `Path generation: ${err.message}`;
    } finally {
      btn.disabled = false;
      btn.blur();
    }
  });
});

themeInput.addEventListener('keydown', e => { if (e.key === 'Enter') generateBtn.click(); });
themeInput.addEventListener('input',   ()  => { if (themeInput.value.trim()) themeError.textContent = ''; });

// ══════════════════════════════════════════════════════════════════════════════
// LIVE CAMERA MODULE
// Uses browser getUserMedia — works on localhost without HTTPS.
// ══════════════════════════════════════════════════════════════════════════════

const camVideo        = document.getElementById('cameraVideo');
const camCanvas       = document.getElementById('cameraCanvas');
const camStartBtn     = document.getElementById('camStartBtn');
const camStopBtn      = document.getElementById('camStopBtn');
const camCaptureBtn   = document.getElementById('camCaptureBtn');
const camFlipBtn      = document.getElementById('camFlipBtn');
const camDeviceSelect = document.getElementById('camDeviceSelect');
const camPlaceholder  = document.getElementById('camPlaceholder');
const camStatusDot    = document.getElementById('camStatusDot');
const camStatusText   = document.getElementById('camStatusText');
const camError        = document.getElementById('camError');
const capturePreview  = document.getElementById('capturePreview');
const captureImg      = document.getElementById('captureImg');
const captureCloseBtn = document.getElementById('captureCloseBtn');

let camStream   = null;   // active MediaStream
let camMirrored = true;   // mirror front-facing cameras by default
let camDeviceId = null;   // currently selected device

// ── Helpers ───────────────────────────────────────────────────────────────────
function camSetStatus(state, text) {
  camStatusDot.className  = 'cam-status-dot' + (state ? ' ' + state : '');
  camStatusText.textContent = text;
}

function camShowError(msg) {
  camError.textContent = msg;
  camError.classList.remove('hidden');
}
function camClearError() {
  camError.textContent = '';
  camError.classList.add('hidden');
}

// ── Enumerate cameras and populate dropdown ───────────────────────────────────
async function camEnumerateDevices() {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const cameras = devices.filter(d => d.kind === 'videoinput');
    camDeviceSelect.innerHTML = '';
    cameras.forEach((cam, i) => {
      const opt = document.createElement('option');
      opt.value = cam.deviceId;
      opt.textContent = cam.label || `Camera ${i + 1}`;
      camDeviceSelect.appendChild(opt);
    });
    if (cameras.length > 0) {
      camDeviceSelect.classList.remove('hidden');
      // Restore previously chosen device if still present
      if (camDeviceId && cameras.some(c => c.deviceId === camDeviceId)) {
        camDeviceSelect.value = camDeviceId;
      } else {
        camDeviceId = cameras[0].deviceId;
      }
    }
  } catch (_) { /* labels unavailable before permission */ }
}

// ── Start camera ──────────────────────────────────────────────────────────────
async function camStart() {
  camClearError();

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    camShowError('Your browser does not support camera access.');
    return;
  }

  // Build constraints — prefer the selected device, fall back to any video
  const constraints = {
    video: camDeviceId
      ? { deviceId: { exact: camDeviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
      : { width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: false,
  };

  try {
    camStream = await navigator.mediaDevices.getUserMedia(constraints);
    camVideo.srcObject = camStream;

    // Mirror front-facing cameras
    camVideo.classList.toggle('mirrored', camMirrored);

    camPlaceholder.classList.add('hidden');
    camStartBtn.classList.add('hidden');
    camStopBtn.classList.remove('hidden');
    camCaptureBtn.classList.remove('hidden');
    camFlipBtn.classList.remove('hidden');
    camSetStatus('live', 'Live');

    // After permission is granted labels become available — re-enumerate
    await camEnumerateDevices();

    // Store the active track's device id
    const track = camStream.getVideoTracks()[0];
    if (track) {
      const settings = track.getSettings();
      if (settings.deviceId) {
        camDeviceId = settings.deviceId;
        camDeviceSelect.value = camDeviceId;
      }
    }

  } catch (err) {
    let msg = 'Camera access failed.';
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError')
      msg = 'Camera permission denied. Allow camera access in your browser and try again.';
    else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError')
      msg = 'No camera found. Make sure your webcam is connected.';
    else if (err.name === 'NotReadableError')
      msg = 'Camera is in use by another application.';
    else if (err.name === 'OverconstrainedError')
      msg = 'Selected camera constraints could not be satisfied. Trying default camera.';
    camShowError(msg);
    camSetStatus('error', 'Error');

    // If a specific device failed, retry with any camera
    if (err.name === 'OverconstrainedError' && camDeviceId) {
      camDeviceId = null;
      camStart();
    }
  }
}

// ── Stop camera ───────────────────────────────────────────────────────────────
function camStop() {
  if (!camStream) return;
  camStream.getTracks().forEach(t => t.stop());
  camStream = null;
  camVideo.srcObject = null;
  camPlaceholder.classList.remove('hidden');
  camStartBtn.classList.remove('hidden');
  camStopBtn.classList.add('hidden');
  camCaptureBtn.classList.add('hidden');
  camFlipBtn.classList.add('hidden');
  camSetStatus('', 'Camera off');
}

// ── Capture frame ─────────────────────────────────────────────────────────────
function camCapture() {
  if (!camStream || !camVideo.videoWidth) return;

  const w = camVideo.videoWidth;
  const h = camVideo.videoHeight;
  camCanvas.width  = w;
  camCanvas.height = h;

  const ctx = camCanvas.getContext('2d');
  if (camMirrored) {
    ctx.translate(w, 0);
    ctx.scale(-1, 1);
  }
  ctx.drawImage(camVideo, 0, 0, w, h);
  if (camMirrored) ctx.setTransform(1, 0, 0, 1, 0, 0); // reset

  const dataUrl = camCanvas.toDataURL('image/jpeg', 0.92);
  captureImg.src = dataUrl;
  capturePreview.classList.remove('hidden');
  capturePreview.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ── Flip mirror ───────────────────────────────────────────────────────────────
function camFlip() {
  camMirrored = !camMirrored;
  camVideo.classList.toggle('mirrored', camMirrored);
}

// ── Switch device ─────────────────────────────────────────────────────────────
camDeviceSelect.addEventListener('change', async () => {
  camDeviceId = camDeviceSelect.value;
  if (camStream) {
    camStop();
    await camStart();
  }
});

// ── Button wiring ─────────────────────────────────────────────────────────────
camStartBtn.addEventListener('click',   camStart);
camStopBtn.addEventListener('click',    camStop);
camCaptureBtn.addEventListener('click', camCapture);
camFlipBtn.addEventListener('click',    camFlip);
captureCloseBtn.addEventListener('click', () => capturePreview.classList.add('hidden'));

// ── Pre-enumerate so device names show before permission (may be blank labels) ─
navigator.mediaDevices?.enumerateDevices().then(camEnumerateDevices).catch(() => {});

// ── Live System Health & Robot State Polling ──────────────────────────────────
async function pollStatus() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    const h = await res.json();
    const statusDot = document.querySelector('#systemStatus .status-dot');
    const statusLabel = document.querySelector('#systemStatus .status-label');
    const statusSub = document.querySelector('#systemStatus .status-sub');
    if (h.ai_available) {
      if (statusDot) {
        statusDot.className = 'status-dot online';
      }
      if (statusLabel) {
        statusLabel.textContent = 'System Online';
      }
      if (statusSub) {
        statusSub.textContent = `${h.provider || 'Gemini AI'} Active`;
      }
    }
  } catch (_) {}
}
setInterval(pollStatus, 6000);
pollStatus();
