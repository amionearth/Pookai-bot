'use strict';

// ══════════════════════════════════════════════════════════════════════════════
// POOKALBOT DASHBOARD — COMPLETE CONTROLLER & SIMULATION ENGINE
// ══════════════════════════════════════════════════════════════════════════════

// ── DOM References ────────────────────────────────────────────────────────────
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

// Sections
const CAMERA_SECTION     = document.getElementById('cameraSection');
const SIMULATION_SECTION = document.getElementById('simulationSection');
const DASHBOARD_CARDS    = document.querySelectorAll(
  '.designer-card, .designs-card, .preview-info-card, .status-card, .workflow-card'
);

// Simulation UI Elements
const simCanvas       = document.getElementById('simCanvas');
const btnSimStart     = document.getElementById('btnSimStart');
const btnSimPause     = document.getElementById('btnSimPause');
const btnSimReset     = document.getElementById('btnSimReset');
const simStateBadge   = document.getElementById('simStateBadge');
const simProgressFill = document.getElementById('simProgressFill');
const simTelemPos     = document.getElementById('simTelemPos');
const simTelemHeading = document.getElementById('simTelemHeading');
const simTelemPen     = document.getElementById('simTelemPen');
const simTelemWp      = document.getElementById('simTelemWp');
const simStatusMsg    = document.getElementById('simStatusMsg');

// Global State
let selectedDesignId = null;
let lastParams       = {};
let currentDesigns   = [];
let simRunning       = false;
let simPaused        = false;
let simIndex         = 0;
let simSpeed         = 5;
let simWaypoints     = [];
let simAnimTimer     = null;
window._designsGenerated = false;

// Safe footer year
if (footerYear) footerYear.textContent = new Date().getFullYear();

// ── Sidebar Toggle ────────────────────────────────────────────────────────────
sidebarToggle?.addEventListener('click', (e) => {
  e.stopPropagation();
  sidebar?.classList.toggle('open');
});

document.addEventListener('click', (e) => {
  if (sidebar && sidebarToggle && !sidebar.contains(e.target) && e.target !== sidebarToggle) {
    sidebar.classList.remove('open');
  }
});

// ── Navigation & Section Switching ────────────────────────────────────────────
function showSection(section) {
  if (section === 'camera') {
    DASHBOARD_CARDS.forEach(c => c.classList.add('hidden'));
    SIMULATION_SECTION?.classList.add('hidden');
    CAMERA_SECTION?.classList.remove('hidden');
    simStopInternal();
  } else if (section === 'simulation') {
    DASHBOARD_CARDS.forEach(c => c.classList.add('hidden'));
    CAMERA_SECTION?.classList.add('hidden');
    SIMULATION_SECTION?.classList.remove('hidden');
    if (typeof camStop === 'function') camStop();
    
    // Ensure simulation canvas is rendered with floor grid immediately
    if (!simWaypoints || simWaypoints.length === 0) {
      simWaypoints = generateDefaultWaypoints('lotus');
    }
    setTimeout(() => {
      renderSimFrame();
    }, 50);
  } else {
    // Dashboard or Designer
    CAMERA_SECTION?.classList.add('hidden');
    SIMULATION_SECTION?.classList.add('hidden');
    if (typeof camStop === 'function') camStop();
    simStopInternal();

    DASHBOARD_CARDS.forEach(c => {
      if (!c.classList.contains('user-hidden')) c.classList.remove('hidden');
    });
    if (!window._designsGenerated) {
      document.querySelector('.designs-card')?.classList.add('hidden');
      document.querySelector('.preview-info-card')?.classList.add('hidden');
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
  });
});

