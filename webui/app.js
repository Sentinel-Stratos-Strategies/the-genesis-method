let plugins = [];

const $ = (id) => document.getElementById(id);

function runPayload() {
  return {
    inputDir: $("input-dir").value.trim(),
    outputName: $("output-name").value.trim(),
    outputBase: $("output-base").value.trim(),
    pipeline: $("pipeline-choice").value,
  };
}

async function postJson(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  let data = {};
  try {
    data = await resp.json();
  } catch (_err) {
    /* ignore empty body */
  }
  if (!resp.ok && data.message === undefined) {
    data.ok = false;
    data.message = `HTTP ${resp.status}`;
  }
  return data;
}

async function fetchStatus() {
  const resp = await fetch("/api/status");
  return resp.json();
}

async function fetchPlugins() {
  const resp = await fetch("/api/plugins");
  return resp.json();
}

async function fetchConfig() {
  const resp = await fetch("/api/config");
  return resp.json();
}

async function fetchLlmConfig() {
  const resp = await fetch("/api/llm/config");
  return resp.json();
}

async function fetchNotifications() {
  const resp = await fetch("/api/notifications");
  return resp.json();
}

function notificationsPayload() {
  return {
    enabled: $("notify-enabled").checked,
    macos_desktop: $("notify-macos").checked,
    email: {
      enabled: $("notify-email-enabled").checked,
      recipients: $("notify-recipients").value
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean),
    },
  };
}

function renderNotifications(data) {
  const cfg = data.config || {};
  const email = cfg.email || {};
  $("notify-enabled").checked = cfg.enabled !== false;
  $("notify-macos").checked = cfg.macos_desktop !== false;
  $("notify-email-enabled").checked = email.enabled !== false;
  $("notify-recipients").value = (email.recipients || []).join(", ");
  const parts = [];
  if (data.actionLog) parts.push(`action log: ${data.actionLog}`);
  if (data.notificationLog) parts.push(`notify log: ${data.notificationLog}`);
  $("notify-status").textContent = parts.length
    ? parts.join(" | ")
    : "Notifications ready.";
}

async function loadNotifications() {
  try {
    const data = await fetchNotifications();
    renderNotifications(data);
  } catch (_err) {
    $("notify-status").textContent = "Notification API unavailable.";
  }
}

function setStatus(text, meta, running) {
  $("run-status").textContent = text;
  $("run-status").classList.toggle("running", !!running);
  $("run-meta").textContent = meta;
}

async function refreshStatus() {
  try {
    const s = await fetchStatus();
    if (s.running) {
      setStatus(`Running ${s.choice}`, `PID ${s.pid} | started ${s.started_at}`, true);
      return;
    }
    if (s.last_choice) {
      const rc = s.last_rc === 0 ? "success" : `failed (rc=${s.last_rc})`;
      setStatus(`Last run: ${rc}`, `${s.last_choice} | finished ${s.last_finished_at || "recently"}`, false);
      return;
    }
    setStatus("Ready", "No active run.", false);
  } catch (_err) {
    setStatus("Status unavailable", "WebUI API not responding.", false);
  }
}

function pluginLabel(plugin) {
  return `${plugin.category} - ${plugin.name}`;
}

function renderPlugins() {
  const grid = $("module-grid");
  const select = $("module-choice");
  grid.innerHTML = "";
  select.innerHTML = "";

  const sorted = [...plugins].sort((a, b) => pluginLabel(a).localeCompare(pluginLabel(b)));
  $("module-count").textContent = `${sorted.length} modules indexed`;

  sorted.forEach((plugin) => {
    const option = document.createElement("option");
    option.value = plugin.id;
    option.textContent = pluginLabel(plugin);
    select.appendChild(option);

    const button = document.createElement("button");
    button.className = "module-card";
    button.type = "button";
    button.innerHTML = `
      <span>${plugin.category}</span>
      <strong>${plugin.name}</strong>
      <small>${plugin.description || "Registered module"}</small>
    `;
    button.addEventListener("click", () => {
      select.value = plugin.id;
    });
    grid.appendChild(button);
  });
}

async function loadPlugins() {
  plugins = await fetchPlugins();
  renderPlugins();
}

async function loadConfig() {
  const cfg = await fetchConfig();
  $("input-dir").value =
    cfg.defaultInputDir || cfg.evidenceInputRoot || "/Volumes/SENTINEL/GENESIS_EVIDENCE_INPUT";
  $("output-base").value =
    cfg.defaultOutputBase || cfg.evidenceOutputRoot || "/Volumes/SENTINEL/GENESIS_EVIDENCE_OUTPUT/runs";
  $("output-name").value = `genesis_case_${new Date().toISOString().slice(0, 19).replaceAll(":", "").replace("T", "_")}`;
}

function llmPayload() {
  return {
    provider: $("llm-provider").value,
    model: $("llm-model").value.trim(),
    base_url: $("llm-base-url").value.trim(),
    api_key_env: $("llm-api-env").value.trim(),
    api_key: $("llm-api-key").value.trim(),
    temperature: Number($("llm-temperature").value || "0.1"),
    memory_roots: $("llm-memory-roots").value.split(",").map((v) => v.trim()).filter(Boolean),
    runtime: {
      runtime_script: $("llm-runtime-script").value.trim(),
    },
  };
}

