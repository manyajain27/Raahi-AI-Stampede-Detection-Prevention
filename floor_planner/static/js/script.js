const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
let currentTool = null;
let elements = []; // to store placed elements
let currentPathway = [];
let isPathwayMode = false;
let pixelsPerMeter = 50;
let isShiftPressed = false;
let previewPoint = null;
let selectedPoint = null;
let isDragging = false;
let selectedElement = null;
let nextId = 1;
let pathwayCounter = 1;
let entryCounter = 1;
let exitCounter = 1;
let chokeCounter = 1;
let jointCounter = 1;
let joints = []; // Automatically detected joints
let bgImage = null;
let bgOpacity = 0.5;
let bgImageDataUrl = null;
let suggestions = []; // {type, x, y, label, reason}

// Resize canvas to fill available space
function resizeCanvas() {
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
  redraw();
}

window.addEventListener("resize", resizeCanvas);
resizeCanvas();

// Tool selection
function setActiveTool(toolName) {
  document
    .querySelectorAll(".tool-btn")
    .forEach((btn) => btn.classList.remove("active"));
  currentTool = toolName;
  if (toolName === "select") {
    canvas.classList.add("select-mode");
  } else {
    canvas.classList.remove("select-mode");
  }
}

document.getElementById("pathway-btn").addEventListener("click", () => {
  finishPathway();
  setActiveTool("pathway");
  document.getElementById("pathway-btn").classList.add("active");
  isPathwayMode = true;
  currentPathway = [];
});

document.getElementById("entry-btn").addEventListener("click", () => {
  finishPathway();
  setActiveTool("entry");
  document.getElementById("entry-btn").classList.add("active");
  isPathwayMode = false;
});

document.getElementById("exit-btn").addEventListener("click", () => {
  finishPathway();
  setActiveTool("exit");
  document.getElementById("exit-btn").classList.add("active");
  isPathwayMode = false;
});

document.getElementById("choke-btn").addEventListener("click", () => {
  finishPathway();
  setActiveTool("choke");
  document.getElementById("choke-btn").classList.add("active");
  isPathwayMode = false;
});

document.getElementById("select-btn").addEventListener("click", () => {
  finishPathway();
  setActiveTool("select");
  document.getElementById("select-btn").classList.add("active");
  isPathwayMode = false;
});

document.getElementById("clear-btn").addEventListener("click", () => {
  if (confirm("Are you sure you want to clear everything?")) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    elements = [];
    joints = [];
    currentPathway = [];
    selectedElement = null;
    hidePropertyEditor();
    updateStats();
  }
});

document.getElementById("export-btn").addEventListener("click", () => {
  exportToYAML();
});

document.getElementById("import-btn").addEventListener("click", () => {
  document.getElementById("file-input").click();
});

document.getElementById("file-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) {
    importFromYAML(file);
    e.target.value = ""; // Reset input
  }
});

document.getElementById("scale-input").addEventListener("input", (e) => {
  pixelsPerMeter = parseInt(e.target.value) || 50;
  document.getElementById("pixels-per-meter").textContent = pixelsPerMeter;
  redraw();
});

document.getElementById("visualize-btn").addEventListener("click", () => {
  // Build the YAML data from current floor plan
  const data = {
    type: "indoor",
    pixelsPerMeter: pixelsPerMeter,
    maxCapacity:
      parseInt(document.getElementById("max-capacity").value) || 1000,
    expectedAttendance:
      parseInt(document.getElementById("expected-attendance").value) || 500,
    pathways: [],
    entries: [],
    exits: [],
    chokePoints: [],
    joints: [],
  };

  elements.forEach((el) => {
    if (el.type === "pathway") {
      data.pathways.push({
        id: el.id,
        name: el.name,
        width: el.width,
        points: el.points,
      });
    } else if (el.type === "entry") {
      data.entries.push({
        id: el.id,
        name: el.name,
        x: el.x,
        y: el.y,
        spawnRate: el.spawnRate,
      });
    } else if (el.type === "exit") {
      data.exits.push({
        id: el.id,
        name: el.name,
        x: el.x,
        y: el.y,
        exitRate: el.exitRate,
      });
    } else if (el.type === "choke") {
      data.chokePoints.push({ id: el.id, name: el.name, x: el.x, y: el.y });
    }
  });

  joints.forEach((joint) => {
    data.joints.push({
      id: joint.id,
      name: joint.name,
      x: joint.x,
      y: joint.y,
      connectedPathways: joint.connectedPathways,
    });
  });

  if (data.pathways.length === 0) {
    alert("Please create at least one pathway before running the visualizer.");
    return;
  }
  if (data.entries.length === 0 || data.exits.length === 0) {
    alert(
      "Please add at least one entry and one exit point before running the visualizer.",
    );
    return;
  }

  const yamlStr = convertToYAML(data);

  // Save and open visualizer
  fetch("/api/save-and-visualize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ yaml: yamlStr, filename: "floor_plan.yaml" }),
  })
    .then((response) => response.json())
    .then((result) => {
      if (result.success) {
        // If embedded in dashboard iframe, tell parent to navigate
        if (window.parent !== window) {
          window.parent.postMessage({
            type: 'raahi_navigate',
            path: '/visualizer',
            venuePath: result.filepath
          }, '*');
        } else {
          window.open(result.visualizer_url, "_blank");
        }
      } else {
        alert("Error saving floor plan: " + (result.error || "Unknown error"));
      }
    })
    .catch((error) => {
      alert("Error: " + error.message);
    });
});

// ==================== BACKGROUND IMAGE ====================

document.getElementById("bg-image-btn").addEventListener("click", () => {
  document.getElementById("bg-image-input").click();
});

document.getElementById("bg-image-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = (ev) => {
      bgImageDataUrl = ev.target.result;
      const img = new Image();
      img.onload = () => {
        bgImage = img;
        document.getElementById("bg-controls").style.display = "block";
        redraw();

        // Ask user: manual trace or AI analyze?
        const choice = confirm(
          "📷 Image loaded!\n\n" +
            "Click OK to use 🤖 AI Analysis (auto-detect pathways)\n" +
            "Click Cancel to use as background for manual tracing",
        );

        if (choice) {
          analyzeImageWithAI(bgImageDataUrl, file.type || "image/png");
        }
      };
      img.src = ev.target.result;
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }
});

function analyzeImageWithAI(dataUrl, mimeType) {
  const btn = document.getElementById("bg-image-btn");
  const originalText = btn.textContent;
  btn.textContent = "⏳ Analyzing...";
  btn.disabled = true;

  fetch("/api/analyze-image", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image: dataUrl, mimeType: mimeType }),
  })
    .then((response) => response.json())
    .then((result) => {
      btn.textContent = originalText;
      btn.disabled = false;

      if (result.success && result.floorPlan) {
        populateFromAI(result.floorPlan);
      } else {
        alert("AI Analysis failed: " + (result.error || "Unknown error"));
      }
    })
    .catch((error) => {
      btn.textContent = originalText;
      btn.disabled = false;
      alert("Error connecting to AI: " + error.message);
    });
}

