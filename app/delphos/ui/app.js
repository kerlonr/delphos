"use strict";
// Interface do Delphos. Os dados vêm do Python por window.pywebview.api (app/delphos/api.py).

const $ = (id) => document.getElementById(id);
let api = null;
let st = null;          // último estado vindo do Python
let device = null;      // { layers: [{ "linha,coluna": código, ccw, cw }], labels, macros, macro_space, actions }
let labels = {};        // código -> nome da tecla
let catalog = [];
let actionTypes = {};
let layer = 0;          // camada em edição
let selected = null;    // tecla em edição
let category = 0;
let nextKeymapTry = 0;
let knobSeq = null, knobAngle = 0;

// Tela (o desenho fica em oled.js)

let popupUntil = 0, lastVolume = null, lastItem = null, scroll = 0;
const ctx = $("oled").getContext("2d");
const img = ctx.createImageData(W, H);

function paintOled() {
  if (!st || !st.connected || !st.screen) {
    drawOffline();
    drawOfflineDots();
  } else {
    const width = textW(mediaLine(st.media.text), 1, false);
    scroll = st.media.status && width > W - MEDIA_X ? (scroll + 1) % (width + 18) : 0;
    renderScreen(st.screen, st.media, performance.now() < popupUntil, scroll);
  }
  for (let i = 0; i < fb.length; i++) img.data.set(fb[i] ? [191, 228, 255, 255] : [0, 0, 0, 255], i * 4);
  ctx.putImageData(img, 0, 0);
}
setInterval(paintOled, 45);

// Teclas

const KEY_SLOTS = ["0,0", "0,1", "0,2", "0,3", "1,0", "1,1", "1,2", "1,3", "2,0", "2,1", "2,2", "2,3"];
const ENCODER_SLOTS = ["ccw", "cw", "0,4"];
const ENCODER_TITLES = { ccw: "Encoder: girar para a esquerda", cw: "Encoder: girar para a direita", "0,4": "Encoder: clique" };
const MACRO_0 = 0x7700, ACTION_0 = 0x7E06;
const EXTRA_CATEGORIES = ["Macro", "Ação no PC", "Atalho", "Código"];

const keyAt = (slot) => device?.layers[layer][slot];
const macroIndex = (code) => (code >= MACRO_0 && code < MACRO_0 + 16 ? code - MACRO_0 : null);
const actionIndex = (code) => (code >= ACTION_0 && code < ACTION_0 + 16 ? code - ACTION_0 : null);
const labelOf = (code) => labels[code] ?? `0x${code.toString(16).toUpperCase()}`;

function buildKeys() {
  for (const slot of KEY_SLOTS) {
    const b = document.createElement("button");
    b.className = "key";
    b.dataset.slot = slot;
    b.addEventListener("click", () => select(slot));
    $("keys").appendChild(b);
  }
  $("knob").addEventListener("click", () => select(ENCODER_SLOTS.includes(selected) ? selected : "cw"));
  for (const b of $("layers").children) {
    b.addEventListener("click", () => {
      layer = Number(b.dataset.layer);
      renderKeys();
      renderEditor();
    });
  }
}

function setDevice(result) {
  device = result;
  if (result) Object.assign(labels, result.labels);
}

function renderKeys() {
  for (const b of $("layers").children) b.setAttribute("aria-pressed", String(Number(b.dataset.layer) === layer));
  for (const b of document.querySelectorAll(".key")) {
    const code = keyAt(b.dataset.slot);
    // Em camadas 1-3, "Transparente" usa a tecla da camada de baixo: mostra apagada.
    b.classList.toggle("empty", code === 1 && layer > 0);
    b.textContent = code == null || (code === 1 && layer > 0) ? "" : labelOf(code).replace(/([/+])/g, "$1​");
    b.classList.toggle("special", code >= 0x7E00 && code <= 0x7E15 || macroIndex(code) !== null);
    b.setAttribute("aria-pressed", String(b.dataset.slot === selected));
  }
  $("knob").setAttribute("aria-pressed", String(ENCODER_SLOTS.includes(selected)));
}

function select(slot) {
  selected = slot;
  const code = keyAt(slot);
  // Abre direto no editor do tipo da tecla (macro, ação) para editar o que já existe.
  if (macroIndex(code) !== null) category = catalog.length;
  else if (actionIndex(code) !== null) category = catalog.length + 1;
  showView("keys");
  renderKeys();
  renderEditor();
}

