import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  Menu,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  X,
  Zap,
} from "lucide-react";
import "./LandingPage.css";

const FALLBACK_LANDING_SETTINGS = {
  brand_name: "Loka-Kin",
  hero_kicker: "PLATFORM KINERJA TIM TERINTEGRASI",
  hero_title: "Dorong Kinerja Tim",
  hero_highlight: "Menjadi Lebih Optimal",
  hero_description: "Platform kinerja karyawan yang memudahkan penetapan target, pelacakan kemajuan, dan pengakuan prestasi secara real-time.",
  hero_cta: "Masuk",
  assurance_one: "Pantau progres real-time",
  assurance_two: "Laporan lebih terukur",
  nav_home: "Home",
  nav_features: "Fitur",
  nav_how: "Cara kerja",
  nav_about: "Tentang",
  show_features: true,
  features_title: "Kerja Tim Menjadi Lebih",
  features_highlight: "Terarah",
  features_description: "LOKA-Kin membantu tim menyusun target, menjalankan pekerjaan, dan melihat hasilnya dengan lebih jelas.",
  show_how: true,
  how_title: "Dari rencana menjadi hasil nyata.",
  how_description: "Semua orang tahu apa yang dikerjakan, siapa penanggung jawabnya, dan sejauh mana progresnya.",
  show_about: true,
  about_title: "Bangun ritme kerja yang lebih baik bersama LOKA-Kin.",
  about_description: "Satukan target, progres, dan capaian tim dalam satu tempat.",
  footer_text: "© LOKA-Kin. Loka Rehabilitasi Narkotika Kalianda.",
  accent_color: "#2458EC",
};

const landingNavigation = [
  { key: "nav_home", href: "#home", enabled: true },
  { key: "nav_features", href: "#fitur", enabledBy: "show_features" },
  { key: "nav_how", href: "#cara-kerja", enabledBy: "show_how" },
  { key: "nav_about", href: "#tentang", enabledBy: "show_about" },
];

const features = [
  {
    icon: Target,
    tone: "blue",
    title: "Target yang terukur",
    description: "Ubah rencana kerja menjadi target yang jelas dan mudah dipantau setiap hari.",
  },
  {
    icon: Activity,
    tone: "violet",
    title: "Progres real-time",
    description: "Lihat perkembangan tugas tim dalam satu ruang kerja yang selalu diperbarui.",
  },
  {
    icon: Users,
    tone: "gold",
    title: "Kolaborasi lebih rapi",
    description: "Semua laporan terhubung dengan staf penanggung jawab dan unit kerjanya.",
  },
];