function populateFromAI(floorPlan) {
  if (elements.length > 0) {
    if (
      !confirm(
        "AI found elements! This will replace your current floor plan. Continue?",
      )
    ) {
      return;
    }
  }

  elements = [];
  joints = [];
  pathwayCounter = 0;
  entryCounter = 0;
  exitCounter = 0;
  chokeCounter = 0;

  const scaleX = canvas.width / 100;
  const scaleY = canvas.height / 100;

  if (floorPlan.pathways) {
    floorPlan.pathways.forEach((p) => {
      const points = p.points.map((pt) => ({
        x: pt.x * scaleX,
        y: pt.y * scaleY,
      }));
      if (points.length >= 2) {
        elements.push({
          id: nextId++,
          type: "pathway",
          name: p.name || `Pathway ${++pathwayCounter}`,
          width: p.width || 2.0,
          points: points,
        });
      }
    });
  }

  if (floorPlan.entries) {
    floorPlan.entries.forEach((e) => {
      elements.push({
        id: nextId++,
        type: "entry",
        name: e.name || `Entry ${++entryCounter}`,
        x: e.x * scaleX,
        y: e.y * scaleY,
        spawnRate: e.spawnRate || 2.0,
      });
    });
  }

  if (floorPlan.exits) {
    floorPlan.exits.forEach((e) => {
      elements.push({
        id: nextId++,
        type: "exit",
        name: e.name || `Exit ${++exitCounter}`,
        x: e.x * scaleX,
        y: e.y * scaleY,
        exitRate: e.exitRate || 3.0,
      });
    });
  }

  if (floorPlan.chokePoints) {
    floorPlan.chokePoints.forEach((c) => {
      elements.push({
        id: nextId++,
        type: "choke",
        name: c.name || `Choke ${++chokeCounter}`,
        x: c.x * scaleX,
        y: c.y * scaleY,
      });
    });
  }

  detectJoints();
  redraw();
  updateStats();

  alert(
    `🤖 AI Analysis Complete!\n\n` +
      `Found:\n` +
      `• ${floorPlan.pathways?.length || 0} pathways\n` +
      `• ${floorPlan.entries?.length || 0} entry points\n` +
      `• ${floorPlan.exits?.length || 0} exit points\n` +
      `• ${floorPlan.chokePoints?.length || 0} choke points\n\n` +
      `You can now edit, move, or add more elements.`,
  );
}

document.getElementById("bg-opacity").addEventListener("input", (e) => {
  bgOpacity = parseInt(e.target.value) / 100;
  document.getElementById("bg-opacity-val").textContent = e.target.value + "%";
  redraw();
});

document.getElementById("bg-remove-btn").addEventListener("click", () => {
  bgImage = null;
  bgImageDataUrl = null;
  document.getElementById("bg-controls").style.display = "none";
  redraw();
});

// ==================== AUTO-DETECT CHOKE POINTS ====================
document.getElementById("auto-choke-btn").addEventListener("click", () => {
  const pathways = elements.filter((e) => e.type === "pathway");
  if (pathways.length === 0) {
    alert("Please create pathways first before auto-detecting choke points.");
    return;
  }

  // Remove existing choke points (ask first)
  const existingChokes = elements.filter((e) => e.type === "choke");
  if (existingChokes.length > 0) {
    if (
      !confirm(
        "This will remove existing choke points and generate new ones. Continue?",
      )
    ) {
      return;
    }
    elements = elements.filter((e) => e.type !== "choke");
  }

  const detectedChokes = autoDetectChokePoints();

  detectedChokes.forEach((choke) => {
    elements.push({
      id: nextId++,
      type: "choke",
      name: `Choke ${chokeCounter++}`,
      x: choke.x,
      y: choke.y,
      reason: choke.reason,
    });
  });

  redraw();
  updateStats();

  // Evaluate capacity risk (expected vs max and vs calculated area)
  const maxCap = parseInt(document.getElementById("max-capacity").value) || 1;
  const expectedCap =
    parseInt(document.getElementById("expected-attendance").value) || 1;
  let riskLevel = "High";
  if (expectedCap / maxCap < 0.5) riskLevel = "Low";
  else if (expectedCap / maxCap < 0.8) riskLevel = "Medium";

  alert(
    `Auto-detected ${detectedChokes.length} choke point(s) based on ${riskLevel} capacity risk:\n${detectedChokes.map((c) => "• " + c.reason).join("\n")}`,
  );
});

function autoDetectChokePoints() {
  const pathways = elements.filter((e) => e.type === "pathway");
  const detected = [];

  // Evaluate risk ratio to determine how aggressive choke point detection should be
  const maxCap = parseInt(document.getElementById("max-capacity").value) || 1;
  const expectedCap =
    parseInt(document.getElementById("expected-attendance").value) || 1;
  const capacityRatio = expectedCap / maxCap;

  // If very few people are expected, we only flag the most extreme bottlenecks
  const isLowRisk = capacityRatio < 0.5;
  const isMediumRisk = capacityRatio >= 0.5 && capacityRatio < 0.8;
  // const isHighRisk = capacityRatio >= 0.8; (implicit default for detection thresholds)

  const minDistance = isLowRisk ? 50 : 30; // Spread choke points out more if risk is low

  function isTooClose(x, y) {
    return detected.some((c) => Math.hypot(c.x - x, c.y - y) < minDistance);
  }

  // 1. NARROW PASSAGES: Find pathway segments narrower than average
  const allWidths = pathways.map((p) => p.width || 2.0);
  const avgWidth =
    allWidths.reduce((a, b) => a + b, 0) / (allWidths.length || 1);

  // Dynamic threshold based on risk
  const widthRatioLimit = isLowRisk ? 0.5 : isMediumRisk ? 0.6 : 0.7;
  const absoluteWidthLimit = isLowRisk ? 1.2 : 1.8;

  pathways.forEach((pathway) => {
    if (
      (pathway.width || 2.0) < avgWidth * widthRatioLimit &&
      (pathway.width || 2.0) < absoluteWidthLimit
    ) {
      // Place choke at midpoint of narrow pathway
      const midIdx = Math.floor(pathway.points.length / 2);
      const pt = pathway.points[midIdx];
      if (!isTooClose(pt.x, pt.y)) {
        detected.push({
          x: pt.x,
          y: pt.y,
          reason: `Narrow passage (${(pathway.width || 2.0).toFixed(1)}m width)`,
        });
      }
    }
  });

  // 2. SHARP TURNS: Find significant direction changes within pathways
  pathways.forEach((pathway) => {
    for (let i = 1; i < pathway.points.length - 1; i++) {
      const p1 = pathway.points[i - 1];
      const p2 = pathway.points[i];
      const p3 = pathway.points[i + 1];

      const angle1 = Math.atan2(p2.y - p1.y, p2.x - p1.x);
      const angle2 = Math.atan2(p3.y - p2.y, p3.x - p2.x);
      let angleDiff = Math.abs(angle2 - angle1);
      if (angleDiff > Math.PI) angleDiff = 2 * Math.PI - angleDiff;

      // Significant turn (> 50 degrees)
      if (angleDiff > (50 * Math.PI) / 180) {
        if (!isTooClose(p2.x, p2.y)) {
          const degrees = Math.round((angleDiff * 180) / Math.PI);
          detected.push({
            x: p2.x,
            y: p2.y,
            reason: `Sharp turn (${degrees}° bend)`,
          });
        }
      }
    }
  });

  // 3. CONVERGENCE ZONES: Joints where 3+ pathways meet
  joints.forEach((joint) => {
    if (joint.connectedPathways.length >= 3) {
      if (!isTooClose(joint.x, joint.y)) {
        detected.push({
          x: joint.x,
          y: joint.y,
          reason: `Convergence zone (${joint.connectedPathways.length} pathways meet)`,
        });
      }
    }
  });

  // 4. BOTTLENECKS: Where a wide pathway connects to a narrow one
  joints.forEach((joint) => {
    if (joint.connectedPathways.length >= 2) {
      const connectedPws = joint.connectedPathways
        .map((id) => pathways.find((p) => p.id === id))
        .filter((p) => p);

      if (connectedPws.length >= 2) {
        const widths = connectedPws.map((p) => p.width || 2.0);
        const maxW = Math.max(...widths);
        const minW = Math.min(...widths);

        // Width ratio > 1.5 means significant bottleneck; threshold scales with risk
        const ratioThreshold = isLowRisk ? 2.5 : isMediumRisk ? 1.8 : 1.5;
        if (maxW / minW > ratioThreshold && !isTooClose(joint.x, joint.y)) {
          detected.push({
            x: joint.x,
            y: joint.y,
            reason: `Bottleneck (${maxW.toFixed(1)}m → ${minW.toFixed(1)}m)`,
          });
        }
      }
    }
  });

  // 5. LONG CORRIDORS: Very long segments with no escape routes
  pathways.forEach((pathway) => {
    for (let i = 1; i < pathway.points.length; i++) {
      const p1 = pathway.points[i - 1];
      const p2 = pathway.points[i];
      const segLength = Math.hypot(p2.x - p1.x, p2.y - p1.y);
      const lengthMeters = segLength / pixelsPerMeter;

      // Long segment - place choke at midpoint (requires shorter segments for high risk)
      const lengthThreshold = isLowRisk ? 15 : isMediumRisk ? 10 : 8;
      if (lengthMeters > lengthThreshold) {
        const midX = (p1.x + p2.x) / 2;
        const midY = (p1.y + p2.y) / 2;
        if (!isTooClose(midX, midY)) {
          detected.push({
            x: midX,
            y: midY,
            reason: `Long corridor (${lengthMeters.toFixed(1)}m)`,
          });
        }
      }
    }
  });

  return detected;
}