// ── Canvas Glowing Orbit Dots ──────────────────────────────────────────────────
if (canvasDots) {
  for (let i = 0; i < 2; i++) {
    const dot = document.createElement('div');
    dot.className = 'orbit-dot';
    canvasDots.appendChild(dot);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// ROBOT SIMULATION ARENA ENGINE
// ══════════════════════════════════════════════════════════════════════════════

function generateDefaultWaypoints(type = 'lotus') {
  const wps = [];
  const R = 32; // 32cm radius

  if (type === 'mandala') {
    // 12-Fold Concentric Diamond Mandala
    [32, 24, 16, 8].forEach((r, idx) => {
      wps.push({ x: r, y: 0, pen: 0 });
      const pts = idx % 2 === 0 ? 12 : 8;
      for (let a = 0; a <= Math.PI * 2 + 0.05; a += (Math.PI * 2) / pts) {
        wps.push({ x: r * Math.cos(a), y: r * Math.sin(a), pen: 1 });
      }
    });
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      wps.push({ x: 8 * Math.cos(a), y: 8 * Math.sin(a), pen: 0 });
      wps.push({ x: 32 * Math.cos(a), y: 32 * Math.sin(a), pen: 1 });
    }
  } else if (type === 'pooram') {
    // 12-Fold Thrissur Pooram Radiant Starburst
    for (let a = 0; a <= Math.PI * 2; a += 0.08) {
      wps.push({ x: R * Math.cos(a), y: R * Math.sin(a), pen: 1 });
    }
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      wps.push({ x: 0, y: 0, pen: 0 });
      for (let t = 0; t <= 1; t += 0.04) {
        const r = R * 0.9 * Math.sin(t * Math.PI);
        const ang = a + (t - 0.5) * (Math.PI / 12) * 1.8;
        wps.push({ x: r * Math.cos(ang), y: r * Math.sin(ang), pen: 1 });
      }
    }
  } else if (type === 'star') {
    // 6-Pointed Starburst
    for (let a = 0; a <= Math.PI * 2; a += 0.08) {
      wps.push({ x: R * Math.cos(a), y: R * Math.sin(a), pen: 1 });
    }
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * Math.PI * 2;
      const aNext = ((i + 2) / 6) * Math.PI * 2;
      wps.push({ x: (R * 0.85) * Math.cos(a), y: (R * 0.85) * Math.sin(a), pen: 0 });
      wps.push({ x: (R * 0.85) * Math.cos(aNext), y: (R * 0.85) * Math.sin(aNext), pen: 1 });
    }
  } else {
    // Default 8-Fold Classic Lotus
    for (let a = 0; a <= Math.PI * 2; a += 0.08) {
      wps.push({ x: R * Math.cos(a), y: R * Math.sin(a), pen: 1 });
    }
    for (let a = 0; a <= Math.PI * 2; a += 0.08) {
      wps.push({ x: (R * 0.65) * Math.cos(a), y: (R * 0.65) * Math.sin(a), pen: 1 });
    }
    for (let p = 0; p < 8; p++) {
      const baseA = (p / 8) * Math.PI * 2;
      wps.push({ x: 0, y: 0, pen: 0 });
      for (let t = 0; t <= 1; t += 0.04) {
        const r = (R * 0.88) * Math.sin(t * Math.PI);
        const a = baseA + (t - 0.5) * (Math.PI / 8) * 1.6;
        wps.push({ x: r * Math.cos(a), y: r * Math.sin(a), pen: 1 });
      }
    }
    for (let a = 0; a <= Math.PI * 2; a += 0.1) {
      wps.push({ x: 7 * Math.cos(a), y: 7 * Math.sin(a), pen: 1 });
    }
  }
  return wps;
}

function worldToSimCanvas(wx, wy) {
  if (!simCanvas) return { x: 280, y: 280 };
  const cx = simCanvas.width / 2;
  const cy = simCanvas.height / 2;
  const scale = 5.8; // pixels per cm
  return {
    x: cx + wx * scale,
    y: cy + wy * scale,
  };
}