function DashboardArtwork() {
  return (
    <div className="hero-visual" aria-label="Ilustrasi dashboard kinerja tim LOKA-Kin">
      <div className="visual-halo" />
      <div className="visual-orbit visual-orbit-one" />
      <div className="visual-orbit visual-orbit-two" />
      <span className="visual-spark visual-spark-one">✦</span>
      <span className="visual-spark visual-spark-two">✦</span>

      <div className="floating-metric floating-metric-progress">
        <span className="floating-metric-icon"><TrendingUp size={17} /></span>
        <span><small>Penyelesaian tugas</small><strong>84% <i>+12%</i></strong></span>
      </div>
      <div className="floating-metric floating-metric-team">
        <span className="mini-avatar-stack"><i>RA</i><i>DI</i><i>+8</i></span>
        <span><strong>Tim kompak</strong><small>Aktivitas terpantau</small></span>
        <CheckCircle2 size={17} className="team-check" />
      </div>

      <div className="dashboard-window">
        <div className="dashboard-window-top">
          <div className="window-dots" aria-hidden="true"><i /><i /><i /></div>
          <div className="window-location"><span className="window-logo">LK</span> Ruang Kinerja</div>
          <div className="window-user"><span>RA</span><i /></div>
        </div>
        <div className="dashboard-window-body">
          <aside className="mock-sidebar" aria-hidden="true">
            <span className="mock-side-mark"><ShieldCheck size={17} /></span>
            <i className="mock-side-active"><BarChart3 size={14} /></i>
            <i><Target size={14} /></i>
            <i><Users size={14} /></i>
            <i><Activity size={14} /></i>
            <span className="mock-side-bottom"><i /></span>
          </aside>
          <div className="mock-dashboard-content">
            <div className="mock-heading">
              <div><small>RINGKASAN KINERJA</small><strong>Performa tim</strong></div>
              <button type="button">7 hari <ChevronDown size={12} /></button>
            </div>
            <div className="mock-stat-grid">
              <div className="mock-stat-card"><span>Total tugas</span><b>128</b><small><i>↑ 8,4%</i> dari pekan lalu</small></div>
              <div className="mock-stat-card"><span>Tugas selesai</span><b>96</b><small><i>↑ 12,2%</i> dari pekan lalu</small></div>
            </div>
            <div className="mock-chart-card">
              <div className="mock-chart-title"><span>Tren penyelesaian</span><small><i /> Target tercapai</small></div>
              <div className="mock-chart-area">
                <div className="mock-y-labels"><span>100</span><span>75</span><span>50</span><span>25</span></div>
                <div className="mock-chart-plot">
                  <div className="mock-chart-lines"><i /><i /><i /><i /></div>
                  <div className="mock-bars" aria-hidden="true">
                    <i style={{ height: "34%" }} /><i style={{ height: "48%" }} /><i style={{ height: "44%" }} />
                    <i style={{ height: "63%" }} /><i style={{ height: "57%" }} /><i style={{ height: "77%" }} /><i style={{ height: "91%" }} />
                  </div>
                  <svg className="mock-trend-line" viewBox="0 0 360 120" preserveAspectRatio="none" aria-hidden="true">
                    <defs><linearGradient id="trendStroke" x1="0" x2="1"><stop offset="0" stopColor="#f7b538" /><stop offset="1" stopColor="#ff8b3d" /></linearGradient></defs>
                    <path d="M8 88 C40 82 43 69 63 74 S99 56 115 62 S148 46 166 52 S202 28 218 37 S254 25 269 29 S306 9 324 17 S345 4 353 8" fill="none" stroke="url(#trendStroke)" strokeWidth="5" strokeLinecap="round" />
                    <path d="M335 8 L353 8 L352 26" fill="none" stroke="#ff8b3d" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
                    <circle cx="269" cy="29" r="5" fill="#fff" stroke="#ff9b38" strokeWidth="3" />
                  </svg>
                </div>
              </div>
              <div className="mock-x-labels"><span>Sen</span><span>Sel</span><span>Rab</span><span>Kam</span><span>Jum</span><span>Sab</span><span>Min</span></div>
            </div>
            <div className="mock-bottom-row">
              <span><i className="mock-bottom-dot blue-dot" /> To Do <b>18</b></span>
              <span><i className="mock-bottom-dot yellow-dot" /> Doing <b>14</b></span>
              <span><i className="mock-bottom-dot green-dot" /> Selesai <b>96</b></span>
            </div>
          </div>
        </div>
      </div>

      <div className="artwork-caption"><span><Zap size={14} fill="currentColor" /></span> Semua progres, satu dashboard</div>

      <svg className="team-illustration" viewBox="0 0 560 270" role="img" aria-label="Tim sedang berkolaborasi di depan dashboard">
        <defs>
          <linearGradient id="tableTop" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stopColor="#fff" /><stop offset="1" stopColor="#dce9ff" /></linearGradient>
          <linearGradient id="chairBlue" x1="0" x2="1"><stop offset="0" stopColor="#514de0" /><stop offset="1" stopColor="#3989f4" /></linearGradient>
          <linearGradient id="shirtGold" x1="0" x2="1"><stop offset="0" stopColor="#ffc64d" /><stop offset="1" stopColor="#f39a2d" /></linearGradient>
          <linearGradient id="shirtPurple" x1="0" x2="1"><stop offset="0" stopColor="#8b63ee" /><stop offset="1" stopColor="#5d49cf" /></linearGradient>
        </defs>
        <ellipse cx="282" cy="247" rx="232" ry="16" fill="#182c89" opacity=".2" />

        {/* Kursi dan figur kiri */}
        <path d="M76 152v49c0 23 19 34 47 34s47-11 47-34v-45" fill="none" stroke="url(#chairBlue)" strokeWidth="13" strokeLinecap="round" />
        <path d="M96 222v21m55-21v21" stroke="#5c6bdc" strokeWidth="8" strokeLinecap="round" />
        <path d="M103 156c7-14 34-18 49-5l17 42-13 23h-59l-11-22z" fill="url(#shirtGold)" />
        <path d="M104 185l-27 16 20 13 24-17m35-11 20 20-18 13-20-18" fill="none" stroke="#c98460" strokeWidth="11" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="119" y="132" width="13" height="23" rx="6" fill="#c98460" />
        <circle cx="126" cy="111" r="25" fill="#d99b72" />
        <path d="M101 108c0-20 13-32 31-30 16 2 24 15 20 31-8-3-15-10-18-18-6 11-17 17-33 17z" fill="#3a2b3e" />
        <circle cx="118" cy="112" r="1.8" fill="#382a35" /><circle cx="135" cy="112" r="1.8" fill="#382a35" />
        <path d="M120 122q7 6 13 0" fill="none" stroke="#9a554d" strokeWidth="2" strokeLinecap="round" />

        {/* Figur berdiri di tengah */}
        <path d="M237 130c8-15 38-17 51-3l14 63-12 40h-61l-9-39z" fill="#f8fbff" />
        <path d="M241 157l-32 30 7 12 38-19m42-25 29-19 8 10-27 31" fill="none" stroke="#d59672" strokeWidth="12" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M245 225l-3 23m39-23 6 23" stroke="#354798" strokeWidth="13" strokeLinecap="round" />
        <path d="M244 133l17 22 16-22" fill="#4d65da" />
        <rect x="255" y="104" width="14" height="26" rx="7" fill="#c98662" />
        <circle cx="262" cy="84" r="25" fill="#d99a70" />
        <path d="M237 83c1-20 13-32 30-30 16 1 24 14 20 30-11-3-19-10-22-19-6 9-15 16-28 19z" fill="#5a382b" />
        <circle cx="254" cy="86" r="1.8" fill="#382a35" /><circle cx="271" cy="86" r="1.8" fill="#382a35" />
        <path d="M256 96q7 6 13 0" fill="none" stroke="#9a554d" strokeWidth="2" strokeLinecap="round" />

        {/* Kursi dan figur kanan */}
        <path d="M344 161v43c0 22 19 33 46 33s45-11 45-33v-38" fill="none" stroke="#5b56dc" strokeWidth="13" strokeLinecap="round" />
        <path d="M366 225v18m49-18v18" stroke="#5c6bdc" strokeWidth="8" strokeLinecap="round" />
        <path d="M359 163c11-17 42-16 54 2l12 39-17 20h-53l-8-24z" fill="url(#shirtPurple)" />
        <path d="M361 188l-27 24 13 11 30-20m39-16 20 22-16 11-20-18" fill="none" stroke="#cb8c69" strokeWidth="11" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="379" y="139" width="13" height="22" rx="6" fill="#cb8c69" />
        <circle cx="386" cy="118" r="25" fill="#e0a77e" />
        <path d="M361 114c0-19 13-31 30-29 16 2 24 14 19 29-9-1-19-7-23-17-6 10-14 16-26 17z" fill="#272a43" />
        <circle cx="378" cy="119" r="1.8" fill="#382a35" /><circle cx="395" cy="119" r="1.8" fill="#382a35" />
        <path d="M380 129q7 6 13 0" fill="none" stroke="#9a554d" strokeWidth="2" strokeLinecap="round" />

        {/* Meja, laptop, dan tanaman */}
        <path d="M40 196c0-7 6-12 13-12h433c8 0 14 5 14 12v12H40z" fill="url(#tableTop)" />
        <path d="M66 208h408l-17 18H83z" fill="#d8e7ff" />
        <path d="M110 207v31m344-31v31" stroke="#eef4ff" strokeWidth="9" strokeLinecap="round" />
        <path d="M166 187h53l-7-31h-39z" fill="#344978" />
        <path d="M174 182h39l-5-21h-30z" fill="#a9d9ff" />
        <path d="M329 185h56l-8-34h-40z" fill="#344978" />
        <path d="M338 179h41l-5-24h-30z" fill="#bfdbff" />
        <path d="M475 183c-6-12-1-23 7-32 7 12 8 24 0 32m5 0c0-16 8-25 20-30 0 13-5 24-16 30m-15 1h28l-4 18h-20z" fill="#5dc78d" />
        <path d="M472 200h36l-4 15h-28z" fill="#f2a34b" />
      </svg>
    </div>
  );
}