// ==================== SMART SUGGESTIONS ====================

document.getElementById("suggest-btn").addEventListener("click", () => {
  const pathways = elements.filter((e) => e.type === "pathway");
  const entries = elements.filter((e) => e.type === "entry");
  const exits = elements.filter((e) => e.type === "exit");
  const chokes = elements.filter((e) => e.type === "choke");

  if (pathways.length === 0) {
    alert("Please create pathways first.");
    return;
  }
  if (entries.length === 0 || exits.length === 0) {
    alert("Please add entry and exit points first.");
    return;
  }

  suggestions = generateSuggestions(pathways, entries, exits, chokes);
  showSuggestionsPanel(suggestions);
  redraw();
});

document
  .getElementById("clear-suggestions-btn")
  .addEventListener("click", () => {
    suggestions = [];
    document.getElementById("suggestions-panel").style.display = "none";
    redraw();
  });

function generateSuggestions(pathways, entries, exits, chokes) {
  const result = [];

  // === BARRICADE SUGGESTIONS ===
  // Place barricades at entry points to control flow rate
  entries.forEach((entry) => {
    // Find the pathway the entry is on and suggest barricade slightly inside
    const nearest = getNearestPointOnPathway(entry.x, entry.y);
    if (nearest) {
      const dx = nearest.x - entry.x;
      const dy = nearest.y - entry.y;
      const dist = Math.hypot(dx, dy);
      // Place barricade 1.5m inside the entry
      const offset = Math.min(
        1.5 * pixelsPerMeter,
        dist > 0 ? 1.5 * pixelsPerMeter : 0,
      );
      result.push({
        type: "barricade",
        x: entry.x + (dist > 0 ? (dx / dist) * offset : 0),
        y: entry.y + (dist > 0 ? (dy / dist) * offset : offset),
        label: "🚧 Barricade",
        reason: `Near ${entry.name} — control incoming crowd flow rate`,
      });
    }
  });

  // Barricades at narrow passages (if choke points exist there)
  chokes.forEach((choke) => {
    result.push({
      type: "barricade",
      x: choke.x + 15,
      y: choke.y - 15,
      label: "🚧 Barricade",
      reason: `Near ${choke.name} — prevent overcrowding at bottleneck`,
    });
  });

  // === VOLUNTEER SUGGESTIONS ===
  // Place volunteers at junctions to direct crowd flow
  joints.forEach((joint) => {
    if (joint.connectedPathways.length >= 2) {
      result.push({
        type: "volunteer",
        x: joint.x,
        y: joint.y - 20,
        label: "🙋 Volunteer",
        reason: `At ${joint.name} — guide crowd at ${joint.connectedPathways.length}-way junction`,
      });
    }
  });

  // Volunteers at midpoints of long corridors
  pathways.forEach((pathway) => {
    for (let i = 1; i < pathway.points.length; i++) {
      const p1 = pathway.points[i - 1];
      const p2 = pathway.points[i];
      const segLength = Math.hypot(p2.x - p1.x, p2.y - p1.y) / pixelsPerMeter;

      if (segLength > 10) {
        result.push({
          type: "volunteer",
          x: (p1.x + p2.x) / 2,
          y: (p1.y + p2.y) / 2 - 20,
          label: "🙋 Volunteer",
          reason: `Along ${pathway.name} — monitor crowd flow in long corridor (${segLength.toFixed(0)}m)`,
        });
      }
    }
  });

  // === SECURITY SUGGESTIONS ===
  // Place security at exits for orderly evacuation
  exits.forEach((exit) => {
    result.push({
      type: "security",
      x: exit.x,
      y: exit.y - 25,
      label: "🛡️ Security",
      reason: `At ${exit.name} — ensure orderly exit flow and prevent counterflow`,
    });
  });

  // Security at high-risk choke points (sharp turns or convergences)
  chokes.forEach((choke) => {
    if (
      choke.reason &&
      (choke.reason.includes("Convergence") || choke.reason.includes("Sharp"))
    ) {
      result.push({
        type: "security",
        x: choke.x - 15,
        y: choke.y + 15,
        label: "🛡️ Security",
        reason: `Near ${choke.name} — high-risk area, prevent stampede`,
      });
    }
  });

  // If there are no choke-based security suggestions, add at choke points anyway
  const securityCount = result.filter((s) => s.type === "security").length;
  if (securityCount <= exits.length && chokes.length > 0) {
    // Add security at the most critical choke point
    const mainChoke = chokes[0];
    result.push({
      type: "security",
      x: mainChoke.x - 15,
      y: mainChoke.y + 15,
      label: "🛡️ Security",
      reason: `Near ${mainChoke.name} — primary bottleneck, crowd management needed`,
    });
  }

  return result;
}

function showSuggestionsPanel(suggestions) {
  const panel = document.getElementById("suggestions-panel");
  const content = document.getElementById("suggestions-content");

  const barricades = suggestions.filter((s) => s.type === "barricade");
  const volunteers = suggestions.filter((s) => s.type === "volunteer");
  const security = suggestions.filter((s) => s.type === "security");

  let html = "";

  if (barricades.length > 0) {
    html +=
      '<p style="font-size: 11px; color: #e67e22; margin: 8px 0 4px 0; font-weight: bold;">BARRICADES (' +
      barricades.length +
      ")</p>";
    barricades.forEach((s) => {
      html += `<div class="suggestion-item suggestion-barricade">
                <strong>${s.label}</strong>${s.reason}
            </div>`;
    });
  }

  if (volunteers.length > 0) {
    html +=
      '<p style="font-size: 11px; color: #3498db; margin: 8px 0 4px 0; font-weight: bold;">VOLUNTEERS (' +
      volunteers.length +
      ")</p>";
    volunteers.forEach((s) => {
      html += `<div class="suggestion-item suggestion-volunteer">
                <strong>${s.label}</strong>${s.reason}
            </div>`;
    });
  }

  if (security.length > 0) {
    html +=
      '<p style="font-size: 11px; color: #e74c3c; margin: 8px 0 4px 0; font-weight: bold;">SECURITY (' +
      security.length +
      ")</p>";
    security.forEach((s) => {
      html += `<div class="suggestion-item suggestion-security">
                <strong>${s.label}</strong>${s.reason}
            </div>`;
    });
  }

  content.innerHTML = html;
  panel.style.display = "block";
}

// Keyboard events
document.addEventListener("keydown", (e) => {
  if (e.key === "Shift") {
    isShiftPressed = true;
  }
});

document.addEventListener("keyup", (e) => {
  if (e.key === "Shift") {
    isShiftPressed = false;
  }
});

