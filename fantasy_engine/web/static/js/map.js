/* Fantasy Engine — CK3-style live frontend.
 *
 * High-level flow:
 *   1. POST /api/sim/new → get civ list + political map URL.
 *   2. Load political-overlay PNG into the main canvas, pickmap PNG into an
 *      offscreen canvas for province → civ lookups.
 *   3. Poll /api/sim/state every ~600ms while the world is unpaused; the
 *      poll returns date/season/civ summaries/recent events.
 *   4. Click a province → resolve civ owner → fetch /api/sim/civ/<name> →
 *      populate ruler card + realm panel.
 *   5. Speed pips POST to /api/sim/control. Pause button toggles.
 *
 * The simulation is server-authoritative — the client never advances time
 * locally; it just renders the latest snapshot.
 */
(function () {
    "use strict";

    // ====================================================================
    // Config
    // ====================================================================

    const POLL_INTERVAL_MS = 600;
    const MIN_CELL_PIXELS = 0.5;   // hard floor — user can zoom out past cover-fit
    const MAX_CELL_PIXELS = 32;
    const ZOOM_STEP = 1.18;
    const DRAG_THRESHOLD_PX = 4;

    const MONTHS_SHORT = ["JAN", "FEB", "MAR", "AVR", "MAI", "JUN", "JUL", "AOÛ", "SEP", "OCT", "NOV", "DÉC"];

    // ====================================================================
    // Camera (world ↔ screen transforms)
    // ====================================================================

    class Camera {
        constructor(worldWidth, worldHeight, viewport) {
            this.worldWidth = worldWidth;
            this.worldHeight = worldHeight;
            this.viewport = viewport;
            this.centerX = worldWidth / 2;
            this.centerY = worldHeight / 2;
            this.cellPixels = this.coverFit();
        }
        // Smallest cellPixels that still fills the viewport edge-to-edge in
        // both axes — used as a hard floor for cellPixels so the background
        // never peeks through. Updated whenever the viewport resizes.
        coverFit() {
            const fitX = this.viewport[0] / this.worldWidth;
            const fitY = this.viewport[1] / this.worldHeight;
            return Math.max(MIN_CELL_PIXELS, Math.max(fitX, fitY));
        }
        screenToWorld(sx, sy) {
            const [vw, vh] = this.viewport;
            return [this.centerX + (sx - vw / 2) / this.cellPixels,
                    this.centerY + (sy - vh / 2) / this.cellPixels];
        }
        worldToScreen(wx, wy) {
            const [vw, vh] = this.viewport;
            return [(wx - this.centerX) * this.cellPixels + vw / 2,
                    (wy - this.centerY) * this.cellPixels + vh / 2];
        }
        pan(dx, dy) {
            this.centerX -= dx / this.cellPixels;
            this.centerY -= dy / this.cellPixels;
            this.clampCenter();
        }
        zoomAt(sx, sy, factor) {
            const before = this.screenToWorld(sx, sy);
            // Honour MIN/MAX so the user can zoom out past cover-fit (the
            // background reads as ocean blue, so the map "floats" cleanly).
            this.cellPixels = Math.max(MIN_CELL_PIXELS, Math.min(MAX_CELL_PIXELS, this.cellPixels * factor));
            const after = this.screenToWorld(sx, sy);
            this.centerX += before[0] - after[0];
            this.centerY += before[1] - after[1];
            this.clampCenter();
        }
        setViewport(vp) { this.viewport = vp; this.clampCenter(); }
        clampCenter() {
            const [vw, vh] = this.viewport;
            const halfW = vw / 2 / this.cellPixels;
            const halfH = vh / 2 / this.cellPixels;
            // Pin the camera so the visible window can never scroll past the
            // edge of the world — keeps the canvas full at all pan offsets.
            if (halfW * 2 >= this.worldWidth) {
                this.centerX = this.worldWidth / 2;
            } else {
                this.centerX = Math.max(halfW, Math.min(this.worldWidth - halfW, this.centerX));
            }
            if (halfH * 2 >= this.worldHeight) {
                this.centerY = this.worldHeight / 2;
            } else {
                this.centerY = Math.max(halfH, Math.min(this.worldHeight - halfH, this.centerY));
            }
        }
    }

    // ====================================================================
    // State
    // ====================================================================

    const state = {
        initial: null,        // /api/sim/initial response
        currentState: null,   // /api/sim/state — refreshed on poll
        selectedCiv: null,    // selected civ name
        selectedCivDetail: null,
        hoveredProvince: null,
        camera: null,
        mapImage: null,
        pickmapData: null,
        pickmapWidth: 0,
        pickmapHeight: 0,
        rulerTab: "family",
        provinceToCiv: null,  // provinceId → civName (precomputed from initial + civ details)
        politicalImageVersion: -1,  // last loaded political PNG version
        activeWarBorders: [],
        pauseRules: null,
        pauseRuleLabels: null,
    };

    const dom = {
        canvas: document.getElementById("map-canvas"),
        bootCurtain: document.getElementById("boot-curtain"),
        // ruler card
        rulerCard: document.getElementById("ruler-card"),
        rulerName: document.getElementById("ruler-name"),
        rulerTitles: document.getElementById("ruler-titles"),
        rulerDynasty: document.getElementById("ruler-dynasty"),
        rulerFaith: document.getElementById("ruler-faith"),
        rulerStats: document.getElementById("ruler-stats"),
        rulerTabBody: document.getElementById("ruler-tab-body"),
        rulerTabs: document.querySelectorAll(".rtab"),
        // resource strip
        rPopulation: document.getElementById("r-population"),
        rTreasury: document.getElementById("r-treasury"),
        rStability: document.getElementById("r-stability"),
        rLegitimacy: document.getElementById("r-legitimacy"),
        rMilitary: document.getElementById("r-military"),
        rWars: document.getElementById("r-wars"),
        // clock
        clockDay: document.getElementById("clock-day"),
        clockMonth: document.getElementById("clock-month"),
        clockYear: document.getElementById("clock-year"),
        clockStatus: document.getElementById("clock-status"),
        clockPause: document.getElementById("btn-pause"),
        clockSpeeds: document.getElementById("clock-speeds"),
        // seed
        seedInput: document.getElementById("seed-input"),
        forgeBtn: document.getElementById("btn-forge"),
        // realm panel
        realmPanel: document.getElementById("realm-panel"),
        realmTitle: document.getElementById("realm-title"),
        realmFlag: document.getElementById("realm-flag"),
        realmBody: document.getElementById("realm-body"),
        // chronicle
        chronicleFeed: document.getElementById("chronicle-feed"),
        chronicleCounter: document.getElementById("chronicle-counter"),
        // minimap
        minimapCanvas: document.getElementById("minimap-canvas"),
        minimapViewport: document.getElementById("minimap-viewport"),
        // banner
        pauseBanner: document.getElementById("pause-banner"),
        // ruler portrait container
        rulerPortrait: document.getElementById("ruler-portrait"),
        // pause-rules popover
        gearBtn: document.getElementById("btn-gear"),
        popover: document.getElementById("pause-popover"),
        popoverMajor: document.getElementById("pause-major-list"),
        popoverMinor: document.getElementById("pause-minor-list"),
        // person card
        personCard: document.getElementById("person-card"),
        personCardBody: document.getElementById("person-card-body"),
        personCardTitle: document.getElementById("person-title"),
        personCardClose: document.getElementById("person-close"),
    };
    const ctx = dom.canvas.getContext("2d");
    const minimapCtx = dom.minimapCanvas.getContext("2d");

    // ====================================================================
    // API
    // ====================================================================

    async function apiNew(seed) {
        const res = await fetch("/api/sim/new", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ seed }),
        });
        if (!res.ok) throw new Error(`new failed: ${res.status}`);
        return await res.json();
    }
    async function apiState() {
        const res = await fetch("/api/sim/state");
        if (!res.ok) throw new Error(`state failed: ${res.status}`);
        return await res.json();
    }
    async function apiControl(action, value) {
        const body = { action };
        if (value != null) body.value = value;
        const res = await fetch("/api/sim/control", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`control failed: ${res.status}`);
        return await res.json();
    }
    async function apiCiv(civName) {
        const res = await fetch(`/api/sim/civ/${encodeURIComponent(civName)}`);
        if (!res.ok) throw new Error(`civ failed: ${res.status}`);
        return await res.json();
    }
    async function apiPauseRules(rules) {
        const res = await fetch("/api/sim/pause-rules", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ rules }),
        });
        if (!res.ok) throw new Error(`pause-rules failed: ${res.status}`);
        return await res.json();
    }
    function loadImage(url) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error(`failed to load ${url}`));
            img.src = url;
        });
    }

    // ====================================================================
    // Boot
    // ====================================================================

    async function boot() {
        showCurtain(true);
        try {
            const seed = parseInt(dom.seedInput.value, 10) || 909;
            const initial = await apiNew(seed);
            await loadInitial(initial);
        } catch (e) {
            console.error(e);
        } finally {
            showCurtain(false);
        }
        startPolling();
    }

    async function loadInitial(initial) {
        state.initial = initial;
        state.selectedCiv = null;
        state.selectedCivDetail = null;
        state.politicalImageVersion = initial.state ? initial.state.political_image_version : 0;

        // Fetch the political map + pickmap. The political URL now carries
        // a `?v=N` so the version bump on each transfer cracks the cache.
        const stamp = Date.now();
        const politicalUrl = (initial.state && initial.state.political_image_url)
            || initial.image_url;
        const [mapImage, pickmapImage] = await Promise.all([
            loadImage(`${politicalUrl}&t=${stamp}`),
            loadImage(`${initial.pickmap_url}?t=${stamp}`),
        ]);
        state.mapImage = mapImage;

        const off = document.createElement("canvas");
        off.width = pickmapImage.naturalWidth;
        off.height = pickmapImage.naturalHeight;
        const offCtx = off.getContext("2d", { willReadFrequently: true });
        offCtx.drawImage(pickmapImage, 0, 0);
        state.pickmapData = offCtx.getImageData(0, 0, off.width, off.height);
        state.pickmapWidth = off.width;
        state.pickmapHeight = off.height;

        resizeCanvas();
        // Camera viewport is in CSS pixels (the unit drawImage uses after the
        // DPR setTransform). Using the canvas's buffer dimensions here would
        // break cover-fit on retina/zoomed displays.
        const rect = dom.canvas.getBoundingClientRect();
        state.camera = new Camera(initial.width, initial.height, [rect.width, rect.height]);

        // Build province → civ lookup from the full ownership array the
        // server ships in initial_payload. Falls back to per-civ samples if
        // the field is missing (older session).
        if (Array.isArray(initial.province_owners)) {
            setProvinceOwners(initial.province_owners);
        } else {
            // Legacy fallback path.
            state.provinceToCiv = new Map();
            const civDetails = await Promise.all(initial.civilizations.map(c => apiCiv(c.name)));
            civDetails.forEach((detail) => {
                for (const p of detail.provinces || []) {
                    state.provinceToCiv.set(p.id, detail.name);
                }
            });
        }

        applyState(initial.state);
        drawMinimap();
        renderMap();
        renderRealmPanel();
    }

    // ====================================================================
    // Polling loop
    // ====================================================================

    let pollTimer = null;
    function startPolling() {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(pollOnce, POLL_INTERVAL_MS);
        pollOnce();
    }
    async function pollOnce() {
        try {
            const s = await apiState();
            applyState(s);
        } catch (e) {
            // server might be restarting; quiet
        }
    }

    // ====================================================================
    // State application
    // ====================================================================

    function applyState(s) {
        state.currentState = s;
        state.activeWarBorders = s.active_war_borders || [];
        if (Array.isArray(s.province_owners)) {
            setProvinceOwners(s.province_owners);
        }
        // Pause rules — render the popover the first time we see them.
        if (s.pause_rules) {
            const changed = JSON.stringify(state.pauseRules) !== JSON.stringify(s.pause_rules)
                || JSON.stringify(state.pauseRuleLabels) !== JSON.stringify(s.pause_rule_labels);
            state.pauseRules = s.pause_rules;
            state.pauseRuleLabels = s.pause_rule_labels || state.pauseRuleLabels;
            if (changed) renderPausePopover();
        }
        // Reload political PNG if the server bumped the version (province
        // transfer happened). Don't block the UI — the old image keeps
        // showing until the new one loads.
        if (typeof s.political_image_version === "number"
            && s.political_image_version !== state.politicalImageVersion) {
            reloadPoliticalImage(s.political_image_url, s.political_image_version);
        }
        renderClock(s);
        renderResourceStrip(s);
        renderChronicle(s);
        renderRealmPanel();
        renderPauseBanner(s);
        renderMap();
        if (state.selectedCiv) {
            // Refresh the selected civ ledger if any of its summary fields changed.
            const summary = (s.civilizations || []).find(c => c.name === state.selectedCiv);
            if (summary) {
                refreshSelectedCivCard(summary);
            }
        }
    }

    function reloadPoliticalImage(url, version) {
        if (!url) return;
        const stamp = Date.now();
        const img = new Image();
        img.onload = () => {
            state.mapImage = img;
            state.politicalImageVersion = version;
            drawMinimap();
            renderMap();
        };
        img.onerror = () => { /* keep old image */ };
        img.src = `${url}&t=${stamp}`;
    }

    function renderClock(s) {
        const [day, month, year] = s.date.split("/");
        dom.clockDay.textContent = day;
        dom.clockMonth.textContent = MONTHS_SHORT[parseInt(month, 10) - 1] || month;
        dom.clockYear.textContent = year;
        dom.clockStatus.textContent = s.paused ? "Paused" : `Speed ${s.speed}`;
        dom.clockPause.classList.toggle("playing", s.paused);
        dom.clockPause.textContent = s.paused ? "▶" : "▮▮";
        // speed pips
        document.querySelectorAll(".pip").forEach(pip => {
            pip.classList.toggle("active", parseInt(pip.dataset.speed, 10) === s.speed);
        });
    }

    function renderResourceStrip(s) {
        // Aggregate world-level resource counts. If a civ is selected, prefer
        // that civ's stats so the strip doubles as "your realm" — CK3 style.
        let summary;
        if (state.selectedCiv) {
            summary = (s.civilizations || []).find(c => c.name === state.selectedCiv);
        }
        if (summary) {
            dom.rPopulation.textContent = formatThousands(summary.population);
            dom.rTreasury.textContent = formatThousands(summary.grain_stores + summary.food_stores);
            dom.rStability.textContent = pct(summary.stability);
            dom.rLegitimacy.textContent = pct(summary.legitimacy);
            dom.rMilitary.textContent = formatThousands(summary.weapons + summary.supply);
            dom.rWars.textContent = summary.at_war_with.length;
        } else {
            const civs = s.civilizations || [];
            const totalPop = civs.reduce((a, c) => a + c.population, 0);
            const totalGrain = civs.reduce((a, c) => a + c.grain_stores + c.food_stores, 0);
            const avgStab = civs.length ? civs.reduce((a, c) => a + c.stability, 0) / civs.length : 0;
            const avgLeg = civs.length ? civs.reduce((a, c) => a + c.legitimacy, 0) / civs.length : 0;
            const totalArms = civs.reduce((a, c) => a + c.weapons + c.supply, 0);
            const wars = (s.active_wars || []).length;
            dom.rPopulation.textContent = formatThousands(totalPop);
            dom.rTreasury.textContent = formatThousands(totalGrain);
            dom.rStability.textContent = pct(avgStab);
            dom.rLegitimacy.textContent = pct(avgLeg);
            dom.rMilitary.textContent = formatThousands(totalArms);
            dom.rWars.textContent = wars;
        }
    }

    let lastChronicleKey = "";
    function renderChronicle(s) {
        const events = s.events || [];
        // Avoid full re-render every poll: only redraw if the tail changed.
        const lastEv = events[events.length - 1];
        const key = lastEv ? `${lastEv.date}|${lastEv.label}|${lastEv.civilization}|${lastEv.details}` : "empty";
        if (key === lastChronicleKey) return;
        lastChronicleKey = key;

        dom.chronicleCounter.textContent = events.length;
        const html = events.slice().reverse().map(ev => `
            <li class="${ev.severity || ''}">
                <div class="chronicle-date">${ev.date}</div>
                <div class="chronicle-text">
                    <span class="chronicle-label">${escapeHtml(ev.label)}</span>
                    <span class="chronicle-civ">${escapeHtml(ev.civilization)}</span>
                    ${ev.other_civilization ? `<span class="chronicle-civ"> · ${escapeHtml(ev.other_civilization)}</span>` : ""}
                    <div>${escapeHtml(ev.details)}</div>
                </div>
            </li>
        `).join("");
        dom.chronicleFeed.innerHTML = html;
    }

    function renderRealmPanel() {
        if (!state.currentState) return;
        const civs = state.currentState.civilizations || [];
        const html = civs.map(c => {
            const isSel = c.name === state.selectedCiv;
            return `
                <div class="realm-row ${isSel ? "selected" : ""}" data-civ="${escapeAttr(c.name)}">
                    <div class="realm-swatch" style="background:${c.color}"></div>
                    <div>
                        <div class="realm-name">${escapeHtml(c.name)}</div>
                        <div style="font-family:var(--font-script);font-style:italic;font-size:11px;color:var(--ink-fade);">${escapeHtml(prettyId(c.region))} · ${escapeHtml(prettyId(c.terrain))}</div>
                    </div>
                    <div class="realm-ruler">${escapeHtml(c.ruler)}</div>
                    <div class="realm-warflag">${c.at_war_with.length ? "⚔" : ""}</div>
                </div>
            `;
        }).join("");
        dom.realmBody.innerHTML = html;
        dom.realmBody.querySelectorAll(".realm-row").forEach(el => {
            el.addEventListener("click", () => selectCiv(el.dataset.civ));
        });
    }

    function renderPauseBanner(s) {
        if (s.paused && s.pause_reason) {
            dom.pauseBanner.textContent = s.pause_reason;
            dom.pauseBanner.classList.add("visible");
        } else {
            dom.pauseBanner.classList.remove("visible");
        }
    }

    // ====================================================================
    // Pause-rules popover
    // ====================================================================

    const MAJOR_RULES = ["famine", "faction_coup", "war_declaration", "route_severed"];
    const MINOR_RULES = ["succession", "battle", "culture_split", "migration"];

    function renderPausePopover() {
        if (!state.pauseRules) return;
        const labels = state.pauseRuleLabels || {};
        const renderGroup = (target, keys) => {
            target.innerHTML = keys.map(k => {
                const checked = state.pauseRules[k] ? "checked" : "";
                const label = labels[k] || k;
                return `<li><label style="display:flex;align-items:center;gap:8px;flex:1;cursor:pointer;">
                    <input type="checkbox" data-rule="${k}" ${checked}>
                    <span>${escapeHtml(label)}</span>
                </label></li>`;
            }).join("");
            target.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                cb.addEventListener("change", async () => {
                    const rule = cb.dataset.rule;
                    const wantOn = cb.checked;
                    try {
                        const res = await apiPauseRules({ [rule]: wantOn });
                        state.pauseRules = res.rules;
                    } catch (e) {
                        cb.checked = !wantOn;
                    }
                });
            });
        };
        renderGroup(dom.popoverMajor, MAJOR_RULES);
        renderGroup(dom.popoverMinor, MINOR_RULES);
    }

    function togglePopover(open) {
        const willOpen = open === undefined ? dom.popover.hasAttribute("hidden") : open;
        if (willOpen) {
            dom.popover.removeAttribute("hidden");
            dom.gearBtn.classList.add("active");
        } else {
            dom.popover.setAttribute("hidden", "");
            dom.gearBtn.classList.remove("active");
        }
    }

    // ====================================================================
    // Civ selection / ruler card
    // ====================================================================

    async function selectCiv(civName) {
        state.selectedCiv = civName;
        try {
            state.selectedCivDetail = await apiCiv(civName);
        } catch (e) {
            console.error(e);
            return;
        }
        revealPanel(dom.rulerCard);
        revealPanel(dom.realmPanel);
        // Update province lookup table for any new provinces in this civ.
        if (state.provinceToCiv && state.selectedCivDetail.provinces) {
            for (const p of state.selectedCivDetail.provinces) {
                state.provinceToCiv.set(p.id, civName);
            }
        }
        renderRulerCard();
        renderRealmPanel();
        renderResourceStrip(state.currentState);
        renderMap();
    }

    function refreshSelectedCivCard(summary) {
        if (!state.selectedCivDetail) return;
        // Patch the live summary fields onto our cached detail so the ruler
        // card reflects the latest tick without a full re-fetch.
        Object.assign(state.selectedCivDetail, {
            ruler: summary.ruler,
            heir: summary.heir,
            population: summary.population,
            stability: summary.stability,
            legitimacy: summary.legitimacy,
            unrest: summary.unrest,
            at_war_with: summary.at_war_with,
            grain_stores: summary.grain_stores,
            food_stores: summary.food_stores,
            weapons: summary.weapons,
            supply: summary.supply,
        });
        renderRulerCard();
    }

    function renderRulerCard() {
        const c = state.selectedCivDetail;
        if (!c) {
            dom.rulerName.textContent = "No Sovereign";
            dom.rulerTitles.textContent = "—";
            dom.rulerDynasty.textContent = "—";
            dom.rulerFaith.textContent = "—";
            dom.rulerStats.innerHTML = "";
            dom.rulerPortrait.innerHTML = placeholderSvg(96);
            dom.rulerTabBody.innerHTML = `<p class="placeholder">Click a province or realm to inspect its sovereign.</p>`;
            return;
        }
        const ruler = c.court.ruler;
        dom.rulerName.textContent = ruler.name;
        dom.rulerTitles.textContent = `Sovereign of ${c.name}`;
        dom.rulerDynasty.textContent = ruler.dynasty ? `House ${prettyId(ruler.dynasty)}` : "—";
        dom.rulerFaith.textContent = `${prettyId(c.faith || c.culture)} · ${prettyId(c.culture)}`;
        // Procedural portrait based on ruler's deterministic agent_id.
        dom.rulerPortrait.innerHTML = renderPortrait(
            decoratePerson({ ...ruler, role: ruler.role || "Ruler" }, c),
            96,
        );

        dom.rulerStats.innerHTML = `
            ${statRow("Population", formatThousands(c.population))}
            ${statRow("Treasury", formatThousands(c.treasury || 0))}
            ${statRow("Stability", pct(c.stability))}
            ${statRow("Legitimacy", pct(c.legitimacy))}
            ${statRow("Unrest", pct(c.unrest))}
            ${statRow("Grain", formatThousands(c.grain_stores))}
            ${statRow("Food", formatThousands(c.food_stores))}
            ${statRow("Provinces", c.province_count || 0)}
            ${statRow("Schism", pct(c.schism_pressure || 0))}
            ${statRow("Wars", c.at_war_with.length)}
        `;
        renderRulerTabBody();
    }

    function statRow(key, val) {
        return `<div class="ruler-stat-row"><span class="key">${escapeHtml(key)}</span><span class="val">${escapeHtml(String(val))}</span></div>`;
    }

    function renderRulerTabBody() {
        const c = state.selectedCivDetail;
        if (!c) return;
        let html = "";
        if (state.rulerTab === "family") {
            html = renderFamilyTab(c);
        } else if (state.rulerTab === "court") {
            html = renderCourtTab(c);
        } else if (state.rulerTab === "factions") {
            html = renderFactionsTab(c);
        } else if (state.rulerTab === "diplomacy") {
            html = renderDiplomacyTab(c);
        }
        dom.rulerTabBody.innerHTML = html;
    }

    // Single delegated click handler on the tab body — survives every
    // innerHTML re-render (the per-row listeners we used before kept getting
    // dropped by polling rebuilds, so clicks silently failed). Walks up from
    // the click target to find the nearest .person-row[data-person] or
    // .relation-row[data-civ-name].
    if (dom.rulerTabBody) {
        dom.rulerTabBody.addEventListener("click", (event) => {
            const personRow = closestFromEventTarget(event, ".person-row[data-person]");
            if (personRow) {
                event.stopPropagation();
                try {
                    const person = JSON.parse(decodeURIComponent(personRow.dataset.person));
                    openPersonCard(person);
                } catch (e) { console.error("bad person payload", e); }
                return;
            }
            const relRow = closestFromEventTarget(event, ".relation-row[data-civ-name]");
            if (relRow) {
                event.stopPropagation();
                selectCiv(relRow.dataset.civName);
            }
        });
    }

    function renderFamilyTab(c) {
        const ruler = decoratePerson(c.court.ruler, c);
        const heir = decoratePerson(c.court.heir, c);
        const consort = c.court.consort ? decoratePerson(c.court.consort, c) : null;
        const parents = (ruler.parents && ruler.parents.length) ? ruler.parents : [];

        const consortBlock = consort
            ? personRow(consort, consort.gender === "male" ? "Consort · Husband" : "Consort · Wife")
            : `<p class="placeholder">Unwed.</p>`;

        const heirBlock = (heir && heir.name && heir.name !== "—")
            ? personRow(heir, "Heir Apparent" + (heir.relation_to_ruler ? " · " + heir.relation_to_ruler : ""))
            : `<p class="placeholder">No heir designated.</p>`;

        return `
            <h3 class="tab-section">Sovereign</h3>
            ${personRow(ruler, "Ruling")}
            ${ruler.heroic_title ? `<div style="font-family:var(--font-script);font-style:italic;color:var(--brass-dark);padding:0 4px 6px;">⚜ ${escapeHtml(ruler.heroic_title)}</div>` : ""}
            ${grudgesBlock(ruler.grudges)}

            <h3 class="tab-section">${consort && consort.gender === "male" ? "Husband" : "Wife"}</h3>
            ${consortBlock}

            <h3 class="tab-section">Heir Apparent</h3>
            ${heirBlock}
            ${heir && heir.dynasty && ruler.dynasty && heir.dynasty !== ruler.dynasty
                ? `<div style="font-family:var(--font-script);font-style:italic;color:var(--ink-fade);font-size:11px;padding:0 4px 6px;">Lineage of House ${escapeHtml(prettyId(heir.dynasty))} through the maternal line.</div>`
                : ""}

            ${parents.length ? `
                <h3 class="tab-section">Bloodline</h3>
                ${parents.map(p => {
                    const parent = decoratePerson({
                        name: p,
                        agent_id: p,
                        dynasty: ruler.dynasty,
                        culture: ruler.culture,
                        age: 60,
                        gender: ruler.gender,
                        role: "Parent",
                        relation_to_ruler: `Parent of ${ruler.name}`,
                    }, c);
                    const payload = encodeURIComponent(JSON.stringify(parent));
                    return `<div class="person-row" data-person="${payload}"${personRowStyle(parent)}><div class="person-portrait">${renderPortrait(parent, 34)}</div><div class="person-info"><div class="person-name">${escapeHtml(p)}</div><div class="person-role">Parent of ${escapeHtml(ruler.name)}</div></div></div>`;
                }).join("")}
            ` : `<h3 class="tab-section">Bloodline</h3><p class="placeholder">Lineage unrecorded.</p>`}
        `;
    }

    function renderCourtTab(c) {
        return `
            <h3 class="tab-section">Marshal</h3>
            ${personRow(c.court.general, "Commander of the host")}

            <h3 class="tab-section">Chancellor</h3>
            ${personRow(c.court.diplomat, "Voice of the realm")}

            ${c.court.steward ? `
                <h3 class="tab-section">Steward</h3>
                ${personRow(c.court.steward, "Keeper of coin")}
            ` : ""}

            <h3 class="tab-section">Heir</h3>
            ${(c.court.heir && c.court.heir.name && c.court.heir.name !== "—")
                ? personRow(c.court.heir, "Heir Apparent")
                : `<p class="placeholder">No heir designated.</p>`}
        `;
    }

    function renderFactionsTab(c) {
        if (!c.factions || !c.factions.length) {
            return `<p class="placeholder">The realm holds no organized factions.</p>`;
        }
        return c.factions.map(f => {
            // Build a person-shaped object from the faction leader so the
            // same Person Card flow applies.
            const leader = decoratePerson(
                f.leader_bio || { name: f.leader_name, dynasty: f.dynasty, role: f.name + " Leader" },
                c,
            );
            const payload = encodeURIComponent(JSON.stringify(leader));
            return `
                <div class="faction-row">
                    <div class="faction-name">${escapeHtml(f.name)}</div>
                    <div class="faction-leader person-row" data-person="${payload}"${personRowStyle(leader, "display:grid;grid-template-columns:34px 1fr;gap:8px;align-items:center;padding:4px 0;border:none;")}>
                        <div class="person-portrait">${renderPortrait(leader, 28)}</div>
                        <div>
                            <div class="person-name" style="font-size:12px;">${escapeHtml(f.leader_name)}</div>
                            <div class="person-role">${f.dynasty && f.dynasty !== "none" ? `House ${escapeHtml(prettyId(f.dynasty))}` : ""}</div>
                        </div>
                    </div>
                    <div style="font-family:var(--font-script);font-style:italic;color:var(--ink-fade);font-size:11px;margin-top:2px;">${escapeHtml(f.agenda)}</div>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <div class="pressure-bar" style="flex:1;"><div class="pressure-fill" style="width:${Math.min(100, Math.max(0, f.pressure * 100)).toFixed(1)}%;"></div></div>
                        <span class="pressure-num">${(f.pressure * 100).toFixed(0)}</span>
                    </div>
                </div>
            `;
        }).join("");
    }

    // Map a numerical relation score into a CK3-style keyword. Engine's
    // relations are roughly -100..+100; the engine seeds them in [-28..+18]
    // and lets memory/aid/war shift them, so the threshold band is calibrated
    // around what actually shows up in play.
    function relationCategory(value, atWar) {
        if (atWar) return { key: "atwar", label: "At War" };
        if (value >=  40) return { key: "ally",     label: "Ally" };
        if (value >=  10) return { key: "friendly", label: "Friendly" };
        if (value >  -10) return { key: "neutral",  label: "Neutral" };
        if (value >  -40) return { key: "hostile",  label: "Hostile" };
        return { key: "enemy", label: "Sworn Enemy" };
    }

    function renderDiplomacyTab(c) {
        if (!c.relations || !c.relations.length) {
            return `<p class="placeholder">The realm stands alone.</p>`;
        }
        const wars = new Set(c.at_war_with || []);
        return `
            <h3 class="tab-section">Foreign Standings</h3>
            ${c.relations.map(r => {
                const atWar = wars.has(r.with);
                const cat = relationCategory(r.value, atWar);
                const cls = r.value > 0 ? "pos" : r.value < 0 ? "neg" : "";
                return `<div class="relation-row" data-civ-name="${escapeAttr(r.with)}" style="cursor:pointer;">
                    <span><span class="relation-pill ${cat.key}">${cat.label}</span>${escapeHtml(r.with)}</span>
                    <span class="relation-val ${cls}">${r.value > 0 ? "+" : ""}${r.value}</span>
                </div>`;
            }).join("")}
        `;
    }

    function personRow(person, badge) {
        const enriched = decoratePerson(person, state.selectedCivDetail);
        const dyn = enriched.dynasty && enriched.dynasty !== "none" ? `House ${escapeHtml(prettyId(enriched.dynasty))}` : "";
        const meta = enriched.age ? `${enriched.age} yrs` : "";
        // Stash a JSON copy on the row so the click handler can pull a fully
        // populated person object (no need to round-trip the engine again).
        const payload = encodeURIComponent(JSON.stringify(enriched));
        return `
            <div class="person-row" data-person="${payload}"${personRowStyle(enriched)}>
                <div class="person-portrait">${renderPortrait(enriched, 34)}</div>
                <div class="person-info">
                    <div class="person-name">${escapeHtml(enriched.name)}</div>
                    <div class="person-role">${escapeHtml(badge || enriched.role || "")}${dyn ? " · " + dyn : ""}</div>
                </div>
                <div class="person-meta">${meta}</div>
            </div>
        `;
    }

    function recentEventsBlock(events) {
        if (!events || !events.length) return "";
        return `
            <div style="margin-top:8px;font-family:var(--font-script);font-size:11.5px;color:var(--ink-soft);">
                <div style="color:var(--brass-dark);font-family:var(--font-display);text-transform:uppercase;font-size:10px;letter-spacing:0.12em;margin-bottom:4px;">Recent</div>
                ${events.slice(0, 3).map(line => `<div style="margin:2px 0;line-height:1.3;">· ${escapeHtml(line)}</div>`).join("")}
            </div>
        `;
    }

    function grudgesBlock(grudges) {
        if (!grudges || !grudges.length) return "";
        return `
            <div style="margin-top:6px;font-size:11px;color:var(--oxblood);font-family:var(--font-script);font-style:italic;">
                Grudges: ${grudges.map(escapeHtml).join(", ")}
            </div>
        `;
    }

    // ====================================================================
    // Map render
    // ====================================================================

    function renderMap() {
        if (!state.mapImage || !state.camera) return;
        const camera = state.camera;
        const { width: cw, height: ch } = dom.canvas;
        ctx.clearRect(0, 0, cw, ch);

        const targetW = state.mapImage.naturalWidth * camera.cellPixels;
        const targetH = state.mapImage.naturalHeight * camera.cellPixels;
        const tl = camera.worldToScreen(0, 0);
        ctx.imageSmoothingEnabled = camera.cellPixels < 5;
        ctx.drawImage(state.mapImage, tl[0], tl[1], targetW, targetH);

        // War-front hatching: any province on a contested border between
        // two civs at war gets a diagonal red overlay.
        drawWarHatching();

        // Hover and selection outlines
        if (state.hoveredProvince !== null) {
            drawProvinceTint(state.hoveredProvince, "rgba(255, 248, 200, 0.18)");
        }
        if (state.selectedCiv && state.selectedCivDetail) {
            // Highlight the selected civ's capital with a brass crown marker.
            const cap = state.selectedCivDetail.capital_province_id;
            if (cap != null) {
                drawProvinceTint(cap, "rgba(244, 213, 130, 0.35)");
            }
        }
        drawMinimapViewport();
    }

    let hatchPattern = null;
    function getHatchPattern() {
        if (hatchPattern) return hatchPattern;
        const tile = document.createElement("canvas");
        tile.width = 8; tile.height = 8;
        const tctx = tile.getContext("2d");
        tctx.fillStyle = "rgba(178, 35, 28, 0.32)";
        tctx.fillRect(0, 0, 8, 8);
        tctx.strokeStyle = "rgba(255, 90, 70, 0.85)";
        tctx.lineWidth = 1.6;
        tctx.beginPath();
        tctx.moveTo(-2, 10); tctx.lineTo(10, -2);
        tctx.moveTo(2, 10); tctx.lineTo(10, 2);
        tctx.stroke();
        hatchPattern = ctx.createPattern(tile, "repeat");
        return hatchPattern;
    }

    function drawWarHatching() {
        if (!state.activeWarBorders || !state.activeWarBorders.length) return;
        const pattern = getHatchPattern();
        for (const border of state.activeWarBorders) {
            for (const pid of border.province_ids) {
                drawProvinceTintWithStyle(pid, pattern);
            }
        }
    }

    function drawProvinceTintWithStyle(provinceId, fillStyle) {
        if (!state.pickmapData) return;
        const camera = state.camera;
        const data = state.pickmapData.data;
        const width = state.pickmapWidth;
        const height = state.pickmapHeight;
        ctx.save();
        ctx.fillStyle = fillStyle;
        for (let y = 0; y < height; y++) {
            let runStart = -1;
            for (let x = 0; x <= width; x++) {
                const id = x < width ? pickmapProvinceId(data, x, y, width) : -1;
                if (id === provinceId && runStart === -1) runStart = x;
                else if (id !== provinceId && runStart !== -1) {
                    const tl = camera.worldToScreen(runStart, y);
                    ctx.fillRect(tl[0], tl[1], (x - runStart) * camera.cellPixels, camera.cellPixels);
                    runStart = -1;
                }
            }
        }
        ctx.restore();
    }

    function drawProvinceTint(provinceId, fill) {
        if (!state.pickmapData) return;
        const camera = state.camera;
        const data = state.pickmapData.data;
        const width = state.pickmapWidth;
        const height = state.pickmapHeight;

        ctx.save();
        ctx.fillStyle = fill;
        for (let y = 0; y < height; y++) {
            let runStart = -1;
            for (let x = 0; x <= width; x++) {
                const id = x < width ? pickmapProvinceId(data, x, y, width) : -1;
                if (id === provinceId && runStart === -1) runStart = x;
                else if (id !== provinceId && runStart !== -1) {
                    const tl = camera.worldToScreen(runStart, y);
                    ctx.fillRect(tl[0], tl[1], (x - runStart) * camera.cellPixels, camera.cellPixels);
                    runStart = -1;
                }
            }
        }
        ctx.restore();
    }

    function pickmapProvinceId(data, x, y, width) {
        const idx = (y * width + x) * 4;
        if (data[idx + 2] === 255) return -1;
        return data[idx] | (data[idx + 1] << 8);
    }

    function pickProvinceAt(canvasX, canvasY) {
        if (!state.camera || !state.pickmapData) return null;
        const [wx, wy] = state.camera.screenToWorld(canvasX, canvasY);
        const px = Math.floor(wx), py = Math.floor(wy);
        if (px < 0 || px >= state.pickmapWidth || py < 0 || py >= state.pickmapHeight) return null;
        const id = pickmapProvinceId(state.pickmapData.data, px, py, state.pickmapWidth);
        return id >= 0 ? id : null;
    }

    // ====================================================================
    // Minimap
    // ====================================================================

    function drawMinimap() {
        if (!state.mapImage) return;
        const c = dom.minimapCanvas;
        const rect = dom.minimapCanvas.getBoundingClientRect();
        c.width = rect.width;
        c.height = rect.height;
        minimapCtx.imageSmoothingEnabled = false;
        minimapCtx.fillStyle = "#000";
        minimapCtx.fillRect(0, 0, c.width, c.height);
        minimapCtx.drawImage(state.mapImage, 0, 0, c.width, c.height);
    }

    function drawMinimapViewport() {
        if (!state.camera || !state.mapImage) return;
        const camera = state.camera;
        const ww = state.mapImage.naturalWidth;
        const wh = state.mapImage.naturalHeight;
        const mc = dom.minimapCanvas.getBoundingClientRect();
        const [vw, vh] = camera.viewport;
        const visW = vw / camera.cellPixels;
        const visH = vh / camera.cellPixels;
        const vx = (camera.centerX - visW / 2) / ww * mc.width;
        const vy = (camera.centerY - visH / 2) / wh * mc.height;
        const vWidth = (visW / ww) * mc.width;
        const vHeight = (visH / wh) * mc.height;
        Object.assign(dom.minimapViewport.style, {
            left: `${Math.max(0, vx)}px`,
            top: `${Math.max(0, vy)}px`,
            width: `${Math.min(mc.width, vWidth)}px`,
            height: `${Math.min(mc.height, vHeight)}px`,
        });
    }

    // ====================================================================
    // Input handlers
    // ====================================================================

    let dragging = false, dragStart = null, dragMoved = false, lastDrag = null;

    dom.canvas.addEventListener("mousedown", (event) => {
        dragStart = { x: event.clientX, y: event.clientY };
        dragMoved = false;
        lastDrag = { x: event.clientX, y: event.clientY };
        dragging = true;
        dom.canvas.classList.add("grabbing");
    });
    window.addEventListener("mouseup", (event) => {
        if (!dragging) return;
        dragging = false;
        dom.canvas.classList.remove("grabbing");
        if (!dragMoved && dragStart) {
            const rect = dom.canvas.getBoundingClientRect();
            const cx = event.clientX - rect.left;
            const cy = event.clientY - rect.top;
            // Bounds check in CSS pixels (rect.width/height), NOT canvas
            // buffer pixels (canvas.width/height) which are DPR-scaled.
            if (cx >= 0 && cx < rect.width && cy >= 0 && cy < rect.height) {
                const id = pickProvinceAt(cx, cy);
                if (id !== null) {
                    const civ = state.provinceToCiv ? state.provinceToCiv.get(id) : null;
                    if (civ) selectCiv(civ);
                }
            }
        }
        dragStart = null; lastDrag = null;
    });
    window.addEventListener("mousemove", (event) => {
        if (dragging && lastDrag) {
            const dx = event.clientX - lastDrag.x;
            const dy = event.clientY - lastDrag.y;
            const totalDx = event.clientX - dragStart.x;
            const totalDy = event.clientY - dragStart.y;
            if (Math.sqrt(totalDx * totalDx + totalDy * totalDy) > DRAG_THRESHOLD_PX) dragMoved = true;
            if (dragMoved && state.camera) {
                state.camera.pan(dx, dy);
                lastDrag = { x: event.clientX, y: event.clientY };
                renderMap();
            }
        } else {
            const rect = dom.canvas.getBoundingClientRect();
            const cx = event.clientX - rect.left;
            const cy = event.clientY - rect.top;
            if (cx < 0 || cx >= rect.width || cy < 0 || cy >= rect.height) {
                if (state.hoveredProvince !== null) {
                    state.hoveredProvince = null;
                    renderMap();
                }
                return;
            }
            const id = pickProvinceAt(cx, cy);
            if (id !== state.hoveredProvince) {
                state.hoveredProvince = id;
                dom.canvas.classList.toggle("pointing", id !== null);
                renderMap();
            }
        }
    });

    dom.canvas.addEventListener("wheel", (event) => {
        event.preventDefault();
        if (!state.camera) return;
        const rect = dom.canvas.getBoundingClientRect();
        const cx = event.clientX - rect.left, cy = event.clientY - rect.top;
        const factor = event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
        state.camera.zoomAt(cx, cy, factor);
        renderMap();
    }, { passive: false });

    dom.canvas.addEventListener("contextmenu", (e) => e.preventDefault());

    // Ruler tabs
    dom.rulerTabs.forEach(btn => {
        btn.addEventListener("click", () => {
            dom.rulerTabs.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.rulerTab = btn.dataset.tab;
            renderRulerTabBody();
        });
    });

    // Pause / resume
    dom.clockPause.addEventListener("click", async () => {
        try {
            await apiControl("toggle");
            pollOnce();
        } catch (e) { console.error(e); }
    });

    // Speed pips
    dom.clockSpeeds.querySelectorAll(".pip").forEach(pip => {
        pip.addEventListener("click", async () => {
            const speed = parseInt(pip.dataset.speed, 10);
            try { await apiControl("speed", speed); pollOnce(); }
            catch (e) { console.error(e); }
        });
    });

    // Gear / pause-rules popover
    dom.gearBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        togglePopover();
    });
    dom.popover.addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("click", () => togglePopover(false));

    // New world
    dom.forgeBtn.addEventListener("click", async () => {
        const seed = parseInt(dom.seedInput.value, 10) || 0;
        showCurtain(true);
        try {
            const initial = await apiNew(seed);
            await loadInitial(initial);
        } catch (e) { console.error(e); }
        finally { showCurtain(false); }
    });
    dom.seedInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") dom.forgeBtn.click();
    });

    // Keyboard shortcuts (CK3-style)
    document.addEventListener("keydown", (event) => {
        if (event.target.tagName === "INPUT") return;
        if (event.code === "Space") { event.preventDefault(); dom.clockPause.click(); }
        else if (event.key >= "1" && event.key <= "5") {
            const speed = parseInt(event.key, 10);
            apiControl("speed", speed).then(pollOnce).catch(console.error);
        } else if (event.key === "Escape") {
            state.selectedCiv = null;
            state.selectedCivDetail = null;
            renderRulerCard();
            renderRealmPanel();
            renderResourceStrip(state.currentState);
            renderMap();
        } else if (event.key === "+" || event.key === "=") {
            zoomFromKeyboard(ZOOM_STEP);
        } else if (event.key === "-" || event.key === "_") {
            zoomFromKeyboard(1 / ZOOM_STEP);
        } else if (event.key === "0") {
            // Reset to the cover-fit default.
            if (state.camera) {
                state.camera.cellPixels = state.camera.coverFit();
                state.camera.centerX = state.camera.worldWidth / 2;
                state.camera.centerY = state.camera.worldHeight / 2;
                state.camera.clampCenter();
                renderMap();
            }
        }
    });

    function zoomFromKeyboard(factor) {
        if (!state.camera) return;
        // Zoom around the canvas centre when triggered by the keyboard.
        const rect = dom.canvas.getBoundingClientRect();
        state.camera.zoomAt(rect.width / 2, rect.height / 2, factor);
        renderMap();
    }

    window.addEventListener("resize", () => {
        resizeCanvas();
        if (state.camera) state.camera.setViewport([dom.canvas.width / (window.devicePixelRatio || 1), dom.canvas.height / (window.devicePixelRatio || 1)]);
        document.querySelectorAll(".panel:not([hidden])").forEach(revealPanel);
        drawMinimap();
        renderMap();
    });

    // ====================================================================
    // Draggable panels + minimize
    // ====================================================================
    //
    // Any element with [data-drag-handle] inside a .panel becomes a grab
    // surface that moves the panel around. Position is committed to inline
    // `style.left/top` in pixels and persisted to localStorage so it sticks
    // across reloads. Buttons inside the handle (e.g. .panel-min) cancel
    // the drag so a click isn't interpreted as a 0px drag.

    function setupPanelDragging() {
        document.querySelectorAll(".panel").forEach(panel => {
            const panelId = panel.dataset.panelId;
            const handle = panel.querySelector("[data-drag-handle]");
            if (!handle) return;

            // Restore saved position if any.
            const saved = readSavedLayout(panelId);
            if (saved) applySavedPosition(panel, saved);

            handle.addEventListener("mousedown", (event) => {
                if (event.target.closest(".panel-min")) return;  // let button clicks through
                event.preventDefault();
                const rect = panel.getBoundingClientRect();
                const offsetX = event.clientX - rect.left;
                const offsetY = event.clientY - rect.top;
                panel.classList.add("dragging");
                // Lock the panel to absolute pixel positioning so its existing
                // top/right anchors don't fight us.
                panel.style.left = `${rect.left}px`;
                panel.style.top = `${rect.top}px`;
                panel.style.right = "auto";
                panel.style.bottom = "auto";

                const onMove = (e) => {
                    const x = Math.max(0, Math.min(window.innerWidth - 60, e.clientX - offsetX));
                    const y = Math.max(0, Math.min(window.innerHeight - 30, e.clientY - offsetY));
                    panel.style.left = `${x}px`;
                    panel.style.top = `${y}px`;
                };
                const onUp = () => {
                    panel.classList.remove("dragging");
                    window.removeEventListener("mousemove", onMove);
                    window.removeEventListener("mouseup", onUp);
                    saveLayout(panelId, {
                        left: panel.style.left,
                        top: panel.style.top,
                    });
                };
                window.addEventListener("mousemove", onMove);
                window.addEventListener("mouseup", onUp);
            });
        });

        // Minimize buttons: hide the panel, drop a tab into the dock.
        document.querySelectorAll(".panel-min").forEach(btn => {
            btn.addEventListener("click", (event) => {
                event.stopPropagation();
                const targetId = btn.dataset.minTarget;
                const target = document.getElementById(targetId);
                if (!target) return;
                target.setAttribute("hidden", "");
                addDockTab(targetId, btn.closest(".panel"));
            });
        });
    }

    function addDockTab(panelId, panel) {
        const dock = document.getElementById("dock");
        if (!dock) return;
        // Avoid duplicates.
        if (dock.querySelector(`[data-restore="${panelId}"]`)) return;
        // Resolve a label from the panel's titlebar.
        const label = (panel.querySelector(".panel-title")
            || panel.querySelector(".realm-title")
            || panel.querySelector(".chronicle-header > span")
            || panel.querySelector(".minimap-header > span"));
        const text = label ? label.textContent.trim() : panelId;
        const tab = document.createElement("button");
        tab.className = "dock-tab";
        tab.dataset.restore = panelId;
        tab.textContent = text;
        tab.addEventListener("click", () => {
            panel.removeAttribute("hidden");
            tab.remove();
        });
        dock.appendChild(tab);
    }

    function readSavedLayout(panelId) {
        try {
            const raw = localStorage.getItem(`fe.panel.${panelId}`);
            return raw ? JSON.parse(raw) : null;
        } catch (e) { return null; }
    }
    function saveLayout(panelId, pos) {
        try { localStorage.setItem(`fe.panel.${panelId}`, JSON.stringify(pos)); }
        catch (e) {}
    }
    function applySavedPosition(panel, pos) {
        if (!pos) return;
        if (pos.left) panel.style.left = pos.left;
        if (pos.top) panel.style.top = pos.top;
        panel.style.right = "auto";
        panel.style.bottom = "auto";
    }

    function revealPanel(panel) {
        if (!panel) return;
        panel.removeAttribute("hidden");

        const panelId = panel.dataset.panelId;
        if (panelId) {
            const dockTab = document.querySelector(`#dock [data-restore="${panelId}"]`);
            if (dockTab) dockTab.remove();
        }

        const rect = panel.getBoundingClientRect();
        if (!rect.width || !rect.height) return;

        let left = rect.left;
        let top = rect.top;
        const margin = 12;
        const offscreen = rect.right < margin
            || rect.bottom < margin
            || rect.left > window.innerWidth - margin
            || rect.top > window.innerHeight - margin;

        if (offscreen) {
            left = Math.round((window.innerWidth - rect.width) / 2);
            top = Math.round((window.innerHeight - rect.height) / 2);
        }

        left = Math.max(margin, Math.min(window.innerWidth - rect.width - margin, left));
        top = Math.max(margin, Math.min(window.innerHeight - rect.height - margin, top));

        panel.style.left = `${left}px`;
        panel.style.top = `${top}px`;
        panel.style.right = "auto";
        panel.style.bottom = "auto";
    }

    // ====================================================================
    // Person Card (floating bio popup)
    // ====================================================================

    function openPersonCard(person) {
        if (!person) return;
        person = decoratePerson(person, state.selectedCivDetail);
        const dyn = person.dynasty && person.dynasty !== "none"
            ? `House ${prettyId(person.dynasty)}` : "";
        const title = person.heroic_title
            ? `<div style="text-align:center;font-family:var(--font-script);font-style:italic;color:var(--brass-dark);font-size:12px;">⚜ ${escapeHtml(person.heroic_title)}</div>`
            : "";
        const civCue = person.civilization
            ? `<button class="open-civ" data-civ="${escapeAttr(person.civilization)}">↩ Realm of ${escapeHtml(person.civilization)}</button>`
            : "";

        const role = person.role || "";
        const profession = person.profession || "";
        const ageLine = person.age ? `${person.age} yrs` : "";
        const birth = person.birth_year ? `b. ${person.birth_year}` : "";

        const stats = [
            ["Role", role],
            ["Calling", profession ? prettyId(profession) : ""],
            ["Age", ageLine],
            ["Born", birth],
            ["Culture", person.culture ? prettyId(person.culture) : ""],
            ["Sex", person.gender ? person.gender[0].toUpperCase() + person.gender.slice(1) : ""],
        ].filter(([, v]) => v);

        const needs = person.needs || {};
        const needsHTML = Object.keys(needs).length ? `
            <div>
                <div style="font-family:var(--font-display);font-size:10.5px;text-transform:uppercase;letter-spacing:0.16em;color:var(--oxblood);margin-bottom:6px;">Needs</div>
                <div class="needs-grid">
                    ${["food","safety","belonging","esteem"].map(k => {
                        const v = Math.max(0, Math.min(100, Number(needs[k] || 0)));
                        return `<span class="nlabel">${k}</span>
                                <div class="nbar"><div class="nbar-fill" style="width:${v}%"></div></div>
                                <span class="nval">${Math.round(v)}</span>`;
                    }).join("")}
                </div>
            </div>` : "";

        const grudges = (person.grudges && person.grudges.length)
            ? `<div style="font-family:var(--font-script);font-size:12px;color:var(--ink-soft);">
                <strong style="color:var(--oxblood);font-family:var(--font-display);font-size:10.5px;text-transform:uppercase;letter-spacing:0.16em;">Grudges</strong>
                <div style="margin-top:4px;">${person.grudges.map(g => `<div>· ${escapeHtml(g)}</div>`).join("")}</div>
              </div>` : "";

        const recent = (person.recent_events && person.recent_events.length)
            ? `<div>
                <div style="font-family:var(--font-display);font-size:10.5px;text-transform:uppercase;letter-spacing:0.16em;color:var(--oxblood);margin-bottom:6px;">Recent</div>
                ${person.recent_events.slice(0, 5).map(e => `<div style="font-family:var(--font-script);font-size:12px;color:var(--ink-soft);margin:2px 0;line-height:1.3;">· ${escapeHtml(e)}</div>`).join("")}
              </div>` : "";

        dom.personCardTitle.textContent = person.name || "Person";
        applyRealmTheme(dom.personCard, person.realm_color);
        dom.personCardBody.innerHTML = `
            <div class="person-portrait-large">${renderPortrait(person, 120)}</div>
            <div class="person-card-name">${escapeHtml(person.name || "Unknown")}</div>
            ${dyn ? `<div class="person-card-dynasty">${escapeHtml(dyn)}</div>` : ""}
            ${role ? `<div class="person-card-role">${escapeHtml(role)}${person.relation_to_ruler ? " · " + escapeHtml(person.relation_to_ruler) : ""}</div>` : ""}
            ${title}
            <div class="person-card-stats">
                ${stats.map(([k,v]) => `<div><span style="color:var(--ink-fade);font-size:10px;text-transform:uppercase;letter-spacing:0.12em;">${escapeHtml(k)}</span><br><span style="font-family:var(--font-mono);">${escapeHtml(String(v))}</span></div>`).join("")}
            </div>
            ${person.parents && person.parents.length ? `
                <div style="font-family:var(--font-script);font-size:12px;color:var(--ink-soft);">
                    <strong style="color:var(--oxblood);font-family:var(--font-display);font-size:10.5px;text-transform:uppercase;letter-spacing:0.16em;">Parents</strong>
                    <div style="margin-top:4px;">${person.parents.map(p => `<div>· ${escapeHtml(p)}</div>`).join("")}</div>
                </div>
            ` : ""}
            ${needsHTML}
            ${grudges}
            ${recent}
            ${civCue}
        `;

        // Wire the realm-jump button.
        const civBtn = dom.personCardBody.querySelector(".open-civ");
        if (civBtn) {
            civBtn.addEventListener("click", () => {
                selectCiv(civBtn.dataset.civ);
                closePersonCard();
            });
        }

        revealPanel(dom.personCard);
    }

    function closePersonCard() {
        dom.personCard.setAttribute("hidden", "");
    }

    if (dom.personCardClose) {
        dom.personCardClose.addEventListener("click", (e) => {
            e.stopPropagation();
            closePersonCard();
        });
    }

    // ====================================================================
    // Procedural portraits (deterministic per agent_id)
    // ====================================================================
    //
    // Each agent's portrait is composed of layered SVG primitives. The
    // `agent_id` is hashed into a small RNG seed so the same character
    // always renders the same way. Culture drives palette; gender + age
    // drive beard / hair greying; role drives accessory overlays.

    const CULTURE_PALETTES = {
        northlands: { skins: ["#f0d3b3", "#e6c6a2", "#dfb892"], hairs: ["#e7d6a0", "#c89858", "#a04525", "#7a4a25"], eyes: ["#3a78b3", "#509cc6", "#71a37e"] },
        desert:     { skins: ["#c79a6a", "#b48355", "#a37246", "#8a5d36"], hairs: ["#1c130b", "#2a1a0c", "#4a2d18"], eyes: ["#3a230f", "#5a3618", "#2a1a0c"] },
        imperial:   { skins: ["#e3c5a3", "#cda886", "#bb8e69"], hairs: ["#2a1a0c", "#4a2d18", "#6f4524", "#1c130b"], eyes: ["#3a230f", "#4a3220", "#6b8d70"] },
        coastal:    { skins: ["#d8b48b", "#c89e75", "#b8895f"], hairs: ["#3a2210", "#5a3a1d", "#84602f"], eyes: ["#3a78b3", "#4a6a85", "#3a4d3a"] },
        highland:   { skins: ["#dfba8b", "#cfa977", "#b88e60"], hairs: ["#864120", "#a04525", "#c2683f", "#5a3a1d"], eyes: ["#3a6f4d", "#5a8d6a", "#3a78b3"] },
        frontier:   { skins: ["#dcb287", "#c8a075", "#b48a5d"], hairs: ["#4a2d18", "#6f4524", "#864120", "#2a1a0c"], eyes: ["#5a4422", "#4a3220", "#3a4d3a"] },
    };
    const FALLBACK_PALETTE = CULTURE_PALETTES.frontier;
    const DYNASTY_COLORS = ["#7a1f1f", "#3c4a78", "#3c6f4a", "#7a5a1f", "#5a2a78", "#1f5a7a", "#7a2a4f", "#3a4a3a"];

    function hashStr(s) {
        // FNV-1a 32-bit
        let h = 2166136261 >>> 0;
        for (let i = 0; i < s.length; i++) {
            h ^= s.charCodeAt(i);
            h = Math.imul(h, 16777619);
        }
        return h >>> 0;
    }
    function mulberry32(seed) {
        let a = seed >>> 0;
        return function () {
            a = (a + 0x6D2B79F5) >>> 0;
            let t = a;
            t = Math.imul(t ^ (t >>> 15), t | 1);
            t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    }
    function pickFrom(rng, list) { return list[Math.floor(rng() * list.length)]; }

    function paletteForCulture(culture) {
        if (!culture) return FALLBACK_PALETTE;
        // Drift cultures are namespaced like "frontier_velis_drifted_1" — strip
        // back to the base.
        for (const key of Object.keys(CULTURE_PALETTES)) {
            if (culture.startsWith(key)) return CULTURE_PALETTES[key];
        }
        return FALLBACK_PALETTE;
    }

    // Geometry constants — fractions of the portrait edge size.
    // Anchored so the head sits high enough to leave room for an accessory
    // (crown/helm) on top, and shoulders fill the bottom third.
    const HEAD_CY = 0.46;       // head centre Y
    const HEAD_RX = 0.22;       // head horizontal radius
    const HEAD_RY = 0.26;       // head vertical radius (slightly tall = oval face)
    const CROWN_BASE_Y = 0.22;  // where crown bottom meets the head top
    const SHOULDER_TOP = 0.78;  // where shoulders start

    function renderPortrait(person, size) {
        size = size || 96;
        if (!person) return placeholderSvg(size);

        const id = person.agent_id || person.name || "anon";
        const seed = hashStr(id);
        const rng = mulberry32(seed);
        const palette = paletteForCulture(person.culture);
        const gender = (person.gender || "").toLowerCase();
        const age = Math.max(0, person.age | 0);
        const role = (person.role || "").toLowerCase();
        const alive = person.alive !== false;
        const heroic = !!person.heroic_title;

        const skin = pickFrom(rng, palette.skins);
        const hair = pickFrom(rng, palette.hairs);
        const eye = pickFrom(rng, palette.eyes);
        const dynastyKey = person.dynasty || person.civilization || id;
        const dynastyColor = DYNASTY_COLORS[hashStr(dynastyKey) % DYNASTY_COLORS.length];
        const realmColor = normalizeHexColor(person.realm_color || person.color);
        const heraldryColor = realmColor || dynastyColor;
        const backdropBase = realmColor || shadeHex(dynastyColor, 0.08);
        const backdropTop = shadeHex(backdropBase, 0.24);
        const backdropBottom = shadeHex(backdropBase, -0.54);
        const robeColor = realmColor
            ? mixColors(realmColor, "#20160d", 0.22)
            : shadeHex(heraldryColor, -0.05);
        const robeShade = shadeHex(robeColor, -0.42);
        const robeTrim = realmColor
            ? mixColors(realmColor, "#f3d98a", 0.58)
            : shadeHex(heraldryColor, 0.20);
        const mantleColor = shadeHex(robeColor, -0.18);

        const greyT = clamp01((age - 45) / 28);
        const hairColor = mixColors(hair, "#e8e6df", greyT * 0.85);
        const balding = gender === "male" && age >= 50 && rng() < 0.55;
        const hasBeard = gender === "male" && age >= 20 && rng() < 0.65;
        const beardStyle = hasBeard ? Math.floor(rng() * 3) : -1;
        const hairStyle = balding ? -1 : Math.floor(rng() * 4);
        const noseStyle = Math.floor(rng() * 3);
        const mouthSmile = (rng() - 0.5) * 0.6;  // -0.3 .. +0.3

        // ===== absolute pixel coordinates =====
        const cx = size / 2;
        const headCY = size * HEAD_CY;
        const headRX = size * HEAD_RX;
        const headRY = size * HEAD_RY;
        const shoulderTop = size * SHOULDER_TOP;

        // ===== layered defs =====
        const defs = `<defs>
            <linearGradient id="bg-${seed}" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="${backdropTop}"/>
                <stop offset="100%" stop-color="${backdropBottom}"/>
            </linearGradient>
            <radialGradient id="banner-${seed}" cx="0.5" cy="0.18" r="0.9">
                <stop offset="0%" stop-color="${shadeHex(heraldryColor, 0.18)}" stop-opacity="0.95"/>
                <stop offset="100%" stop-color="${shadeHex(heraldryColor, -0.28)}" stop-opacity="0.88"/>
            </linearGradient>
            <radialGradient id="face-${seed}" cx="0.5" cy="0.45" r="0.6">
                <stop offset="0%" stop-color="${shadeHex(skin, 0.10)}"/>
                <stop offset="80%" stop-color="${skin}"/>
                <stop offset="100%" stop-color="${shadeHex(skin, -0.22)}"/>
            </radialGradient>
        </defs>`;

        // ===== hair (renders behind head if long, in front if styled forward) =====
        const hairBack = renderHairBack(hairStyle, cx, headCY, headRX, headRY, hairColor);
        const hairFront = renderHairFront(hairStyle, cx, headCY, headRX, headRY, hairColor, balding);

        // ===== shoulders / robe =====
        const shoulders = `<path d="
            M 0 ${size}
            L 0 ${shoulderTop + size * 0.05}
            Q ${cx * 0.7} ${shoulderTop - size * 0.02}, ${cx} ${shoulderTop - size * 0.04}
            Q ${cx * 1.3} ${shoulderTop - size * 0.02}, ${size} ${shoulderTop + size * 0.05}
            L ${size} ${size} Z"
            fill="${robeColor}" stroke="${robeShade}" stroke-width="${size * 0.012}"/>
            <path d="M ${cx - size * 0.48} ${size}
            L ${cx - size * 0.32} ${shoulderTop + size * 0.02}
            Q ${cx - size * 0.10} ${shoulderTop - size * 0.04}, ${cx} ${shoulderTop - size * 0.03}
            L ${cx - size * 0.03} ${size} Z"
            fill="${mantleColor}" opacity="0.88"/>
            <path d="M ${cx + size * 0.48} ${size}
            L ${cx + size * 0.32} ${shoulderTop + size * 0.02}
            Q ${cx + size * 0.10} ${shoulderTop - size * 0.04}, ${cx} ${shoulderTop - size * 0.03}
            L ${cx + size * 0.03} ${size} Z"
            fill="${mantleColor}" opacity="0.88"/>
            <path d="M ${cx - size * 0.05} ${shoulderTop} L ${cx} ${size * 0.92} L ${cx + size * 0.05} ${shoulderTop} Z"
            fill="${robeTrim}" opacity="0.95"/>
            <path d="M ${cx - size * 0.16} ${shoulderTop + size * 0.01}
            Q ${cx} ${shoulderTop - size * 0.02}, ${cx + size * 0.16} ${shoulderTop + size * 0.01}"
            stroke="${robeTrim}" stroke-width="${size * 0.028}" stroke-linecap="round" fill="none" opacity="0.9"/>
            <circle cx="${cx}" cy="${shoulderTop + size * 0.11}" r="${size * 0.026}" fill="${shadeHex(robeTrim, -0.08)}" stroke="${robeShade}" stroke-width="${size * 0.01}"/>`;

        // ===== neck =====
        const neckW = headRX * 0.55;
        const neckTop = headCY + headRY * 0.85;
        const neckBottom = shoulderTop + size * 0.005;
        const neck = `<path d="
            M ${cx - neckW} ${neckTop}
            Q ${cx - neckW * 1.1} ${(neckTop + neckBottom) / 2}, ${cx - neckW * 0.9} ${neckBottom}
            L ${cx + neckW * 0.9} ${neckBottom}
            Q ${cx + neckW * 1.1} ${(neckTop + neckBottom) / 2}, ${cx + neckW} ${neckTop} Z"
            fill="${shadeHex(skin, -0.18)}"/>`;

        // ===== face =====
        const face = `<ellipse cx="${cx}" cy="${headCY}" rx="${headRX}" ry="${headRY}"
            fill="url(#face-${seed})" stroke="${shadeHex(skin, -0.35)}" stroke-width="${size * 0.01}"/>`;

        // ===== eyebrows + eyes =====
        const eyeY = headCY - headRY * 0.08;
        const eyeOffsetX = headRX * 0.42;
        const eyebrowY = eyeY - headRY * 0.20;
        const browLift = -0.005 + 0.01 * rng();
        const eyebrows = `
            <path d="M ${cx - eyeOffsetX - headRX * 0.18} ${eyebrowY}
                     Q ${cx - eyeOffsetX} ${eyebrowY - headRX * 0.10 + size * browLift},
                       ${cx - eyeOffsetX + headRX * 0.18} ${eyebrowY}"
                  stroke="${hairColor}" stroke-width="${size * 0.018}" fill="none" stroke-linecap="round"/>
            <path d="M ${cx + eyeOffsetX - headRX * 0.18} ${eyebrowY}
                     Q ${cx + eyeOffsetX} ${eyebrowY - headRX * 0.10 + size * browLift},
                       ${cx + eyeOffsetX + headRX * 0.18} ${eyebrowY}"
                  stroke="${hairColor}" stroke-width="${size * 0.018}" fill="none" stroke-linecap="round"/>`;
        const eyes = `
            <ellipse cx="${cx - eyeOffsetX}" cy="${eyeY}" rx="${headRX * 0.18}" ry="${headRY * 0.10}" fill="#fffaee"/>
            <ellipse cx="${cx + eyeOffsetX}" cy="${eyeY}" rx="${headRX * 0.18}" ry="${headRY * 0.10}" fill="#fffaee"/>
            <circle cx="${cx - eyeOffsetX}" cy="${eyeY + headRY * 0.012}" r="${headRX * 0.085}" fill="${eye}"/>
            <circle cx="${cx + eyeOffsetX}" cy="${eyeY + headRY * 0.012}" r="${headRX * 0.085}" fill="${eye}"/>
            <circle cx="${cx - eyeOffsetX}" cy="${eyeY + headRY * 0.012}" r="${headRX * 0.035}" fill="#0c0a08"/>
            <circle cx="${cx + eyeOffsetX}" cy="${eyeY + headRY * 0.012}" r="${headRX * 0.035}" fill="#0c0a08"/>`;

        // ===== nose =====
        const noseTop = eyeY + headRY * 0.18;
        const noseBottom = eyeY + headRY * 0.55;
        let nose;
        if (noseStyle === 0) {
            // Straight ridge
            nose = `<path d="M ${cx} ${noseTop}
                     L ${cx - headRX * 0.06} ${noseBottom}
                     Q ${cx} ${noseBottom + headRY * 0.04}, ${cx + headRX * 0.06} ${noseBottom} Z"
                  fill="${shadeHex(skin, -0.18)}" opacity="0.75"/>`;
        } else if (noseStyle === 1) {
            // Aquiline (curved)
            nose = `<path d="M ${cx + headRX * 0.02} ${noseTop}
                     Q ${cx - headRX * 0.04} ${(noseTop + noseBottom) / 2},
                       ${cx - headRX * 0.05} ${noseBottom}
                     Q ${cx} ${noseBottom + headRY * 0.04}, ${cx + headRX * 0.07} ${noseBottom}
                     Z"
                  fill="${shadeHex(skin, -0.20)}" opacity="0.75"/>`;
        } else {
            // Snub (round)
            nose = `<ellipse cx="${cx}" cy="${noseBottom - headRY * 0.02}" rx="${headRX * 0.10}" ry="${headRY * 0.06}"
                  fill="${shadeHex(skin, -0.22)}" opacity="0.7"/>`;
        }

        // ===== mouth =====
        const mouthY = noseBottom + headRY * 0.20;
        const mouthW = headRX * 0.32;
        const mouthDip = headRY * 0.04 * (mouthSmile < 0 ? -1 : 1) * Math.abs(mouthSmile);
        const mouth = `<path d="M ${cx - mouthW} ${mouthY}
                  Q ${cx} ${mouthY + (mouthSmile >= 0 ? mouthDip + headRY * 0.03 : -mouthDip)},
                    ${cx + mouthW} ${mouthY}"
                  stroke="${shadeHex(skin, -0.50)}" stroke-width="${size * 0.014}" fill="none" stroke-linecap="round"/>
            <path d="M ${cx - mouthW * 0.85} ${mouthY + headRY * 0.005}
                  Q ${cx} ${mouthY + headRY * 0.06}, ${cx + mouthW * 0.85} ${mouthY + headRY * 0.005}"
                  stroke="${mixColors(skin, '#7a2222', 0.45)}" stroke-width="${size * 0.014}" fill="none" stroke-linecap="round" opacity="0.65"/>`;

        // ===== beard =====
        const beard = renderBeard(beardStyle, cx, headCY, headRX, headRY, mouthY,
            mixColors(hair, "#9a8c70", greyT * 0.7));

        // ===== accessory based on role =====
        let accessory = "";
        if (role === "ruler" || person.role === "Ruler" || role === "ruling") {
            accessory = crownSvg(size, cx, headCY, headRX, headRY);
        } else if (role === "general" || role === "marshal" || role === "commander") {
            accessory = helmSvg(size, cx, headCY, headRX, headRY, heraldryColor);
        } else if (role === "diplomat" || role === "chancellor" || role === "envoy") {
            accessory = scrollSvg(size, cx, headCY);
        } else if (role === "heir") {
            accessory = circletSvg(size, cx, headCY, headRX, headRY);
        }

        const heroicGlow = heroic
            ? `<circle cx="${cx}" cy="${headCY}" r="${headRX * 1.55}" fill="none" stroke="rgba(244,213,130,0.85)" stroke-width="${size * 0.025}"/>`
            : "";
        const deathOverlay = !alive
            ? `<rect width="${size}" height="${size}" fill="rgba(8,6,4,0.55)"/>
               <text x="${cx}" y="${size * 0.62}" text-anchor="middle" fill="#bdb6a3" font-size="${size * 0.42}" font-family="serif">✝</text>`
            : "";

        return `<svg viewBox="0 0 ${size} ${size}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            ${defs}
            <rect width="${size}" height="${size}" fill="url(#bg-${seed})"/>
            <path d="M 0 ${size * 0.24}
                Q ${cx} ${size * 0.02}, ${size} ${size * 0.24}
                L ${size} 0 L 0 0 Z"
                fill="url(#banner-${seed})" opacity="0.96"/>
            ${shoulders}
            ${neck}
            ${hairBack}
            ${face}
            ${eyebrows}
            ${eyes}
            ${nose}
            ${mouth}
            ${beard}
            ${hairFront}
            ${accessory}
            ${heroicGlow}
            ${deathOverlay}
        </svg>`;
    }

    function renderHairBack(style, cx, cy, rx, ry, color) {
        if (style < 0) return "";
        // Long hair around the back of the head, draped to shoulders.
        if (style === 1 || style === 3) {
            return `<path d="
                M ${cx - rx * 1.05} ${cy}
                Q ${cx - rx * 1.15} ${cy + ry * 1.4}, ${cx - rx * 0.7} ${cy + ry * 1.6}
                L ${cx + rx * 0.7} ${cy + ry * 1.6}
                Q ${cx + rx * 1.15} ${cy + ry * 1.4}, ${cx + rx * 1.05} ${cy}
                Q ${cx} ${cy - ry * 1.0}, ${cx - rx * 1.05} ${cy} Z"
                fill="${color}" opacity="0.95"/>`;
        }
        return "";
    }

    function renderHairFront(style, cx, cy, rx, ry, color, balding) {
        if (balding) {
            // Receded hair: thin band at the back-top
            return `<path d="
                M ${cx - rx * 0.95} ${cy - ry * 0.55}
                Q ${cx} ${cy - ry * 0.85}, ${cx + rx * 0.95} ${cy - ry * 0.55}
                L ${cx + rx * 0.85} ${cy - ry * 0.40}
                Q ${cx} ${cy - ry * 0.50}, ${cx - rx * 0.85} ${cy - ry * 0.40} Z"
                fill="${color}"/>`;
        }
        switch (style) {
            case 0: // Cap of hair, fringe
                return `<path d="
                    M ${cx - rx * 1.02} ${cy - ry * 0.10}
                    Q ${cx - rx * 1.10} ${cy - ry * 0.85}, ${cx} ${cy - ry * 1.05}
                    Q ${cx + rx * 1.10} ${cy - ry * 0.85}, ${cx + rx * 1.02} ${cy - ry * 0.10}
                    L ${cx + rx * 0.85} ${cy - ry * 0.30}
                    Q ${cx + rx * 0.40} ${cy - ry * 0.55}, ${cx} ${cy - ry * 0.45}
                    Q ${cx - rx * 0.40} ${cy - ry * 0.55}, ${cx - rx * 0.85} ${cy - ry * 0.30} Z"
                    fill="${color}"/>`;
            case 1: // Side-parted with long-back: front fringe
                return `<path d="
                    M ${cx - rx * 1.0} ${cy - ry * 0.10}
                    Q ${cx - rx * 0.85} ${cy - ry * 0.95}, ${cx + rx * 0.30} ${cy - ry * 0.95}
                    Q ${cx + rx * 0.95} ${cy - ry * 0.75}, ${cx + rx * 1.02} ${cy - ry * 0.05}
                    L ${cx + rx * 0.40} ${cy - ry * 0.55}
                    Q ${cx + rx * 0.10} ${cy - ry * 0.65}, ${cx - rx * 0.85} ${cy - ry * 0.30} Z"
                    fill="${color}"/>`;
            case 2: // Tonsure / cropped: small swept fringe
                return `<path d="
                    M ${cx - rx * 0.95} ${cy - ry * 0.20}
                    Q ${cx} ${cy - ry * 0.95}, ${cx + rx * 0.95} ${cy - ry * 0.20}
                    L ${cx + rx * 0.75} ${cy - ry * 0.45}
                    Q ${cx} ${cy - ry * 0.55}, ${cx - rx * 0.75} ${cy - ry * 0.45} Z"
                    fill="${color}"/>`;
            case 3: // Long-flowing with full crown
            default:
                return `<path d="
                    M ${cx - rx * 1.05} ${cy - ry * 0.05}
                    Q ${cx - rx * 1.05} ${cy - ry * 0.95}, ${cx} ${cy - ry * 1.10}
                    Q ${cx + rx * 1.05} ${cy - ry * 0.95}, ${cx + rx * 1.05} ${cy - ry * 0.05}
                    L ${cx + rx * 0.90} ${cy - ry * 0.40}
                    Q ${cx} ${cy - ry * 0.65}, ${cx - rx * 0.90} ${cy - ry * 0.40} Z"
                    fill="${color}"/>`;
        }
    }

    function renderBeard(style, cx, cy, rx, ry, mouthY, color) {
        if (style < 0) return "";
        if (style === 0) {
            // Full beard wrapping jaw
            return `<path d="
                M ${cx - rx * 0.92} ${cy + ry * 0.20}
                Q ${cx - rx * 0.95} ${cy + ry * 1.05}, ${cx} ${cy + ry * 1.15}
                Q ${cx + rx * 0.95} ${cy + ry * 1.05}, ${cx + rx * 0.92} ${cy + ry * 0.20}
                Q ${cx + rx * 0.55} ${mouthY - ry * 0.05}, ${cx} ${mouthY - ry * 0.05}
                Q ${cx - rx * 0.55} ${mouthY - ry * 0.05}, ${cx - rx * 0.92} ${cy + ry * 0.20} Z"
                fill="${color}"/>`;
        }
        if (style === 1) {
            // Goatee
            return `<path d="
                M ${cx - rx * 0.30} ${mouthY + ry * 0.02}
                Q ${cx - rx * 0.40} ${cy + ry * 1.00}, ${cx} ${cy + ry * 1.10}
                Q ${cx + rx * 0.40} ${cy + ry * 1.00}, ${cx + rx * 0.30} ${mouthY + ry * 0.02}
                Q ${cx + rx * 0.18} ${mouthY + ry * 0.10}, ${cx} ${mouthY + ry * 0.06}
                Q ${cx - rx * 0.18} ${mouthY + ry * 0.10}, ${cx - rx * 0.30} ${mouthY + ry * 0.02} Z"
                fill="${color}"/>`;
        }
        // Stubble shadow
        return `<ellipse cx="${cx}" cy="${cy + ry * 0.62}" rx="${rx * 0.85}" ry="${ry * 0.30}"
                fill="${color}" opacity="0.30"/>`;
    }

    function placeholderSvg(size) {
        const cx = size / 2;
        return `<svg viewBox="0 0 ${size} ${size}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <rect width="${size}" height="${size}" fill="#2a1d10"/>
            <ellipse cx="${cx}" cy="${size * HEAD_CY}" rx="${size * HEAD_RX}" ry="${size * HEAD_RY}" fill="#5a4530" opacity="0.7"/>
            <path d="M 0 ${size} L 0 ${size * SHOULDER_TOP} Q ${cx} ${size * 0.74}, ${size} ${size * SHOULDER_TOP} L ${size} ${size} Z" fill="#3a2d1d"/>
        </svg>`;
    }

    // Crown sits on top of the head, scaled to the head width; tines stay
    // above the head silhouette so it doesn't punch into the face.
    function crownSvg(s, cx, headCY, headRX, headRY) {
        const baseY = headCY - headRY * 0.95;
        const leftX = cx - headRX * 1.05;
        const rightX = cx + headRX * 1.05;
        const tineH = s * 0.10;
        const bandH = s * 0.04;
        return `
            <path d="
                M ${leftX} ${baseY}
                L ${leftX} ${baseY - bandH * 0.7}
                L ${cx - headRX * 0.65} ${baseY - tineH * 0.55}
                L ${cx - headRX * 0.30} ${baseY - tineH}
                L ${cx} ${baseY - tineH * 0.55}
                L ${cx + headRX * 0.30} ${baseY - tineH}
                L ${cx + headRX * 0.65} ${baseY - tineH * 0.55}
                L ${rightX} ${baseY - bandH * 0.7}
                L ${rightX} ${baseY}
                Z"
                fill="#d4a85c" stroke="#5a3f15" stroke-width="${s * 0.012}" stroke-linejoin="round"/>
            <rect x="${leftX}" y="${baseY - bandH * 0.4}"
                width="${rightX - leftX}" height="${bandH * 0.45}"
                fill="#a8802b" stroke="#5a3f15" stroke-width="${s * 0.008}"/>
            <circle cx="${cx - headRX * 0.30}" cy="${baseY - tineH * 0.95}" r="${s * 0.018}" fill="#b22222"/>
            <circle cx="${cx + headRX * 0.30}" cy="${baseY - tineH * 0.95}" r="${s * 0.018}" fill="#1f5a7a"/>
            <circle cx="${cx}" cy="${baseY - tineH * 0.5}" r="${s * 0.018}" fill="#7a1f5a"/>`;
    }

    function circletSvg(s, cx, headCY, headRX, headRY) {
        const baseY = headCY - headRY * 0.85;
        return `<rect x="${cx - headRX * 1.0}" y="${baseY}" width="${headRX * 2.0}" height="${s * 0.04}"
                rx="${s * 0.01}" fill="#d4a85c" stroke="#5a3f15" stroke-width="${s * 0.010}"/>
            <circle cx="${cx}" cy="${baseY + s * 0.02}" r="${s * 0.018}" fill="#3a78b3"/>`;
    }

    function helmSvg(s, cx, headCY, headRX, headRY, dynastyColor) {
        const top = headCY - headRY * 1.10;
        const brow = headCY - headRY * 0.10;
        return `
            <path d="M ${cx - headRX * 1.10} ${brow}
                Q ${cx - headRX * 1.10} ${top + headRY * 0.05}, ${cx} ${top}
                Q ${cx + headRX * 1.10} ${top + headRY * 0.05}, ${cx + headRX * 1.10} ${brow}
                L ${cx + headRX * 1.05} ${brow + s * 0.025}
                Q ${cx + headRX * 0.55} ${brow - s * 0.005}, ${cx} ${brow + s * 0.005}
                Q ${cx - headRX * 0.55} ${brow - s * 0.005}, ${cx - headRX * 1.05} ${brow + s * 0.025} Z"
                fill="#7a8090" stroke="#2a3142" stroke-width="${s * 0.014}" stroke-linejoin="round"/>
            <rect x="${cx - s * 0.02}" y="${top - s * 0.04}" width="${s * 0.04}" height="${s * 0.08}" fill="${shadeHex(dynastyColor, -0.1)}"/>
            <rect x="${cx - headRX * 0.04}" y="${brow + s * 0.005}" width="${headRX * 0.08}" height="${s * 0.06}" fill="#1a1f2c"/>`;
    }

    function scrollSvg(s, cx, headCY) {
        // Diplomat: a small scroll tucked at the lower-right, near the shoulder.
        const x = cx + s * 0.28, y = s * 0.62;
        return `<rect x="${x}" y="${y}" width="${s * 0.16}" height="${s * 0.05}" rx="${s * 0.02}"
                fill="#f3e1b4" stroke="#5a3f15" stroke-width="${s * 0.012}"/>
            <line x1="${x + s * 0.02}" y1="${y + s * 0.025}" x2="${x + s * 0.14}" y2="${y + s * 0.025}"
                stroke="#5a3f15" stroke-width="${s * 0.006}"/>`;
    }

    // Color helpers
    function clamp01(v) { return Math.max(0, Math.min(1, v)); }
    function hexToRgb(h) {
        const m = h.replace("#","");
        return [parseInt(m.slice(0,2),16), parseInt(m.slice(2,4),16), parseInt(m.slice(4,6),16)];
    }
    function rgbToHex(r,g,b) {
        return "#" + [r,g,b].map(v => Math.max(0,Math.min(255,v|0)).toString(16).padStart(2,"0")).join("");
    }
    function mixColors(a, b, t) {
        const [r1,g1,b1] = hexToRgb(a), [r2,g2,b2] = hexToRgb(b);
        return rgbToHex(r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t);
    }
    function shadeHex(h, amount) {
        const [r,g,b] = hexToRgb(h);
        if (amount >= 0) return rgbToHex(r+(255-r)*amount, g+(255-g)*amount, b+(255-b)*amount);
        return rgbToHex(r*(1+amount), g*(1+amount), b*(1+amount));
    }

    function normalizeHexColor(value) {
        if (typeof value !== "string") return "";
        const trimmed = value.trim();
        return /^#[0-9a-fA-F]{6}$/.test(trimmed) ? trimmed : "";
    }

    function closestFromEventTarget(event, selector) {
        const target = event.target;
        if (target instanceof Element) return target.closest(selector);
        if (target && target.parentElement) return target.parentElement.closest(selector);
        return null;
    }

    function setProvinceOwners(provinceOwners) {
        state.provinceToCiv = new Map();
        provinceOwners.forEach((civName, pid) => {
            if (civName) state.provinceToCiv.set(pid, civName);
        });
    }

    function civColorByName(civName) {
        if (!civName) return "";
        if (state.selectedCivDetail && state.selectedCivDetail.name === civName && state.selectedCivDetail.color) {
            return state.selectedCivDetail.color;
        }
        const current = (state.currentState && state.currentState.civilizations || []).find(c => c.name === civName);
        if (current && current.color) return current.color;
        const initial = (state.initial && state.initial.civilizations || []).find(c => c.name === civName);
        return initial && initial.color ? initial.color : "";
    }

    function decoratePerson(person, civ) {
        if (!person) return person;
        const civilization = person.civilization || (civ && civ.name) || "";
        const realmColor = normalizeHexColor(person.realm_color || person.color || (civ && civ.color) || civColorByName(civilization));
        return { ...person, civilization, realm_color: realmColor };
    }

    function realmThemeStyle(color) {
        const realmColor = normalizeHexColor(color);
        if (!realmColor) return "";
        const soft = mixColors(realmColor, "#f4ecdb", 0.84);
        const border = mixColors(realmColor, "#22150b", 0.42);
        return `--realm-color:${realmColor};--realm-color-soft:${soft};--realm-color-border:${border};`;
    }

    function personRowStyle(person, extraCss = "") {
        const themed = realmThemeStyle(person && person.realm_color);
        const cssText = `${themed}${extraCss}`;
        return cssText ? ` style="${escapeAttr(cssText)}"` : "";
    }

    function applyRealmTheme(element, color) {
        const themed = realmThemeStyle(color);
        ["--realm-color", "--realm-color-soft", "--realm-color-border"].forEach(name => element.style.removeProperty(name));
        if (!themed) return;
        themed.split(";").forEach(rule => {
            if (!rule) return;
            const [name, value] = rule.split(":");
            if (name && value) element.style.setProperty(name.trim(), value.trim());
        });
    }

    // ====================================================================
    // Helpers
    // ====================================================================

    function resizeCanvas() {
        const rect = dom.canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        dom.canvas.width = Math.floor(rect.width * dpr);
        dom.canvas.height = Math.floor(rect.height * dpr);
        dom.canvas.style.width = `${rect.width}px`;
        dom.canvas.style.height = `${rect.height}px`;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function showCurtain(show) {
        dom.bootCurtain.classList.toggle("hidden", !show);
    }

    function escapeHtml(s) {
        return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        }[c]));
    }
    function escapeAttr(s) { return escapeHtml(s); }
    // Engine-side stability/legitimacy/unrest/schism are already on a 0-100
    // scale, so pct just rounds. Don't scale — that's how we ended up with
    // the "6263%" bug.
    function pct(v) {
        if (v == null || isNaN(v)) return "0%";
        return `${Math.round(Number(v))}%`;
    }
    function prettyId(s) {
        if (!s) return "";
        return String(s)
            .replace(/_/g, " ")
            .replace(/\b\w/g, c => c.toUpperCase());
    }
    function formatThousands(n) {
        n = Number(n) || 0;
        if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + "M";
        if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + "K";
        return String(Math.round(n));
    }

    // ====================================================================
    // Boot
    // ====================================================================

    document.addEventListener("DOMContentLoaded", () => {
        const defaultSeed = parseInt(document.body.dataset.defaultSeed, 10) || 909;
        dom.seedInput.value = defaultSeed;
        resizeCanvas();
        setupPanelDragging();
        boot();
    });
})();
