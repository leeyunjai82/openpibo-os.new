// 프록시(/tools/) 아래에서도, 포트로 직접 접속해도 같은 코드가 돌게 한다.
//
//   프록시:  허브가 HTML 에 window.__BASE__ = "/tools" 를 심어 준다  (ide/proxy.py)
//   직접:    __BASE__ 가 없으므로 '' — 예전과 똑같이 동작한다
//
// 절대 URL 을 만들 때 반드시 BASE 를 앞에 붙일 것.
// 안 붙이면 프록시 아래에서 허브 루트로 새어 나간다.
const BASE = (typeof window !== 'undefined' && window.__BASE__) || '';

window.addEventListener('beforeunload', () => {
  // 허브의 토글 주소다. BASE 를 붙이면 안 된다 — 이건 뒤쪽 앱이 아니라 허브 것이다.
  fetch(`${location.origin}/tools?enable=off`, { keepalive: true}).catch(() => {});
});

let fullscreen = false;

const fullscreenTxt = document.getElementById('fullscreen_txt');
const fullscreenBt = document.getElementById('fullscreen_bt');

const updateIcon = function () {
  fullscreenTxt.innerHTML = fullscreen
    ? '<i class="fa-solid fa-minimize"></i>'
    : '<i class="fa-solid fa-maximize"></i>';
};

updateIcon();

fullscreenBt.addEventListener('click', (e) => {
  e.preventDefault();
  if (!fullscreen && document.documentElement.requestFullscreen) {
    document.documentElement.requestFullscreen();
    fullscreen = true;
  } else if (fullscreen && document.exitFullscreen) {
    document.exitFullscreen();
    fullscreen = false;
  }
  updateIcon();
});

const motor_default = [0, 0, -80, 0, 0, 0, 0, 0, 80, 0];

document.addEventListener('fullscreenchange', function () {
  fullscreen = !!document.fullscreenElement;
  updateIcon();
});

// --- Popup elements ---
const alertPopup = document.getElementById('alertPopup');
const confirmPopup = document.getElementById('confirmPopup');
const promptPopup = document.getElementById('promptPopup');

const alertMessageElement = document.getElementById('alertMessageElement');
const alertOkBtn = document.getElementById('alertOkBtn');

const confirmMessageElement = document.getElementById('confirmMessageElement');
const confirmOkBtn = document.getElementById('confirmOkBtn');
const confirmCancelBtn = document.getElementById('confirmCancelBtn');

const promptMessageElement = document.getElementById('promptMessageElement');
const promptInputElement = document.getElementById('promptInputElement');
const promptOkBtn = document.getElementById('promptOkBtn');
const promptCancelBtn = document.getElementById('promptCancelBtn');

function hidePopups() {
  if (alertPopup) alertPopup.style.display = 'none';
  if (confirmPopup) confirmPopup.style.display = 'none';
  if (promptPopup) promptPopup.style.display = 'none';
}

async function alert_popup(message) {
  hidePopups();
  if (!alertPopup || !alertMessageElement || !alertOkBtn) {
    console.error("Alert popup elements not found!");
    return;
  }
  alertMessageElement.textContent = message;
  alertPopup.style.display = 'flex';
  alertOkBtn.focus();
  const handler = function () { hidePopups(); };
  alertOkBtn.removeEventListener('click', handler);
  alertOkBtn.addEventListener('click', handler, { once: true });
}

async function confirm_popup(message) {
  return new Promise((resolve) => {
    hidePopups();
    const popupElement = document.getElementById('confirmPopup');
    const msgElement = document.getElementById('confirmMessageElement');
    const okButton = document.getElementById('confirmOkBtn');
    const cancelButton = document.getElementById('confirmCancelBtn');
    if (!popupElement || !msgElement || !okButton || !cancelButton) {
      resolve(false);
      return;
    }
    msgElement.textContent = message;
    popupElement.style.display = 'flex';
    okButton.focus();
    const okHandler = function () { cleanup(); resolve(true); };
    const cancelHandler = function () { cleanup(); resolve(false); };
    const cleanup = function () {
      okButton.removeEventListener('click', okHandler);
      cancelButton.removeEventListener('click', cancelHandler);
      hidePopups();
    };
    okButton.removeEventListener('click', okHandler);
    cancelButton.removeEventListener('click', cancelHandler);
    okButton.addEventListener('click', okHandler);
    cancelButton.addEventListener('click', cancelHandler);
  });
}

async function prompt_popup(message, defaultValue = '') {
  return new Promise((resolve) => {
    hidePopups();
    const popupElement = document.getElementById('promptPopup');
    const msgElement = document.getElementById('promptMessageElement');
    const inputElement = document.getElementById('promptInputElement');
    const okButton = document.getElementById('promptOkBtn');
    const cancelButton = document.getElementById('promptCancelBtn');
    if (!popupElement || !msgElement || !inputElement || !okButton || !cancelButton) {
      resolve(null);
      return;
    }
    msgElement.textContent = message;
    inputElement.value = defaultValue;
    popupElement.style.display = 'flex';
    inputElement.focus();
    const okHandler = function () { cleanup(); resolve(inputElement.value); };
    const cancelHandler = function () { cleanup(); resolve(null); };
    const enterKeyHandler = (event) => { if (event.key === 'Enter') okHandler(); };
    const cleanup = function () {
      okButton.removeEventListener('click', okHandler);
      cancelButton.removeEventListener('click', cancelHandler);
      inputElement.removeEventListener('keydown', enterKeyHandler);
      hidePopups();
    };
    okButton.removeEventListener('click', okHandler);
    cancelButton.removeEventListener('click', cancelHandler);
    inputElement.removeEventListener('keydown', enterKeyHandler);
    okButton.addEventListener('click', okHandler);
    cancelButton.addEventListener('click', cancelHandler);
    inputElement.addEventListener('keydown', enterKeyHandler);
  });
}

document.getElementById("logo_bt").addEventListener("click", function () {
  // 셸 안이면 맨 바깥 창을 옮긴다 (셸 안에 셸이 겹치지 않게)
  (window.top || window).location.href = '/';
});

// 프록시 아래에서는 /tools/socket.io 로 붙어야 한다.
// BASE 를 안 붙이면 허브 자신의 socket.io 에 연결돼 엉뚱한 서버와 이야기한다.
const socket = io(location.origin, { path: `${BASE}/socket.io` });

const onoffVal = document.getElementById('onoff_val');
const onoffCount = document.getElementById('onoff_count');
onoffVal.innerHTML = `<i class="fas fa-toggle-off fa-sm fa-fade" style="--fa-animation-duration: 2s; --fa-fade-opacity: 0.6">&nbsp;off</i>`;

let onoff_count = 0;
let onoff_intv = setInterval(() => {
  onoffCount.innerHTML = `<i style="opacity:0.6">${++onoff_count}</i>`;
}, 2000);

socket.on("onoff", function (data) {
  onoffVal.innerHTML = data?
    `<i class="fas fa-toggle-on">&nbsp;on</i>`
    : `<i class="fas fa-toggle-off fa-sm fa-fade" style="--fa-animation-duration: 2s; --fa-fade-opacity: 0.6">&nbsp;off</i>`

  if (data == true) {
    socket.emit("disp_motion");
    clearInterval(onoff_intv);
    onoffCount.innerHTML = "";
    for (let i = 0; i < 10; i++) {
      $("#m" + i + "_value").val(motor_default[i]);
      $("#m" + i + "_range").val(motor_default[i]);
    }
    socket.emit("set_motors", { pos_lst: motor_default });
  }
});

// ─────────────────────────────────────────────
// 음성 목록 (speech 탭 + simulator tts 카드 공용)
// ─────────────────────────────────────────────
const offlineVoices = [
  { value: "m1", key: "v_m1" }, { value: "m2", key: "v_m2" },
  { value: "m3", key: "v_m3" }, { value: "m4", key: "v_m4" },
  { value: "m5", key: "v_m5" }, { value: "f1", key: "v_f1" },
  { value: "f2", key: "v_f2" }, { value: "f3", key: "v_f3" },
  { value: "f4", key: "v_f4" }, { value: "f5", key: "v_f5" },
];
const onlineVoices = [
  { value: "main",   key: "main"   }, { value: "man1",  key: "man"   },
  { value: "woman1", key: "woman"  }, { value: "boy",   key: "boy"   },
  { value: "girl",   key: "girl"   }, { value: "gtts",  key: "gtts"  },
  { value: "e_gtts", key: "e_gtts" },
];
const isOfflineVoice = (v) => offlineVoices.some(o => o.value === v);

