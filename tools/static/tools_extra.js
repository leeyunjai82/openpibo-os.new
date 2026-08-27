/**
 * tools_extra.js — Tools UX 보조 (전면 개선)
 */
(function () {
  'use strict';

  function clamp(v) { const n = parseInt(v,10); return isNaN(n)?0:Math.min(255,Math.max(0,n)); }
  function toHex(r,g,b) { return '#'+[r,g,b].map(x=>('0'+clamp(x).toString(16)).slice(-2)).join(''); }
  function hexToRgb(hex) { return [parseInt(hex.slice(1,3),16),parseInt(hex.slice(3,5),16),parseInt(hex.slice(5,7),16)]; }
  function hookSocket(cb) { if(typeof socket==='undefined'){setTimeout(()=>hookSocket(cb),200);return;} cb(socket); }

  /* 1. 눈 색상 피커 ↔ RGB 입력 동기화 */
  const pickerR = document.getElementById('eye_color_picker_r');
  const pickerL = document.getElementById('eye_color_picker_l');

  // RGB → 피커
  function syncPickerFromRgb() {
    const r0=clamp($('#d_n0_val').val()),g0=clamp($('#d_n1_val').val()),b0=clamp($('#d_n2_val').val());
    const r1=clamp($('#d_n3_val').val()),g1=clamp($('#d_n4_val').val()),b1=clamp($('#d_n5_val').val());
    if(pickerR) pickerR.value = toHex(r0,g0,b0);
    if(pickerL) pickerL.value = toHex(r1,g1,b1);
  }

  for(let i=0;i<6;i++){
    const el=document.getElementById(`d_n${i}_val`);
    if(el) ['input','change'].forEach(ev=>el.addEventListener(ev, syncPickerFromRgb));
  }

  // 피커 → RGB
  if(pickerR) {
    // input: 드래그 중 RGB 숫자만 업데이트
    pickerR.addEventListener('input', () => {
      const [r,g,b] = hexToRgb(pickerR.value);
      $('#d_n0_val').val(r); $('#d_n1_val').val(g); $('#d_n2_val').val(b);
    });
    // change: 피커 닫힐 때 로봇에 실제 반영
    pickerR.addEventListener('change', () => {
      const [r,g,b] = hexToRgb(pickerR.value);
      $('#d_n0_val').val(r); $('#d_n1_val').val(g); $('#d_n2_val').val(b);
      ['#d_n0_val','#d_n1_val','#d_n2_val'].forEach(s => $(s).trigger('click'));
    });
  }
  if(pickerL) {
    pickerL.addEventListener('input', () => {
      const [r,g,b] = hexToRgb(pickerL.value);
      $('#d_n3_val').val(r); $('#d_n4_val').val(g); $('#d_n5_val').val(b);
    });
    pickerL.addEventListener('change', () => {
      const [r,g,b] = hexToRgb(pickerL.value);
      $('#d_n3_val').val(r); $('#d_n4_val').val(g); $('#d_n5_val').val(b);
      ['#d_n3_val','#d_n4_val','#d_n5_val'].forEach(s => $(s).trigger('click'));
    });
  }

  hookSocket(s => s.on('update_neopixel', () => setTimeout(syncPickerFromRgb, 50)));
  setTimeout(syncPickerFromRgb, 300);

  // 초기화 버튼 클릭 시 color picker 동기화
  document.getElementById('eye_reset_bt')?.addEventListener('click', () => {
    setTimeout(syncPickerFromRgb, 0);
  });

  /* 2. 업로드 영역 dragover 시각 피드백 (실제 업로드는 input change → index.js) */
  ['upload_audio', 'upload_image'].forEach(id => {
    const input = document.getElementById(id);
    if (!input) return;
    const area = input.closest('.upload-area');
    if (!area) return;
    ['dragenter','dragover'].forEach(ev => input.addEventListener(ev, () => area.classList.add('dragover')));
    ['dragleave','drop'].forEach(ev => input.addEventListener(ev, () => area.classList.remove('dragover')));
  });
  function setupUploadDrop(zoneId, inputId, uploadUrl, fieldName) {
    const zone  = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    if (!zone) return;

    ['dragenter','dragover','dragleave','drop'].forEach(ev =>
      zone.addEventListener(ev, e => e.preventDefault())
    );
    zone.addEventListener('dragenter', () => zone.classList.add('dragover'));
    zone.addEventListener('dragover',  () => zone.classList.add('dragover'));
    zone.addEventListener('dragleave', (e) => {
      if (!zone.contains(e.relatedTarget)) zone.classList.remove('dragover');
    });
    zone.addEventListener('drop', async (e) => {
      zone.classList.remove('dragover');
      const files = Array.from(e.dataTransfer.files);
      if (!files.length) return;

      if (uploadUrl) {
        // 오디오/이미지: 직접 fetch 업로드
        const formData = new FormData();
        formData.append(fieldName, files[0]);
        try {
          const res = await fetch(uploadUrl, { method: 'POST', body: formData });
          const msg = res.ok
            ? (typeof translations !== 'undefined' ? translations['file_ok'][lang] : '업로드 완료!')
            : '업로드 실패: ' + res.statusText;
          await alert_popup(msg);
        } catch(err) { await alert_popup('오류: ' + err.message); }
      } else {
        // JSON/CSV: index.js change 핸들러 위임
        if (!input) return;
        try {
          const dt = new DataTransfer();
          dt.items.add(files[0]);
          input.files = dt.files;
        } catch(err) { console.warn('DataTransfer:', err); }
        $(input).trigger('change');
      }
    });
  }

  // 루트 절대 경로를 그대로 쓰면 프록시(/tools/) 아래에서 허브로 올라간다.
  // BASE 는 index.js 가 window.__BASE__ 에서 만들어 둔 값이다.
  setupUploadDrop('drop_zone_audio',  'upload_audio',     `${BASE}/upload_file/myaudio`, 'data');
  setupUploadDrop('drop_zone_image',  'upload_image',     `${BASE}/upload_file/myimage`, 'data');
  setupUploadDrop('drop_zone_motion', 'v_import_motion',  null, null);
  setupUploadDrop('drop_zone_csv',    's_upload_csv',     null, null);

  /* 3. 오디오 플레이어 */
  const micAudioEl   = document.getElementById('mic_audio_player');
  const audioPlayer  = document.getElementById('audio_player');

  // 마이크 재생 버튼 → 플레이어 표시
  $('#mic_replay_bt').on('click', function () {
    if (!micAudioEl) return;
    micAudioEl.src = `/download_mic?t=${Date.now()}`;
    micAudioEl.style.display = 'block';
    micAudioEl.play().catch(() => {});
  });

  // 오디오 재생 버튼 → 플레이어에 src 표시
  $('#play_audio_bt').on('click', function () {
    const fn = $('#audiofiles').val();
    const p  = $('#audiopath').val();
    if (!fn || fn === '-' || !audioPlayer) return;
    // 서버에서 직접 스트리밍하는 경우 (경로가 있으면)
    audioPlayer.style.display = 'block';
    audioPlayer.src = `/play_audio_stream?path=${encodeURIComponent(p + '/' + fn)}`;
  });

  $('#stop_audio_bt').on('click', function () {
    if (audioPlayer) { audioPlayer.pause(); audioPlayer.currentTime = 0; }
  });

  /* 4. Vision 결과 파싱 */
  const vResultEl    = document.getElementById('v_result');
  const vResultCards = document.getElementById('v_result_cards');

  function renderVisionResult(raw) {
    if (!vResultCards) return;
    if (!raw || !raw.trim()) {
      vResultCards.innerHTML = '<div class="v-result-empty"><span data-key="none">결과 없음</span></div>';
      return;
    }
    // JSON 파싱 시도
    try {
      const data = JSON.parse(raw);
      if (Array.isArray(data)) {
        if (data.length === 0) {
          vResultCards.innerHTML = '<div class="v-result-empty">감지된 항목 없음</div>';
          return;
        }
        vResultCards.innerHTML = data.map((item, i) => {
          const text = typeof item === 'object'
            ? Object.entries(item).map(([k,v]) => `<b>${k}</b>: ${JSON.stringify(v)}`).join(' | ')
            : String(item);
          return `<div class="v-result-card">${i+1}. ${text}</div>`;
        }).join('');
      } else {
        vResultCards.innerHTML = `<div class="v-result-card">${raw}</div>`;
      }
    } catch {
      // JSON 아니면 텍스트 그대로
      vResultCards.innerHTML = raw.split('\n').filter(l => l.trim()).map(l =>
        `<div class="v-result-card">${l}</div>`
      ).join('');
    }
  }

  // v_result textarea 변경 감지 → 카드 렌더링
  if (vResultEl) {
    const vObs = new MutationObserver(() => renderVisionResult(vResultEl.value));
    vObs.observe(vResultEl, { attributes: true, childList: true, subtree: true });
    // index.js가 .text()로 세팅 — input 이벤트 대신 주기적 폴링
    setInterval(() => {
      const cur = vResultEl.value;
      if (vResultCards && cur !== (vResultCards.dataset.last || '')) {
        vResultCards.dataset.last = cur;
        renderVisionResult(cur);
      }
    }, 500);
  }

  hookSocket(s => s.on('stream', (data) => {
    if (data && data.data !== undefined) {
      setTimeout(() => renderVisionResult(typeof data.data === 'string' ? data.data : JSON.stringify(data.data)), 0);
    }
  }));

  /* 5. 모션 예제 버튼 그리드 */
  const motionSamplesEl=document.getElementById('motion_samples');
  if(motionSamplesEl){
    const obs=new MutationObserver(()=>{
      const links=motionSamplesEl.querySelectorAll('a');
      if(!links.length) return;
      obs.disconnect();
      motionSamplesEl.className='motion-sample-grid';
      motionSamplesEl.innerHTML='';
      links.forEach(link=>{
        const name=link.textContent.trim();
        const btn=document.createElement('button');
        btn.className='motion-sample-btn'; btn.textContent=name; btn.title=name;
        btn.addEventListener('click',()=>{
          if(typeof socket!=='undefined') socket.emit('load_motion',name);
          btn.classList.add('running');
          setTimeout(()=>btn.classList.remove('running'),1200);
        });
        motionSamplesEl.appendChild(btn);
      });
    });
    obs.observe(motionSamplesEl,{childList:true});
  }

  /* 6. 비전 퀵 버튼 그리드 — 그룹 분리, translations 연동 */
  const visionGrid = document.getElementById('vision_quick_grid');
  const vFuncSel   = document.getElementById('v_func_type');

  // key: translations key, icon: 이모지
  const visionGroups = [
    [
      {value:'camera',               key:'camera',               icon:'📷'},
    ],
    [
      {value:'face',                 key:'v_face',               icon:'😊'},
      {value:'face_landmark',        key:'v_face_landmark',      icon:'🗺'},
      {value:'hand',                 key:'v_hand',               icon:'✋'},
      {value:'pose',                 key:'v_pose',               icon:'🧍'},
    ],
    [
      {value:'object',               key:'v_object',             icon:'🔍'},
      {value:'track',                key:'v_track',              icon:'🎯'},
      {value:'qr',                   key:'v_qr',                 icon:'▣'},
      {value:'marker',               key:'v_marker',             icon:'⬛'},
    ],
    [
      {value:'grayscale',            key:'v_grayscale',          icon:'⬜'},
      {value:'canny',                key:'v_canny',              icon:'〰'},
      {value:'cartoon',              key:'v_cartoon',            icon:'🎨'},
      {value:'sketch_rgb',           key:'v_sketch_rgb',         icon:'✏'},
      {value:'detail',               key:'v_detail',             icon:'🔬'},
      {value:'edgePreservingFilter', key:'v_edgePreservingFilter',icon:'💧'},
    ],
  ];

  function getVisionLabel(key, icon) {
    if (typeof translations !== 'undefined' && translations[key] && typeof lang !== 'undefined') {
      return icon + ' ' + translations[key][lang];
    }
    return icon;
  }

  if (visionGrid && vFuncSel) {
    visionGroups.forEach((group, gi) => {
      if (gi > 0) {
        const sep = document.createElement('div');
        sep.className = 'vision-group-sep';
        visionGrid.appendChild(sep);
      }
      const row = document.createElement('div');
      row.className = 'vision-group-row';
      group.forEach(({value, key, icon}) => {
        const btn = document.createElement('button');
        btn.className = 'vision-quick-btn';
        btn.textContent = getVisionLabel(key, icon);
        btn.dataset.value = value;
        btn.dataset.key = key;
        btn.dataset.icon = icon;
        if (value === 'camera') btn.classList.add('active');
        btn.addEventListener('click', () => {
          visionGrid.querySelectorAll('.vision-quick-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          vFuncSel.value = value;
          $(vFuncSel).trigger('change');
        });
        row.appendChild(btn);
      });
      visionGrid.appendChild(row);
    });

    // 언어 변경 시 버튼 텍스트 갱신
    const langSelect = document.getElementById('language');
    if (langSelect) {
      langSelect.addEventListener('change', () => {
        setTimeout(() => {
          visionGrid.querySelectorAll('.vision-quick-btn').forEach(btn => {
            btn.textContent = getVisionLabel(btn.dataset.key, btn.dataset.icon);
          });
        }, 100);
      });
    }

    hookSocket(s => s.on('disp_vision', (val) => {
      visionGrid.querySelectorAll('.vision-quick-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.value === val)
      );
    }));
  }

  /* 7. TTS 글자수 카운터 */
  const ttsSel=document.getElementById('s_tts_val');
  const charCount=document.getElementById('tts_char_count');
  if(ttsSel&&charCount){
    const upd=()=>{ const l=ttsSel.value.length; charCount.textContent=`${l} / 100`; charCount.classList.toggle('warn',l>80); };
    ttsSel.addEventListener('input',upd); upd();
  }

  /* 8. 마이크 상태 */
  hookSocket(s=>s.on('mic',(d)=>{
    const el=document.getElementById('mic_status'); if(!el) return;
    el.innerHTML=(d&&(d.includes('중')||d.toLowerCase().includes('rec')))
      ?`<i class="fa-solid fa-microphone fa-beat" style="color:var(--red)"></i> ${d}`
      :`<span style="color:#666">${d}</span>`;
  }));

})();