function renderSimFrame() {
  if (!simCanvas) return;
  const ctx = simCanvas.getContext('2d');
  const w = simCanvas.width;
  const h = simCanvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const scale = 5.8;

  ctx.clearRect(0, 0, w, h);

  // 1. Draw Floor Coordinate Grid & Centimeter Rings
  ctx.strokeStyle = 'rgba(200, 155, 60, 0.22)';
  ctx.lineWidth = 1;
  [10, 20, 30, 40].forEach(r_cm => {
    ctx.beginPath();
    ctx.arc(cx, cy, r_cm * scale, 0, Math.PI * 2);
    ctx.stroke();
    // Centimeter label
    ctx.fillStyle = 'rgba(120, 90, 40, 0.45)';
    ctx.font = '10px Consolas, monospace';
    ctx.fillText(`${r_cm}cm`, cx + 4, cy - r_cm * scale + 12);
  });

  // Crosshairs
  ctx.strokeStyle = 'rgba(200, 155, 60, 0.25)';
  ctx.beginPath();
  ctx.moveTo(cx, 12); ctx.lineTo(cx, h - 12);
  ctx.moveTo(12, cy); ctx.lineTo(w - 12, cy);
  ctx.stroke();

  if (!simWaypoints || simWaypoints.length === 0) return;

  const total = simWaypoints.length;
  const upto  = Math.min(simIndex, total);

  // 2. Draw planned path guide (faint gold dashed)
  ctx.strokeStyle = 'rgba(200, 155, 60, 0.35)';
  ctx.lineWidth = 1.4;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  let started = false;
  for (let i = 0; i < total; i++) {
    const p = worldToSimCanvas(simWaypoints[i].x, simWaypoints[i].y);
    if (!started) { ctx.moveTo(p.x, p.y); started = true; }
    else { ctx.lineTo(p.x, p.y); }
  }
  ctx.stroke();
  ctx.setLineDash([]); // Reset

  // 3. Draw accumulating drawn ink trail (thick vibrant green chalk)
  ctx.strokeStyle = '#2e7d32';
  ctx.lineWidth = 3.6;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.shadowColor = 'rgba(46, 125, 50, 0.45)';
  ctx.shadowBlur = 5;

  let drawing = false;
  ctx.beginPath();
  for (let i = 0; i < upto; i++) {
    const wp = simWaypoints[i];
    const p = worldToSimCanvas(wp.x, wp.y);
    if (wp.pen === 1) {
      if (!drawing) { ctx.moveTo(p.x, p.y); drawing = true; }
      else { ctx.lineTo(p.x, p.y); }
    } else {
      drawing = false;
    }
  }
  ctx.stroke();
  ctx.shadowBlur = 0; // Reset shadow

  // 4. Draw Virtual Mobile Robot
  if (upto > 0 && upto <= total) {
    const curWp = simWaypoints[upto - 1];
    const prevWp = upto > 1 ? simWaypoints[upto - 2] : curWp;
    const p = worldToSimCanvas(curWp.x, curWp.y);
    
    let theta = 0;
    if (curWp.x !== prevWp.x || curWp.y !== prevWp.y) {
      theta = Math.atan2(curWp.y - prevWp.y, curWp.x - prevWp.x);
    }

    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.rotate(theta);

    // Chassis body
    ctx.fillStyle = '#2d1a0e';
    ctx.beginPath();
    ctx.arc(0, 0, 15, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#e8c97a';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Wheels
    ctx.fillStyle = '#111';
    ctx.fillRect(-7, -19, 14, 4);
    ctx.fillRect(-7, 15, 14, 4);

    // Heading arrow (front)
    ctx.fillStyle = '#e8403a';
    ctx.beginPath();
    ctx.moveTo(17, 0);
    ctx.lineTo(10, -5);
    ctx.lineTo(10, 5);
    ctx.closePath();
    ctx.fill();

    // Pen indicator
    ctx.fillStyle = curWp.pen === 1 ? '#388e3c' : '#c62828';
    ctx.beginPath();
    ctx.arc(0, 0, 4, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();

    // Update telemetry UI
    if (simTelemPos)     simTelemPos.textContent = `(${curWp.x.toFixed(1)}, ${curWp.y.toFixed(1)}) cm`;
    if (simTelemHeading) simTelemHeading.textContent = `${Math.round(theta * 180 / Math.PI)}°`;
    if (simTelemPen) {
      simTelemPen.textContent = curWp.pen === 1 ? 'DOWN (Chalk)' : 'UP (Travel)';
      simTelemPen.style.color = curWp.pen === 1 ? '#2e7d32' : '#c62828';
    }
    const pct = Math.round((upto / total) * 100);
    if (simTelemWp)      simTelemWp.textContent = `${upto} / ${total} (${pct}%)`;
    if (simProgressFill) simProgressFill.style.width = `${pct}%`;
  }
}

function simStep() {
  if (!simRunning || simPaused) return;

  const total = simWaypoints.length;
  if (simIndex < total) {
    simIndex = Math.min(total, simIndex + Math.max(1, Math.round(simSpeed / 2)));
    renderSimFrame();
    simAnimTimer = setTimeout(simStep, 35);
  } else {
    simRunning = false;
    if (simStateBadge) {
      simStateBadge.textContent = 'Done ✓';
      simStateBadge.className = 'sim-badge active';
    }
    if (simStatusMsg) {
      simStatusMsg.textContent = '✨ Simulated autonomous drawing completed successfully!';
    }
    if (btnSimStart) btnSimStart.disabled = false;
    if (btnSimPause) btnSimPause.disabled = true;
  }
}

function simStopInternal() {
  simRunning = false;
  simPaused  = false;
  clearTimeout(simAnimTimer);
}

// Preset Buttons
document.querySelectorAll('.sim-preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.sim-preset-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const preset = btn.dataset.preset || 'lotus';
    simStopInternal();
    simIndex = 0;
    simWaypoints = generateDefaultWaypoints(preset);
    if (simStatusMsg) simStatusMsg.textContent = `Loaded preset "${preset}" (${simWaypoints.length} waypoints). Ready!`;
    if (simStateBadge) {
      simStateBadge.textContent = 'Ready';
      simStateBadge.className = 'sim-badge';
    }
    if (btnSimStart) btnSimStart.disabled = false;
    if (btnSimPause) btnSimPause.disabled = true;
    renderSimFrame();
  });
});

