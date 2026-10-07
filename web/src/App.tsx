import { content } from "./content";

export function App() {
  return (
    <div className="app">
      <a className="skip-link" href="#main">
        {content.skipLink}
      </a>
      <header className="topbar">
        <p className="brand">{content.product}</p>
      </header>
      <nav className="sidebar" aria-label={content.navLabel}>
        <ul>
          {content.nav.map((item) => (
            <li key={item.href}>
              <a href={item.href} aria-current="page">
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <main id="main" tabIndex={-1}>
        <h1>{content.pageTitle}</h1>
        <section className="card" aria-labelledby="empty-title">
          <h2 id="empty-title">{content.emptyTitle}</h2>
          <p>{content.emptyBody}</p>
        </section>
      </main>
    </div>
  );
}
