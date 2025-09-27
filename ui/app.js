const apiBaseInput = document.getElementById("apiBase");
const healthStatus = document.getElementById("health-status");
const globalAlert = document.getElementById("global-alert");
const sessionList = document.getElementById("session-list");
const signupResult = document.getElementById("signup-result");
const loginStatus = document.getElementById("login-status");
const foundOutput = document.getElementById("found-output");
const lostOutput = document.getElementById("lost-output");
const matchesOutput = document.getElementById("matches-output");
const claimOutput = document.getElementById("claim-output");
const verifyOutput = document.getElementById("verify-output");

const state = {
  owner: { token: null, profile: null },
  finder: { token: null, profile: null },
  lastFound: null,
  lastLost: null,
  lastMatches: [],
  lastClaim: null,
};

function showAlert(type, message) {
  if (!message) {
    globalAlert.classList.add("d-none");
    return;
  }
  globalAlert.className = `alert alert-${type}`;
  globalAlert.textContent = message;
  globalAlert.classList.remove("d-none");
}

function truncateToken(token) {
  if (!token) return "—";
  return `${token.slice(0, 12)}…${token.slice(-6)}`;
}

function updateSessions() {
  sessionList.innerHTML = "";
  ["owner", "finder"].forEach((role) => {
    const { token, profile } = state[role];
    const li = document.createElement("li");
    li.className = "list-group-item d-flex justify-content-between align-items-center";
    const name = profile?.display_name || profile?.email || "—";
    li.innerHTML = `
      <span><strong>${role.toUpperCase()}</strong> · ${name}</span>
      <code class="text-muted">${truncateToken(token)}</code>
    `;
    sessionList.appendChild(li);
  });
}

async function apiFetch(path, { method = "GET", token, body, headers = {} } = {}) {
  const base = apiBaseInput.value.replace(/\/$/, "");
  const init = {
    method,
    headers: {
      Accept: "application/json",
      ...headers,
    },
  };

  if (token) {
    init.headers.Authorization = `Bearer ${token}`;
  }

  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const response = await fetch(`${base}${path}`, init);
  const contentType = response.headers.get("content-type") || "";
  let data;
  if (contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = await response.text();
  }
  if (!response.ok) {
    const message = typeof data === "string" && data.trim() ? data : JSON.stringify(data);
    throw new Error(message || `${response.status} ${response.statusText}`);
  }
  return data;
}

function parseTags(input) {
  return input
    .split(",")
    .map((tag) => tag.trim().toLowerCase())
    .filter(Boolean);
}

function toIso(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function ensureToken(role) {
  const { token } = state[role];
  if (!token) {
    throw new Error(`Log in as ${role} first.`);
  }
  return token;
}

// Health check
const apiConfigForm = document.getElementById("api-config-form");
apiConfigForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await apiFetch("/healthz");
    healthStatus.innerHTML = `<span class="badge text-bg-success">${data.status}</span>`;
    showAlert("success", "Gateway reachable.");
  } catch (error) {
    healthStatus.innerHTML = `<span class="badge text-bg-danger">offline</span>`;
    showAlert("danger", error.message);
  }
});

// Signup
const signupForm = document.getElementById("signup-form");
signupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  signupResult.textContent = "";
  try {
    const email = document.getElementById("signupEmail").value.trim();
    const password = document.getElementById("signupPassword").value;
    const displayName = document.getElementById("signupDisplayName").value.trim();
    const payload = { email, password, display_name: displayName };
    const data = await apiFetch("/auth/signup", { method: "POST", body: payload });
    signupResult.textContent = `Created user ${data.email}`;
    signupForm.reset();
    showAlert("success", "Account created.");
  } catch (error) {
    signupResult.textContent = error.message;
    showAlert("danger", error.message);
  }
});

// Login
const loginForm = document.getElementById("login-form");
loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginStatus.textContent = "";
  try {
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;
    const slot = document.getElementById("loginRole").value;
    const payload = { email, password };
    const data = await apiFetch("/auth/login", { method: "POST", body: payload });
    const token = data.access_token;
    state[slot].token = token;
    try {
      const profile = await apiFetch("/auth/me", { token });
      state[slot].profile = profile;
    } catch (profileError) {
      console.warn("Failed to load profile", profileError);
    }
    updateSessions();
    loginStatus.innerHTML = `<span class="text-success">Stored ${slot} token.</span>`;
    showAlert("success", `Logged in as ${slot}.`);
  } catch (error) {
    loginStatus.innerHTML = `<span class="text-danger">${error.message}</span>`;
    showAlert("danger", error.message);
  }
});

