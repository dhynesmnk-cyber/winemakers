# Font licences

All three faces are self-hosted (DESIGN.md §3: zero runtime font fetching, no
Google Fonts link, no `@import` from a CDN). All three are licensed under the
**SIL Open Font Licence 1.1**, which permits redistribution and web embedding
provided the licence travels with the files.

Downloaded 2026-08-07. Latin subsets.

| File | Face | Author | Licence |
|---|---|---|---|
| `fraunces-variable.woff2` | Fraunces (variable, `opsz` + `wght` 300–600) | Undercase Type / Phaedra Charles, Flavia Zimbardi | SIL OFL 1.1 |
| `newsreader-variable.woff2` | Newsreader (variable, `opsz` + `wght` 400–600) | Production Type | SIL OFL 1.1 |
| `newsreader-400italic.woff2` | Newsreader Italic 400 | Production Type | SIL OFL 1.1 |
| `ibm-plex-mono-400.woff2` | IBM Plex Mono 400 | IBM / Mike Abbink, Bold Monday | SIL OFL 1.1 |
| `ibm-plex-mono-500.woff2` | IBM Plex Mono 500 | IBM / Mike Abbink, Bold Monday | SIL OFL 1.1 |

Full licence text: <https://openfontlicense.org/open-font-license-official-text/>

Upstream sources:

- Fraunces — <https://github.com/undercasetype/Fraunces>
- Newsreader — <https://github.com/productiontype/Newsreader>
- IBM Plex — <https://github.com/IBM/plex>

**Do not replace these with a CDN link.** The site performs zero runtime data
fetching (TRD.md §4.4) and a font request to another host would be the only
external call on the page.
