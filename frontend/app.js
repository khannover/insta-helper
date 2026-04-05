// ---- State ----
function defaultApiUrl() {
  const saved = localStorage.getItem('ih_api');
  if (saved) return saved;

  if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
    if (window.location.port === '3000') {
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }
    return window.location.origin;
  }

  return 'http://localhost:8000';
}

let state = {
  apiUrl: defaultApiUrl(),
  mediaId: null,
  mediaType: null,
  audioId: null,
  aspect: '9:16',
  fx: [],
  animFx: [],
  cropMode: 'center',
  cropRect: null, // [x1, y1, x2, y2] normalized
  outputFormat: 'auto',
  videoCodec: 'h264',
};

class CropManager {
  constructor() {
    this.box = document.getElementById('cropBox');
    this.container = document.getElementById('cropContainer');
    this.img = document.getElementById('cropImg');
    this.isDragging = false;
    this.isResizing = false;
    this.currentHandle = null;
    this.startX = 0; this.startY = 0;
    this.startLeft = 0; this.startTop = 0;
    this.startWidth = 0; this.startHeight = 0;

    this.box.onmousedown = (e) => this.startDrag(e);
    document.querySelectorAll('.crop-handle').forEach(h => {
      h.onmousedown = (e) => this.startResize(e, h.dataset.handle);
    });
    window.onmousemove = (e) => this.handleMouseMove(e);
    window.onmouseup = () => this.stopAll();
  }

  initFor(img) {
    this.img = img;
    this.resetBox(state.aspect);
  }

  resetBox(ratioStr) {
    const cw = this.container.clientWidth;
    const ch = (this.img.naturalHeight / this.img.naturalWidth) * cw;
    this.container.style.height = ch + 'px';

    let w, h;
    if (ratioStr === 'custom') {
      w = cw * 0.8; h = ch * 0.8;
    } else {
      const parts = ratioStr.split(':');
      const r = parts[0] / parts[1];
      if (cw / ch > r) {
        h = ch * 0.8; w = h * r;
      } else {
        w = cw * 0.8; h = w / r;
      }
    }
    this.setBoxPos((cw - w) / 2, (ch - h) / 2, w, h);
    this.updateState();
  }

  startDrag(e) {
    if (e.target.classList.contains('crop-handle')) return;
    this.isDragging = true;
    this.startX = e.clientX; this.startY = e.clientY;
    this.startLeft = this.box.offsetLeft; this.startTop = this.box.offsetTop;
    e.preventDefault();
  }

  startResize(e, handle) {
    this.isResizing = true;
    this.currentHandle = handle;
    this.startX = e.clientX; this.startY = e.clientY;
    this.startLeft = this.box.offsetLeft; this.startTop = this.box.offsetTop;
    this.startWidth = this.box.offsetWidth; this.startHeight = this.box.offsetHeight;
    e.stopPropagation();
    e.preventDefault();
  }

  handleMouseMove(e) {
    if (!this.isDragging && !this.isResizing) return;

    const dx = e.clientX - this.startX;
    const dy = e.clientY - this.startY;
    const cw = this.container.clientWidth;
    const ch = this.container.clientHeight;

    if (this.isDragging) {
      let l = this.startLeft + dx;
      let t = this.startTop + dy;
      l = Math.max(0, Math.min(l, cw - this.box.offsetWidth));
      t = Math.max(0, Math.min(t, ch - this.box.offsetHeight));
      this.box.style.left = l + 'px';
      this.box.style.top = t + 'px';
    } else if (this.isResizing) {
      this.applyResize(dx, dy, cw, ch);
    }
    this.updateState();
  }

  applyResize(dx, dy, cw, ch) {
    let l = this.startLeft, t = this.startTop, w = this.startWidth, h = this.startHeight;
    const ratio = state.aspect === 'custom' ? null : (parseInt(state.aspect.split(':')[0]) / parseInt(state.aspect.split(':')[1]));

    const hdl = this.currentHandle;
    if (hdl.includes('r')) w = Math.min(this.startWidth + dx, cw - l);
    if (hdl.includes('l')) {
      const newW = Math.max(10, this.startWidth - dx);
      const newL = Math.max(0, this.startLeft + (this.startWidth - newW));
      w = this.startWidth + (this.startLeft - newL);
      l = newL;
    }
    if (hdl.includes('b')) h = Math.min(this.startHeight + dy, ch - t);
    if (hdl.includes('t')) {
      const newH = Math.max(10, this.startHeight - dy);
      const newT = Math.max(0, this.startTop + (this.startHeight - newH));
      h = this.startHeight + (this.startTop - newT);
      t = newT;
    }

    if (ratio) {
      // Constraints
      if (hdl === 'r' || hdl === 'l' || hdl === 't' || hdl === 'b') {
          if (hdl === 'r' || hdl === 'l') h = w / ratio;
          else w = h * ratio;
      } else {
          // Corner handles
          if (w / h > ratio) h = w / ratio; else w = h * ratio;
      }
      // Re-check bounds
      if (l + w > cw) { w = cw - l; h = w / ratio; }
      if (t + h > ch) { h = ch - t; w = h * ratio; }
    }

    this.setBoxPos(l, t, w, h);
  }

