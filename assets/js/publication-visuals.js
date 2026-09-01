(function () {
  "use strict";

  var observer;
  var mutationFrame;
  var sourceMap = {};

  function publicationId(index) {
    return "pub-" + String(index + 1).padStart(3, "0");
  }

  function loadSources() {
    return window.fetch("/assets/img/publications/sources.json", { cache: "force-cache" })
      .then(function (response) {
        if (!response.ok) throw new Error("Unable to load publication image sources");
        return response.json();
      })
      .then(function (entries) {
        return entries.reduce(function (map, entry) {
          if (entry.image && entry.image_source) map[entry.id] = entry;
          return map;
        }, {});
      })
      .catch(function () { return {}; });
  }

  function makeVisual(entry, title, card) {
    var figure = document.createElement("figure");
    var image = document.createElement("img");
    figure.className = "publication-visual";
    image.src = entry.image;
    image.alt = "Representative figure from “" + title + "”";
    image.loading = "lazy";
    image.decoding = "async";
    image.addEventListener("error", function () {
      figure.remove();
      card.classList.add("publication-item--no-visual");
    }, { once: true });
    figure.appendChild(image);
    return figure;
  }

  function ensureObserver() {
    if (observer || !("IntersectionObserver" in window)) return;
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var card = entry.target;
        if (entry.isIntersecting && !card.classList.contains("is-visible")) {
          var delay = Number(card.dataset.publicationIndex || 0) % 6 * 55;
          card.style.transitionDelay = delay + "ms";
          card.classList.add("is-visible");
          window.setTimeout(function () { card.style.transitionDelay = ""; }, delay + 620);
        }
      });
    }, { rootMargin: "90px 0px -4%", threshold: 0.06 });
  }

  function enhance() {
    var page = document.querySelector(".publication-page");
    if (!page) return;
    page.classList.add("publication-motion");
    ensureObserver();

    page.querySelectorAll(".publication-item").forEach(function (card, index) {
      if (card.dataset.publicationVisual === "ready") return;
      card.dataset.publicationVisual = "ready";
      card.dataset.publicationIndex = index;

      var heading = card.querySelector("h3");
      var dot = card.querySelector(":scope > .publication-dot");
      var entry = sourceMap[publicationId(index)];
      if (heading && dot && entry) {
        dot.insertAdjacentElement("afterend", makeVisual(entry, heading.textContent.trim(), card));
      } else {
        card.classList.add("publication-item--no-visual");
      }

      if (observer) observer.observe(card);
      else card.classList.add("is-visible");
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
    loadSources().then(function (sources) {
      sourceMap = sources;
      scheduleEnhance();
      var app = document.getElementById("app");
      if (app && "MutationObserver" in window) {
        new MutationObserver(scheduleEnhance).observe(app, { childList: true, subtree: true });
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
}());
