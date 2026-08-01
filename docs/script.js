document.documentElement.classList.add("reveal-ready");

const navToggle = document.querySelector(".nav-toggle");
const siteNav = document.querySelector(".site-nav");

if (navToggle && siteNav) {
  navToggle.addEventListener("click", () => {
    const isOpen = siteNav.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", String(isOpen));
  });

  siteNav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      siteNav.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
    });
  });
}

const revealItems = document.querySelectorAll("[data-reveal]");

if ("IntersectionObserver" in window) {
  const revealObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  revealItems.forEach((item) => {
    const isInitiallyVisible = item.getBoundingClientRect().top < window.innerHeight * 1.05;
    if (isInitiallyVisible) {
      item.classList.add("is-visible");
    } else {
      revealObserver.observe(item);
    }
  });
} else {
  revealItems.forEach((item) => item.classList.add("is-visible"));
}

const currentYear = document.querySelector("#current-year");
if (currentYear) currentYear.textContent = new Date().getFullYear();

// On GitHub Pages, infer the repository URL from the standard hostname and
// project path. Local fallbacks remain useful when opening the site from disk.
const isGitHubPages = window.location.hostname.endsWith(".github.io");
if (isGitHubPages) {
  const owner = window.location.hostname.split(".")[0];
  const repository = window.location.pathname.split("/").filter(Boolean)[0];

  if (owner && repository) {
    const repositoryUrl = `https://github.com/${owner}/${repository}`;
    document.querySelectorAll("[data-repo-link]").forEach((link) => {
      link.href = repositoryUrl;
      link.target = "_blank";
      link.rel = "noreferrer";
    });

    document.querySelectorAll("[data-report-link]").forEach((link) => {
      link.href = `${repositoryUrl}/raw/refs/heads/main/dashboard/healthcare_operations_intelligence.pbix`;
    });
  }
}