// Speed Multipliers
document.querySelectorAll('.sim-speed-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.sim-speed-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    simSpeed = parseInt(btn.dataset.speed || '5', 10);
  });
});

// Simulation Control Actions
btnSimStart?.addEventListener('click', async () => {
  if (simRunning && simPaused) {
    simPaused = false;
    if (btnSimPause) btnSimPause.textContent = '⏸ Pause';
    if (simStateBadge) simStateBadge.textContent = 'Drawing…';
    simStep();
    return;
  }

  if (simWaypoints.length === 0) {
    if (simStatusMsg) simStatusMsg.textContent = 'Vectorizing design for virtual robot…';
    if (selectedDesignId) {
      try {
        const resp = await fetch('/api/designs/vectorize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ design_id: selectedDesignId, canvas_cm: 60 }),
        });
        const data = await resp.json();
        if (data.waypoints && data.waypoints.length > 0) {
          simWaypoints = data.waypoints;
        }
      } catch (_) {}
    }
    if (simWaypoints.length === 0) {
      simWaypoints = generateDefaultWaypoints('lotus');
    }
  }

  simRunning = true;
  simPaused  = false;
  simIndex   = 0;
  if (btnSimStart) btnSimStart.disabled = true;
  if (btnSimPause) {
    btnSimPause.disabled = false;
    btnSimPause.textContent = '⏸ Pause';
  }
  if (simStateBadge) {
    simStateBadge.textContent = 'Drawing…';
    simStateBadge.className = 'sim-badge active';
  }
  if (simStatusMsg) simStatusMsg.textContent = `🚀 Virtual robot drawing ${simWaypoints.length} waypoints @ ${simSpeed}× speed…`;
  
  simStep();
});