const getVisions = (socket) => {
  $("#v_img").on("click", (evt) => {
    let rect = evt.target.getBoundingClientRect();
    x = Math.floor(evt.clientX - rect.left);
    y = Math.floor(evt.clientY - rect.top);
    w = Math.floor(rect.right - rect.left);
    h = Math.floor(rect.bottom - rect.top);
    cx = Math.floor((640 * x) / w);
    cy = Math.floor((480 * y) / h);
    x1 = cx<100?0:cx-100;
    y1 = cy<100?0:cy-100;
    x2 = x1+200>640?640:x1+200;
    y2 = y1+200>480?480:y1+200;
    socket.emit("object_tracker_init", {x1:x1,y1:y1, x2:x2, y2:y2});
  });

  let img_x = 0;
  let img_y = 0;
  $("#v_img").on("mousemove", (evt) => {
    let rect = evt.target.getBoundingClientRect();
    x = Math.floor(evt.clientX - rect.left);
    y = Math.floor(evt.clientY - rect.top);
    w = Math.floor(rect.right - rect.left);
    h = Math.floor(rect.bottom - rect.top);
    cx = Math.floor((640 * x) / w);
    cy = Math.floor((480 * y) / h);
    cx = cx<0?0:cx; cx = cx>640?640:cx;
    cy = cy<0?0:cy; cy = cy>480?480:cy;
    if (Math.abs(img_x - cx) > 10 || Math.abs(img_y - cy) > 10 ) {
      socket.emit('update_img_pointer', {x:cx, y:cy});
      img_x = cx; img_y = cy;
    }
  });

  socket.on("disp_vision", function (data) {
    $("#v_func_type").val(data);
  });

  socket.on("stream", function (data) {
    $("#v_img").prop("src", `data:image/jpeg;charset=utf-8;base64,${data["img"]}`);
    $("#v_result").text(data["data"]);
  });

  $("#v_func_type").change(function () {
    socket.emit("detect", $(this).val());
  });

  socket.emit("marker_length", Number($('#marker_length').val()));
  $('#marker_length').on("focusout keydown", function (evt) {
    if (evt.type == "focusout" || (evt.type == "keydown" && evt.keyCode == 13)) {
      socket.emit("marker_length", Number($('#marker_length').val()));
    }
  });
  $('#marker_length').on("click", function (evt) {
    socket.emit("marker_length", Number($('#marker_length').val()));
  });

  $("#v_capture").on("click", function () {
    let capture_a = document.createElement("a");
    capture_a.setAttribute("href", "/download_img");
    capture_a.setAttribute("download", "");
    capture_a.click();
  });

  $("#v_upload_tm").on("change", (e) => {
    let formData = new FormData();
    formData.append("data", $("#v_upload_tm")[0].files[0]);
    $("#v_upload_tm").val("");
    $.ajax({
      url: `/upload_tm`, type: "post", data: formData,
      contentType: false, processData: false,
    }).always(async (xhr, status) => {
      if (status == "success") {
        await alert_popup(translations["file_ok"][lang]);
      } else {
        await alert_popup(`${translations["file_error"][lang]}\n >> ${xhr.responseJSON["result"]}`);
        $("#v_upload_tm").val("");
      }
    });
  });

  $("#v_tilt_range").on("click touchend", function (evt) {
    $("#m5_range").val(Number($("#v_tilt_range").val()));
    $("#m5_value").val(Number($("#v_tilt_range").val()));
    $("#v_location").text(`${$("#m4_range").val()}, ${$("#m5_range").val()}`);
    socket.emit("set_motor", { idx: 5, pos: Number($("#v_tilt_range").val()) });
  });
  $("#v_pan_range").on("click touchend", function (evt) {
    $("#m4_range").val(Number($("#v_pan_range").val()));
    $("#m4_value").val(Number($("#v_pan_range").val()));
    $("#v_location").text(`${$("#m4_range").val()}, ${$("#m5_range").val()}`);
    socket.emit("set_motor", { idx: 4, pos: Number($("#v_pan_range").val()) });
  });
  $("#v_tilt_reset").on("click", function (evt) {
    $("#v_tilt_range").val(0);
    $("#m5_range").val(0); $("#m5_value").val(0);
    $("#v_location").text(`${$("#m4_range").val()}, 0`);
    socket.emit("set_motor", { idx: 5, pos: 0 });
  });
  $("#v_pan_reset").on("click", () => {
    $("#v_pan_range").val(0);
    $("#m4_range").val(0); $("#m4_value").val(0);
    $("#v_location").text(`0, ${$("#m5_range").val()}`);
    socket.emit("set_motor", { idx: 4, pos: 0 });
  });
};

let checkOled = (x, y, size) => {
  if (isNaN(x) || x < 0 || x > 128) return false;
  if (isNaN(y) || y < 0 || y > 64) return false;
  if (isNaN(size) || size < 1 || size > 50) return false;
  return true;
};

const getDevices = (socket) => {
  socket.on("update_neopixel", function (data) {
    for (let i = 0; i < 6; i++) $("#d_n" + i + "_val").val(data[i]);
  });

  socket.on("update_device", function (data) {
    $("#d_pir_val").text(data[0].toLowerCase());
    $("#d_touch_val").text(data[1].toLowerCase());
  });

  for (let i = 0; i < 6; i++) {
    let tneopixel = "#d_n" + i + "_val";
    $(tneopixel).on("focusout keydown", function (evt) {
      if (evt.type == "focusout" || (evt.type == "keydown" && evt.keyCode == 13)) {
        let val = Number($(this).val());
        let min = Number($(this).attr("min"));
        let max = Number($(this).attr("max"));
        if (isNaN(val) || val < min || val > max) {
          alert(translations["range_warn"][lang](min, max));
          $(this).val(0);
        } else {
          socket.emit("set_neopixel", { idx: i, value: val });
        }
      }
    });
    $(tneopixel).on("click", function (evt) {
      socket.emit("set_neopixel", { idx: i, value: $(this).val() });
    });
  }

  $("#eye_reset_bt").on("click", function (evt) {
    for (let i = 0; i < 6; i++) $("#d_n" + i + "_val").val(0);
    socket.emit("eye_update", "0,0,0,0,0,0");
  });

  $("#d_otext_val").on("keydown", function (evt) {
    if (evt.type == "keydown" && evt.keyCode == 13) {
      let text = $("#d_otext_val").val().trim();
      let x = Number($("#d_ox_val").val());
      let y = Number($("#d_oy_val").val());
      let size = Number($("#d_osize_val").val());
      if (checkOled(x, y, size)) socket.emit("set_oled", { x, y, size, text });
      else alert(translations["oled_input_error"][lang]);
    }
  });

  ["#d_ox_val", "#d_oy_val", "#d_osize_val"].forEach((sel) => {
    $(sel).on("click keydown", function (evt) {
      if (evt.type == "click" || (evt.type == "keydown" && evt.keyCode == 13)) {
        let text = $("#d_otext_val").val().trim();
        if (text == "") return;
        let x = Number($("#d_ox_val").val());
        let y = Number($("#d_oy_val").val());
        let size = Number($("#d_osize_val").val());
        if (checkOled(x, y, size)) socket.emit("set_oled", { x, y, size, text });
        else alert(translations["oled_input_error"][lang]);
      }
    });
  });

  $("#oled_bt").on("click", function (evt) {
    let text = $("#d_otext_val").val().trim();
    if (text == "") return;
    let x = Number($("#d_ox_val").val());
    let y = Number($("#d_oy_val").val());
    let size = Number($("#d_osize_val").val());
    if (checkOled(x, y, size)) socket.emit("set_oled", { x, y, size, text });
    else alert(translations["oled_input_error"][lang]);
  });

  $("#upload_oled").on("change", (e) => {
    let formData = new FormData();
    formData.append("data", $("#upload_oled")[0].files[0]);
    $("#upload_oled").val("");
    $.ajax({
      url: `/upload_oled`, type: "post", data: formData,
      contentType: false, processData: false,
    }).always((xhr, status) => {
      if (status == "success") alert(translations["file_ok"][lang]);
      else {
        alert(`${translations["file_error"][lang]}\n >> ${xhr.responseJSON["result"]}`);
        $("#upload_oled").val("");
      }
    });
  });

  $("#clear_oled_bt").on("click", function () {
    socket.emit("clear_oled");
  });

  socket.on("oled_path", (data) => {
    $("#oledfiles").empty();
    $("#oledfiles").append(`<option value='-'>${translations["select"][lang]}</option>`);
    for (let i = 0; i < data.length; i++) {
      let filename = data[i];
      let extension = filename.split(".")[1].toLowerCase();
      if (["png", "jpg"].includes(extension))
        $("#oledfiles").append(`<option value="${filename}">${filename.split(".jpg")[0]}</option>`);
    }
  });

  $("#oledpath").on("change", () => {
    let p = $("#oledpath").val();
    if (p != "-") socket.emit("oled_path", p);
  });

  $("#oledfiles").on("change", () => {
    let filename = $("#oledfiles").val();
    if (filename != "-") socket.emit("set_oled_image", `${$("#oledpath").val()}/${filename}`);
  });

  socket.on("mic", function (d) { $("#mic_status").text(d); });

  $("#mic_bt").on("click", function () {
    let tmictime = "#mic_time_val";
    let val = Number($(tmictime).val());
    let min = Number($(tmictime).attr("min"));
    let max = Number($(tmictime).attr("max"));
    if (isNaN(val) || val < min || val > max) {
      alert(translations["audio_input_error"][lang]);
      return;
    }
    $("#mic_status").html("<i class='fa-solid fa-fade'>녹음 중</i>");
    socket.emit("mic", { time: val, volume: Number($("#volume").val()) });
  });

  $("#mic_replay_bt").on("click", function () {
    socket.emit("mic_replay", { volume: Number($("#volume").val()) });
  });

  socket.on("audio_path", (data) => {
    $("#audiofiles").empty();
    $("#audiofiles").append(`<option value='-'>${translations["select"][lang]}</option>`);
    for (let i = 0; i < data.length; i++) {
      let filename = data[i];
      let extension = filename.split(".")[1];
      if (["mp3", "wav"].includes(extension))
        $("#audiofiles").append(`<option value="${filename}">${filename.split(".")[0]}</option>`);
    }
  });

  $("#audiopath").on("change", () => {
    let p = $("#audiopath").val();
    if (p != "-") socket.emit("audio_path", p);
  });

  $("#play_audio_bt").on("click", function () {
    let filename = $("#audiofiles").val();
    if (filename == "-") { alert(translations["music_name_empty"][lang]); return; }
    socket.emit("play_audio", { filename: `${$("#audiopath").val()}/${filename}`, volume: Number($("#volume").val()) });
  });

  $("#stop_audio_bt").on("click", function () {
    socket.emit("stop_audio");
  });

  $("#upload_audio").on("change", (e) => {
    let formData = new FormData();
    formData.append("data", $("#upload_audio")[0].files[0]);
    $("#upload_audio").val("");
    $.ajax({
      url: `/upload_file/myaudio`, type: "post", data: formData,
      contentType: false, processData: false,
    }).always((xhr, status) => {
      if (status == "success") alert(translations["file_ok"][lang]);
      else { alert(`${translations["file_error"][lang]}\n >> ${xhr.responseJSON["result"]}`); $("#upload_audio").val(""); }
    });
  });

  $("#upload_image").on("change", (e) => {
    let formData = new FormData();
    formData.append("data", $("#upload_image")[0].files[0]);
    $("#upload_image").val("");
    $.ajax({
      url: `/upload_file/myimage`, type: "post", data: formData,
      contentType: false, processData: false,
    }).always((xhr, status) => {
      if (status == "success") alert(translations["file_ok"][lang]);
      else { alert(`${translations["file_error"][lang]}\n >> ${xhr.responseJSON["result"]}`); $("#upload_image").val(""); }
    });
  });
};

