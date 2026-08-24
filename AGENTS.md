# AGENTS.md

## Tech Stack

- Next.js (App Router)
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- lucide-react

Use shadcn/ui for common UI components whenever appropriate.

Use lucide-react as the icon library. Do not introduce additional icon packages without a clear reason.

Do not introduce another UI framework without a clear reason.

---

## Responsive UI

This is a responsive web application for desktop, tablet, and mobile.

- Use Mobile First design.
- Base styles should target mobile.
- Use `md:`, `lg:`, and `xl:` to progressively enhance larger screens.
- Avoid `max-*:` responsive overrides unless necessary.
- Prefer `h-dvh` / `min-h-dvh` over `h-screen` / `min-h-screen` for full-height mobile layouts.
- Consider safe-area insets for fixed or sticky elements attached to mobile viewport edges.
- Mobile inputs, selects, and textareas should use at least `text-base` (16px).
- Use `min-w-0` for flex/grid children containing dynamic content.
- Long URLs, IPv6 addresses, UUIDs, hostnames, provider names, and plan names must not cause unintended horizontal overflow.
- Use `break-words` where appropriate.
- Use `overflow-x-auto` for content that legitimately requires horizontal scrolling, such as wide tables and code blocks.
- Prefer responsive CSS/layout over duplicated mobile and desktop DOM.
- Mobile layouts should adapt information density and interaction patterns rather than simply shrinking desktop layouts.

### Responsive Component Preferences

- Use `Sheet` for mobile navigation when appropriate.
- Consider `Drawer` for complex mobile filters and action panels.
- Use `Dialog` for short confirmations and alerts.
- Reuse shadcn/ui primitives instead of creating equivalent components from scratch.

### Styling

- Use Tailwind CSS for normal styling.
- Avoid unnecessary custom CSS and inline `style=""`.
- Always use `cn()` when merging Tailwind classes or custom `className` props.
- Do not manually concatenate Tailwind class strings when class merging is required.

---

## Accessibility

Build accessible interfaces by default.

- Use semantic HTML elements.
- Use `<button>` instead of clickable `<div>` elements.
- Form controls must have appropriate labels.
- Interactive elements must be keyboard accessible.
- Maintain visible focus states.
- Provide accessible names for icon-only buttons.
- Do not rely on color alone to communicate important information.
- Maintain sufficient color contrast and readable text sizes.

---

## Next.js / React

- Prefer Server Components by default.
- Only use `"use client"` when client-side interaction, state, effects, or browser APIs actually require it.
- Avoid unnecessary client-side JavaScript.
- Use Next.js Metadata and appropriate SEO practices for public pages.
- Prefer semantic HTML and accessible interactive elements.
- Provide appropriate loading, error, empty, and not-found states where applicable.

---

## VPS Data

This project monitors, compares, and recommends VPS products.

Important user-facing information includes:

- Provider
- Location
- Price
- CPU / RAM / Storage
- Traffic / Bandwidth
- Network / Route
- Availability
- Recommendation score
- Discounts and price changes

Desktop can display more information simultaneously.

Mobile should prioritize important information and move secondary details into expandable sections, drawers, or detail pages when appropriate.

Large tables must have an intentional mobile strategy, such as:

- Horizontal scrolling
- Reduced columns
- Hidden secondary columns
- Responsive cards

Do not simply squeeze a large desktop table into a mobile screen.

---

## Data Freshness

VPS inventory and pricing can change frequently.

- Store and preserve the timestamp of crawled or updated VPS data.
- Indicate when data was last updated when freshness matters.
- Distinguish stale or expired data from recently verified data.
- Do not present outdated availability or pricing information as real-time data.
- Preserve historical timestamps when historical tracking is required.

---

## Pricing

- Preserve the original price and currency returned by each provider.
- Never overwrite the original provider price with a converted value.
- Handle currency conversion separately from the original price.
- Use a consistent exchange-rate strategy for cross-currency comparisons.
- Clearly distinguish original prices from converted or estimated prices.
- Do not imply that a converted price is the provider's actual billed price.

---

## Backend

- Keep API routes, business logic, data access, and external services separated.
- Keep business logic out of API route handlers when practical.
- Follow the project's existing validation, typing, and data-access conventions.
- Do not introduce a new validation library or backend framework without a clear reason.
- Handle API errors explicitly and return appropriate status codes.
- Do not expose secrets or sensitive information through APIs or logs.
- Avoid unnecessary database queries and N+1 query patterns.
- Use asynchronous code appropriately for I/O-bound operations.
- Keep API changes backward-compatible when practical.