// Post found item
const foundForm = document.getElementById("found-form");
foundForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  foundOutput.textContent = "";
  try {
    const token = ensureToken("finder");
    const payload = {
      title: document.getElementById("foundTitle").value.trim(),
      description: document.getElementById("foundDescription").value.trim(),
      tags: parseTags(document.getElementById("foundTags").value),
      location: {
        zone: document.getElementById("foundZone").value.trim() || null,
      },
      when: toIso(document.getElementById("foundWhen").value),
      category: document.getElementById("foundCategory").value.trim() || null,
      photos: [],
      verificationPrompts: document
        .getElementById("foundPrompts")
        .value.split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
    };

    const photoUrl = document.getElementById("foundPhoto").value.trim();
    if (photoUrl) {
      payload.photos.push({
        url: photoUrl,
        thumbnails: [],
        safety: { facesBlurred: true, piiRedacted: true },
      });
    }

    const data = await apiFetch("/items/found", {
      method: "POST",
      body: payload,
      token,
    });
    state.lastFound = data;
    foundOutput.textContent = JSON.stringify(data, null, 2);
    showAlert("success", "Found item created.");
  } catch (error) {
    foundOutput.textContent = error.message;
    showAlert("danger", error.message);
  }
});

// Post lost item
const lostForm = document.getElementById("lost-form");
lostForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  lostOutput.textContent = "";
  try {
    const token = ensureToken("owner");
    const payload = {
      title: document.getElementById("lostTitle").value.trim(),
      description: document.getElementById("lostDescription").value.trim(),
      tags: parseTags(document.getElementById("lostTags").value),
      location: {
        zone: document.getElementById("lostZone").value.trim() || null,
      },
      when: toIso(document.getElementById("lostWhen").value),
      category: document.getElementById("lostCategory").value.trim() || null,
      photos: [],
    };
    const data = await apiFetch("/items/lost", {
      method: "POST",
      body: payload,
      token,
    });
    state.lastLost = data;
    lostOutput.textContent = JSON.stringify(data, null, 2);
    showAlert("success", "Lost item created.");
  } catch (error) {
    lostOutput.textContent = error.message;
    showAlert("danger", error.message);
  }
});

// Fetch matches
const matchesBtn = document.getElementById("matches-btn");
matchesBtn.addEventListener("click", async () => {
  matchesOutput.textContent = "";
  try {
    if (!state.lastLost) {
      throw new Error("Post a lost item first.");
    }
    const itemId = state.lastLost.id;
    const params = new URLSearchParams({ itemId, k: "5" }).toString();
    const data = await apiFetch(`/matches?${params}`);
    state.lastMatches = data;
    matchesOutput.textContent = JSON.stringify(data, null, 2);
    if (Array.isArray(data) && data.length) {
      document.getElementById("claimItemId").value = state.lastLost.id;
      document.getElementById("claimCandidateId").value = data[0].candidateId;
      showAlert("success", "Matches fetched.");
    } else {
      showAlert("warning", "No matches returned.");
    }
  } catch (error) {
    matchesOutput.textContent = error.message;
    showAlert("danger", error.message);
  }
});

// Submit claim
const claimForm = document.getElementById("claim-form");
claimForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  claimOutput.textContent = "";
  try {
    const token = ensureToken("owner");
    const itemId = document.getElementById("claimItemId").value.trim();
    const candidateId = document.getElementById("claimCandidateId").value.trim();
    if (!itemId || !candidateId) {
      throw new Error("Provide item and candidate IDs.");
    }
    let answers;
    try {
      answers = JSON.parse(document.getElementById("claimAnswers").value);
    } catch (parseError) {
      throw new Error("Answers must be valid JSON.");
    }
    const payload = { itemId, candidateId, answers };
    const data = await apiFetch("/claims", { method: "POST", body: payload, token });
    state.lastClaim = data;
    claimOutput.textContent = JSON.stringify(data, null, 2);
    showAlert("success", "Claim opened.");
  } catch (error) {
    claimOutput.textContent = error.message;
    showAlert("danger", error.message);
  }
});

// Finder verify claim
const verifyBtn = document.getElementById("verify-btn");
verifyBtn.addEventListener("click", async () => {
  verifyOutput.textContent = "";
  try {
    const token = ensureToken("finder");
    if (!state.lastClaim) {
      throw new Error("Open a claim first.");
    }
    const claimId = state.lastClaim.id;
    const data = await apiFetch(`/claims/${claimId}`, {
      method: "PATCH",
      body: { action: "verify" },
      token,
    });
    state.lastClaim = data;
    verifyOutput.textContent = JSON.stringify(data, null, 2);
    showAlert("success", "Claim verified by finder.");
  } catch (error) {
    verifyOutput.textContent = error.message;
    showAlert("danger", error.message);
  }
});

updateSessions();
showAlert(null, null);