canvas.addEventListener("mousedown", (e) => {
  const rect = canvas.getBoundingClientRect();
  let x = e.clientX - rect.left;
  let y = e.clientY - rect.top;

  if (currentTool === "select") {
    // Check if clicking on an element
    const element = findElementNear(x, y);
    if (element) {
      selectElement(element);
      selectedPoint = findPointNear(x, y);
      if (selectedPoint) {
        isDragging = true;
      }
    } else {
      selectedElement = null;
      hidePropertyEditor();
    }
  } else if (isPathwayMode) {
    let finalX = x;
    let finalY = y;

    // Apply grid snapping if shift is pressed
    if (isShiftPressed) {
      finalX = Math.round(x / pixelsPerMeter) * pixelsPerMeter;
      finalY = Math.round(y / pixelsPerMeter) * pixelsPerMeter;
    } else if (currentPathway.length > 0) {
      // Angle snapping (old shift behavior, now always on unless grid snap)
      const lastPoint = currentPathway[currentPathway.length - 1];
      const snapped = snapToAngle(lastPoint.x, lastPoint.y, x, y);
      finalX = snapped.x;
      finalY = snapped.y;
    }

    currentPathway.push({ x: finalX, y: finalY });
    redraw();
  } else if (currentTool) {
    // Apply grid snapping if shift is pressed
    if (isShiftPressed) {
      x = Math.round(x / pixelsPerMeter) * pixelsPerMeter;
      y = Math.round(y / pixelsPerMeter) * pixelsPerMeter;
    }
    placePoint(x, y, currentTool);
  }
});

canvas.addEventListener("mousemove", (e) => {
  const rect = canvas.getBoundingClientRect();
  let x = e.clientX - rect.left;
  let y = e.clientY - rect.top;

  if (currentTool === "select" && isDragging && selectedPoint) {
    // Apply grid snapping if shift is pressed
    if (isShiftPressed) {
      x = Math.round(x / pixelsPerMeter) * pixelsPerMeter;
      y = Math.round(y / pixelsPerMeter) * pixelsPerMeter;
    }

    // If moving a non-pathway point (entry/exit/choke), constrain to pathway
    if (
      selectedElement &&
      (selectedElement.type === "entry" ||
        selectedElement.type === "exit" ||
        selectedElement.type === "choke")
    ) {
      const nearest = getNearestPointOnPathway(x, y);
      if (nearest) {
        x = nearest.x;
        y = nearest.y;
      }
    }

    // Update point position
    selectedPoint.x = x;
    selectedPoint.y = y;
    redraw();
  } else if (isPathwayMode && currentPathway.length > 0) {
    // Show preview line
    previewPoint = { x, y };
    if (isShiftPressed) {
      // Grid snapping
      previewPoint.x = Math.round(x / pixelsPerMeter) * pixelsPerMeter;
      previewPoint.y = Math.round(y / pixelsPerMeter) * pixelsPerMeter;
    } else {
      // Angle snapping
      const lastPoint = currentPathway[currentPathway.length - 1];
      const snapped = snapToAngle(lastPoint.x, lastPoint.y, x, y);
      previewPoint = snapped;
    }
    redraw();
  }
});

canvas.addEventListener("mouseup", (e) => {
  if (isDragging) {
    isDragging = false;
    selectedPoint = null;
    detectJoints(); // Re-detect joints after movement
    redraw(); // Ensure colors update after movement
  }
});

canvas.addEventListener("mouseleave", (e) => {
  previewPoint = null;
  redraw();
});

canvas.addEventListener("dblclick", (e) => {
  if (isPathwayMode && currentPathway.length > 1) {
    previewPoint = null;
    finishPathway();
  }
});

function finishPathway() {
  if (currentPathway.length > 1) {
    elements.push({
      id: nextId++,
      type: "pathway",
      name: `Pathway ${pathwayCounter++}`,
      width: 2.0,
      points: [...currentPathway],
    });
    currentPathway = [];
    detectJoints(); // Auto-detect joints after adding pathway
    redraw();
    updateStats();
  }
}

function placePoint(x, y, type) {
  // Validate entry, exit, and choke points must be on pathway
  if (type === "choke" || type === "entry" || type === "exit") {
    if (!isPointOnAnyPathway(x, y)) {
      const typeLabel = type.charAt(0).toUpperCase() + type.slice(1);
      alert(`${typeLabel} points must be placed on a pathway!`);
      return;
    }
  }

  const element = { id: nextId++, type, x, y };

  if (type === "entry") {
    element.name = `Entry ${entryCounter++}`;
    element.spawnRate = 1.0;
  } else if (type === "exit") {
    element.name = `Exit ${exitCounter++}`;
    element.exitRate = 1.0;
  } else if (type === "choke") {
    element.name = `Choke ${chokeCounter++}`;
  }

  elements.push(element);
  redraw();
  updateStats();
}

function findElementNear(x, y, threshold = 15) {
  // Check joints first (they take priority for selection)
  for (let joint of joints) {
    if (Math.hypot(joint.x - x, joint.y - y) < threshold) {
      return joint;
    }
  }

  // Check all elements
  for (let el of elements) {
    if (el.type === "pathway") {
      for (let point of el.points) {
        if (Math.hypot(point.x - x, point.y - y) < threshold) {
          return el;
        }
      }
    } else if (el.x !== undefined && el.y !== undefined) {
      if (Math.hypot(el.x - x, el.y - y) < threshold) {
        return el;
      }
    }
  }
  return null;
}

function findPointNear(x, y, threshold = 10) {
  // Check pathway points
  for (let el of elements) {
    if (el.type === "pathway") {
      for (let point of el.points) {
        if (Math.hypot(point.x - x, point.y - y) < threshold) {
          return point;
        }
      }
    } else if (el.x !== undefined && el.y !== undefined) {
      if (Math.hypot(el.x - x, el.y - y) < threshold) {
        return el;
      }
    }
  }
  return null;
}

function isPointOnAnyPathway(x, y, threshold = 20) {
  for (let el of elements) {
    if (el.type === "pathway") {
      for (let i = 1; i < el.points.length; i++) {
        const p1 = el.points[i - 1];
        const p2 = el.points[i];
        const dist = distanceToSegment(x, y, p1.x, p1.y, p2.x, p2.y);
        if (dist < threshold) {
          return true;
        }
      }
    }
  }
  return false;
}

function getNearestPointOnPathway(x, y) {
  let minDist = Infinity;
  let nearestPoint = null;

  for (let el of elements) {
    if (el.type === "pathway") {
      for (let i = 1; i < el.points.length; i++) {
        const p1 = el.points[i - 1];
        const p2 = el.points[i];
        const point = nearestPointOnSegment(x, y, p1.x, p1.y, p2.x, p2.y);
        const dist = Math.hypot(point.x - x, point.y - y);

        if (dist < minDist) {
          minDist = dist;
          nearestPoint = point;
        }
      }
    }
  }

  return nearestPoint;
}

function nearestPointOnSegment(px, py, x1, y1, x2, y2) {
  const A = px - x1;
  const B = py - y1;
  const C = x2 - x1;
  const D = y2 - y1;
  const dot = A * C + B * D;
  const lenSq = C * C + D * D;
  let param = -1;
  if (lenSq !== 0) param = dot / lenSq;

  let xx, yy;
  if (param < 0) {
    xx = x1;
    yy = y1;
  } else if (param > 1) {
    xx = x2;
    yy = y2;
  } else {
    xx = x1 + param * C;
    yy = y1 + param * D;
  }

  return { x: xx, y: yy };
}