---

## Crawlers & Background Jobs

- Keep provider-specific crawler logic isolated from shared crawler utilities.
- Prefer provider-specific adapters over duplicated crawler implementations.
- Make data ingestion idempotent.
- Prefer upsert or equivalent mechanisms based on stable provider and plan identifiers.
- Make scheduled jobs safe to retry.
- Use reasonable timeouts and bounded retry strategies.
- Respect provider rate limits.
- Support configurable request headers such as User-Agent when necessary.
- Support configurable proxy routing when necessary, preferably per provider or crawler.
- Never hard-code API keys, proxy credentials, tokens, or other secrets.
- Validate, normalize, and sanitize crawled data before storing it.
- Preserve historical data when required.
- A failure from one provider must not stop unrelated providers.
- Log important crawler failures and execution results clearly.
- Prefer graceful degradation when a provider is temporarily unavailable.

---

## Crawl Scheduling

- Crawl frequency should be configurable per provider or crawler.
- Scheduling should consider provider importance, data volatility, request cost, and rate limits.
- Providers with frequently changing inventory or pricing may use shorter intervals.
- Providers with relatively stable data may use longer intervals.
- Do not assume every provider requires the same crawl frequency.
- Avoid unnecessarily frequent requests to external providers.

---

## Crawler Testing

- Prefer recorded fixtures or mocked responses for crawler tests.
- Normal tests must not depend on live third-party websites or external network availability.
- Include fixtures for normal, changed, incomplete, and error responses when practical.
- Test parsing, normalization, validation, and persistence independently from live crawling.
- Live provider checks may be used for manual verification or dedicated monitoring, but must not be required for the normal test suite.

---

## Data & Database

- Treat database constraints as part of data integrity.
- Use appropriate unique constraints for naturally unique entities.
- Prefer database-level uniqueness for identifiers that must never be duplicated.
- Use transactions when multiple related database changes must succeed or fail together.
- Add indexes based on actual query patterns.
- Avoid unnecessary full-table scans for frequently accessed data.
- Handle timestamps consistently and explicitly.
- Do not silently discard historical data when historical tracking is required.

---

## Security

- Never hard-code API keys, passwords, tokens, proxy credentials, or other secrets.
- Use environment variables or the project's established secret-management mechanism.
- Never expose server-side secrets to client-side code.
- Validate and sanitize external input.
- Do not blindly trust crawled or third-party data.
- Avoid logging sensitive information.
- Use parameterized database queries or the project's safe database abstraction.
- Be careful with redirects, external URLs, file paths, and user-provided content.

---

## SEO & Performance

This is a public website where SEO and performance are important.

- Use appropriate page titles and meta descriptions.
- Use canonical URLs where appropriate.
- Provide appropriate Open Graph metadata.
- Prefer semantic and crawlable HTML.
- Avoid unnecessary duplicate or thin pages.
- Prefer Server Components where appropriate.
- Avoid unnecessary client-side JavaScript.
- Optimize images and large assets.
- Avoid unnecessary API requests.
- Use caching when data does not require real-time freshness.
- Use pagination or virtualization when datasets become large.

---

## Testing & Verification

After meaningful changes, run the relevant checks when available:

- TypeScript checks
- ESLint
- Unit tests
- Integration tests
- Build
- API tests
- Relevant crawler tests

For responsive UI verification, consider at least these viewport widths:

- 375px
- 390px
- 430px
- 768px
- 1024px
- 1440px

For UI changes, verify:

- Desktop layout
- Tablet layout
- Mobile layout
- No unintended horizontal overflow
- Long content does not break the layout
- Touch interactions
- Loading states
- Empty states
- Error states
- Keyboard navigation for interactive elements
- Visible focus states where applicable

When browser or screenshot tools are available, inspect important pages at multiple viewport sizes instead of relying only on code inspection.

Do not claim that a change is verified unless the relevant checks were actually run.

---

## Agent Rules

- Read and follow this `AGENTS.md` before making changes.
- Inspect the existing code before implementing changes.
- Reuse existing components, APIs, services, utilities, and established patterns when appropriate.
- Do not blindly rewrite working code.
- Do not modify unrelated code.
- Do not introduce unnecessary dependencies or abstractions.
- Do not invent APIs, data structures, files, or project conventions that have not been verified.
- Preserve existing functionality unless the task explicitly requires changing it.
- For major architectural decisions, explain important trade-offs before making the change.
- After implementation, review the changed code.
- Run appropriate checks for the affected functionality.
- Report what was changed, what was actually verified, and any remaining issues.
