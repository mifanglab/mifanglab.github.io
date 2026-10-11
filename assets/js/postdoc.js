(function () {
  "use strict";
  var status = document.getElementById("copy-status");
  var timeout;

  function announce(message) {
    window.clearTimeout(timeout);
    status.textContent = message;
    status.classList.add("is-visible");
    timeout = window.setTimeout(function () {
      status.classList.remove("is-visible");
    }, 4000);
  }

  function fallbackCopy(text) {
    var previousFocus = document.activeElement;
    var input = document.createElement("textarea");
    input.value = text;
    input.setAttribute("readonly", "");
    input.style.position = "fixed";
    input.style.opacity = "0";
    input.style.top = "0";
    document.body.appendChild(input);
    input.select();
    input.setSelectionRange(0, text.length);
    var copied = false;
    try { copied = document.execCommand("copy"); }
    finally {
      input.remove();
      if (previousFocus && previousFocus.focus) previousFocus.focus({ preventScroll: true });
    }
    if (!copied) throw new Error("Copy unavailable");
  }

  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var text = button.getAttribute("data-copy");
      var result = window.isSecureContext && navigator.clipboard && navigator.clipboard.writeText
        ? navigator.clipboard.writeText(text).catch(function () { fallbackCopy(text); })
        : Promise.resolve().then(function () { fallbackCopy(text); });
      result.then(function () {
        announce(button.getAttribute("data-success"));
      }).catch(function () {
        announce("复制未成功，请长按选择：" + text);
      });
    });
  });

  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if ("IntersectionObserver" in window && !reducedMotion) {
    var reveal = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          reveal.unobserve(entry.target);
        }
      });
    }, { threshold: 0.04, rootMargin: "0px 0px -20px 0px" });
    document.documentElement.classList.add("motion-ready");
    document.querySelectorAll("[data-reveal]").forEach(function (element) { reveal.observe(element); });
  }

  if ("IntersectionObserver" in window) {
    var currentSection = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { entry.target.classList.toggle("is-current", entry.isIntersecting); });
    }, { rootMargin: "-12% 0px -55% 0px", threshold: 0 });
    document.querySelectorAll(".content-section").forEach(function (section) { currentSection.observe(section); });
  }

  var progress = document.querySelector(".reading-progress");
  var scheduled = false;
  function updateProgress() {
    var total = document.documentElement.scrollHeight - window.innerHeight;
    var ratio = total > 0 ? Math.min(1, Math.max(0, window.scrollY / total)) : 0;
    progress.style.transform = "scaleX(" + ratio + ")";
    scheduled = false;
  }
  function scheduleProgress() {
    if (!scheduled) {
      scheduled = true;
      window.requestAnimationFrame(updateProgress);
    }
  }
  window.addEventListener("scroll", scheduleProgress, { passive: true });
  window.addEventListener("resize", scheduleProgress);
  updateProgress();
}());