function distanceToSegment(px, py, x1, y1, x2, y2) {
  const A = px - x1;
  const B = py - y1;
  const C = x2 - x1;
  const D = y2 - y1;
  const dot = A * C + B * D;
  const lenSq = C * C + D * D;
  let param = -1;
  if (lenSq !== 0) param = dot / lenSq;

  let xx, yy;
  if (param < 0) {
    xx = x1;
    yy = y1;
  } else if (param > 1) {
    xx = x2;
    yy = y2;
  } else {
    xx = x1 + param * C;
    yy = y1 + param * D;
  }

  const dx = px - xx;
  const dy = py - yy;
  return Math.sqrt(dx * dx + dy * dy);
}

function getLargestPathwayNetwork() {
  if (elements.filter((e) => e.type === "pathway").length === 0) return [];

  // Build adjacency list
  const pathways = elements.filter((e) => e.type === "pathway");
  const networks = [];
  const visited = new Set();

  for (let pathway of pathways) {
    if (visited.has(pathway.id)) continue;

    const network = [];
    const queue = [pathway];
    visited.add(pathway.id);

    while (queue.length > 0) {
      const current = queue.shift();
      network.push(current);

      // Find connected pathways
      for (let other of pathways) {
        if (visited.has(other.id)) continue;
        if (arePathwaysConnected(current, other)) {
          visited.add(other.id);
          queue.push(other);
        }
      }
    }

    networks.push(network);
  }

  // Return largest network
  return networks.reduce(
    (largest, current) => (current.length > largest.length ? current : largest),
    [],
  );
}

function arePathwaysConnected(p1, p2, threshold = 15) {
  // Check if any endpoint of p1 is close to any endpoint of p2
  const p1Start = p1.points[0];
  const p1End = p1.points[p1.points.length - 1];
  const p2Start = p2.points[0];
  const p2End = p2.points[p2.points.length - 1];

  return (
    Math.hypot(p1Start.x - p2Start.x, p1Start.y - p2Start.y) < threshold ||
    Math.hypot(p1Start.x - p2End.x, p1Start.y - p2End.y) < threshold ||
    Math.hypot(p1End.x - p2Start.x, p1End.y - p2Start.y) < threshold ||
    Math.hypot(p1End.x - p2End.x, p1End.y - p2End.y) < threshold ||
    arePathwaysConnectedViaJoint(p1, p2)
  );
}

function arePathwaysConnectedViaJoint(p1, p2) {
  // Check if both pathways share a joint
  for (let joint of joints) {
    const p1Connected = joint.connectedPathways.includes(p1.id);
    const p2Connected = joint.connectedPathways.includes(p2.id);
    if (p1Connected && p2Connected) {
      return true;
    }
  }
  return false;
}

function detectJoints() {
  joints = [];
  jointCounter = 1;

  const pathways = elements.filter((e) => e.type === "pathway");
  const jointThreshold = 15; // pixels

  // Check for endpoint connections (where pathways meet at ends)
  const endpointJoints = new Map(); // key: "x,y", value: {x, y, pathwayIds: []}

  for (let pathway of pathways) {
    const startPoint = pathway.points[0];
    const endPoint = pathway.points[pathway.points.length - 1];

    // Check start point
    let foundStart = false;
    for (let [key, joint] of endpointJoints) {
      if (
        Math.hypot(joint.x - startPoint.x, joint.y - startPoint.y) <
        jointThreshold
      ) {
        joint.connectedPathways.push(pathway.id);
        joint.x = (joint.x + startPoint.x) / 2; // Average position
        joint.y = (joint.y + startPoint.y) / 2;
        foundStart = true;
        break;
      }
    }
    if (!foundStart) {
      endpointJoints.set(`${startPoint.x},${startPoint.y}`, {
        x: startPoint.x,
        y: startPoint.y,
        connectedPathways: [pathway.id],
      });
    }

    // Check end point
    let foundEnd = false;
    for (let [key, joint] of endpointJoints) {
      if (
        Math.hypot(joint.x - endPoint.x, joint.y - endPoint.y) < jointThreshold
      ) {
        if (!joint.connectedPathways.includes(pathway.id)) {
          joint.connectedPathways.push(pathway.id);
          joint.x = (joint.x + endPoint.x) / 2;
          joint.y = (joint.y + endPoint.y) / 2;
        }
        foundEnd = true;
        break;
      }
    }
    if (!foundEnd) {
      endpointJoints.set(`${endPoint.x},${endPoint.y}`, {
        x: endPoint.x,
        y: endPoint.y,
        connectedPathways: [pathway.id],
      });
    }
  }

  // Check for segment intersections (where pathways cross each other)
  for (let i = 0; i < pathways.length; i++) {
    for (let j = i + 1; j < pathways.length; j++) {
      const p1 = pathways[i];
      const p2 = pathways[j];

      // Check all segment pairs for intersection
      for (let a = 1; a < p1.points.length; a++) {
        for (let b = 1; b < p2.points.length; b++) {
          const intersection = getLineIntersection(
            p1.points[a - 1].x,
            p1.points[a - 1].y,
            p1.points[a].x,
            p1.points[a].y,
            p2.points[b - 1].x,
            p2.points[b - 1].y,
            p2.points[b].x,
            p2.points[b].y,
          );

          if (intersection) {
            // Check if this intersection is already near an existing joint
            let existingJoint = null;
            for (let [key, joint] of endpointJoints) {
              if (
                Math.hypot(joint.x - intersection.x, joint.y - intersection.y) <
                jointThreshold
              ) {
                existingJoint = joint;
                break;
              }
            }

            if (existingJoint) {
              if (!existingJoint.connectedPathways.includes(p1.id)) {
                existingJoint.connectedPathways.push(p1.id);
              }
              if (!existingJoint.connectedPathways.includes(p2.id)) {
                existingJoint.connectedPathways.push(p2.id);
              }
            } else {
              endpointJoints.set(`int_${intersection.x},${intersection.y}`, {
                x: intersection.x,
                y: intersection.y,
                connectedPathways: [p1.id, p2.id],
              });
            }
          }
        }
      }
    }
  }

  // Check for T-junctions (where one pathway's endpoint meets another pathway's segment)
  for (let i = 0; i < pathways.length; i++) {
    for (let j = 0; j < pathways.length; j++) {
      if (i === j) continue;

      const p1 = pathways[i]; // Check endpoints of this pathway
      const p2 = pathways[j]; // Against segments of this pathway

      const endpoints = [p1.points[0], p1.points[p1.points.length - 1]];

      for (let endpoint of endpoints) {
        // Check if endpoint is near any segment of p2
        for (let b = 1; b < p2.points.length; b++) {
          const segStart = p2.points[b - 1];
          const segEnd = p2.points[b];

          const dist = distanceToSegment(
            endpoint.x,
            endpoint.y,
            segStart.x,
            segStart.y,
            segEnd.x,
            segEnd.y,
          );

          if (dist < jointThreshold) {
            // Find the nearest point on the segment
            const nearestPt = nearestPointOnSegment(
              endpoint.x,
              endpoint.y,
              segStart.x,
              segStart.y,
              segEnd.x,
              segEnd.y,
            );

            // Check if this is already near an existing joint
            let existingJoint = null;
            for (let [key, joint] of endpointJoints) {
              if (
                Math.hypot(joint.x - nearestPt.x, joint.y - nearestPt.y) <
                jointThreshold
              ) {
                existingJoint = joint;
                break;
              }
            }

            if (existingJoint) {
              if (!existingJoint.connectedPathways.includes(p1.id)) {
                existingJoint.connectedPathways.push(p1.id);
              }
              if (!existingJoint.connectedPathways.includes(p2.id)) {
                existingJoint.connectedPathways.push(p2.id);
              }
            } else {
              endpointJoints.set(`tjunc_${nearestPt.x},${nearestPt.y}`, {
                x: nearestPt.x,
                y: nearestPt.y,
                connectedPathways: [p1.id, p2.id],
              });
            }
          }
        }
      }
    }
  }

  // Convert to joints array (only keep joints with 2+ pathways)
  for (let [key, joint] of endpointJoints) {
    if (joint.connectedPathways.length >= 2) {
      joints.push({
        id: nextId++,
        name: `Joint ${jointCounter++}`,
        x: joint.x,
        y: joint.y,
        connectedPathways: joint.connectedPathways,
      });
    }
  }
}

