import { act } from "react";
import { createRoot } from "react-dom/client";
import LandingPage from "./LandingPage";

test("landing page displays the updated hero, features and achievement wording", async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  try {
    await act(async () => { root.render(<LandingPage />); });
    expect(container.querySelector("h1").textContent).toBe("Dorong Kinerja Tim Menjadi Lebih Optimal");
    expect(container.querySelector("#fitur h2").textContent).toBe("Kerja Tim Menjadi Lebih Terarah");
    expect(container.querySelector(".how-steps article:last-child strong").textContent).toBe("Target Capaian");
    expect(container.textContent).not.toMatch(/rayakan\s+capaian/i);
  } finally {
    await act(async () => { root.unmount(); });
    container.remove();
    delete global.IS_REACT_ACT_ENVIRONMENT;
  }
});

beforeEach(() => { window.history.replaceState(null, "", "/"); });
afterEach(() => { jest.restoreAllMocks(); window.history.replaceState(null, "", "/"); });

test("each menu scrolls to its section, updates the active link and closes the mobile menu", async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const scroll = jest.fn();
  const previous = HTMLElement.prototype.scrollIntoView;
  HTMLElement.prototype.scrollIntoView = scroll;
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  try {
    await act(async () => { root.render(<LandingPage />); });
    for (const href of ["#fitur", "#cara-kerja", "#tentang", "#home"]) {
      await act(async () => { container.querySelector(".landing-menu-toggle").click(); });
      expect(container.querySelector(".landing-nav").classList.contains("is-open")).toBe(true);
      const link = container.querySelector(`.landing-nav a[href="${href}"]`);
      await act(async () => { link.click(); });
      expect(window.location.hash).toBe(href);
      expect(link.getAttribute("aria-current")).toBe("location");
      expect(document.activeElement).toBe(container.querySelector(href));
      expect(scroll.mock.instances.at(-1)).toBe(container.querySelector(href));
      expect(container.querySelector(".landing-nav").classList.contains("is-open")).toBe(false);
    }
  } finally {
    await act(async () => { root.unmount(); });
    container.remove();
    HTMLElement.prototype.scrollIntoView = previous;
    delete global.IS_REACT_ACT_ENVIRONMENT;
  }
});

test("hidden sections do not produce dead navigation links", async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.createElement("div");
  const root = createRoot(container);
  try {
    await act(async () => { root.render(<LandingPage settings={{ show_features: false, show_how: false, show_about: false }} />); });
    expect(container.querySelectorAll(".landing-nav a")).toHaveLength(1);
    for (const href of ["#fitur", "#cara-kerja", "#tentang"]) {
      expect(container.querySelector(href)).toBeNull();
    }
  } finally {
    await act(async () => { root.unmount(); });
    delete global.IS_REACT_ACT_ENVIRONMENT;
  }
});