btnSimPause?.addEventListener('click', () => {
  if (!simRunning) return;
  simPaused = !simPaused;
  if (btnSimPause) btnSimPause.textContent = simPaused ? '▶ Resume' : '⏸ Pause';
  if (simStateBadge) {
    simStateBadge.textContent = simPaused ? 'Paused' : 'Drawing…';
    simStateBadge.className = simPaused ? 'sim-badge paused' : 'sim-badge active';
  }
  if (!simPaused) simStep();
});

btnSimReset?.addEventListener('click', () => {
  simStopInternal();
  simIndex = 0;
  renderSimFrame();
  if (btnSimStart) btnSimStart.disabled = false;
  if (btnSimPause) {
    btnSimPause.disabled = true;
    btnSimPause.textContent = '⏸ Pause';
  }
  if (simStateBadge) {
    simStateBadge.textContent = 'Ready';
    simStateBadge.className = 'sim-badge';
  }
  if (simProgressFill) simProgressFill.style.width = '0%';
  if (simTelemPos)     simTelemPos.textContent = '(0.0, 0.0) cm';
  if (simTelemHeading) simTelemHeading.textContent = '0°';
  if (simTelemPen)     simTelemPen.textContent = 'UP (Travel)';
  if (simTelemWp)      simTelemWp.textContent = '0 / 0 (0%)';
  if (simStatusMsg)    simStatusMsg.textContent = 'Simulator reset.';
});

// ══════════════════════════════════════════════════════════════════════════════
// GEMINI AI DESIGN GENERATOR
// ══════════════════════════════════════════════════════════════════════════════

generateBtn?.addEventListener('click', async () => {
  const theme      = themeInput?.value.trim();
  const symmetry   = symmetrySelect?.options[symmetrySelect.selectedIndex]?.text || '8-fold';
  const complexity = complexitySelect?.value || 'medium';
  const style      = styleSelect?.value || 'traditional';

  if (!theme) {
    if (themeError) themeError.textContent = 'Please enter a theme before generating.';
    themeInput?.focus();
    return;
  }
  if (themeError) themeError.textContent = '';
  lastParams = { theme, symmetry, complexity, style };

  if (generateBtn) {
    generateBtn.disabled = true;
    generateBtn.classList.add('loading');
  }
  if (generateMsg) generateMsg.textContent = `Asking Gemini AI to create designs for "${theme}"…`;
  
  designsSection?.classList.add('hidden');
  previewInfoSection?.classList.add('hidden');

  try {
    const resp = await fetch('/api/generate-design', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ theme, symmetry, complexity, style }),
    });

    const data = await resp.json();

    if (!resp.ok || !data.ok) {
      throw new Error(data.error || `Server returned ${resp.status}`);
    }

    if (!Array.isArray(data.designs) || data.designs.length === 0) {
      throw new Error('AI returned no designs. Try a different theme.');
    }

    currentDesigns = data.designs;
    if (generateMsg) generateMsg.textContent = `${currentDesigns.length} AI designs generated for "${theme}".`;
    window._designsGenerated = true;
    showDesigns(currentDesigns);

  } catch (err) {
    if (generateMsg) generateMsg.textContent = '';
    if (themeError) {
      themeError.textContent = `Generation failed: ${err.message}`;
      themeError.style.color = '#c62828';
    }
    console.error('Design generation error:', err);
  } finally {
    if (generateBtn) {
      generateBtn.disabled = false;
      generateBtn.classList.remove('loading');
    }
  }
});