function showEditor(id) {
  for (const e of ["capture", "macroEditor", "actionEditor", "codeEditor"]) $(e).hidden = e !== id;
  $("items").hidden = id !== null;
}

function renderEditor() {
  const editing = Boolean(selected && device);
  $("keysEmpty").hidden = editing;
  $("keysEdit").hidden = !editing;
  $("editError").hidden = true;
  if (!editing) return;

  $("slots").hidden = !ENCODER_SLOTS.includes(selected);
  for (const b of $("slots").children) b.setAttribute("aria-pressed", String(b.dataset.slot === selected));
  $("editTitle").textContent = (ENCODER_TITLES[selected] ?? "Tecla") + (layer ? ` · camada ${layer}` : "");
  $("editCurrent").textContent = `Agora: ${labelOf(keyAt(selected))}`;

  $("chips").replaceChildren(...[...catalog.map((c) => c.name), ...EXTRA_CATEGORIES].map((name, i) => {
    const b = document.createElement("button");
    b.textContent = name;
    b.setAttribute("aria-pressed", String(i === category));
    b.addEventListener("click", () => { category = i; renderEditor(); });
    return b;
  }));

  const extra = EXTRA_CATEGORIES[category - catalog.length];
  if (extra === "Macro") return openMacro();
  if (extra === "Ação no PC") return openAction();
  if (extra === "Atalho") return openCapture();
  if (extra === "Código") return openCode();
  showEditor(null);
  $("items").replaceChildren(...catalog[category].items.map((item) => {
    const b = document.createElement("button");
    b.textContent = item.label;
    b.classList.toggle("current", item.code === keyAt(selected));
    b.addEventListener("click", () => assign(api.set_key(layer, selected, item.code)));
    return b;
  }));
}

async function assign(pending) {
  try {
    setDevice(await pending);
  } catch (e) {
    $("editError").textContent = String(e.message || e).replace(/^.*?: /, "") || "Não gravou: o Delphos está conectado?";
    $("editError").hidden = false;
    return;
  }
  renderKeys();
  renderEditor();
}

// Atalho

let captured = null;
let captureMode = null; // "key" = atalho da tecla; "macro" = passo de macro

function openCapture() {
  showEditor("capture");
  captureMode = "key";
  captured = null;
  $("captureView").textContent = "…";
  $("captureSave").disabled = true;
}

document.addEventListener("keydown", async (e) => {
  if (!captureMode || $("view-keys").hidden) return;
  if (["Control", "Shift", "Alt", "Meta"].includes(e.key)) return;
  if (document.activeElement?.tagName === "INPUT") return;
  e.preventDefault();
  const mods = [e.ctrlKey && "ctrl", e.shiftKey && "shift", e.altKey && "alt", e.metaKey && "meta"].filter(Boolean);
  const shortcut = await api.shortcut(mods, e.code);
  if (captureMode === "macro") {
    captureMode = null;
    $("macroKeyHint").hidden = true;
    if (shortcut) macroSteps.push(...await api.shortcut_steps(shortcut.code));
    return renderSteps();
  }
  if (!shortcut) {
    $("captureView").textContent = "Tecla não suportada";
    return;
  }
  captured = shortcut.code;
  labels[shortcut.code] = shortcut.label;
  $("captureView").textContent = shortcut.label;
  $("captureSave").disabled = false;
});
$("captureSave").addEventListener("click", () => captured != null && assign(api.set_key(layer, selected, captured)));

// Macro

let macroSteps = [];
const KEY_NAMES = { 0xE0: "Ctrl", 0xE1: "Shift", 0xE2: "Alt", 0xE3: "Win" };
const keyName = (code) => KEY_NAMES[code] ?? labelOf(code);

function openMacro() {
  showEditor("macroEditor");
  captureMode = null;
  const index = macroIndex(keyAt(selected));
  macroSteps = index === null ? [] : structuredClone(device.macros[index]);
  renderSteps();
}

function describeStep(step) {
  if (step.type === "text") return `Digitar "${step.value}"`;
  if (step.type === "delay") return `Esperar ${step.ms} ms`;
  return { tap: "Apertar", down: "Segurar", up: "Soltar" }[step.type] + " " + keyName(step.key);
}