export default function LandingPage({ onLogin, authenticated = false, settings = {} }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("#home");
  const pageRef = useRef(null);

  const navigateToSection = useCallback((href, updateHistory = true) => {
    if (!["#home", "#fitur", "#cara-kerja", "#tentang"].includes(href)) return;
    const section = pageRef.current?.querySelector(href);
    if (!section) return;
    setMobileMenuOpen(false);
    setActiveSection(href);
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    section.scrollIntoView?.({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
    section.focus({ preventScroll: true });
    if (updateHistory && window.location.hash !== href) {
      try {
        // Update this app's URL, never the Arena parent frame's navigation.
        window.history.pushState(null, "", href);
      } catch {
        // Scrolling still works when an embedded browser restricts history.
      }
    }
  }, []);

  const handleSectionClick = (event, href) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigateToSection(href);
  };

  useEffect(() => {
    const restoreSection = () => navigateToSection(window.location.hash || "#home", false);
    if (window.location.hash) restoreSection();
    window.addEventListener("hashchange", restoreSection);
    window.addEventListener("popstate", restoreSection);
    return () => {
      window.removeEventListener("hashchange", restoreSection);
      window.removeEventListener("popstate", restoreSection);
    };
  }, [navigateToSection, settings?.show_features, settings?.show_how, settings?.show_about]);
  const content = { ...FALLBACK_LANDING_SETTINGS, ...(settings || {}) };
  const navLinks = landingNavigation
    .filter((link) => link.enabled || content[link.enabledBy])
    .map((link) => ({ label: content[link.key], href: link.href }));

  const openDashboard = () => {
    setMobileMenuOpen(false);
    onLogin?.();
  };

  return (
    <div ref={pageRef} className="landing-page" style={{ "--landing-primary": content.accent_color || "#2458EC" }}>
      <section className="landing-stage" id="home" tabIndex={-1}>
        <div className="landing-frame">
          <div className="landing-decoration landing-decoration-coin coin-one" aria-hidden="true">✦</div>
          <div className="landing-decoration landing-decoration-coin coin-two" aria-hidden="true">◉</div>
          <div className="landing-decoration landing-decoration-coin coin-three" aria-hidden="true">✦</div>
          <div className="landing-decoration landing-decoration-spark spark-one" aria-hidden="true">✦</div>
          <div className="landing-decoration landing-decoration-spark spark-two" aria-hidden="true">✧</div>

          <header className="landing-header">
            <a className="landing-brand" href="#home" aria-label="LOKA-Kin beranda" onClick={(event) => handleSectionClick(event, "#home")}>
              <span className="landing-brand-mark"><ShieldCheck size={24} strokeWidth={2.7} /></span>
              <span className="landing-brand-name">{content.brand_name}</span>
            </a>

            <button
              className="landing-menu-toggle"
              type="button"
              aria-label={mobileMenuOpen ? "Tutup menu" : "Buka menu"}
              aria-expanded={mobileMenuOpen}
              onClick={() => setMobileMenuOpen((open) => !open)}
            >
              {mobileMenuOpen ? <X size={21} /> : <Menu size={21} />}
            </button>

            <nav className={mobileMenuOpen ? "landing-nav is-open" : "landing-nav"} aria-label="Navigasi utama">
              {navLinks.map((link) => (
                <a
                  className={activeSection === link.href ? "landing-nav-link is-active" : "landing-nav-link"}
                  aria-current={activeSection === link.href ? "location" : undefined}
                  href={link.href}
                  key={link.href}
                  onClick={(event) => handleSectionClick(event, link.href)}
                >
                  {link.label}
                </a>
              ))}
            </nav>

            <div className="landing-header-actions">
              <a className="landing-home-quicklink" href="#home" data-testid="landing-home-quicklink" onClick={(event) => handleSectionClick(event, "#home")}>{content.nav_home}</a>
              <button className="landing-header-cta" type="button" onClick={openDashboard}>
                {authenticated ? "Dashboard" : content.hero_cta} <ArrowUpRight size={15} />
              </button>
            </div>
          </header>

          <main>
            <div className="landing-hero">
              <div className="hero-copy">
                <div className="hero-kicker"><Sparkles size={14} /> {content.hero_kicker}</div>
                <h1>{content.hero_title} <span>{content.hero_highlight}</span></h1>
                <p className="hero-description">{content.hero_description}</p>
                <div className="hero-actions">
                  <button className="hero-button hero-button-start" type="button" onClick={openDashboard}>
                    {authenticated ? "Buka dashboard" : content.hero_cta} <ArrowRight size={17} />
                  </button>
                </div>
                <div className="hero-assurance">
                  <span><CheckCircle2 size={15} /> {content.assurance_one}</span>
                  <i />
                  <span><CheckCircle2 size={15} /> {content.assurance_two}</span>
                </div>
              </div>
              <DashboardArtwork />
            </div>

            <svg className="hero-wave" viewBox="0 0 1440 125" preserveAspectRatio="none" aria-hidden="true">
              <path d="M0,58 C190,119 360,117 540,85 C742,49 835,109 1016,100 C1187,92 1305,47 1440,52 L1440,125 L0,125 Z" fill="#f7faff" />
            </svg>
          </main>
        </div>
      </section>

      {content.show_features && <section className="landing-features landing-section" id="fitur" tabIndex={-1}>
        <div className="landing-section-heading">
          <span className="landing-section-kicker">SATU RUANG KERJA, BANYAK KEMAJUAN</span>
          <h2>{content.features_title} <em>{content.features_highlight}</em></h2>
          <p>{content.features_description}</p>
        </div>
        <div className="landing-feature-grid">
          {features.map(({ icon: Icon, tone, title, description }, index) => (
            <article className="landing-feature-card" key={title}>
              <div className={`feature-icon ${tone}`}><Icon size={21} /></div>
              <span className="feature-number">0{index + 1}</span>
              <h3>{title}</h3>
              <p>{description}</p>
              <a href="#cara-kerja" onClick={(event) => handleSectionClick(event, "#cara-kerja")} aria-label={`Pelajari ${title}`}><ArrowUpRight size={17} /></a>
            </article>
          ))}
        </div>
      </section>}

      {content.show_how && <section className="landing-how-it-works landing-section" id="cara-kerja" tabIndex={-1}>
        <div className="how-copy">
          <span className="landing-section-kicker">ALUR YANG SEDERHANA</span>
          <h2>{content.how_title}</h2>
          <p>{content.how_description}</p>
          <button className="how-cta" type="button" onClick={openDashboard}>Jelajahi dashboard <ArrowRight size={16} /></button>
        </div>
        <div className="how-steps">
          <article><span>01</span><div><strong>Tetapkan target</strong><p>Buat laporan dan sasaran kerja yang jelas.</p></div></article>
          <article><span>02</span><div><strong>Pantau progres</strong><p>Perbarui status pekerjaan seiring proses berjalan.</p></div></article>
          <article><span>03</span><div><strong>Target Capaian</strong><p>Lihat hasil kerja dan apresiasi kontribusi tim.</p></div></article>
        </div>
      </section>}

      {content.show_about && <section className="landing-cta-section" id="tentang" tabIndex={-1}>
        <div className="landing-cta-glow" />
        <span className="landing-section-kicker">MULAI LANGKAH BERIKUTNYA</span>
        <h2>{content.about_title}</h2>
        <p>{content.about_description}</p>
        <button type="button" onClick={openDashboard}>Buka dashboard <ArrowRight size={17} /></button>
      </section>}

      <footer className="landing-footer">
        <a className="landing-footer-brand" href="#home" onClick={(event) => handleSectionClick(event, "#home")}><span className="landing-brand-mark"><ShieldCheck size={19} /></span> {content.brand_name}</a>
        <span>{content.footer_text.replace("©", `© ${new Date().getFullYear()}`)}</span>
        <a href="#home" onClick={(event) => handleSectionClick(event, "#home")}>Kembali ke atas <ChevronDown size={14} /></a>
      </footer>
    </div>
  );
}