function getLineIntersection(x1, y1, x2, y2, x3, y3, x4, y4) {
  const denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
  if (Math.abs(denom) < 0.0001) return null; // Lines are parallel

  const t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom;
  const u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom;

  // Check if intersection is within both line segments
  if (t >= 0.01 && t <= 0.99 && u >= 0.01 && u <= 0.99) {
    return {
      x: x1 + t * (x2 - x1),
      y: y1 + t * (y2 - y1),
    };
  }
  return null;
}

function selectElement(element) {
  selectedElement = element;
  showPropertyEditor(element);
}

function showPropertyEditor(element) {
  const editor = document.getElementById("property-editor");
  const content = document.getElementById("property-content");

  content.innerHTML = "";

  if (element.type === "pathway") {
    content.innerHTML = `
            <div class="property-group">
                <label>Name:</label>
                <input type="text" id="prop-name" value="${element.name}">
            </div>
            <div class="property-group">
                <label>Width (meters):</label>
                <input type="number" id="prop-width" value="${element.width}" min="0.5" max="10" step="0.1">
            </div>
            <button class="delete-btn" onclick="deleteSelectedElement()">Delete Pathway</button>
        `;
  } else if (element.type === "entry") {
    content.innerHTML = `
            <div class="property-group">
                <label>Name:</label>
                <input type="text" id="prop-name" value="${element.name}">
            </div>
            <div class="property-group">
                <label>Spawn Rate (people/sec):</label>
                <input type="number" id="prop-spawn-rate" value="${element.spawnRate}" min="0" step="0.1">
            </div>
            <button class="delete-btn" onclick="deleteSelectedElement()">Delete Entry</button>
        `;
  } else if (element.type === "exit") {
    content.innerHTML = `
            <div class="property-group">
                <label>Name:</label>
                <input type="text" id="prop-name" value="${element.name}">
            </div>
            <div class="property-group">
                <label>Exit Rate (people/sec):</label>
                <input type="number" id="prop-exit-rate" value="${element.exitRate}" min="0" step="0.1">
            </div>
            <button class="delete-btn" onclick="deleteSelectedElement()">Delete Exit</button>
        `;
  } else if (element.type === "choke") {
    content.innerHTML = `
            <div class="property-group">
                <label>Name:</label>
                <input type="text" id="prop-name" value="${element.name}">
            </div>
            <button class="delete-btn" onclick="deleteSelectedElement()">Delete Choke Point</button>
        `;
  } else if (element.type === "joint") {
    const pathwayNames = element.connectedPathways
      .map((id) => {
        const p = elements.find((e) => e.id === id);
        return p ? p.name : `Pathway ${id}`;
      })
      .join(", ");

    content.innerHTML = `
            <div class="property-group">
                <label>Name:</label>
                <input type="text" id="prop-name" value="${element.name}">
            </div>
            <div class="property-group">
                <label>Connected Pathways:</label>
                <p style="font-size: 12px; color: #bdc3c7;">${pathwayNames}</p>
            </div>
            <p style="font-size: 11px; color: #7f8c8d; margin-top: 10px;">Joints are auto-detected at pathway intersections</p>
        `;
  }

  // Add event listeners
  const nameInput = document.getElementById("prop-name");
  if (nameInput) {
    nameInput.addEventListener("input", (e) => {
      element.name = e.target.value;
    });
  }

  const widthInput = document.getElementById("prop-width");
  if (widthInput) {
    widthInput.addEventListener("input", (e) => {
      element.width = parseFloat(e.target.value);
      redraw();
    });
  }

  const spawnRateInput = document.getElementById("prop-spawn-rate");
  if (spawnRateInput) {
    spawnRateInput.addEventListener("input", (e) => {
      element.spawnRate = parseFloat(e.target.value);
    });
  }

  const exitRateInput = document.getElementById("prop-exit-rate");
  if (exitRateInput) {
    exitRateInput.addEventListener("input", (e) => {
      element.exitRate = parseFloat(e.target.value);
    });
  }

  editor.style.display = "block";
}

function hidePropertyEditor() {
  document.getElementById("property-editor").style.display = "none";
}

function deleteSelectedElement() {
  if (selectedElement) {
    elements = elements.filter((e) => e.id !== selectedElement.id);
    selectedElement = null;
    hidePropertyEditor();
    redraw();
    updateStats();
  }
}

function snapToAngle(x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const distance = Math.hypot(dx, dy);
  const angle = Math.atan2(dy, dx);

  // Snap to 15-degree increments
  const snapAngle = Math.round(angle / (Math.PI / 12)) * (Math.PI / 12);

  return {
    x: x1 + distance * Math.cos(snapAngle),
    y: y1 + distance * Math.sin(snapAngle),
  };
}

function pixelsToMeters(pixels) {
  return (pixels / pixelsPerMeter).toFixed(2);
}

function updateStats() {
  const pathwayCount = elements.filter((e) => e.type === "pathway").length;
  const entryCount = elements.filter((e) => e.type === "entry").length;
  const exitCount = elements.filter((e) => e.type === "exit").length;
  const chokeCount = elements.filter((e) => e.type === "choke").length;
  const jointCount = joints.length;

  document.getElementById("pathway-count").textContent = pathwayCount;
  document.getElementById("entry-count").textContent = entryCount;
  document.getElementById("exit-count").textContent = exitCount;
  document.getElementById("choke-count").textContent = chokeCount;

  // Update joint count if element exists
  const jointCountEl = document.getElementById("joint-count");
  if (jointCountEl) jointCountEl.textContent = jointCount;

  // Calculate physical capacity of the drawn pathways
  let totalArea = 0;
  elements
    .filter((e) => e.type === "pathway")
    .forEach((p) => {
      let lengthPixels = 0;
      for (let i = 1; i < p.points.length; i++) {
        lengthPixels += Math.hypot(
          p.points[i].x - p.points[i - 1].x,
          p.points[i].y - p.points[i - 1].y,
        );
      }
      const lengthMeters = lengthPixels / pixelsPerMeter;
      totalArea += lengthMeters * (p.width || 2.0);
    });

  const physicalCapacity = Math.round(totalArea * 2);

  // Update the Risk Density UI based on user inputs vs physical capacity
  const maxCapacityInput = document.getElementById("max-capacity");
  const expectedAttendanceInput = document.getElementById(
    "expected-attendance",
  );
  const riskSpan = document.getElementById("density-risk");

  if (maxCapacityInput && expectedAttendanceInput && riskSpan) {
    const maxVal = parseInt(maxCapacityInput.value) || 1;
    const expectVal = parseInt(expectedAttendanceInput.value) || 0;

    let ratio = expectVal / maxVal;

    // Also factor in the drawn physical pathways if they are very small
    if (physicalCapacity > 0 && expectVal > physicalCapacity * 1.5) {
      ratio = 1.0; // Artificial risk spike because there are too many people for drawn pathways
    }

    const percent = Math.round(ratio * 100);

    if (ratio < 0.5) {
      riskSpan.textContent = `Low (${percent}%)`;
      riskSpan.style.color = "#27ae60"; // Green
    } else if (ratio < 0.8) {
      riskSpan.textContent = `Medium (${percent}%)`;
      riskSpan.style.color = "#f39c12"; // Orange
    } else {
      riskSpan.textContent = `High (${percent}%)`;
      riskSpan.style.color = "#c0392b"; // Red
    }
  }
}