function renderSteps() {
  $("macroSteps").replaceChildren(...macroSteps.map((step, i) => {
    const li = document.createElement("li");
    li.textContent = describeStep(step);
    const remove = document.createElement("button");
    remove.className = "icon";
    remove.textContent = "×";
    remove.setAttribute("aria-label", "Remover passo");
    remove.addEventListener("click", () => { macroSteps.splice(i, 1); renderSteps(); });
    li.appendChild(remove);
    return li;
  }));
  $("macroSpace").textContent = `Espaço total das 16 macros: ${device.macro_space} bytes`;
}

$("addText").addEventListener("click", () => {
  const value = $("macroText").value;
  if (!value) return;
  macroSteps.push({ type: "text", value });
  $("macroText").value = "";
  renderSteps();
});
$("addKey").addEventListener("click", () => {
  captureMode = "macro";
  $("macroKeyHint").hidden = false;
  $("addKey").blur();
});
$("addDelay").addEventListener("click", () => { macroSteps.push({ type: "delay", ms: 100 }); renderSteps(); });
$("macroSave").addEventListener("click", () => assign(api.save_macro(layer, selected, macroSteps)));

// Ação no PC

function openAction() {
  showEditor("actionEditor");
  captureMode = null;
  const index = actionIndex(keyAt(selected));
  const action = index === null ? null : device.actions[index];
  $("actionType").replaceChildren(...Object.entries(actionTypes).map(([value, text]) => new Option(text, value)));
  $("actionType").value = action?.type ?? "program";
  $("actionTarget").value = action?.target ?? "";
  renderActionFields(action?.target);
}

function renderActionFields(target) {
  const type = $("actionType").value;
  const isApp = type === "mute_app";
  $("actionTarget").hidden = isApp || type === "close_selected";
  $("actionApp").hidden = !isApp;
  $("actionPick").hidden = !["program", "folder"].includes(type);
  $("actionTarget").placeholder = { program: "Caminho do programa", site: "youtube.com", folder: "Caminho da pasta" }[type] ?? "";
  if (isApp) {
    const apps = (st?.apps ?? []).filter((a) => a.key !== "__master__");
    $("actionApp").replaceChildren(...apps.map((a) => new Option(a.name, a.key)));
    if (target) $("actionApp").value = target;
  }
}

$("actionType").addEventListener("change", () => { $("actionTarget").value = ""; renderActionFields(); });
$("actionPick").addEventListener("click", async () => {
  const path = await api.pick_file($("actionType").value === "folder");
  if (path) $("actionTarget").value = path;
});
$("actionSave").addEventListener("click", () => {
  const type = $("actionType").value;
  const app = $("actionApp").selectedOptions[0];
  const action = type === "mute_app"
    ? { type, target: app?.value ?? "", label: app?.text ?? "" }
    : { type, target: type === "close_selected" ? "" : $("actionTarget").value };
  assign(api.save_action(layer, selected, action));
});

// Código

function openCode() {
  showEditor("codeEditor");
  captureMode = null;
  $("codeInput").value = `0x${keyAt(selected).toString(16).toUpperCase().padStart(4, "0")}`;
}
$("codeSave").addEventListener("click", () => {
  const code = parseInt($("codeInput").value, 16);
  if (Number.isNaN(code) || code < 0 || code > 0xFFFF) {
    $("editError").textContent = "Use um número hexadecimal entre 0x0000 e 0xFFFF.";
    $("editError").hidden = false;
    return;
  }
  assign(api.set_key(layer, selected, code));
});

for (const b of $("slots").children) b.addEventListener("click", () => select(b.dataset.slot));
$("resetKeys").addEventListener("click", () => assign(api.reset_keys()));

// Mixer

