async function runChoice(choice) {
  const resp = await fetch(`/api/run/${choice}`, { method: "POST" });
  return resp.json();
}

async function fetchStatus() {
  const resp = await fetch("/api/status");
  return resp.json();
}

function setStatus(text, meta, running) {
  const statusEl = document.getElementById("run-status");
  const metaEl = document.getElementById("run-meta");
  statusEl.textContent = text;
  statusEl.classList.toggle("running", !!running);
  metaEl.textContent = meta;
}

async function refreshStatus() {
  try {
    const s = await fetchStatus();
    if (s.running) {
      setStatus(
        `Running choice ${s.choice}`,
        `PID ${s.pid} | started ${s.started_at}`,
        true
      );
    } else if (s.last_choice) {
      const rc = s.last_rc === 0 ? "success" : `failed (rc=${s.last_rc})`;
      setStatus(
        `Last run: ${rc}`,
        `choice ${s.last_choice} | finished ${s.last_finished_at || "recently"}`,
        false
      );
    } else {
      setStatus("Ready", "No active run.", false);
    }
  } catch (_err) {
    setStatus("Status unavailable", "WebUI API not responding.", false);
  }
}

function bindActions() {
  const runButtons = document.querySelectorAll(".tile.run");
  runButtons.forEach((btn) => {
    btn.addEventListener("click", async () => {
      const choice = btn.dataset.choice;
      if (!choice) return;
      setStatus(`Starting choice ${choice}...`, "Submitting action to backend.", true);
      try {
        const out = await runChoice(choice);
        if (out.ok) {
          setStatus(`Running choice ${choice}`, out.message, true);
        } else {
          setStatus("Run blocked", out.message || "Unknown error.", false);
        }
      } catch (_err) {
        setStatus("Run error", "Could not reach backend.", false);
      }
      await refreshStatus();
    });
  });
}

bindActions();
refreshStatus();
setInterval(refreshStatus, 3000);