const getMotions = (socket) => {
  for (let i = 0; i < 10; i++) {
    let tval = "#m" + i + "_value";
    let trange = "#m" + i + "_range";

    $(trange).on("input", function (evt) { $(tval).val($(trange).val()); });
    $(trange).on("click touchend", function (evt) {
      socket.emit("set_motor", { idx: i, pos: Number($(trange).val()) });
    });
    $(tval).on("focusout keydown", async function (evt) {
      if (evt.type == "focusout" || (evt.type == "keydown" && evt.keyCode == 13)) {
        let pos = Number($(this).val());
        let min = Number($(this).attr("min"));
        let max = Number($(this).attr("max"));
        if (isNaN(pos) || pos < min || pos > max) {
          $(this).val($(trange).val());
          await alert_popup(translations["range_warn"][lang](min, max));
        } else {
          $(trange).val(pos);
          socket.emit("set_motor", { idx: i, pos: pos });
        }
      }
    });
    $(tval).on("click", function (evt) {
      let pos = $(tval).val();
      $(trange).val(pos);
      socket.emit("set_motor", { idx: i, pos: Number(pos) });
    });
  }

  $("#m_time_val").on("focusout keydown", async function (evt) {
    if (evt.type == "focusout" || (evt.type == "keydown" && evt.keyCode == 13)) {
      let pos = Number($(this).val());
      let min = Number($(this).attr("min"));
      let max = Number($(this).attr("max"));
      if (isNaN(pos) || pos < min || pos > max) {
        $(this).val(0);
        await alert_popup(translations["range_warn"][lang](min, max));
      }
    }
  });

  $("#init_bt").on("click", function () {
    for (let i = 0; i < 10; i++) {
      $("#m" + i + "_value").val(motor_default[i]);
      $("#m" + i + "_range").val(motor_default[i]);
    }
    socket.emit("set_motors", { pos_lst: motor_default });
  });

  $("#add_frame_bt").on("click", function () {
    socket.emit("add_frame", $("#m_time_val").val() * 1000);
  });

  socket.on("disp_motion", function (datas) {
    if ("pos" in datas) {
      let data = datas["pos"];
      for (let i = 0; i < 10; i++) {
        $("#m" + i + "_value").val(data[i]);
        $("#m" + i + "_range").val(data[i]);
      }
    }
    if ("record" in datas) {
      let res = [];
      for (name in datas["record"]) res.push(name);
      $('#motor_record').text(res.join(', '));
    }
    if ("table" in datas) {
      let data = datas["table"];
      for (let i = 0; i < data.length; i++) {
        if (i != 0)
          for (let j = 0; j < 10; j++)
            data[i].d[j] = data[i].d[j] == 999 ? data[i - 1].d[j] : data[i].d[j];
      }
      $("#motor_table > tbody").empty();
      for (let i = 0; i < data.length; i++) {
        $("#motor_table > tbody").append(
          $("<tr>")
            .append(
              $("<td>").append(data[i].seq / 1000 + ` <span data-key='second'>${translations["second"][lang]}</>`),
              $("<td>").append(data[i].d[0]), $("<td>").append(data[i].d[1]),
              $("<td>").append(data[i].d[2]), $("<td>").append(data[i].d[3]),
              $("<td>").append(data[i].d[4]), $("<td>").append(data[i].d[5]),
              $("<td>").append(data[i].d[6]), $("<td>").append(data[i].d[7]),
              $("<td>").append(data[i].d[8]), $("<td>").append(data[i].d[9])
            )
            .hover(
              function () { $(this).animate({ opacity: "0.5" }, 100); },
              function () { $(this).animate({ opacity: "1" }, 100); }
            )
            .click(function () {
              let pos_lst = [];
              let lst = $(this).children();
              lst.each((idx) => {
                if (idx == 0) {
                  $("#m_time_val").val(Number(lst.eq(idx).text().split(" 초")[0]));
                  return;
                } else {
                  let val = Number(lst.eq(idx).text());
                  $("#m" + (idx - 1) + "_value").val(val);
                  $("#m" + (idx - 1) + "_range").val(val);
                  pos_lst[idx - 1] = val;
                }
              });
              socket.emit("set_motors", { pos_lst: pos_lst });
            })
            .dblclick(async function () {
              let t = $(this).text().split(" 초")[0];
              if (await confirm_popup(translations["confirm_motion_delete"][lang](t))) {
                socket.emit("delete_frame", Number(t) * 1000);
                $(this).remove();
              }
            })
        );
      }
    }
  });

  $("#export_motion_bt").on("click", function() {
    let motion_a = document.createElement("a");
    if($("#motion_name_val").val() == "") motion_a.setAttribute("href", `/export_motion/all`);
    else motion_a.setAttribute("href", `/export_motion/${$("#motion_name_val").val()}`);
    motion_a.setAttribute("download", "");
    motion_a.click();
  });

  $("#v_import_motion").on("change", (e) => {
    let formData = new FormData();
    formData.append("data", $("#v_import_motion")[0].files[0]);
    $("#v_import_motion").val("");
    $.ajax({
      url: `/import_motion`, type: "post", data: formData,
      contentType: false, processData: false,
    }).always(async (xhr, status) => {
      if (status == "success") await alert_popup(translations["file_ok"][lang]);
      else {
        await alert_popup(`${translations["file_error"][lang]}\n >> ${xhr.responseJSON["result"]}`);
        $("#v_import_motion").val("");
      }
    });
  });

  $("#init_frame_bt").on("click", async function () {
    if (await confirm_popup(translations["confirm_motion_delete_all"][lang])) {
      socket.emit("init_frame");
      $("#motor_table > tbody").empty();
    }
  });

  $("#play_frame_bt").on("click", async function () {
    if ($("#motor_table > tbody").text()) {
      socket.emit("play_frame", $("#play_cycle_val").val());
    } else {
      await alert_popup(translations["motion_empty"][lang]);
    }
  });

  $("#play_cycle_val").on("focusout keydown", async function (evt) {
    if (evt.type == "focusout" || (evt.type == "keydown" && evt.keyCode == 13)) {
      let val = Number($(this).val());
      let min = Number($(this).attr("min"));
      let max = Number($(this).attr("max"));
      if (!Number.isInteger(val) || val < min || val > max) {
        await alert_popup(translations["range_warn"][lang](min, max));
        $(this).val(1);
      }
    }
  });

  $("#stop_frame_bt").on("click", function () { socket.emit("stop_frame"); });

  $("#add_motion_bt").on("click", async function () {
    let motionName = $("#motion_name_val").val().trim();
    if (motionName == "") { await alert_popup(translations["motion_name_empty"][lang]); return; }
    if (await confirm_popup(translations["confirm_motion_register"][lang](motionName))) {
      socket.emit("add_motion", motionName);
      $("#motion_name_val").val("");
    }
  });

  $("#load_motion_bt").on("click", async function () {
    let motionName = $("#motion_name_val").val().trim();
    if (motionName == "") { await alert_popup(translations["motion_name_empty"][lang]); return; }
    if (await confirm_popup(translations["confirm_motion_load"][lang](motionName))) {
      socket.emit("load_motion", motionName);
      $("#motion_name_val").val("");
    }
  });

  const sample_motions = [
    'left', 'left_half', 'right', 'right_half', 'forward1', 'backward1', 'step1',
    'cheer1', 'cheer2', 'wave1', 'think1', 'wake_up3', 'yes_h', 'no_h', 'head_h',
    'spin_h', 'clapping1', 'handshaking', 'greeting', 'hand1', 'foot1',
    'speak1', 'speak2', 'welcome', 'dance1', 'dance2', 'dance3', 'dance4', 'dance5'
  ];

  $('#motion_samples').html(sample_motions.map((e) =>
    `<a id="motion_${e}_bt" style="color:#df7e3d;cursor:pointer">${e}</a>`
  ).join(', '));

  for (idx in sample_motions) {
    $(`#motion_${sample_motions[idx]}_bt`).on("click", function () {
      let i = sample_motions.indexOf($(this).text());
      socket.emit("load_motion", sample_motions[i]);
    });
  }

  $("#delete_motion_bt").on("click", async function () {
    let motionName = $("#motion_name_val").val().trim();
    if (motionName == "") { await alert_popup(translations["motion_name_empty"][lang]); return; }
    if (await confirm_popup(translations["confirm_motion_delete"][lang](motionName))) {
      socket.emit("delete_motion", motionName);
      $("#motion_name_val").val("");
    }
  });

  $("#reset_motion_bt").on("click", async function () {
    if (await confirm_popup(translations["confirm_motion_delete_all"][lang])) socket.emit("reset_motion");
  });
};

