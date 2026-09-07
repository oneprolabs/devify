// Builds and navigates to a mailto: link only at click time, inside the
// browser. This keeps the address out of the prerendered static HTML (which
// VitePress generates via SSR) so plain HTML-scraping bots never see it —
// the address only ever exists inside this compiled function body and the
// live DOM after a real click.
export function openMail({ user, domain, subject }) {
  const query = subject ? `?subject=${encodeURIComponent(subject)}` : ''
  window.location.href = `mailto:${user}@${domain}${query}`
}