// Add event listeners to input fields to trigger stats update on change
document.addEventListener("DOMContentLoaded", () => {
  const maxCap = document.getElementById("max-capacity");
  const expAtt = document.getElementById("expected-attendance");
  if (maxCap) maxCap.addEventListener("input", updateStats);
  if (expAtt) expAtt.addEventListener("input", updateStats);
});

function redraw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Draw grid
  drawGrid();

  // Draw background image if loaded
  if (bgImage) {
    ctx.save();
    ctx.globalAlpha = bgOpacity;
    // Scale image to fit canvas while preserving aspect ratio
    const imgAspect = bgImage.width / bgImage.height;
    const canvasAspect = canvas.width / canvas.height;
    let drawW, drawH, drawX, drawY;
    if (imgAspect > canvasAspect) {
      drawW = canvas.width;
      drawH = canvas.width / imgAspect;
      drawX = 0;
      drawY = (canvas.height - drawH) / 2;
    } else {
      drawH = canvas.height;
      drawW = canvas.height * imgAspect;
      drawX = (canvas.width - drawW) / 2;
      drawY = 0;
    }
    ctx.drawImage(bgImage, drawX, drawY, drawW, drawH);
    ctx.restore();
  }

  // Get largest pathway network
  const largestNetwork = getLargestPathwayNetwork();
  const largestNetworkIds = new Set(largestNetwork.map((p) => p.id));

  // Draw elements
  elements.forEach((el) => {
    if (el.type === "pathway") {
      const isConnected = largestNetworkIds.has(el.id);
      drawPathway(el.points, false, el.width || 2.0, isConnected);
    } else if (el.type === "entry") {
      ctx.beginPath();
      ctx.arc(el.x, el.y, 10, 0, 2 * Math.PI);
      ctx.fillStyle = "#27ae60";
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.lineWidth = 1;
    } else if (el.type === "exit") {
      ctx.beginPath();
      ctx.arc(el.x, el.y, 10, 0, 2 * Math.PI);
      ctx.fillStyle = "#e74c3c";
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.lineWidth = 1;
    } else if (el.type === "choke") {
      ctx.beginPath();
      ctx.moveTo(el.x, el.y - 12);
      ctx.lineTo(el.x - 10, el.y + 10);
      ctx.lineTo(el.x + 10, el.y + 10);
      ctx.closePath();
      ctx.fillStyle = "#f39c12";
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.lineWidth = 1;
    }
  });

  // Draw joints
  joints.forEach((joint) => {
    const size = 8 + joint.connectedPathways.length * 2; // Size based on connections
    ctx.beginPath();
    ctx.arc(joint.x, joint.y, size, 0, 2 * Math.PI);
    ctx.fillStyle = "#9b59b6"; // Purple for joints
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw connection count
    ctx.fillStyle = "#fff";
    ctx.font = "bold 10px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(joint.connectedPathways.length, joint.x, joint.y);
    ctx.lineWidth = 1;
  });

  // Draw current pathway being created
  if (currentPathway.length > 0) {
    drawPathway(currentPathway, true, 2.0, false);

    // Draw preview line
    if (previewPoint) {
      const lastPoint = currentPathway[currentPathway.length - 1];
      ctx.beginPath();
      ctx.moveTo(lastPoint.x, lastPoint.y);
      ctx.lineTo(previewPoint.x, previewPoint.y);
      ctx.strokeStyle = "#3498db";
      ctx.lineWidth = 3;
      ctx.setLineDash([5, 5]);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.lineWidth = 1;

      // Draw distance label
      const distance = Math.hypot(
        previewPoint.x - lastPoint.x,
        previewPoint.y - lastPoint.y,
      );
      const meters = pixelsToMeters(distance);
      const midX = (lastPoint.x + previewPoint.x) / 2;
      const midY = (lastPoint.y + previewPoint.y) / 2;

      ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
      ctx.fillRect(midX - 25, midY - 12, 50, 24);
      ctx.fillStyle = "#2c3e50";
      ctx.font = "12px Arial";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(meters + "m", midX, midY);
    }
  }

  // Draw suggestion markers
  if (typeof suggestions !== "undefined" && suggestions.length > 0) {
    suggestions.forEach((s) => {
      const colors = {
        barricade: { bg: "#e67e22", border: "#d35400", emoji: "🚧" },
        volunteer: { bg: "#3498db", border: "#2980b9", emoji: "🙋" },
        security: { bg: "#e74c3c", border: "#c0392b", emoji: "🛡️" },
      };
      const style = colors[s.type] || colors.barricade;

      // Draw marker circle
      ctx.beginPath();
      ctx.arc(s.x, s.y, 14, 0, 2 * Math.PI);
      ctx.fillStyle = style.bg;
      ctx.globalAlpha = 0.85;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = style.border;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.lineWidth = 1;

      // Draw emoji
      ctx.font = "14px Arial";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(style.emoji, s.x, s.y);

      // Draw label
      ctx.font = "bold 10px Arial";
      ctx.fillStyle = style.bg;
      ctx.fillText(s.label, s.x, s.y - 22);
    });
  }
}

function drawGrid() {
  ctx.strokeStyle = "#bdc3c7";
  ctx.lineWidth = 0.5;

  // Draw vertical lines every meter
  for (let x = 0; x < canvas.width; x += pixelsPerMeter) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }

  // Draw horizontal lines every meter
  for (let y = 0; y < canvas.height; y += pixelsPerMeter) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }

  ctx.lineWidth = 1;
}

function drawPathway(points, isActive, width = 2.0, isConnected = false) {
  if (points.length < 1) return;

  // Draw the pathway line
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i++) {
    ctx.lineTo(points[i].x, points[i].y);
  }

  // Color based on connectivity
  if (isActive) {
    ctx.strokeStyle = "#3498db";
  } else if (isConnected) {
    ctx.strokeStyle = "#27ae60"; // Green for connected
  } else {
    ctx.strokeStyle = "#95a5a6"; // Gray for disconnected
  }

  // Width based on meter width
  ctx.lineWidth = (width * pixelsPerMeter) / 2; // Scale width
  ctx.stroke();
  ctx.lineWidth = 1;

  // Draw distance labels on segments
  if (points.length > 1 && !isActive) {
    for (let i = 1; i < points.length; i++) {
      const p1 = points[i - 1];
      const p2 = points[i];
      const distance = Math.hypot(p2.x - p1.x, p2.y - p1.y);
      const meters = pixelsToMeters(distance);
      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;

      ctx.fillStyle = "rgba(255, 255, 255, 0.8)";
      ctx.fillRect(midX - 20, midY - 10, 40, 20);
      ctx.fillStyle = "#2c3e50";
      ctx.font = "11px Arial";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(meters + "m", midX, midY);
    }
  }

  // Draw control points
  points.forEach((point, index) => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, 5, 0, 2 * Math.PI);
    ctx.fillStyle = isActive ? "#3498db" : "#2980b9";
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;
  });
}