  setBoxPos(l, t, w, h) {
    this.box.style.left = l + 'px';
    this.box.style.top = t + 'px';
    this.box.style.width = w + 'px';
    this.box.style.height = h + 'px';
  }

  stopAll() {
    this.isDragging = false; this.isResizing = false;
  }

  updateState() {
    const cw = this.container.clientWidth, ch = this.container.clientHeight;
    const x1 = this.box.offsetLeft / cw;
    const y1 = this.box.offsetTop / ch;
    const x2 = (this.box.offsetLeft + this.box.offsetWidth) / cw;
    const y2 = (this.box.offsetTop + this.box.offsetHeight) / ch;
    state.cropRect = [x1, y1, x2, y2];
    drawCanvas();
  }
}

const cropManager = new CropManager();

document.getElementById('apiUrl').value = state.apiUrl;
document.getElementById('outputFormat').value = state.outputFormat;
document.getElementById('videoCodec').value = state.videoCodec;

document.getElementById('outputFormat').addEventListener('change', e => {
  state.outputFormat = e.target.value;
  syncExportOptions();
});

document.getElementById('videoCodec').addEventListener('change', e => {
  state.videoCodec = e.target.value;
});

syncExportOptions();

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
  btn.onclick = () => {
    document.querySelectorAll('.aspect-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.aspect = btn.dataset.ratio;
    if (state.mediaType === 'image') {
      const img = document.getElementById('cropImg');
      if (img.src) cropManager.resetBox(state.aspect);
    }
    drawCanvas();
  };
});

// FX buttons (Multiple)
document.querySelectorAll('.fx-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const val = btn.dataset.fx;
    if (val === 'none') {
      state.fx = [];
      document.querySelectorAll('.fx-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    } else {
      document.querySelector('.fx-btn[data-fx="none"]').classList.remove('active');
      if (state.fx.includes(val)) {
        state.fx = state.fx.filter(f => f !== val);
        btn.classList.remove('active');
      } else {
        state.fx.push(val);
        btn.classList.add('active');
      }
      if (state.fx.length === 0) document.querySelector('.fx-btn[data-fx="none"]').classList.add('active');
    }
    drawCanvas();
  });
});

// Animation FX buttons (Multiple)
document.querySelectorAll('.anim-fx-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const val = btn.dataset.anim;
    console.log('Animation FX toggled:', val);
    if (val === 'none') {
      state.animFx = [];
      document.querySelectorAll('.anim-fx-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    } else {
      document.querySelector('.anim-fx-btn[data-anim="none"]').classList.remove('active');
      if (state.animFx.includes(val)) {
        state.animFx = state.animFx.filter(f => f !== val);
        btn.classList.remove('active');
      } else {
        state.animFx.push(val);
        btn.classList.add('active');
      }
      if (state.animFx.length === 0) document.querySelector('.anim-fx-btn[data-anim="none"]').classList.add('active');
    }
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

function updateSourceActions(data = null) {
  const actions = document.getElementById('sourceActions');
  const link = document.getElementById('sourceDownloadLink');

  if (data && data.type === 'image' && data.download && data.prompt) {
    actions.style.display = 'flex';
    link.href = data.download.startsWith('http') ? data.download : state.apiUrl + data.download;
    link.download = data.id || 'generated-image';
    return;
  }

  actions.style.display = 'none';
  link.removeAttribute('href');
  link.removeAttribute('download');
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
      showSourcePreview(d); // Pass the whole data object
      updateSourceActions();
      document.getElementById('sourceInfo').textContent = `${d.original_name} (${d.type})`;
      dz.classList.add('has-file'); dz.querySelector('p').textContent = file.name;
      drawCanvas(); setStatus('Uploaded.','ok');
    } else { setStatus('Upload error: '+(d.detail||'?'),'error'); }
  } catch(e) { setStatus('Upload failed: '+e.message,'error'); }
}

function showSourcePreview(data) {
  const isVideo = data.type === 'video';
  state.mediaId = data.id;
  state.mediaType = isVideo ? 'video' : 'image';
  
  const url = data.url.startsWith('http') ? data.url : state.apiUrl + data.url;

  if (isVideo) {
    document.getElementById('mediaPreview').style.display = 'flex';
    document.getElementById('cropContainer').style.display = 'none';
    const preview = document.getElementById('mediaPreview');
    preview.innerHTML = `<video src="${url}" controls muted loop style="max-width:100%; max-height:240px;"></video>`;
  } else {
    document.getElementById('mediaPreview').style.display = 'none';
    document.getElementById('cropContainer').style.display = 'block';
    const cropImg = document.getElementById('cropImg');
    cropImg.src = url;
    cropImg.onload = () => {
      cropManager.initFor(cropImg);
    };
  }
}