const getSpeech = (socket) => {
  // ── 음성 유형 라디오 + 필터 select ──────────────────
  const updateVoiceSelect = (mode, selectedVal) => {
    const list = mode === "offline" ? offlineVoices : onlineVoices;
    const sel = document.getElementById("s_voice_type_select");
    sel.innerHTML = list.map(v =>
      `<option value="${v.value}" ${selectedVal === v.value ? "selected" : ""}>${translations[v.key]?.[lang] || v.value}</option>`
    ).join('');
  };

  updateVoiceSelect("offline", null);

  document.querySelectorAll("input[name=s_voice_mode]").forEach(radio => {
    radio.addEventListener("change", (e) => updateVoiceSelect(e.target.value, null));
  });
  // ─────────────────────────────────────────────────────

  const max_tts_length = 100;

  const doTts = async () => {
    if ($("input[name=s_voice_en]:checked").val() == "off") {
      await alert_popup(translations["voice_enable"][lang]);
      return;
    }
    let string = $("#s_tts_val").val().trim();
    if (string == "") { await alert_popup(translations["text_empty"][lang]); return; }
    if (string.length > max_tts_length) { await alert_popup(translations["text_size_limit"][lang](max_tts_length)); return; }
    socket.emit("tts", {
      text: string,
      voice_type: document.getElementById("s_voice_type_select").value,
      volume: Number($("#volume").val()),
    });
  };

  $("#s_tts_bt").on("click", doTts);
  $("#s_tts_val").on("keypress", async function (evt) {
    if (evt.keyCode == 13) await doTts();
  });

  $("#s_upload_csv").on("change", (e) => {
    let formData = new FormData();
    formData.append("data", $("#s_upload_csv")[0].files[0]);
    $("#s_upload_csv").val("");
    $.ajax({
      url: `/upload_csv`, type: "post", data: formData,
      contentType: false, processData: false,
    }).always(async (xhr, status) => {
      if (status == "success") await alert_popup(translations["file_ok"][lang]);
      else {
        await alert_popup(`${translations["file_error"][lang]}\n >> ${xhr.responseJSON["result"]}`);
        $("#s_upload_csv").val("");
      }
    });
  });

  $("#s_reset_csv_bt").on("click", async function () {
    socket.emit("reset_csv", {lang: lang});
    $("#s_upload_csv").val("");
    await alert_popup(translations["reset_ok"][lang]);
  });

  const doQuestion = () => {
    let q = $("#s_question_val").val().trim();
    if (q == "") return;
    $("#s_question_val").prop("disabled", true);
    setTimeout(() => $("#s_question_val").val("."), 200);
    setTimeout(() => $("#s_question_val").val(".."), 400);
    setTimeout(() => $("#s_question_val").val("..."), 600);
    setTimeout(() => {
      socket.emit("question", {
        question: q.toLowerCase(),
        n: lang == "ko" ? 2 : 4,
        voice_en: $("input[name=s_voice_en]:checked").val(),
        voice_type: document.getElementById("s_voice_type_select").value,
        volume: Number($("#volume").val()),
      });
      $("#s_question_val").prop("disabled", false);
      $("#s_question_val").val(q);
    }, 800);
  };

  $("#s_question_val").on("keypress", async function (evt) {
    if (evt.keyCode == 13) {
      let q = $(this).val().trim();
      if (q == "") { await alert_popup(translations["text_empty"][lang]); return; }
      doQuestion();
    }
  });

  $("#s_chat_bt").on("click", async function () {
    let q = $("#s_question_val").val().trim();
    if (q == "") { await alert_popup(translations["text_empty"][lang]); return; }
    doQuestion();
  });

  const doTranslate = async () => {
    let txt = $("#s_translate_val").val().trim();
    if (txt == "") { await alert_popup(translations["text_empty"][lang]); return; }
    socket.emit("translate", {
      langtype: $("select[name=s_lang_type]").val(),
      voice_en: $("input[name=s_voice_en]:checked").val(),
      volume: Number($("#volume").val()),
      text: txt
    });
  };

  $("#s_translate_bt").on("click", doTranslate);
  $("#s_translate_val").on("keypress", async function (evt) {
    if (evt.keyCode == 13) await doTranslate();
  });

  socket.on("disp_translate", (data) => { $("#s_translate_result_val").val(data); });

  socket.on("mic", function (d) { $("#mic_status").text(d); });

  $("#mic_bt").on("click", async function () {
    let tmictime = "#mic_time_val";
    let val = Number($(tmictime).val());
    let min = Number($(tmictime).attr("min"));
    let max = Number($(tmictime).attr("max"));
    if (isNaN(val) || val < min || val > max) {
      await alert_popup(translations["audio_input_error"][lang]);
      return;
    }
    $("#mic_status").html("<i class='fa-solid fa-fade'>녹음 중</i>");
    socket.emit("mic", { time: val, volume: Number($("#volume").val()) });
  });

  $("#mic_replay_bt").on("click", function () {
    socket.emit("mic_replay", { volume: Number($("#volume").val()) });
  });

  socket.on("disp_speech", function (data) {
    if ("answer" in data) $("#s_answer_val").val(data["answer"]);
    if ("chat_list" in data) {
      $("#s_record_tb > tbody").empty();
      rec = data["chat_list"];
      for (idx in rec) {
        if (rec[idx].length == 0) continue;
        $("#s_record_tb").append(
          $("<tr>").append(
            $("<td>").append(rec[idx][0]),
            $("<td>").append(rec[idx][1]),
            $("<td>").append(rec[idx][2])
          )
        );
      }
    }
  });
};