const escapeHtml = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function buildChannel(app) {
  const li = document.createElement("li");
  li.dataset.key = app.key;
  li.innerHTML = `<span class="pick"></span><button class="name"></button>
    <input type="range" min="0" max="100" aria-label="Volume"><output></output>
    <button class="icon mute" aria-label="Mutar"><svg viewBox="0 0 16 16"><path d="M2 6h3l4-3v10l-4-3H2Z"/><path class="x" d="M11 6l4 4M15 6l-4 4" fill="none"/></svg></button>
    <button class="icon hide" aria-label="Ocultar do mixer" title="Ocultar do mixer"><svg viewBox="0 0 16 16"><path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5Z" fill="none"/><path d="M2 14 14 2" fill="none"/></svg></button>`;
  const hide = li.querySelector(".hide");
  hide.hidden = app.key === "__master__";
  hide.addEventListener("click", () => api.hide_app(app.key, app.name));
  const slider = li.querySelector("input");
  li.querySelector(".name").addEventListener("click", () => api.select(app.key));
  slider.addEventListener("input", () => {
    li.querySelector("output").textContent = slider.value;
    api.set_volume(app.key, Number(slider.value));
  });
  li.querySelector(".mute").addEventListener("click", () => api.toggle_mute(app.key));
  return li;
}

function renderMixer() {
  const list = $("channels");
  // Só recria a lista quando entra ou sai um app, para não atrapalhar quem está arrastando um volume.
  const keys = st.apps.map((a) => a.key).join("|");
  if (list.dataset.keys !== keys) {
    list.dataset.keys = keys;
    list.replaceChildren(...st.apps.map(buildChannel));
  }
  for (const app of st.apps) {
    const li = list.querySelector(`li[data-key="${CSS.escape(app.key)}"]`);
    li.classList.toggle("sel", app.selected);
    li.classList.toggle("off", app.muted);
    li.querySelector(".name").textContent = app.name;
    li.querySelector(".mute").classList.toggle("on", app.muted);
    li.querySelector(".mute").disabled = app.silent;
    li.classList.toggle("silent", app.silent);
    li.title = app.silent ? "Sem som ainda: o volume funciona quando o app tocar algo" : "";
    const slider = li.querySelector("input");
    slider.disabled = app.silent;
    if (document.activeElement !== slider) {
      slider.value = app.volume;
      li.querySelector("output").textContent = app.volume;
    }
  }

  const hidden = st.hidden_apps;
  $("hiddenApps").hidden = !hidden.length;
  const hkeys = hidden.map((a) => a.key).join("|");
  if ($("hiddenList").dataset.keys !== hkeys) {
    $("hiddenList").dataset.keys = hkeys;
    $("hiddenList").replaceChildren(...hidden.map((a) => {
      const b = document.createElement("button");
      b.className = "ghost";
      b.textContent = `${a.name} ✕`;
      b.title = "Mostrar de novo no mixer";
      b.addEventListener("click", () => api.show_app(a.key));
      return b;
    }));
  }

  const media = st.media;
  $("now").hidden = !media.text;
  $("nowState").textContent = ["Parado", "Tocando", "Pausado"][media.status];
  $("nowTitle").textContent = media.text.replace("\x1f", " — ");
  $("playIcon").setAttribute("d", media.status === 1 ? "M4 3h3v10H4ZM9 3h3v10H9Z" : "M5 3v10l8-5Z");

  $("mics").innerHTML = st.mics.length
    ? st.mics.map(([name, muted]) => `<li><b>${escapeHtml(name)}</b><span class="${muted ? "m" : ""}">${muted ? "mudo" : "ativo"}</span></li>`).join("")
    : "<li>Nenhum microfone encontrado</li>";
}
for (const b of document.querySelectorAll("[data-media]")) b.addEventListener("click", () => api.media(b.dataset.media));

// Ajustes

async function loadSettings() {
  const s = await api.settings();
  $("autostart").checked = s.autostart;
  $("step").value = s.step;
  $("stepOut").textContent = `${s.step}%`;
  $("installRow").hidden = !s.is_exe;
  if (s.running_installed) {
    $("installInfo").textContent = `Versão ${s.version}, instalada. Para remover, use "Aplicativos instalados" do Windows.`;
    $("install").hidden = true;
  } else if (s.installed) {
    $("installInfo").textContent = `Instalada: versão ${s.installed_version ?? "?"}. Esta: ${s.version}.`;
    $("install").textContent = "Atualizar instalação";
  } else {
    $("installInfo").textContent = "Copia o Delphos para a pasta de programas, com atalho no menu Iniciar.";
  }
}
$("autostart").addEventListener("change", (e) => api.set_autostart(e.target.checked));
$("step").addEventListener("input", (e) => {
  $("stepOut").textContent = `${e.target.value}%`;
  api.set_step(Number(e.target.value));
});
$("openLog").addEventListener("click", () => api.open_log());
$("testScreen").addEventListener("click", () => api.test_screen());
$("flash").addEventListener("click", () => api.flash());
$("outdatedFlash").addEventListener("click", () => { showView("settings"); api.flash(); });
$("install").addEventListener("click", () => {
  $("install").disabled = true;
  $("installInfo").textContent = "Instalando… o Delphos vai reabrir sozinho.";
  api.install();
});