function renderLlmStatus(status) {
  const cfg = status.config || {};
  const runtime = cfg.runtime || {};
  const training = cfg.training || {};
  const paths = status.paths || {};
  const secret = status.secret || {};
  const rt = status.runtime || {};

  $("llm-status").textContent = rt.reachable
    ? `Local runtime reachable (${(rt.models || []).length} models)`
    : `Runtime not reachable${rt.error ? `: ${rt.error}` : ""}`;
  $("llm-provider").value = cfg.provider || "ollama";
  $("llm-model").value = cfg.model || "mistral-nemo:latest";
  $("llm-base-url").value = cfg.base_url || "http://127.0.0.1:11436";
  $("llm-api-env").value = cfg.api_key_env || "GENESIS_LLM_API_KEY";
  $("llm-temperature").value = cfg.temperature ?? 0.1;
  $("llm-runtime-script").value = runtime.runtime_script || "/Volumes/Stratos_Tools/projects/The_Genesis_Method/tools/ai/run_genesis_ollama_runtime.sh";
  $("llm-memory-roots").value = (cfg.memory_roots || []).join(", ");
  $("llm-api-key").value = "";

  $("llm-runtime-detail").textContent = [
    `${cfg.model || "model"} @ ${cfg.base_url || "base URL unset"}`,
    paths.runtime_script_exists ? "runtime script found" : "runtime script missing",
    paths.ollama_bin_exists ? "ollama found" : "ollama missing",
    paths.orbstack_exists ? "OrbStack found" : "OrbStack not found",
  ].join(" | ");
  $("llm-training-detail").textContent = [
    training.repo || "Unsloth repo unset",
    paths.unsloth_repo_exists ? "repo found" : "repo missing",
    paths.training_manifest_exists ? "job manifest found" : "job manifest missing",
  ].join(" | ");
  $("llm-secret-detail").textContent = secret.present
    ? `${secret.env} present (${secret.masked})`
    : `${secret.env || "GENESIS_LLM_API_KEY"} not present`;
}

async function loadLlmConfig() {
  const status = await fetchLlmConfig();
  renderLlmStatus(status);
}

function bindActions() {
  $("refresh-modules").addEventListener("click", loadPlugins);

  $("run-folder").addEventListener("click", async () => {
    setStatus("Starting folder pipeline", "Submitting enterprise folder run.", true);
    const out = await postJson("/api/folder/run", runPayload());
    setStatus(out.ok ? "Folder pipeline queued" : "Run blocked", out.message || "No response.", out.ok);
    await refreshStatus();
  });

  $("run-module").addEventListener("click", async () => {
    const pluginId = $("module-choice").value;
    setStatus(`Starting ${pluginId}`, "Submitting module run.", true);
    const out = await postJson(`/api/plugins/run/${pluginId}`, runPayload());
    setStatus(out.ok ? "Module queued" : "Run blocked", out.message || "No response.", out.ok);
    await refreshStatus();
  });

  $("save-llm").addEventListener("click", async () => {
    $("llm-status").textContent = "Saving AI engine configuration...";
    const out = await postJson("/api/llm/save", llmPayload());
    if (out.status) renderLlmStatus(out.status);
  });

  $("test-llm").addEventListener("click", async () => {
    $("llm-status").textContent = "Testing AI engine...";
    const out = await postJson("/api/llm/test", {});
    if (out.status) renderLlmStatus(out.status);
  });

  $("start-llm").addEventListener("click", async () => {
    $("llm-status").textContent = "Starting local LLM runtime...";
    const out = await postJson("/api/llm/start", llmPayload());
    $("llm-status").textContent = out.message || "Runtime command submitted.";
    await refreshStatus();
    setTimeout(loadLlmConfig, 2500);
  });

  $("save-notify").addEventListener("click", async () => {
    $("notify-status").textContent = "Saving notification settings...";
    const out = await postJson("/api/notifications/save", notificationsPayload());
    if (out.config) renderNotifications({ config: out.config, actionLog: "", notificationLog: "" });
    $("notify-status").textContent = out.message || "Notification settings saved.";
  });

  $("test-notify").addEventListener("click", async () => {
    $("notify-status").textContent = "Sending test notification...";
    const out = await postJson("/api/notifications/test", {
      message: "Genesis dashboard test — notifications and log delivery are active.",
    });
    const delivered = out.result?.delivered?.length || 0;
    const errors = out.result?.errors?.length || 0;
    $("notify-status").textContent = out.message
      ? `${out.message} (${delivered} delivered, ${errors} errors)`
      : "Test complete.";
    await loadNotifications();
  });
}

async function main() {
  await loadConfig();
  await loadNotifications();
  await loadLlmConfig();
  await loadPlugins();
  bindActions();
  await refreshStatus();
  setInterval(refreshStatus, 3000);
}

main().catch(() => setStatus("Startup error", "Could not initialize WebUI.", false));