const getSimulations = (socket) => {
  let selectFile = null;
  let selectFileContents = [];
  $("#sequence_title").hide();
  $("#config_contents").parent().hide();
  $("#timeline_play_bt").hide();
  $("#timeline_stop_bt").hide();
  $("#timeline_card").parent().css("opacity", 0);
  $("#timeline_bottom_wrap").hide();
  $("section.timeline").css("align-self", "baseline");
  $("#sequence_contents").show("slide");

  const playing = {
    value: false,
    get status() { return this.value; },
    set status(v) {
      this.value = v;
      if (v) $("#timeline_body").addClass("playing");
      else $("#timeline_body").removeClass("playing");
    },
  };

  const simSocket = (name, params, cb) => {
    const tempSocket = {
      sim_play_item: (data) => { socket.emit("sim_play_item", data); },
      sim_play_items: (data) => {
        playing.status = true;
        const rows = $("#timeline_body .timeline.row");
        rows.removeClass("selected");
        const times = data.reduce((acc, { time: t }, i) => {
          const time = i === 0 ? t * 1000 : t * 1000 - data[i - 1].time * 1000;
          acc.push(() => new Promise((resolve, reject) => {
            if (!playing.status) {
              rows.attr("tabindex", 0).blur();
              rows.removeClass("selected");
              reject(true);
            } else {
              setTimeout(() => {
                rows.attr("tabindex", 0).blur();
                rows.removeClass("selected");
                const row = rows.eq(i);
                row.addClass("selected");
                row.attr("tabindex", -1).focus();
                resolve(true);
              }, time);
            }
          }));
          return acc;
        }, []);
        const execPlays = (arr) => arr.reduce((a, c) => a.then(c).catch(() => {}), Promise.resolve());
        execPlays(times).then(() => {
          playing.status = false;
          const timeVal = $("#config_time_input").val().replace(".", "_");
          handleTimelineItemClick($(`div[name=timeline_row_${timeVal}]`));
        });
        socket.emit("sim_play_items", data);
      },
      sim_stop_item: (data) => { socket.emit("sim_stop_item", data); },
      sim_stop_items: () => { playing.status = false; socket.emit("sim_stop_items"); },
      sim_update_audio: (type, cb) => { socket.on("sim_update_audio", cb); socket.emit("sim_update_audio", type); },
      sim_update_oled: (type, cb) => { socket.on("sim_update_oled", cb); socket.emit("sim_update_oled", type); },
      sim_update_motion: (type, cb) => { socket.on("sim_update_motion", cb); socket.emit("sim_update_motion", type); },
      sim_add_items: ({ name, data }) => { socket.emit("sim_add_items", { name, data }); },
      sim_remove_items: (name) => {
        if (name) socket.emit("sim_remove_items", name);
        else socket.emit("sim_remove_items");
      },
      sim_load_item: (name, cb) => { socket.on("sim_load_item", (data) => cb({ name, data })); socket.emit("sim_load_item", name); },
      sim_load_items: (cb) => { socket.on("sim_load_items", (data) => cb(data)); socket.emit("sim_load_items"); },
    };
    return cb ? tempSocket[name](params, cb) : tempSocket[name](params);
  };

  socket.on("sim_result", (res) => {
    if (typeof res === "object") {
      const [[key, v]] = Object.entries(res);
      const playBtn = $(`#${key}_play_bt`);
      if (v === "stop" && playBtn.children("i").hasClass("fa-stop")) {
        playBtn.children("i").removeClass("fa-stop").addClass("fa-play");
      }
    }
  });

  const getSimFile = () => JSON.parse(localStorage.getItem("sim_file"));
  const setSimFile = ({ name, data, index }) => {
    let obj = { name, data, index };
    if (!name && !data) { const oldData = getSimFile(); obj = { ...oldData, index }; }
    localStorage.setItem("sim_file", JSON.stringify(obj));
  };

  const setSimItem = ({ time, eye, oled, motion, audio, tts }) => {
    const lastData = {};
    if (eye && eye.content && eye.content.join("").length) lastData.eye = eye;
    if (oled && oled.content) lastData.oled = oled;
    if (motion && motion.content) lastData.motion = motion;
    if (audio && audio.content) lastData.audio = audio;
    if (tts && tts.content) lastData.tts = tts;
    lastData.time = time;
    const oldData = getSimFile();
    if (oldData && "data" in oldData) {
      const index = oldData.data.findIndex((item) => item.time === time);
      localStorage.setItem("sim_file", JSON.stringify({ ...oldData, index, lastData }));
    }
  };

  const onFileList = () => {
    $("#sequence_list").empty();
    simSocket("sim_load_items", (fileList) => {
      if (fileList.length) {
        $("#no_sequence_warn").addClass("hide");
        $("#sequence_list").removeClass("hide");
        $("#sequence_list").children().remove();
        const listItem = fileList.map((name, i) => {
          let btnGroup = $("<div></div>").addClass("horizontal").css({ gap: "0.5em", "flex-grow": 0 });
          let openBtn = $(`<button name="open_file_${i}"><span data-key="load">${lang=="ko"?"불러오기":"Load"}</span></button>`);
          let removeBtn = $(`<button name="remove_file_${i}"><span data-key="remove">${lang=="ko"?"지우기":"Remove"}</span></button>`).addClass("btn-red");
          openBtn.on("click", () => openSequence(name));
          removeBtn.off("click").on("click", (e) => {
            const index = e.currentTarget.name.split("_")[2];
            if (fileList[index] === selectFile) {
              if (confirm(translations["confirm_current_sequence_delete"][lang])) {
                simSocket("sim_remove_items", fileList[index]);
                openSequence(null);
              }
            } else if (confirm(translations["confirm_sequence_delete"][lang](fileList[index]))) {
              simSocket("sim_remove_items", fileList[index]);
              openSequence(null);
            }
            onFileList();
          });
          btnGroup.append(openBtn, removeBtn);
          let li = $(`<li name="file_${i}"></li>`).addClass("horizontal space-between");
          li.append(`<p>${name}</p>`, btnGroup);
          return li;
        });
        $("#sequence_list").append(...listItem);
      } else {
        $("#sequence_list").addClass("hide");
        $("#no_sequence_warn").removeClass("hide");
      }
    });
  };

  const foldSimulatorFile = (v) => {
    if (v) {
      $("#sequence_title_fold_bt").hide();
      $("#sequence_title_unfold_bt").show();
      $("#sequence_contents").hide();
      $("#config_contents").parent().show();
      $("#timeline_play_bt").show();
      $("#timeline_stop_bt").show();
      $("#timeline_card").parent().css("opacity", 1);
      $("#timeline_bottom_wrap").show();
      $("section.timeline").css("align-self", "unset");
      $("#sequence_title").show("fade");
    } else {
      onFileList();
      if (!selectFile) $("#sequence_title").hide();
      $("#config_contents").parent().hide();
      $("#timeline_play_bt").hide();
      $("#timeline_stop_bt").hide();
      $("#timeline_card").parent().css("opacity", 0);
      $("#timeline_bottom_wrap").hide();
      $("section.timeline").css("align-self", "baseline");
      $("#sequence_contents").show("shake");
      $("#sequence_title_fold_bt").show();
      $("#sequence_title_unfold_bt").hide();
    }
  };

  const openSequence = (v) => {
    if (v) $("#sequence_warn").hide(); else $("#sequence_warn").show();
    $("h3[name=sequence_title]").text(v);
    $("#sequence_name_val").val("");
    if (v) {
      simSocket("sim_load_item", v, (args) => {
        const { name, data } = args;
        selectFile = name;
        selectFileContents = data;
        setSimFile({ name, data, index: data && data.length ? data.length - 1 : 0 });
        foldSimulatorFile(name);
        setConfigSection(selectFileContents && selectFileContents.length ? selectFileContents[0] : null);
        setTimelineSection(selectFileContents);
      });
    } else {
      selectFile = "";
      selectFileContents = null;
      setSimFile({ name: "", data: [], index: -1 });
      foldSimulatorFile(false);
    }
  };

  $("#sequence_name_val").off("keyup").on("keyup", (e) => {
    $(e.target).val(e.target.value.replace(/[^\da-zA-Z]/g, ""));
  });

  $("#add_sequence_bt").off("click").on("click", function () {
    const title = $("#sequence_name_val").val();
    const fileList = Array.from($("#sequence_list li p")).map((el) => $(el).text());
    if (title) {
      if (fileList.indexOf(title) < 0) {
        simSocket("sim_add_items", { name: title, data: [] });
        onFileList();
        openSequence(title);
      } else { alert(translations["sequence_exist"][lang]); }
    } else { alert(translations["title_empty"][lang]); }
  });

  $("#remove_all_sequence_bt").off("click").on("click", function (e) {
    if ($("#sequence_list").children().length && confirm(translations["confirm_sequence_delete_all"][lang])) {
      simSocket("sim_remove_items");
      openSequence(null);
      onFileList();
    }
  });

  $("#sequence_title_unfold_bt").off("click").on("click", function () { foldSimulatorFile(false); });
  $("#sequence_title_fold_bt").off("click").on("click", function (e) { foldSimulatorFile(true); });
  $("#sequence_save_bt").off("click").on("click", () => {
    simSocket("sim_add_items", { name: selectFile, data: selectFileContents });
  });

  const handleTimelineItemClick = (row, bCheck) => {
    if (playing.status) return;
    const time = Number(row.text());
    const checkbox = row.find("div.cell input[type=checkbox]");
    if (bCheck) {
      checkbox.prop("checked", checkbox.prop("checked"));
    } else {
      row.siblings().removeClass("selected").attr("tabindex", 0).blur();
      row.addClass("selected").attr("tabindex", -1).focus();
      const index = selectFileContents.findIndex((item) => item.time === time);
      setSimFile({ index });
      setConfigSection(selectFileContents[index]);
    }
    const checkedRows = $("#timeline_body .timeline.row:not(.hide) input[type=checkbox]:checked");
    $("#timeline_all_check").prop("checked", checkedRows.length === selectFileContents.length);
  };

  const addTimelineItem = (item) => {
    if (!item) return;
    const timelineBody = $("#timeline_body");
    const itemName = `timeline_row_${item.time.toString().replace(".", "_")}`;
    if (!timelineBody.has(`div[name=${itemName}]`).length) {
      timelineBody.append($(`<div name="${itemName}" class="timeline row hide"></div>`));
    }
    const newList = Array.from(timelineBody.children()).sort((a, b) => {
      const [as, ams] = $(a).attr("name").replace("timeline_row_", "").split("_");
      const [bs, bms] = $(b).attr("name").replace("timeline_row_", "").split("_");
      const at = ams ? Number(`${as}.${ams}`) : Number(as);
      const bt = bms ? Number(`${bs}.${bms}`) : Number(bs);
      return at - bt;
    });
    timelineBody.children().remove();
    newList.forEach((r) => {
      $(r).off("click").on("click", (e) => {
        if (playing.status) { e.preventDefault(); return; }
        handleTimelineItemClick($(e.currentTarget), $(e.target).prop("type") === "checkbox");
      });
      timelineBody.append(r);
    });
    timelineBody.children().removeClass("hide");
    selectFileContents = selectFileContents.filter(({ time }) => time !== item.time);
    const tr = timelineBody.children(`div[name=${itemName}]`);
    tr.children().remove();
    const contents = {};
    const items = Object.entries({ eye: null, motion: null, audio: null, oled: null, tts: null, ...item });
    const fItems = items.reduce((acc, [k, v]) => {
      if (k === "time") { contents[k] = v; return { ...acc, [k]: v }; }
      else if (
        (k === "eye" && v && v.content && v.content.reduce((a, c) => (c || c === 0 ? a + Number(c) : c), 0)) ||
        (k === "motion" && v && v.content) || (k === "audio" && v && v.content) ||
        (k === "oled" && v && v.content) || (k === "tts" && v && v.content)
      ) { contents[k] = v; return { ...acc, [k]: true }; }
      return { ...acc, [k]: false };
    }, {});
    const cells = new Array(Object.keys(fItems).length);
    cells[0] = $(`<div class="timeline cell">${fItems.time}</div>`);
    cells[1] = fItems.eye   ? $(`<div class="timeline cell use"></div>`) : $(`<div class="timeline cell"></div>`);
    cells[2] = fItems.oled  ? $(`<div class="timeline cell use"></div>`) : $(`<div class="timeline cell"></div>`);
    cells[3] = fItems.motion? $(`<div class="timeline cell use"></div>`) : $(`<div class="timeline cell"></div>`);
    cells[4] = fItems.audio ? $(`<div class="timeline cell use"></div>`) : $(`<div class="timeline cell"></div>`);
    cells[5] = fItems.tts   ? $(`<div class="timeline cell use"></div>`) : $(`<div class="timeline cell"></div>`);
    const checkbox = $(`<input type="checkbox" /></div>`);
    checkbox.off("change").on("change", (e) => {
      if (playing.status) { e.preventDefault(); return; }
      const checkedRows = $("#timeline_body .timeline.row:not(.hide) input[type=checkbox]:checked");
      if (checkedRows.length === selectFileContents.length) $("#timeline_all_check").prop("checked", true);
    });
    tr.append($(`<div class="timeline cell">`).append(checkbox));
    tr.append(...cells);
    selectFileContents.push(contents);
    selectFileContents.sort((a, b) => a.time - b.time);
  };

  const setTimelineSection = (list = [], index = 0) => {
    const playBtn = $("#timeline_play_bt");
    const stopBtn = $("#timeline_stop_bt");
    stopBtn.off("click").on("click", () => simSocket("sim_stop_items"));
    playBtn.off("click").on("click", () => simSocket("sim_play_items", selectFileContents));
    const allCheckbox = $("#timeline_all_check");
    allCheckbox.off("click").on("click", (e) => { if (playing.status) { e.preventDefault(); return; } });
    allCheckbox.off("change").on("change", (e) => {
      if (playing.status) { e.preventDefault(); return; }
      $("#timeline_body input[type=checkbox]").prop("checked", $(e.target).is(":checked"));
    });
    const delBtn = $("#timeline_del_bt");
    delBtn.off("click").on("click", () => {
      const rows = $("#timeline_body input[type=checkbox]:checked").parents(".timeline.row");
      if (!rows.length) { alert(translations["remove_timeline_empty"][lang]); return; }
      if (confirm(translations["confirm_sequence_timeline"][lang])) {
        if (allCheckbox.is(":checked")) {
          setTimelineSection([]);
          allCheckbox.prop("checked", false);
          selectFileContents = [];
        } else {
          Array.from(rows).map((item) => {
            selectFileContents = selectFileContents.filter((content) => content.time !== Number($(item).text()));
            $(item).remove(".row");
            $(item).children().remove();
          });
        }
        setSimFile({ name: selectFile, data: selectFileContents, index: selectFileContents.length - 1 });
      }
    });
    $("#timeline_body").children().remove();
    if (list.length) {
      list.forEach(addTimelineItem);
      if (index > -1) {
        const itemName = `timeline_row_${list[index].time.toString().replace(".", "_")}`;
        handleTimelineItemClick($(`div[name=${itemName}]`));
      }
    } else {
      selectFileContents = [];
      setConfigSection();
    }
  };

  const setConfigSection = (obj) => {
    const volume = Number($("#volume").val());
    const initialData = {
      eye: { type: "default", content: [] },
      motion: { type: "default", content: null, cycle: 1 },
      audio: { type: "/home/pi/openpibo-files/audio/music/", content: "", volume },
      oled: { type: "text", content: null, x: 0, y: 0, size: 10 },
      tts: { type: "m1", content: "", volume },
    };

    const configData = {
      data: { ...initialData, time: 0 },
      get value() { return this.data; },
      set value(v) { this.data = { ...this.data, ...v }; setSimItem(this.data); },
      set val(param) {
        const { key, value: v, bInit } = param;
        const playBtn = $(`#${key}_play_bt`);
        if (playBtn.children("i").hasClass("fa-stop")) {
          playBtn.children("i").removeClass("fa-stop").addClass("fa-play");
          simSocket("sim_stop_item", key);
        }
        if (bInit) this.data[key] = { ...initialData[key], ...v };
        else this.data[key] = { ...this.data[key], ...v };
        setSimItem(this.data);
      },
    };

    const radioButtonClickHandler = (e) => {
      const target = $(e.target);
      const [key] = target.parents("div.config.card").attr("id").split("_");
      Array.from(target.siblings("input[type=radio]")).map((el) => $(el).prop("checked", false));
      target.prop("checked", true);
      const keyData = configData.value[key];
      if (!keyData || (keyData && "type" in keyData && keyData.type !== target.val())) {
        simSocket("sim_stop_item", key);
        if (key === "eye") {
          if (target.val() === "custom" && keyData.content.join("").length) {
            configData.val = { key: "eye", value: { type: target.val(), content: keyData.content }, bInit: true };
          } else {
            configData.val = { key: "eye", value: { type: target.val() }, bInit: true };
          }
        } else if (key === "motion") {
          configData.val = { key: "motion", value: { type: target.val() }, bInit: true };
        } else if (key === "oled") {
          configData.val = { key: "oled", value: { type: target.val() }, bInit: true };
        }
      }
    };

    const setCardBtnEvent = (key) => {
      const playBtn = $(`#${key}_play_bt`);
      const initBtn = $(`#${key}_init_bt`);
      playBtn.off("click").on("click", () => {
        const icon = playBtn.children("i");
        if (icon.hasClass("fa-play")) {
          const { content } = configData.data[key];
          if ((key === "eye" && content.join("").length) || content) {
            icon.removeClass("fa-play").addClass("fa-stop");
            if (key === "audio" || key === "tts") {
              simSocket("sim_play_item", { key, ...configData.data[key], volume: Number($("#volume").val()) });
            } else {
              simSocket("sim_play_item", { key, ...configData.data[key] });
            }
          }
        } else {
          icon.removeClass("fa-stop").addClass("fa-play");
          simSocket("sim_stop_item", key);
        }
      });
      initBtn.off("click").on("click", () => {
        simSocket("sim_stop_item", key);
        switch (key) {
          case "eye":    return setEyeColorCard(initialData[key]);
          case "motion": return setMotionCard(initialData[key]);
          case "audio":  return setAudioCard(initialData[key]);
          case "oled":   return setOledCard(initialData[key]);
          case "tts":    return setTtsCard(initialData[key]);
        }
      });
    };

    /* 눈 색상 카드 */
    const setEyeColorCard = (data) => {
      configData.val = { key: "eye", value: data, bInit: true };
      const eyeColorList = [
        { name: "255_0_0", value: [239, 51, 64] }, { name: "242_113_28", value: [242, 113, 28] },
        { name: "255_222_34", value: [255, 222, 34] }, { name: "0_255_0", value: [33, 186, 69] },
        { name: "3_191_215", value: [3, 191, 215] }, { name: "163_51_200", value: [163, 51, 200] },
        { name: "255_142_223", value: [255, 142, 223] }, { name: "255_255_255", value: [255, 255, 255] },
      ];
      const transColorValue = (v) => {
        if (v === null) return "";
        const n = Number(v);
        return (n >= 0 && n <= 255) ? n : "";
      };
      const setEyeColor = ([eye, rs, gs, bs]) => {
        const r = transColorValue(rs); const g = transColorValue(gs); const b = transColorValue(bs);
        const target = $(`span[name=${eye}_${r}_${g}_${b}]`);
        Array.from($(`#eye_color_group_${eye} div.swatch span.color`)).forEach((el) => $(el).removeClass("selected"));
        target.addClass("selected");
        if (r > 199 && g > 199 && b > 199) target.addClass("inverse");
        const inputKeyDownHandler = (e) => {
          const name = $(e.target).attr("name");
          const value = $(e.target).val().replace(/[^\d]/g, "");
          if (Number(value) < 0) $(e.target).val(0);
          else if (Number(value) > 255) $(e.target).val(255);
          else if (value) $(e.target).val(value);
          const content = configData.value.eye.content || data.content || new Array(6).fill("");
          const [t, color, side] = name.split("_");
          let idx = side === "r" ? 0 : 3;
          if (color === "red") idx += 0;
          else if (color === "green") idx += 1;
          else if (color === "blue") idx += 2;
          content.splice(idx, 1, value);
          configData.val = { key: "eye", value: { content } };
        };
        const inputR = $(`#color_input_${eye} input[name=color_red_${eye}]`);
        const inputG = $(`#color_input_${eye} input[name=color_green_${eye}]`);
        const inputB = $(`#color_input_${eye} input[name=color_blue_${eye}]`);
        inputR.val(r); inputG.val(g); inputB.val(b);
        inputR.off("keyup").on("keyup", inputKeyDownHandler);
        inputG.off("keyup").on("keyup", inputKeyDownHandler);
        inputB.off("keyup").on("keyup", inputKeyDownHandler);
        let arr = configData.value.eye.content || data.content;
        if (arr && arr.length) {
          const [rr, rg, rb, lr, lg, lb] = arr;
          arr = eye === "r" ? [r, g, b, lr, lg, lb] : [rr, rg, rb, r, g, b];
        } else {
          arr = eye === "r" ? [r, g, b, null, null, null] : [null, null, null, r, g, b];
        }
        configData.val = { key: "eye", value: { content: arr } };
      };
      let eyeArr = [];
      ["r", "l"].map((eye) => {
        const eyeGroup = $(`#eye_color_group_${eye}>div.color.swatch`);
        eyeGroup.children().remove();
        setEyeColor([eye]);
        const eyeColors = eyeColorList.map(({ name, value: [r, g, b] }) => {
          const el = $(`<span class="color" name="${eye}_${name}" style="background: rgb(${r}, ${g}, ${b})"></span>`);
          if (data.content && data.content.length) {
            const [rr, rg, rb, lr, lg, lb] = data.content;
            const colors = name.split("_");
            const red = transColorValue(colors[0]); const green = transColorValue(colors[1]); const blue = transColorValue(colors[2]);
            if (eye === "r" && rr === red && rg === green && rb === blue) { el.attr("selected", true); eyeArr.unshift(...[red, green, blue]); }
            else if (eye === "l" && lr === red && lg === green && lb === blue) { el.attr("selected", true); eyeArr.push(...[red, green, blue]); }
          }
          el.on("click", (e) => setEyeColor($(e.target).attr("name").split("_")));
          return el;
        });
        eyeGroup.append(...eyeColors);
      });
      if (data.type === "custom") {
        eyeArr = [...data.content];
        $(".color-swatch-group .color.swatch").addClass("hide");
        $(".color-input-wrap input[type=tel]").prop("readonly", false);
      } else {
        $(".color-swatch-group .color.swatch").removeClass("hide");
        $(".color-input-wrap input[type=tel]").prop("readonly", true);
      }
      if (eyeArr.length === 6) {
        const [rr, rg, rb, lr, lg, lb] = eyeArr;
        setEyeColor(["r", rr, rg, rb]);
        setEyeColor(["l", lr, lg, lb]);
      }
      const eyeRadioList = [{ name: "default", value: "기본" }, { name: "custom", value: "사용자" }];
      const eyeRadioGroup = $("#eye_radio_group");
      eyeRadioGroup.children().remove();
      const inputRadios = eyeRadioList.map(({ name }) => {
        const radioInput = $(`<input type="radio" id="eye_${name}" name="eye_${name}" value="${name}" />`);
        radioInput.prop("checked", (!data && name === "default") || (data && data.type === name));
        radioInput.off("click").on("click", (e) => {
          radioButtonClickHandler(e);
          if (e.target.name === "eye_custom") {
            $(".color-swatch-group .color.swatch").addClass("hide");
            $(".color-input-wrap input[type=tel]").prop("readonly", false);
          } else {
            $(".color-swatch-group .color.swatch").removeClass("hide");
            $(".color-input-wrap input[type=tel]").prop("readonly", true);
            setEyeColor(["r", null, null, null]);
            setEyeColor(["l", null, null, null]);
          }
        });
        return [radioInput, $(`<label for="eye_${name}" data-key="${name}">${translations[name][lang]}</label>`)];
      });
      eyeRadioGroup.append(...inputRadios.flat());
      setCardBtnEvent("eye");
    };

    /* 모션 카드 */
    const setMotionCard = (data) => {
      configData.val = { key: "motion", type: "default", value: data, bInit: true };
      const setMotionList = (list, name, cycle) => {
        const motionSelect = $("#motion_select");
        motionSelect.children().remove();
        motionSelect.append($(`<option value="" ${name===""?"selected":""} data-key="select_motion">${translations["select_motion"][lang]}</option>`));
        list.map((li) => motionSelect.append($(`<option value="${li}" ${name === li ? "selected" : ""}>${li}</option>`)));
        motionSelect.on("change", (e) => { configData.val = { key: "motion", value: { content: e.target.value } }; });
        const motionRepeat = $("#motion_cycle_input");
        motionRepeat.val(cycle || 1);
        motionRepeat.on("change", (e) => {
          let val = Math.min(99, Math.max(1, Number(e.target.value)));
          configData.val = { key: "motion", value: { cycle: val } };
        });
      };
      const motionRadioList = [{ name: "default" }, { name: "mymotion" }];
      const motionRadioGroup = $("#motion_radio_group");
      motionRadioGroup.children().remove();
      const inputRadios = motionRadioList.map(({ name }) => {
        const radioInput = $(`<input type="radio" id="motion_${name}" name="motion_${name}" value="${name}" />`);
        radioInput.prop("checked", (!data && name === "default") || (data && data.type === name));
        radioInput.off("click").on("click", (e) => {
          radioButtonClickHandler(e);
          configData.val = { key: "motion", value: { type: e.target.value, content: "" } };
          simSocket("sim_update_motion", e.target.value, (list) => setMotionList(list));
        });
        return [radioInput, $(`<label for="motion_${name}" data-key="${name}">${translations[name][lang]}</label>`)];
      });
      motionRadioGroup.append(...inputRadios.flat());
      simSocket("sim_update_motion", data && data.type ? data.type : "default", (list) => setMotionList(list, data && data.content, data && data.cycle));
      setCardBtnEvent("motion");
    };

    /* 오디오 카드 */
    const setAudioCard = (data) => {
      configData.val = { key: "audio", value: data, bInit: true };
      const setAudioList = (list, type, sData) => {
        const content = sData && sData.type === type ? sData.content : null;
        const audioFileSelect = $("#audio_select");
        audioFileSelect.children().remove();
        audioFileSelect.append($(`<option value="" ${content === '' ? "selected" : ""} data-key="select_audio">${translations["select_audio"][lang]}</option>`));
        list.map((li) => audioFileSelect.append($(`<option value="${li}" ${li === content ? "selected" : ""}>${li.replace(/^\/.+(\/)/gim, "")}</option>`)));
        audioFileSelect.off("change").on("change", (e) => {
          configData.val = { key: "audio", value: { type, content: e.target.value } };
        });
      };
      const path = "/home/pi/openpibo-files/audio/";
      const audioRadioList = [
        { name: "music",   value: `${path}music/`,   label: "music"   },
        { name: "voice",   value: `${path}voice/`,   label: "voice"   },
        { name: "effect",  value: `${path}effect/`,  label: "effect"  },
        { name: "piano",   value: `${path}piano/`,   label: "piano"   },
        { name: "animal",  value: `${path}animal/`,  label: "animal_audio" },
        { name: "myaudio", value: "/home/pi/myaudio/", label: "myaudio" },
      ];
      const audioRadioGroup = $("#audio_radio_group");
      audioRadioGroup.children().remove();
      const inputRadios = audioRadioList.map(({ name, label, value }) => {
        const radioInput = $(`<input type="radio" id="audio_${name}" name="audio_${name}" value="${value}" />`);
        radioInput.prop("checked", (!data && name === "music") || (data && data.type === value));
        radioInput.off("click").on("click", (e) => {
          radioButtonClickHandler(e);
          configData.val = { key: "audio", value: { type: e.target.value, content: "" } };
          simSocket("sim_update_audio", e.target.value, (list) => setAudioList(list, e.target.value));
        });
        return [radioInput, $(`<label for="audio_${name}" data-key="${label}">${translations[label][lang]}</label>`)];
      });
      audioRadioGroup.append(...inputRadios.flat());
      const type = data && data.type ? data.type : audioRadioList[0].value;
      simSocket("sim_update_audio", type, (list) => setAudioList(list, type, data));
      setCardBtnEvent("audio");
    };

    /* 디스플레이 카드 */
    const setOledCard = (data) => {
      configData.val = { key: "oled", value: data, bInit: true };
      const setOledImageList = (list, imgPath, name) => {
        const imgSelect = $("#oled_img_select");
        imgSelect.children().remove();
        imgSelect.append($(`<option value="" data-key="select_image">${translations["select_image"][lang]}</option>`));
        list.map((li) => {
          const value = `${imgPath}/${li}`;
          imgSelect.append($(`<option value="${value}" ${value === `${imgPath}/${name}` ? "selected" : ""}>${li.replace(/[\.]+[a-z]+$/gim, "")}</option>`));
        });
        imgSelect.off("change").on("change", (e) => {
          configData.val = { key: "oled", value: { type: "image", content: e.target.value } };
        });
      };
      const setOledImagePathList = (path, img) => {
        const oledImgOptionsList = [
          { value: "", label: "select_image_type" },
          { value: "/home/pi/openpibo-files/image/animal", label: "animal_image" },
          { value: "/home/pi/openpibo-files/image/expression", label: "expression" },
          { value: "/home/pi/openpibo-files/image/family", label: "family" },
          { value: "/home/pi/openpibo-files/image/food", label: "food" },
          { value: "/home/pi/openpibo-files/image/furniture", label: "furniture" },
          { value: "/home/pi/openpibo-files/image/game", label: "game" },
          { value: "/home/pi/openpibo-files/image/goods", label: "goods" },
          { value: "/home/pi/openpibo-files/image/kitchen", label: "kitchen" },
          { value: "/home/pi/openpibo-files/image/machine", label: "machine" },
          { value: "/home/pi/openpibo-files/image/recycle", label: "recycle" },
          { value: "/home/pi/openpibo-files/image/sport", label: "sport" },
          { value: "/home/pi/openpibo-files/image/transport", label: "transport" },
          { value: "/home/pi/openpibo-files/image/weather", label: "weather" },
          { value: "/home/pi/openpibo-files/image/etc", label: "etc" },
          { value: "/home/pi/openpibo-files/image/sample", label: "sample" },
          { value: "/home/pi/myimage", label: "myimage" },
        ];
        const oledPathSelect = $("#oled_path_select");
        oledPathSelect.children().remove();
        if (!path) setOledImageList([], path, img);
        const oledPathOptions = oledImgOptionsList.map(({ label, value }) => {
          if (path === value) simSocket("sim_update_oled", value, (list) => setOledImageList(list, path, img));
          return $(`<option value="${value}" ${path === value ? "selected" : ""} data-key="${label}">${translations[label][lang]}</option>`);
        });
        oledPathSelect.off("change").on("change", (e) => {
          configData.val = { key: "oled", value: { type: e.target.value, content: "" } };
          simSocket("sim_update_oled", e.target.value, (list) => setOledImageList(list, e.target.value, ""));
        });
        oledPathSelect.append(...oledPathOptions);
      };
      const setOledContent = (type, obj) => {
        if (type === "image") {
          $("#oled_text_group").hide();
          $("#oled_img_group").show();
          if (obj && obj.content) {
            const [path, img] = obj.content.split("/").reduce((a, c, i, arr) => {
              if (i === arr.length - 1) return [a[0], c];
              return [a[0] + (c ? "/" + c : ""), a[1]];
            }, [[], []]);
            setOledImagePathList(path, img);
          } else setOledImagePathList();
        } else {
          $("#oled_img_group").hide();
          $("#oled_text_group").show();
          const oledTA = $("#oled_textarea");
          let content = "", x = 0, y = 0, size = 10;
          if (obj && "content" in obj && "x" in obj && "y" in obj && "size" in obj) {
            content = obj.content; x = obj.x; y = obj.y; size = obj.size;
          }
          oledTA.val(content);
          oledTA.off("change").on("change", (e) => {
            configData.val = { key: "oled", value: { type, content: e.target.value } };
          });
          Array.from($("#oled_text_config input")).map((item) => {
            if (item.id === "oled_x") $(item).val(x);
            else if (item.id === "oled_y") $(item).val(y);
            else if (item.id === "oled_size") $(item).val(size);
            $(item).off("change").on("change", (e) => {
              const key = e.target.name.split("oled_")[1];
              configData.val = { key: "oled", value: { [key]: Number(e.target.value) } };
            });
          });
        }
      };
      const oledRadioList = [{ name: "text" }, { name: "image" }];
      const oledRadioGroup = $("#oled_radio_group");
      oledRadioGroup.children().remove();
      const oledInputRadios = oledRadioList.map(({ name }) => {
        const radioInput = $(`<input type="radio" id="oled_${name}" name="oled_${name}" value="${name}" />`);
        radioInput.prop("checked", (!data && name === "text") || (data && data.type === name));
        radioInput.off("click").on("click", (e) => {
          radioButtonClickHandler(e);
          const t = e.target.name.indexOf("image") > 0 ? "image" : "text";
          configData.val = { key: "motion", value: { type: t, content: "" } };
          setOledContent(t);
        });
        return [radioInput, $(`<label for="oled_${name}" data-key="${name}">${translations[name][lang]}</label>`)];
      });
      oledRadioGroup.append(...oledInputRadios.flat());
      if (data) setOledContent(data.type, data || { content: "", x: 0, y: 0, size: 10 });
      else setOledContent("text", { content: "", x: 0, y: 0, size: 10 });
      setCardBtnEvent("oled");
    };

    /* TTS 카드: 오프라인/온라인 라디오 + 필터 select */
    const setTtsCard = (data) => {
      configData.val = { key: "tts", value: data, bInit: true };

      const currentMode = data && isOfflineVoice(data.type) ? "offline" : "online";

      // 라디오 그룹 렌더
      const ttsVoiceModeGroup = $("#tts_voice_mode_group");
      ttsVoiceModeGroup.children().remove();
      ["offline", "online"].forEach((mode) => {
        const radio = $(`<input type="radio" name="tts_voice_mode" value="${mode}" ${currentMode === mode ? "checked" : ""} />`);
        const label = $(`<label>${translations[mode + "_voice"][lang]}</label>`);
        ttsVoiceModeGroup.append(radio, label, $(`<span>&nbsp;</span>`));
      });

      // select 갱신 함수
      const updateTtsSelect = (mode, selectedVal) => {
        const list = mode === "offline" ? offlineVoices : onlineVoices;
        const ttsSelect = $("#tts_select");
        ttsSelect.children().remove();
        list.forEach(({ value, key }) => {
          ttsSelect.append($(`<option value="${value}" ${selectedVal === value ? "selected" : ""}>${translations[key]?.[lang] || value}</option>`));
        });
        const cur = ttsSelect.val();
        if (cur) configData.val = { key: "tts", value: { type: cur } };
      };

      updateTtsSelect(currentMode, data && data.type);

      $("input[name=tts_voice_mode]").off("change").on("change", (e) => {
        updateTtsSelect(e.target.value, null);
      });

      $("#tts_select").off("change").on("change", (e) => {
        configData.val = { key: "tts", value: { type: e.target.value } };
      });

      const ttsTA = $("#tts_textarea");
      ttsTA.val((data && data.content) || "");
      ttsTA.off("change").on("change", (e) => {
        configData.val = { key: "tts", value: { content: e.target.value.slice(0, 48) } };
      });

      setCardBtnEvent("tts");
    };

    configData.value = obj;
    setEyeColorCard(configData.value.eye);
    setMotionCard(configData.value.motion);
    setAudioCard(configData.value.audio);
    setOledCard(configData.value.oled);
    setTtsCard(configData.value.tts);

    const timeInput = $("#config_time_input");
    timeInput.val(configData.value.time || 0);
    timeInput.off("change").on("change", (e) => { configData.value = { time: Number(e.target.value) }; });
    const timeSave = $("#config_time_bt");
    timeSave.off("click").on("click", () => {
      const t = timeInput.val();
      if (/\d+\.+\d{1}$|^\d{1,}$/g.test(t)) {
        const time = Number(timeInput.val()) || 0;
        const validCheck = Object.entries(configData.value).reduce((a, [k, v]) => {
          if (k === "time") return a;
          const { content } = v;
          if (k === "eye") return content.filter((v) => v && v).length ? true : a || false;
          return content ? true : a || false;
        }, false);
        if (validCheck) {
          const itemName = `timeline_row_${time.toString().replace(".", "_")}`;
          addTimelineItem({
            ...configData.value,
            audio: { ...configData.value.audio, volume: Number($("#volume").val()) },
            tts: { ...configData.value.tts, volume: Number($("#volume").val()) },
            time,
          }, true);
          handleTimelineItemClick($(`div[name=${itemName}]`));
          const index = $("#timeline_body").children().index($(`div[name=${itemName}]`));
          setSimFile({ name: selectFile, data: selectFileContents, index });
        } else { alert(translations["not_complete_setting"][lang]); }
      } else { alert(translations["unit_warn"][lang](0.1)); }
    });
  };

  const loadedFile = getSimFile();
  if (loadedFile) {
    selectFile = loadedFile.name;
    selectFileContents = loadedFile.data;
    const index = loadedFile.index;
    $("#sequence_warn").hide();
    $("h3[name=sequence_title]").text(selectFile);
    foldSimulatorFile(selectFile);
    setTimelineSection(selectFileContents, index);
    if ("lastData" in loadedFile && loadedFile.lastData) setConfigSection(loadedFile.lastData);
  } else {
    setConfigSection();
    setTimelineSection();
  }
  onFileList();
};