async function backup(pending, done) {
  try {
    const result = await pending;
    if (!result) return;
    if (typeof result === "object") setDevice(result);
    $("backupMsg").textContent = done;
  } catch (e) {
    $("backupMsg").textContent = `Não deu: ${String(e.message || e)}`;
  }
  $("backupMsg").hidden = false;
  renderKeys();
}
$("exportBackup").addEventListener("click", () => backup(api.export_backup(), "Backup salvo."));
$("importBackup").addEventListener("click", () => backup(api.import_backup(), "Backup restaurado no Delphos."));

function renderFirmware() {
  const flash = st.flash, fw = st.firmware;
  const outdated = fw && fw.installed !== fw.bundled;
  $("fwInfo").textContent = !fw ? "Conecte o Delphos para ver a versão."
    : outdated ? `Instalado: ${fw.installed ?? "antigo"} · disponível: ${fw.bundled}`
    : `Versão ${fw.installed}, atualizado.`;
  $("flash").disabled = flash.running;
  $("outdated").hidden = !outdated || flash.running;
  $("flashMsg").hidden = !flash.message;
  $("flashMsg").textContent = flash.message;
  $("flashMsg").classList.toggle("boot", flash.needs_boot);
}

// Geral

function showView(view) {
  for (const t of document.querySelectorAll("[data-view]")) t.setAttribute("aria-selected", String(t.dataset.view === view));
  for (const id of ["keys", "mixer", "settings"]) $(`view-${id}`).hidden = id !== view;
}
for (const t of document.querySelectorAll("[data-view]")) t.addEventListener("click", () => showView(t.dataset.view));
$("micPill").addEventListener("click", () => api.toggle_mic());

function renderDevice() {
  // Volume mudou no mesmo item: mostra o número grande, como o Delphos faz.
  const s = st.screen;
  if (s) {
    if (s.key === lastItem && lastVolume !== null && s.volume !== lastVolume) popupUntil = performance.now() + 1200;
    lastVolume = s.volume;
    lastItem = s.key;
  }
  // Teclas físicas apertadas acendem no desenho; o encoder gira junto.
  const down = new Set(st.keys_down);
  for (const b of document.querySelectorAll(".key")) b.classList.toggle("down", down.has(b.dataset.slot));
  $("knob").classList.toggle("down", down.has("0,4"));
  if (knobSeq !== null && st.knob.seq !== knobSeq) {
    knobAngle += 18 * st.knob.dir * (st.knob.seq - knobSeq);
    $("knob").querySelector(".knob-cap").style.transform = `rotate(${knobAngle}deg)`;
  }
  knobSeq = st.knob.seq;

  $("micPill").classList.toggle("muted", st.mic_muted);
  $("micText").textContent = st.mic_muted ? "Microfone mudo" : "Microfone ativo";
  $("conn").textContent = st.connected ? "Delphos conectado" : "Delphos desconectado. Confira o cabo USB.";
  $("conn").classList.toggle("ok", st.connected);
}

async function tick() {
  try {
    st = await api.state();
  } catch {
    return;
  }
  // Lê as teclas ao conectar; se o Delphos ainda não respondeu (reiniciando), tenta de novo em 2 s.
  if (st.connected && !device && performance.now() > nextKeymapTry) {
    nextKeymapTry = performance.now() + 2000;
    setDevice(await api.keymap());
    renderKeys();
    renderEditor();
  }
  if (!st.connected) device = null;
  renderDevice();
  renderMixer();
  renderFirmware();
}

window.addEventListener("pywebviewready", async () => {
  api = window.pywebview.api;
  ({ catalog, labels, action_types: actionTypes } = await api.meta());
  buildKeys();
  renderKeys();
  renderEditor();
  await loadSettings();
  await tick();
  setInterval(tick, 250);
});
