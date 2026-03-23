// ---- State ----
let state = {
  apiUrl: localStorage.getItem('ih_api') || 'http://localhost:8000',
  mediaId: null,
  mediaType: null,
  audioId: null,
  aspect: '9:16',
};

document.getElementById('apiUrl').value = state.apiUrl;

// Tabs
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + tab).classList.add('active');
  });
});

// Aspect ratio
document.querySelectorAll('.aspect-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.aspect-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.aspect = btn.dataset.aspect;
    drawCanvas();
  });
});

// Sliders
['textX','textY'].forEach(id => {
  document.getElementById(id).addEventListener('input', e => {
    document.getElementById(id + 'Val').textContent = parseFloat(e.target.value).toFixed(2);
    updatePreviewOverlay();
  });
});
['overlayText','fontSize','textColor','glitchToggle'].forEach(id => {
  document.getElementById(id).addEventListener('input', updatePreviewOverlay);
  document.getElementById(id).addEventListener('change', updatePreviewOverlay);
});

function saveApiUrl() {
  state.apiUrl = document.getElementById('apiUrl').value.trim().replace(/\/$/,'');
  localStorage.setItem('ih_api', state.apiUrl);
  setStatus('API URL saved.','ok');
}

// Media dropzone
const dz = document.getElementById('dropzone');
dz.addEventListener('click', () => document.getElementById('fileInput').click());
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag'); });
dz.addEventListener('dragleave', () => dz.classList.remove('drag'));
dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('drag'); if(e.dataTransfer.files[0]) uploadMedia(e.dataTransfer.files[0]); });
document.getElementById('fileInput').addEventListener('change', e => { if(e.target.files[0]) uploadMedia(e.target.files[0]); });

async function uploadMedia(file) {
  setStatus('Uploading...','info');
  const fd = new FormData(); fd.append('file', file);
  try {
    const r = await fetch(`${state.apiUrl}/api/media/upload`,{method:'POST',body:fd});
    const d = await r.json();
    if (d.id) {
      state.mediaId = d.id; state.mediaType = d.type;
      showSourcePreview(d.url, d.type);
      document.getElementById('sourceInfo').textContent = `${d.original_name} (${d.type})`;
      dz.classList.add('has-file'); dz.querySelector('p').textContent = file.name;
      drawCanvas(); setStatus('Uploaded.','ok');
    } else { setStatus('Upload error: '+(d.detail||'?'),'error'); }
  } catch(e) { setStatus('Upload failed: '+e.message,'error'); }
}

function showSourcePreview(url, type) {
  const box = document.getElementById('previewBox');
  box.innerHTML = '';
  const full = state.apiUrl + url;
  if (type === 'video') {
    const v = document.createElement('video');
    v.src = full; v.controls = true; v.muted = true;
    box.appendChild(v);
  } else {
    const img = document.createElement('img');
    img.src = full; img.onload = () => drawCanvas();
    box.appendChild(img);
  }
}

async function generateImage() {
  const prompt = document.getElementById('genPrompt').value.trim();
  if (!prompt) return;
  setStatus('Generating...','info');
  try {
    const r = await fetch(`${state.apiUrl}/api/generate/image`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        prompt,
        width: +document.getElementById('genWidth').value,
        height: +document.getElementById('genHeight').value,
        model: document.getElementById('genModel').value,
      })
    });
    const d = await r.json();
    if (d.id) {
      state.mediaId = d.id; state.mediaType = 'image';
      showSourcePreview(d.url,'image');
      document.getElementById('sourceInfo').textContent = 'Generated: '+prompt.slice(0,40);
      drawCanvas(); setStatus('Generated.','ok');
    } else { setStatus('Error: '+(d.detail||'?'),'error'); }
  } catch(e) { setStatus('Failed: '+e.message,'error'); }
}

// Audio dropzone
const adz = document.getElementById('audioDropzone');
adz.addEventListener('click', () => document.getElementById('audioInput').click());
adz.addEventListener('dragover', e => { e.preventDefault(); adz.classList.add('drag'); });
adz.addEventListener('dragleave', () => adz.classList.remove('drag'));
adz.addEventListener('drop', e => { e.preventDefault(); adz.classList.remove('drag'); if(e.dataTransfer.files[0]) uploadAudio(e.dataTransfer.files[0]); });
document.getElementById('audioInput').addEventListener('change', e => { if(e.target.files[0]) uploadAudio(e.target.files[0]); });