const handleMenu = (name) => {
  if (name === "speech") {
    $("#s_question_val").val("");
    $("#s_answer_val").val("");
    socket.emit("disp_speech");
  } else if (name === "vision") {
    $("#v_tilt_range").val($("#m5_range").val());
    $("#v_pan_range").val($("#m4_range").val());
    $("#v_location").text(`${$("#m4_range").val()}, ${$("#m5_range").val()}`);
    socket.emit("disp_vision");
  } else if (name === "motion") {
    socket.emit("disp_motion");
  }
  socket.emit("vision_sleep", name == "vision" ? "off" : "on");
  if (name != "motion") {
    socket.emit("set_motor", { idx: 0, pos: 0 });
    socket.emit("set_motor", { idx: 6, pos: 0 });
  }
  $("h4#content_header").text(name.toUpperCase());
  $("nav").find("button").removeClass("menu-selected");
  $(`button[name=${name}]`).addClass("menu-selected");
  $("article").not(`#article_${name}`).hide("slide");
  $(`main>div.content`).removeClass("modal");
  $(`#article_${name}`).show("slide");
};

getVisions(socket);
getMotions(socket);
getSpeech(socket);
getDevices(socket);
getSimulations(socket);

handleMenu("device");
const menus = $("nav").find("button");
menus.each((idx) => {
  const element = menus.get(idx);
  const name = element.getAttribute("name");
  element.addEventListener("click", () => handleMenu(name));
});

