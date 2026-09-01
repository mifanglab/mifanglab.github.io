(function () {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";
  var observer;
  var mutationFrame;

  var palettes = [
    { dark: "#102a43", mid: "#2f80ed", light: "#77d7f7", glow: "#a7f3d0" },
    { dark: "#201547", mid: "#7c3aed", light: "#c4b5fd", glow: "#67e8f9" },
    { dark: "#0d3540", mid: "#0891b2", light: "#67e8f9", glow: "#bef264" },
    { dark: "#3b173d", mid: "#c026d3", light: "#f0abfc", glow: "#fcd34d" },
    { dark: "#3c1f1b", mid: "#ea580c", light: "#fdba74", glow: "#fde68a" }
  ];

  function add(parent, name, attributes, text) {
    var node = document.createElementNS(NS, name);
    Object.keys(attributes || {}).forEach(function (key) {
      node.setAttribute(key, attributes[key]);
    });
    if (text) node.textContent = text;
    parent.appendChild(node);
    return node;
  }

  function hashTitle(title) {
    var hash = 2166136261;
    for (var i = 0; i < title.length; i += 1) {
      hash ^= title.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function classify(title) {
    var value = title.toLowerCase();
    if (/clinical hallucination|foundation model|prompt|clip-|multimodal|multi-modal|omics|\blvlm|\bgan\b|diffusion model/.test(value)) {
      return { key: "ai", label: "AI • MULTIMODAL" };
    }
    if (/brain tumor|cortical|alzheimer|dementia|neurodegenerative|perivascular|brain mapping/.test(value)) {
      return { key: "brain", label: "NEURO • IMAGING" };
    }
    if (/digital subtraction|\bdsa\b|cerebrovascular|cerebral artery|tof-mra|carotid/.test(value)) {
      return { key: "angio", label: "DSA • MRA" };
    }
    if (/corneal|cornea|pterygium|eyelash|cataract|anterior segment|optic disc|fovea/.test(value)) {
      return { key: "cornea", label: "ANTERIOR • EYE" };
    }
    if (/\boct\b|octa|optical coherence|choroid|macular|retinal layer|pathological fluid|hyperreflective/.test(value)) {
      return { key: "oct", label: "OCT • OCTA" };
    }
    if (/retina|retinal|ophthalmic|vessel|vascular|tubular|microaneurysm|arteriole|venule/.test(value)) {
      return { key: "retina", label: "RETINA • VESSELS" };
    }
    if (/microscope|multi-focus/.test(value)) {
      return { key: "micro", label: "MICRO • FUSION" };
    }
    if (/heart|\bcmr\b|parapneumonic|neonatal|facial expression/.test(value)) {
      return { key: "clinical", label: "CLINICAL • IMAGING" };
    }
    return { key: "ai", label: "MEDICAL • AI" };
  }

  function buildBase(svg, palette, id, label, index, hash) {
    var defs = add(svg, "defs", {});
    var gradient = add(defs, "linearGradient", { id: id, x1: "0", y1: "0", x2: "1", y2: "1" });
    add(gradient, "stop", { offset: "0%", "stop-color": palette.dark });
    add(gradient, "stop", { offset: "64%", "stop-color": palette.mid });
    add(gradient, "stop", { offset: "100%", "stop-color": palette.light });
    add(svg, "rect", { x: "0", y: "0", width: "176", height: "112", rx: "13", fill: "url(#" + id + ")" });

    var grid = add(svg, "g", { opacity: "0.1", stroke: "#ffffff", "stroke-width": "0.55" });
    [24, 48, 72, 96, 120, 144].forEach(function (x) {
      add(grid, "line", { x1: x, y1: "0", x2: x, y2: "112" });
    });
    [22, 44, 66, 88].forEach(function (y) {
      add(grid, "line", { x1: "0", y1: y, x2: "176", y2: y });
    });

    add(svg, "circle", {
      cx: 142 + (hash % 17), cy: 20 + (hash % 11), r: "34",
      fill: palette.glow, opacity: "0.1"
    });
    add(svg, "line", {
      class: "pub-scan", x1: "8", y1: "19", x2: "168", y2: "19",
      stroke: palette.glow, "stroke-width": "1", opacity: "0.7"
    });
    add(svg, "rect", { x: "8", y: "88", width: "93", height: "15", rx: "7.5", fill: "#071525", opacity: "0.54" });
    add(svg, "text", { class: "pub-visual-label", x: "15", y: "98.2", fill: "#ffffff", opacity: "0.94" }, label);
    add(svg, "text", { class: "pub-visual-index", x: "166", y: "98", fill: "#ffffff", opacity: "0.68", "text-anchor": "end" }, "MI² / " + String(index + 1).padStart(2, "0"));
  }

  function drawRetina(svg, palette, hash) {
    var turn = (hash % 13) - 6;
    add(svg, "circle", { cx: "79", cy: "45", r: "31", fill: "#061a2a", opacity: "0.56", stroke: "#ffffff", "stroke-opacity": "0.34", "stroke-width": "1" });
    add(svg, "circle", { cx: "61", cy: "45", r: "7", fill: palette.glow, opacity: "0.78" });
    var vessels = add(svg, "g", { fill: "none", stroke: "#f5fbff", "stroke-linecap": "round", transform: "rotate(" + turn + " 79 45)" });
    add(vessels, "path", { class: "pub-flow", d: "M61 45 C76 42 89 31 113 23 M75 40 C88 46 101 55 121 62 M70 47 C82 58 90 67 106 76", "stroke-width": "2.2" });
    add(vessels, "path", { d: "M84 35 C92 27 98 19 101 12 M92 32 C103 35 112 36 126 33 M93 51 C105 46 116 43 132 45 M91 61 C103 63 113 70 119 78 M78 56 C71 67 68 74 68 82", "stroke-width": "1.1", opacity: "0.78" });
    [[101, 12], [126, 33], [132, 45], [119, 78], [68, 82]].forEach(function (point) {
      add(svg, "circle", { cx: point[0], cy: point[1], r: "1.8", fill: palette.glow, opacity: "0.86" });
    });
  }

  function drawOct(svg, palette, hash) {
    var shift = hash % 6;
    add(svg, "rect", { x: "27", y: "13", width: "122", height: "66", rx: "5", fill: "#071a2d", opacity: "0.55", stroke: "#ffffff", "stroke-opacity": "0.3" });
    var layers = add(svg, "g", { fill: "none", "stroke-linecap": "round" });
    [0, 1, 2, 3, 4].forEach(function (i) {
      var y = 29 + i * 9;
      var curve = i % 2 === 0 ? shift : -shift;
      add(layers, "path", {
        d: "M31 " + y + " C58 " + (y - 6 + curve) + " 84 " + (y + 7) + " 111 " + (y + 1 - curve) + " S137 " + (y - 3) + " 145 " + y,
        stroke: i === 2 ? palette.glow : "#ffffff",
        "stroke-width": i === 2 ? "2.2" : "1.15",
        opacity: i === 2 ? "0.95" : String(0.4 + i * 0.09)
      });
    });
    add(svg, "ellipse", { cx: 87 + shift, cy: "50", rx: "9", ry: "5", fill: palette.light, opacity: "0.34", stroke: palette.glow, "stroke-width": "1" });
    add(svg, "line", { x1: 119 + shift, y1: "17", x2: 119 + shift, y2: "75", stroke: palette.glow, "stroke-width": "0.8", opacity: "0.72" });
  }

  function drawBrain(svg, palette, hash) {
    var group = add(svg, "g", { transform: "translate(" + ((hash % 5) - 2) + " 0)" });
    add(group, "path", { d: "M73 72 C53 73 41 62 44 48 C37 38 44 26 55 25 C58 14 72 12 80 19 C89 11 104 17 106 28 C119 29 124 43 117 53 C121 66 108 76 96 72 C89 79 78 79 73 72Z", fill: "#08172b", opacity: "0.58", stroke: "#ffffff", "stroke-width": "1.3", "stroke-opacity": "0.7" });
    add(group, "path", { d: "M81 20 C76 27 79 34 85 38 C76 42 76 51 83 55 C77 61 79 68 84 75 M58 27 C64 32 62 39 56 43 M107 30 C99 33 98 40 103 44 M49 54 C59 51 65 57 64 66 M101 54 C93 57 93 66 98 72", fill: "none", stroke: palette.light, "stroke-width": "1.4", opacity: "0.78", "stroke-linecap": "round" });
    var network = add(group, "g", { stroke: palette.glow, fill: palette.glow, "stroke-width": "0.9", opacity: "0.9" });
    add(network, "path", { class: "pub-flow", d: "M59 34 L73 46 L90 31 L105 47 L88 62 L67 60 Z", fill: "none" });
    [[59, 34], [73, 46], [90, 31], [105, 47], [88, 62], [67, 60]].forEach(function (point, i) {
      add(network, "circle", { cx: point[0], cy: point[1], r: i % 2 ? "2.3" : "1.8" });
    });
  }

  function drawAngio(svg, palette, hash) {
    var shift = (hash % 7) - 3;
    add(svg, "path", { d: "M91 12 C112 12 127 27 127 46 C127 59 121 69 111 75 L72 75 C62 67 57 57 57 46 C57 27 71 12 91 12Z", fill: "#061a2a", opacity: "0.52", stroke: "#ffffff", "stroke-opacity": "0.42" });
    var vessels = add(svg, "g", { fill: "none", stroke: palette.glow, "stroke-linecap": "round", transform: "translate(" + shift + " 0)" });
    add(vessels, "path", { class: "pub-flow", d: "M91 79 C90 65 91 54 89 42 C87 34 80 29 75 21 M90 56 C78 52 71 44 67 34 M90 48 C101 45 109 36 112 25", "stroke-width": "2.4" });
    add(vessels, "path", { d: "M88 42 C97 36 101 28 102 19 M79 51 C70 57 65 64 63 72 M102 44 C112 49 118 56 121 66 M76 31 C68 28 64 23 61 17 M111 35 C118 31 122 26 125 20", "stroke-width": "1.25", opacity: "0.84" });
    add(svg, "rect", { x: "137", y: "17", width: "2", height: "51", rx: "1", fill: "#ffffff", opacity: "0.36" });
    add(svg, "rect", { x: "137", y: 28 + (hash % 22), width: "2", height: "13", rx: "1", fill: palette.glow, opacity: "0.9" });
  }

  function drawCornea(svg, palette, hash) {
    var turn = (hash % 9) - 4;
    add(svg, "path", { d: "M31 47 Q87 10 145 47 Q88 83 31 47Z", fill: "#061a2a", opacity: "0.48", stroke: "#ffffff", "stroke-opacity": "0.62", "stroke-width": "1.3" });
    add(svg, "circle", { cx: "88", cy: "47", r: "21", fill: "none", stroke: palette.light, "stroke-width": "2", opacity: "0.68" });
    add(svg, "circle", { cx: "88", cy: "47", r: "8", fill: palette.glow, opacity: "0.76" });
    var nerves = add(svg, "g", { fill: "none", stroke: "#ffffff", "stroke-linecap": "round", transform: "rotate(" + turn + " 88 47)" });
    add(nerves, "path", { class: "pub-flow", d: "M39 62 C53 48 58 67 72 50 S94 29 107 42 S123 62 139 50", "stroke-width": "1.5", opacity: "0.9" });
    add(nerves, "path", { d: "M48 31 C63 43 61 58 79 69 M112 24 C104 35 111 49 124 55", "stroke-width": "1", opacity: "0.64" });
  }

  function drawAi(svg, palette, hash) {
    var shift = (hash % 9) - 4;
    var cards = [[24, 22], [53, 15], [112, 22], [126, 52], [37, 54]];
    cards.forEach(function (point, i) {
      add(svg, "rect", { x: point[0] + shift, y: point[1], width: i === 1 ? "29" : "24", height: i === 1 ? "22" : "19", rx: "4", fill: i === 1 ? palette.glow : "#071a2d", opacity: i === 1 ? "0.74" : "0.55", stroke: "#ffffff", "stroke-opacity": "0.5" });
    });
    var links = add(svg, "g", { fill: "none", stroke: "#ffffff", "stroke-width": "1", opacity: "0.66" });
    add(links, "path", { class: "pub-flow", d: "M48 31 L68 27 L89 48 L124 31 M89 48 L49 64 M89 48 L138 61" });
    add(svg, "circle", { cx: "89", cy: "48", r: "13", fill: palette.mid, stroke: palette.glow, "stroke-width": "1.6", opacity: "0.96" });
    add(svg, "path", { d: "M82 48 L87 53 L97 42", fill: "none", stroke: "#ffffff", "stroke-width": "2.1", "stroke-linecap": "round", "stroke-linejoin": "round" });
  }

  function drawMicro(svg, palette, hash) {
    var shift = (hash % 7) - 3;
    add(svg, "rect", { x: "34", y: "19", width: "68", height: "50", rx: "6", fill: "#071a2d", opacity: "0.58", stroke: "#ffffff", "stroke-opacity": "0.48" });
    add(svg, "rect", { x: "73", y: "27", width: "68", height: "50", rx: "6", fill: palette.mid, opacity: "0.48", stroke: palette.glow, "stroke-opacity": "0.76" });
    [[53, 37, 6], [79, 51, 9], [106, 42, 7], [122, 61, 5], [56, 59, 4]].forEach(function (cell, i) {
      add(svg, "circle", { cx: cell[0] + shift, cy: cell[1], r: cell[2], fill: i % 2 ? palette.glow : palette.light, opacity: i % 2 ? "0.48" : "0.34", stroke: "#ffffff", "stroke-opacity": "0.48" });
    });
    add(svg, "path", { class: "pub-flow", d: "M28 77 L58 64 L84 70 L110 54 L148 62", fill: "none", stroke: "#ffffff", "stroke-width": "1.2", opacity: "0.75" });
  }

  function drawClinical(svg, palette, hash) {
    var shift = (hash % 7) - 3;
    add(svg, "rect", { x: "26", y: "16", width: "124", height: "61", rx: "8", fill: "#061a2a", opacity: "0.52", stroke: "#ffffff", "stroke-opacity": "0.38" });
    add(svg, "path", { class: "pub-flow", d: "M32 52 L49 52 L57 38 L67 65 L78 46 L88 52 L103 52 L111 33 L122 62 L132 52 L145 52", fill: "none", stroke: palette.glow, "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round", transform: "translate(" + shift + " 0)" });
    add(svg, "circle", { cx: "47", cy: "29", r: "7", fill: palette.light, opacity: "0.42" });
    add(svg, "circle", { cx: "132", cy: "29", r: "7", fill: palette.mid, opacity: "0.58" });
  }

  var drawings = {
    retina: drawRetina,
    oct: drawOct,
    brain: drawBrain,
    angio: drawAngio,
    cornea: drawCornea,
    ai: drawAi,
    micro: drawMicro,
    clinical: drawClinical
  };

  function makeVisual(title, index) {
    var hash = hashTitle(title);
    var kind = classify(title);
    var palette = palettes[hash % palettes.length];
    var figure = document.createElement("figure");
    var svg = add(figure, "svg", {
      viewBox: "0 0 176 112",
      preserveAspectRatio: "xMidYMid slice",
      role: "img",
      "aria-label": kind.label + " representative illustration",
      focusable: "false"
    });
    var gradientId = "pub-gradient-" + index + "-" + (hash % 100000);
    figure.className = "publication-visual publication-visual--" + kind.key;
    buildBase(svg, palette, gradientId, kind.label, index, hash);
    drawings[kind.key](svg, palette, hash);
    return figure;
  }

  function ensureObserver() {
    if (observer || !("IntersectionObserver" in window)) return;
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var card = entry.target;
        if (entry.isIntersecting) {
          card.classList.add("is-in-view");
          if (!card.classList.contains("is-visible")) {
            var delay = Number(card.dataset.publicationIndex || 0) % 6 * 55;
            card.style.transitionDelay = delay + "ms";
            card.classList.add("is-visible");
            window.setTimeout(function () { card.style.transitionDelay = ""; }, delay + 620);
          }
        } else {
          card.classList.remove("is-in-view");
        }
      });
    }, { rootMargin: "90px 0px -4%", threshold: 0.06 });
  }

  function enhance() {
    var page = document.querySelector(".publication-page");
    if (!page) return;
    page.classList.add("publication-motion");
    ensureObserver();
    var cards = page.querySelectorAll(".publication-item");
    cards.forEach(function (card, index) {
      if (card.dataset.publicationVisual === "ready") return;
      card.dataset.publicationVisual = "ready";
      card.dataset.publicationIndex = index;
      card.style.setProperty("--visual-delay", (index % 7) * -430 + "ms");
      var heading = card.querySelector("h3");
      var dot = card.querySelector(":scope > .publication-dot");
      if (heading && dot) dot.insertAdjacentElement("afterend", makeVisual(heading.textContent.trim(), index));
      if (observer) {
        observer.observe(card);
      } else {
        card.classList.add("is-visible", "is-in-view");
      }
    });
  }

  function scheduleEnhance() {
    if (mutationFrame) return;
    mutationFrame = window.requestAnimationFrame(function () {
      mutationFrame = 0;
      enhance();
    });
  }

  function start() {
    scheduleEnhance();
    var app = document.getElementById("app");
    if (app && "MutationObserver" in window) {
      new MutationObserver(scheduleEnhance).observe(app, { childList: true, subtree: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
}());