async function uploadAudio(file) {
  setStatus('Uploading audio...','info');
  const fd = new FormData(); fd.append('file', file);
  try {
    const r = await fetch(`${state.apiUrl}/api/media/upload`,{method:'POST',body:fd});
    const d = await r.json();
    if (d.id) {
      state.audioId = d.id;
      adz.classList.add('has-file'); adz.querySelector('p').textContent = file.name;
      document.getElementById('audioTimeRow').style.display = 'grid';
      document.getElementById('audioInfo').textContent = 'Audio: '+file.name;
      setStatus('Audio uploaded.','ok');
    } else { setStatus('Audio error.','error'); }
  } catch(e) { setStatus('Audio failed: '+e.message,'error'); }
}

// Canvas
function drawCanvas() {
  const canvas = document.getElementById('previewCanvas');
  const ctx = canvas.getContext('2d');
  const [aw,ah] = aspectDims(state.aspect);
  const scale = 380 / Math.max(aw,ah);
  canvas.width = aw*scale; canvas.height = ah*scale;
  ctx.fillStyle = '#111'; ctx.fillRect(0,0,canvas.width,canvas.height);
  const img = document.querySelector('#previewBox img');
  if (img && img.complete && state.mediaType==='image') {
    const ir = img.naturalWidth/img.naturalHeight, cr = canvas.width/canvas.height;
    let sx=0,sy=0,sw=img.naturalWidth,sh=img.naturalHeight;
    if (ir>cr) { sw=img.naturalHeight*cr; sx=(img.naturalWidth-sw)/2; }
    else { sh=img.naturalWidth/cr; sy=(img.naturalHeight-sh)/2; }
    ctx.drawImage(img,sx,sy,sw,sh,0,0,canvas.width,canvas.height);
  }
  updatePreviewOverlay();
}

function updatePreviewOverlay() {
  const el = document.getElementById('overlayPreview');
  const canvas = document.getElementById('previewCanvas');
  const text = document.getElementById('overlayText').value;
  if (!text) { el.textContent=''; return; }
  const x = +document.getElementById('textX').value;
  const y = +document.getElementById('textY').value;
  const size = +document.getElementById('fontSize').value;
  const color = document.getElementById('textColor').value;
  const glitch = document.getElementById('glitchToggle').checked;
  const cw = canvas.offsetWidth||canvas.width;
  const ch = canvas.offsetHeight||canvas.height;
  el.textContent = text;
  el.style.fontSize = Math.max(8, Math.round(size*(cw/1080)))+'px';
  el.style.color = color;
  el.style.textShadow = glitch ? '-4px 0 rgba(255,0,80,0.7),4px 0 rgba(0,255,220,0.7)' : 'none';
  const rect = canvas.getBoundingClientRect();
  const wrap = document.querySelector('.canvas-wrap').getBoundingClientRect();
  el.style.left = (rect.left-wrap.left + x*cw)+'px';
  el.style.top  = (rect.top -wrap.top  + y*ch)+'px';
  el.style.transform = 'translate(-50%,-50%)';
}

function aspectDims(a) {
  return {'16:9':[1920,1080],'9:16':[1080,1920],'3:4':[1080,1440],'1:1':[1080,1080]}[a]||[1080,1080];
}

async function renderExport() {
  if (!state.mediaId) { setStatus('Load media first.','error'); return; }
  const text = document.getElementById('overlayText').value.trim();
  const body = {
    media_id: state.mediaId,
    aspect: state.aspect,
    text: text ? {
      text,
      x: +document.getElementById('textX').value,
      y: +document.getElementById('textY').value,
      font_size: +document.getElementById('fontSize').value,
      color: document.getElementById('textColor').value,
      glitch: document.getElementById('glitchToggle').checked,
    } : null,
    audio_id: state.audioId||null,
    audio_start: +document.getElementById('audioStart').value||0,
    audio_end: document.getElementById('audioEnd').value ? +document.getElementById('audioEnd').value : null,
  };
  setStatus('Rendering...','info');
  document.getElementById('resultBox').style.display='none';
  try {
    const r = await fetch(`${state.apiUrl}/api/export/render`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    const d = await r.json();
    if (d.download) { setStatus('Done!','ok'); showResult(d); }
    else { setStatus('Error: '+(d.detail||JSON.stringify(d)),'error'); }
  } catch(e) { setStatus('Failed: '+e.message,'error'); }
}

function showResult(data) {
  const box=document.getElementById('resultBox');
  const vid=document.getElementById('resultVideo');
  const img=document.getElementById('resultImage');
  const lnk=document.getElementById('downloadLink');
  box.style.display='flex';
  const full = state.apiUrl+data.url;
  const dl   = state.apiUrl+data.download;
  if (data.id.match(/\.(mp4|mov|webm)$/i)) {
    vid.style.display='block'; img.style.display='none'; vid.src=full;
  } else {
    img.style.display='block'; vid.style.display='none'; img.src=full;
  }
  lnk.href=dl; lnk.download=data.id;
}

function setStatus(msg,type='info') {
  const el=document.getElementById('statusBox');
  el.textContent=msg; el.className='status-box '+type;
}