const menus_ds = $("#article_home").find("a");
menus_ds.each((idx) => {
  const element = menus_ds.get(idx);
  const name = element.getAttribute("name");
  element.addEventListener("click", () => handleMenu(name.split('_ds')[0]));
});

// ── 언어 적용 함수 ────────────────────────────────────────────
const setLanguage = (langCode) => {
  document.querySelectorAll('[data-key]').forEach(el => {
    const key = el.getAttribute('data-key');
    if (translations[key] && translations[key][langCode]) {
      el.textContent = translations[key][langCode];
    }
  });
};

// ── voice select 갱신 (언어 변경 시 공용) ────────────────────
const refreshVoiceSelect = (langCode) => {
  const mode = document.querySelector("input[name=s_voice_mode]:checked")?.value || "offline";
  const sel = document.getElementById("s_voice_type_select");
  if (!sel) return;
  const list = mode === "offline" ? offlineVoices : onlineVoices;
  const cur = sel.value;
  sel.innerHTML = list.map(v =>
    `<option value="${v.value}" ${cur === v.value ? "selected" : ""}>${translations[v.key]?.[langCode] || v.value}</option>`
  ).join('');
};

// ── 언어 토글 버튼 ────────────────────────────────────────────
const languageSel   = document.getElementById('language');
const langToggleBtn = document.getElementById('lang-toggle');

// 초기화
languageSel.value = lang;
langToggleBtn.textContent = lang === 'ko' ? 'EN' : 'KO';
setLanguage(lang);
localStorage.setItem('language', lang);

// 버튼 클릭 → lang 변수 + select + UI 동시 갱신
langToggleBtn.addEventListener('click', () => {
  lang = lang === 'ko' ? 'en' : 'ko';
  languageSel.value = lang;          // select도 동기화
  localStorage.setItem('language', lang);
  setLanguage(lang);
  langToggleBtn.textContent = lang === 'ko' ? 'EN' : 'KO';
  refreshVoiceSelect(lang);
});

// (hidden) select로 직접 바꾸는 경우 대비
languageSel.addEventListener('change', () => {
  lang = languageSel.value;
  localStorage.setItem('language', lang);
  setLanguage(lang);
  langToggleBtn.textContent = lang === 'ko' ? 'EN' : 'KO';
  refreshVoiceSelect(lang);
});