async function generateImage() {
  const prompt = document.getElementById('genPrompt').value.trim();
  if (!prompt) return;
  const seedValue = document.getElementById('genSeed').value.trim();
  if (seedValue && !/^\d+$/.test(seedValue)) {
    setStatus('Seed must be a whole number.','error');
    return;
  }

  setStatus('Generating...','info');
  try {
    const body = {
      prompt,
      width: +document.getElementById('genWidth').value,
      height: +document.getElementById('genHeight').value,
      model: document.getElementById('genModel').value,
    };
    if (seedValue) body.seed = Number(seedValue);

    const r = await fetch(`${state.apiUrl}/api/generate/image`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    const d = await r.json();
    if (d.id) {
      showSourcePreview(d); 
      updateSourceActions(d);
      document.getElementById('sourceInfo').textContent = d.seed !== null && d.seed !== undefined
        ? `Generated: ${prompt.slice(0,40)} | Seed ${d.seed}`
        : `Generated: ${prompt.slice(0,40)}`;
      drawCanvas(); setStatus('Generated.','ok');
    } else { setStatus('Error: '+(d.detail||'?'),'error'); }
  } catch(e) { setStatus('Failed: '+e.message,'error'); }
}

function rerollImage() {
  const seed = Math.floor(Math.random() * 2147483647);
  document.getElementById('genSeed').value = String(seed);
  generateImage();
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
  const img = document.getElementById('cropImg');
  if (img && img.complete && state.mediaType==='image') {
    const ir = img.naturalWidth/img.naturalHeight, cr = canvas.width/canvas.height;
    let sx=0,sy=0,sw=img.naturalWidth,sh=img.naturalHeight;
    
    if (state.cropRect) {
      const [x1, y1, x2, y2] = state.cropRect;
      sx = x1 * img.naturalWidth;
      sy = y1 * img.naturalHeight;
      sw = (x2 - x1) * img.naturalWidth;
      sh = (y2 - y1) * img.naturalHeight;
    } else {
      if (ir>cr) { 
        sw=img.naturalHeight*cr; 
        if (state.cropMode === 'top') sx = 0;
        else if (state.cropMode === 'bottom') sx = img.naturalWidth - sw;
        else sx=(img.naturalWidth-sw)/2; 
      }
      else { 
        sh=img.naturalWidth/cr; 
        if (state.cropMode === 'top') sy = 0;
        else if (state.cropMode === 'bottom') sy = img.naturalHeight - sh;
        else sy=(img.naturalHeight-sh)/2; 
      }
    }
    ctx.drawImage(img,sx,sy,sw,sh,0,0,canvas.width,canvas.height);
  }
  
  // Combined CSS filter preview
  let filterStr = '';
  if (state.fx.includes('grayscale')) filterStr += 'grayscale(100%) ';
  if (state.fx.includes('sepia')) filterStr += 'sepia(100%) ';
  if (state.fx.includes('blur')) filterStr += 'blur(4px) ';
  if (state.fx.includes('invert')) filterStr += 'invert(100%) ';
  if (state.fx.includes('vignette')) filterStr += 'contrast(1.1) brightness(0.9) ';
  
  canvas.style.filter = filterStr || 'none';

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
  if (a === 'custom' && state.cropRect) {
    const [x1, y1, x2, y2] = state.cropRect;
    const ratio = (x2 - x1) / (y2 - y1);
    const img = document.getElementById('cropImg');
    if (img && img.naturalHeight) {
      const realRatio = ratio * (img.naturalWidth / img.naturalHeight);
      if (realRatio > 1) {
        return [1080, Math.round(1080 / realRatio)];
      } else {
        return [Math.round(1080 * realRatio), 1080];
      }
    }
  }
  return {'16:9':[1920,1080],'9:16':[1080,1920],'3:4':[1080,1440],'1:1':[1080,1080]}[a]||[1080,1080];
}

async function renderExport() {
  if (!state.mediaId) { setStatus('Load media first.','error'); return; }
  if (state.outputFormat === 'gif' && state.audioId) {
    setStatus('GIF export is silent only. Remove audio or choose MP4.','error');
    return;
  }

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
    fx: state.fx,
    anim_fx: state.animFx,
    crop_rect: state.cropRect,
    output_format: state.outputFormat,
    video_codec: state.videoCodec,
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
  lnk.textContent = data.id.match(/\.(gif)$/i) ? 'Download GIF' : 'Download';
  lnk.href=dl; lnk.download=data.id;
}

function syncExportOptions() {
  const codec = document.getElementById('videoCodec');
  const hint = document.getElementById('exportHint');

  codec.disabled = state.outputFormat !== 'mp4';

  if (state.outputFormat === 'gif') {
    hint.textContent = 'GIF exports are silent and capped to 12s, 12 fps, and 720px on the longest side.';
  } else if (state.outputFormat === 'png') {
    hint.textContent = 'PNG export is for still-image output only.';
  } else if (state.outputFormat === 'mp4') {
    hint.textContent = state.videoCodec === 'h265'
      ? 'H.265 exports are smaller, but browser playback compatibility is weaker than H.264.'
      : 'H.264 is the default for best browser and device compatibility.';
  } else {
    hint.textContent = 'Auto uses PNG for still images and MP4 for animated or audio exports.';
  }
}

function setStatus(msg,type='info') {
  const el=document.getElementById('statusBox');
  el.textContent=msg; el.className='status-box '+type;
}
