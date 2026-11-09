---
name: web-development
description: Build websites and web apps with HTML, CSS and JavaScript — layout, responsive design, forms, accessibility, fetching data, and getting a site online. Use for "make a website", "fix my CSS", "how do I center this", "build a landing page", "JavaScript isn't working".
audience: developers
field: Technology
courses: MDN Learn Web Development (Mozilla) | https://developer.mozilla.org/en-US/docs/Learn_web_development ; freeCodeCamp Responsive Web Design and JavaScript certifications | https://www.freecodecamp.org/learn ; The Odin Project Foundations | https://www.theodinproject.com/ ; web.dev Learn (Google) | https://web.dev/learn
source: Echo (written for Echo from these courses' syllabi)
license: same as Echo
---

# Web development

## 1. How the web works
A browser asks a server for a page (HTTP); it gets **HTML** (structure), **CSS** (looks) and **JavaScript** (behaviour). DevTools (F12) shows the page's elements, styles, console errors and network requests — open it first when something looks wrong.

## 2. HTML: meaning first
- Use semantic tags: `header, nav, main, section, article, footer, h1–h6, button, a, label`.
- One `h1` per page; headings in order; every image has `alt` text; every input has a `<label>`.
- Forms: `<form>`, `name` on inputs, proper `type` (`email`, `tel`, `number`), and `required` where needed.

## 3. CSS: layout without fighting it
- Box model: content + padding + border + margin; set `box-sizing: border-box` everywhere.
- **Flexbox** for one direction (nav bars, centring: `display:flex; justify-content:center; align-items:center`). **Grid** for two-dimensional page layouts.
- **Responsive**: mobile-first styles, then `@media (min-width: 768px)`; relative units (`rem`, `%`, `clamp()`); `<meta name="viewport" content="width=device-width, initial-scale=1">`.
- Keep colours and spacing in CSS variables (`--brand: #0a7`).

## 4. JavaScript basics
- Select and change: `document.querySelector`, `element.addEventListener("click", …)`, `textContent`, `classList.toggle`.
- Data: `fetch(url).then(r => r.json())` or `async/await` with `try/catch`; show loading and error states.
- Never put secret API keys in front-end code.

## 5. Accessibility and performance checklist
Keyboard works everywhere (Tab order, visible focus); colour contrast ≥ 4.5:1; images compressed (WebP/AVIF) with width/height set; lazy-load below-the-fold images; run Lighthouse in DevTools and fix the top issues.

## 6. Getting it online
Static sites: GitHub Pages, Netlify or Cloudflare Pages (free). With a backend: a small VPS or a platform like Render. Buy a domain, point DNS, and use HTTPS. For sites that must stay private (home or office only), keep them on the local network instead.

## 7. Debugging routine
Reproduce → check the console for the first red error → check the element's computed styles → check the network tab for failed requests (status 404/500, CORS) → change one thing at a time.