function showDesigns(designs) {
  if (!designsGrid) return;
  designsGrid.innerHTML = '';
  selectedDesignId = null;

  designs.forEach(design => {
    const card = document.createElement('article');
    card.className = 'design-card';
    card.setAttribute('role', 'listitem');
    card.dataset.id = design.id;

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

    card.querySelector('button')?.addEventListener('click', () => selectDesign(design.id));
    card.addEventListener('click', e => { if (e.target.tagName !== 'BUTTON') selectDesign(design.id); });
    designsGrid.appendChild(card);
  });

  designsSection?.classList.remove('hidden');
  previewDefaultBox?.classList.add('hidden');
  previewInfoBox?.classList.remove('hidden');
  if (previewInfoText) previewInfoText.textContent = 'Select a design below to preview it here.';
  designsSection?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function selectDesign(id) {
  selectedDesignId = id;
  const design = currentDesigns.find(d => d.id === id);
  if (!design) return;

  designsGrid?.querySelectorAll('.design-card').forEach(card => {
    const btn = card.querySelector('button'), sel = card.dataset.id === id;
    card.classList.toggle('selected', sel);
    if (btn) {
      btn.textContent = sel ? 'Selected ✓' : 'Select Design';
      btn.classList.toggle('selected', sel);
    }
  });

  if (previewSvgWrap) {
    previewSvgWrap.innerHTML = design.svg;
    previewSvgWrap.classList.add('has-design');
  }
  if (canvasPlaceholder) canvasPlaceholder.style.display = 'none';

  previewInfoBox?.classList.remove('hidden');
  previewDefaultBox?.classList.add('hidden');
  if (previewInfoText) previewInfoText.textContent = `"${design.name}" — ${design.symmetry} symmetry, ${design.complexity}.`;
  continueBtn2?.classList.remove('hidden');

  if (previewTheme)      previewTheme.textContent      = lastParams.theme || '—';
  if (previewName)       previewName.textContent       = design.name;
  if (previewSymmetry)   previewSymmetry.textContent   = design.symmetry;
  if (previewComplexity) previewComplexity.textContent = design.complexity;
  continueTodo?.classList.add('hidden');
  previewInfoSection?.classList.remove('hidden');
  previewInfoSection?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

[continueBtn, continueBtn2].forEach(btn => {
  btn?.addEventListener('click', async () => {
    if (!selectedDesignId) {
      alert('Please select a design first.');
      return;
    }
    if (continueTodo) {
      continueTodo.classList.remove('hidden');
      continueTodo.textContent = 'Generating polar plotter waypoints and vector path…';
    }
    btn.disabled = true;

    try {
      const resp = await fetch('/api/designs/vectorize', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ design_id: selectedDesignId, canvas_cm: 60 }),
      });
      const data = await resp.json();
      if (data.status === 'ok') {
        if (data.waypoints && data.waypoints.length > 0) {
          simWaypoints = data.waypoints;
        }
        if (continueTodo) {
          continueTodo.textContent = `✓ Vectorized ${data.waypoints.length} waypoints. Est. drawing time: ${Math.round(data.estimated_drawing_time_sec/60)}m. Ready for robot & simulation!`;
          continueTodo.style.background = '#e8f5e9';
          continueTodo.style.color = '#2e7d32';
          continueTodo.style.borderColor = '#c8e6c9';
        }
      } else if (continueTodo) {
        continueTodo.textContent = `Vectorization note: ${data.error?.message || 'Ready'}`;
      }
    } catch (err) {
      if (continueTodo) continueTodo.textContent = `Path generation: ${err.message}`;
    } finally {
      btn.disabled = false;
      btn.blur();
    }
  });
});

themeInput?.addEventListener('keydown', e => { if (e.key === 'Enter') generateBtn?.click(); });
themeInput?.addEventListener('input',   ()  => { if (themeInput.value.trim() && themeError) themeError.textContent = ''; });