function exportToYAML() {
  const data = {
    type: "indoor",
    pixelsPerMeter: pixelsPerMeter,
    maxCapacity:
      parseInt(document.getElementById("max-capacity").value) || 1000,
    expectedAttendance:
      parseInt(document.getElementById("expected-attendance").value) || 500,
    pathways: [],
    entries: [],
    exits: [],
    chokePoints: [],
    joints: [],
  };

  elements.forEach((el) => {
    if (el.type === "pathway") {
      data.pathways.push({
        id: el.id,
        name: el.name,
        width: el.width,
        points: el.points,
      });
    } else if (el.type === "entry") {
      data.entries.push({
        id: el.id,
        name: el.name,
        x: el.x,
        y: el.y,
        spawnRate: el.spawnRate,
      });
    } else if (el.type === "exit") {
      data.exits.push({
        id: el.id,
        name: el.name,
        x: el.x,
        y: el.y,
        exitRate: el.exitRate,
      });
    } else if (el.type === "choke") {
      data.chokePoints.push({
        id: el.id,
        name: el.name,
        x: el.x,
        y: el.y,
      });
    }
  });

  // Add joints
  joints.forEach((joint) => {
    data.joints.push({
      id: joint.id,
      name: joint.name,
      x: joint.x,
      y: joint.y,
      connectedPathways: joint.connectedPathways,
    });
  });

  const yamlStr = convertToYAML(data);
  const blob = new Blob([yamlStr], { type: "text/yaml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "floor_plan.yaml";
  a.click();
  URL.revokeObjectURL(url);
}

function convertToYAML(obj, indent = 0) {
  let yaml = "";
  const spaces = "  ".repeat(indent);

  for (let key in obj) {
    const value = obj[key];
    if (Array.isArray(value)) {
      yaml += `${spaces}${key}:\n`;
      value.forEach((item) => {
        if (typeof item === "object") {
          yaml += `${spaces}  -\n`;
          yaml += convertToYAML(item, indent + 2)
            .split("\n")
            .map((line) => (line ? "  " + line : ""))
            .join("\n");
        } else {
          yaml += `${spaces}  - ${item}\n`;
        }
      });
    } else if (typeof value === "object" && value !== null) {
      yaml += `${spaces}${key}:\n`;
      yaml += convertToYAML(value, indent + 1);
    } else {
      yaml += `${spaces}${key}: ${value}\n`;
    }
  }
  return yaml;
}

function importFromYAML(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const yamlText = e.target.result;
      const data = parseYAML(yamlText);

      elements = [];
      nextId = 1;
      pathwayCounter = 1;
      entryCounter = 1;
      exitCounter = 1;
      chokeCounter = 1;

      if (data.pixelsPerMeter) {
        pixelsPerMeter = data.pixelsPerMeter;
        document.getElementById("scale-input").value = pixelsPerMeter;
        document.getElementById("pixels-per-meter").textContent =
          pixelsPerMeter;
      }
      if (data.maxCapacity) {
        document.getElementById("max-capacity").value = data.maxCapacity;
      }
      if (data.expectedAttendance) {
        document.getElementById("expected-attendance").value =
          data.expectedAttendance;
      }

      if (data.pathways) {
        data.pathways.forEach((p) => {
          elements.push({
            id: nextId++,
            type: "pathway",
            name: p.name,
            width: p.width,
            points: p.points,
          });
          pathwayCounter++;
        });
      }

      if (data.entries) {
        data.entries.forEach((e) => {
          elements.push({
            id: nextId++,
            type: "entry",
            name: e.name,
            x: e.x,
            y: e.y,
            spawnRate: e.spawnRate,
          });
          entryCounter++;
        });
      }

      if (data.exits) {
        data.exits.forEach((e) => {
          elements.push({
            id: nextId++,
            type: "exit",
            name: e.name,
            x: e.x,
            y: e.y,
            exitRate: e.exitRate,
          });
          exitCounter++;
        });
      }

      if (data.chokePoints) {
        data.chokePoints.forEach((c) => {
          elements.push({
            id: nextId++,
            type: "choke",
            name: c.name,
            x: c.x,
            y: c.y,
          });
          chokeCounter++;
        });
      }

      detectJoints(); // Re-detect joints after import
      redraw();
      updateStats();
      alert("Floor plan imported successfully!");
    } catch (error) {
      alert("Error importing YAML file: " + error.message);
      console.error("YAML parse error:", error);
    }
  };
  reader.readAsText(file);
}

function parseYAML(yamlText) {
  // More robust YAML parser
  const lines = yamlText.split("\n");
  const result = {
    pixelsPerMeter: 50,
    pathways: [],
    entries: [],
    exits: [],
    chokePoints: [],
    joints: [],
  };

  let currentSection = null;
  let currentObject = null;
  let currentSubArray = null;
  let currentSubObject = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed || trimmed.startsWith("#")) continue;

    const indent = line.search(/\S/);

    // Top level key (indent 0)
    if (indent === 0 && trimmed.includes(":")) {
      const colonIndex = trimmed.indexOf(":");
      const key = trimmed.substring(0, colonIndex).trim();
      const value = trimmed.substring(colonIndex + 1).trim();

      if (value) {
        result[key] = isNaN(value) ? value : parseFloat(value);
      } else {
        currentSection = key;
      }
      currentObject = null;
      currentSubArray = null;
      currentSubObject = null;
    }
    // Array item start (indent 2, starts with -)
    else if (indent === 2 && trimmed.startsWith("-")) {
      currentObject = {};
      if (currentSection === "pathways") result.pathways.push(currentObject);
      else if (currentSection === "entries") result.entries.push(currentObject);
      else if (currentSection === "exits") result.exits.push(currentObject);
      else if (currentSection === "chokePoints")
        result.chokePoints.push(currentObject);
      else if (currentSection === "joints") result.joints.push(currentObject);
      currentSubArray = null;
      currentSubObject = null;
    }
    // Object property (indent 4-6)
    else if (
      (indent === 4 || indent === 6) &&
      trimmed.includes(":") &&
      !trimmed.startsWith("-") &&
      currentObject
    ) {
      const colonIndex = trimmed.indexOf(":");
      const key = trimmed.substring(0, colonIndex).trim();
      const value = trimmed.substring(colonIndex + 1).trim();

      if (value) {
        currentObject[key] = isNaN(value) ? value : parseFloat(value);
      } else {
        // Start of sub-array (like points or connectedPathways)
        currentObject[key] = [];
        currentSubArray = currentObject[key];
      }
      currentSubObject = null;
    }
    // Sub-array item (indent 8, starts with -)
    else if (indent === 8 && trimmed.startsWith("-") && currentSubArray) {
      const content = trimmed.substring(1).trim();

      if (content === "") {
        // Object will follow
        currentSubObject = {};
        currentSubArray.push(currentSubObject);
      } else {
        // Simple value
        currentSubArray.push(isNaN(content) ? content : parseFloat(content));
      }
    }
    // Sub-object property (indent 12)
    else if (indent === 12 && trimmed.includes(":") && currentSubObject) {
      const colonIndex = trimmed.indexOf(":");
      const key = trimmed.substring(0, colonIndex).trim();
      const value = trimmed.substring(colonIndex + 1).trim();
      currentSubObject[key] = isNaN(value) ? value : parseFloat(value);
    }
  }

  return result;
}

// Listen for messages from Raahi dashboard (parent window)
window.addEventListener('message', function(event) {
  if (!event.data || !event.data.type) return;

  if (event.data.type === 'raahi_set_capacity') {
    // Pre-fill capacity fields
    const maxCapEl = document.getElementById('max-capacity');
    const expCapEl = document.getElementById('expected-attendance');
    if (maxCapEl && event.data.maxCapacity) {
      maxCapEl.value = event.data.maxCapacity;
      maxCapEl.dispatchEvent(new Event('input'));
    }
    if (expCapEl && event.data.expectedAttendance) {
      expCapEl.value = event.data.expectedAttendance;
      expCapEl.dispatchEvent(new Event('input'));
    }
    console.log('[Raahi] Capacity pre-loaded:', event.data.maxCapacity);
  }

  if (event.data.type === 'raahi_load_image') {
    // Load background image from data URL
    const img = new Image();
    img.onload = function() {
      bgImage = img;
      bgImageDataUrl = event.data.dataUrl;
      bgOpacity = 0.5;
      const opacitySlider = document.getElementById('bg-opacity');
      if (opacitySlider) opacitySlider.value = 0.5;
      const removeBtn = document.getElementById('remove-bg');
      if (removeBtn) removeBtn.style.display = 'inline-block';
      redraw();
      console.log('[Raahi] Background image pre-loaded:', event.data.fileName);
    };
    img.src = event.data.dataUrl;
  }
});

// Initial draw
redraw();
updateStats();