// Quick Preset Pills
document.querySelectorAll('.preset-pill').forEach(pill => {
  pill.addEventListener('click', () => {
    if (themeInput) {
      themeInput.value = pill.dataset.theme || '';
      themeInput.focus();
    }
    generateBtn?.click();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
// LIVE CAMERA MODULE
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

let camStream   = null;
let camMirrored = true;
let camDeviceId = null;

function camSetStatus(state, text) {
  if (camStatusDot) camStatusDot.className = 'cam-status-dot' + (state ? ' ' + state : '');
  if (camStatusText) camStatusText.textContent = text;
}

function camShowError(msg) {
  if (camError) {
    camError.textContent = msg;
    camError.classList.remove('hidden');
  }
}
function camClearError() {
  if (camError) {
    camError.textContent = '';
    camError.classList.add('hidden');
  }
}

async function camEnumerateDevices() {
  try {
    if (!navigator.mediaDevices?.enumerateDevices || !camDeviceSelect) return;
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
      if (camDeviceId && cameras.some(c => c.deviceId === camDeviceId)) {
        camDeviceSelect.value = camDeviceId;
      } else {
        camDeviceId = cameras[0].deviceId;
      }
    }
  } catch (_) {}
}

async function camStart() {
  camClearError();

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    camShowError('Your browser does not support camera access.');
    return;
  }

  const constraints = {
    video: camDeviceId
      ? { deviceId: { exact: camDeviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
      : { width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: false,
  };

  try {
    camStream = await navigator.mediaDevices.getUserMedia(constraints);
    if (camVideo) {
      camVideo.srcObject = camStream;
      camVideo.classList.toggle('mirrored', camMirrored);
    }

    camPlaceholder?.classList.add('hidden');
    camStartBtn?.classList.add('hidden');
    camStopBtn?.classList.remove('hidden');
    camCaptureBtn?.classList.remove('hidden');
    camFlipBtn?.classList.remove('hidden');
    camSetStatus('live', 'Live');

    await camEnumerateDevices();

    const track = camStream.getVideoTracks()[0];
    if (track) {
      const settings = track.getSettings();
      if (settings.deviceId && camDeviceSelect) {
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
    camShowError(msg);
    camSetStatus('error', 'Error');
  }
}

function camStop() {
  if (!camStream) return;
  camStream.getTracks().forEach(t => t.stop());
  camStream = null;
  if (camVideo) camVideo.srcObject = null;
  camPlaceholder?.classList.remove('hidden');
  camStartBtn?.classList.remove('hidden');
  camStopBtn?.classList.add('hidden');
  camCaptureBtn?.classList.add('hidden');
  camFlipBtn?.classList.add('hidden');
  camSetStatus('', 'Camera off');
}

function camCapture() {
  if (!camStream || !camVideo || !camVideo.videoWidth || !camCanvas) return;

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
  if (camMirrored) ctx.setTransform(1, 0, 0, 1, 0, 0);

  const dataUrl = camCanvas.toDataURL('image/jpeg', 0.92);
  if (captureImg) captureImg.src = dataUrl;
  capturePreview?.classList.remove('hidden');
  capturePreview?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function camFlip() {
  camMirrored = !camMirrored;
  camVideo?.classList.toggle('mirrored', camMirrored);
}

camDeviceSelect?.addEventListener('change', async () => {
  camDeviceId = camDeviceSelect.value;
  if (camStream) {
    camStop();
    await camStart();
  }
});

camStartBtn?.addEventListener('click',   camStart);
camStopBtn?.addEventListener('click',    camStop);
camCaptureBtn?.addEventListener('click', camCapture);
camFlipBtn?.addEventListener('click',    camFlip);
captureCloseBtn?.addEventListener('click', () => capturePreview?.classList.add('hidden'));

navigator.mediaDevices?.enumerateDevices().then(camEnumerateDevices).catch(() => {});

// ── Live System Health Polling ────────────────────────────────────────────────
async function pollStatus() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    const h = await res.json();
    const statusDot = document.querySelector('#systemStatus .status-dot');
    const statusLabel = document.querySelector('#systemStatus .status-label');
    const statusSub = document.querySelector('#systemStatus .status-sub');
    if (h.ai_available) {
      if (statusDot)   statusDot.className = 'status-dot online';
      if (statusLabel) statusLabel.textContent = 'System Online';
      if (statusSub)   statusSub.textContent = `${h.provider || 'Gemini AI'} Active`;
    }
  } catch (_) {}
}
setInterval(pollStatus, 8000);
pollStatus();
