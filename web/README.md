# React frontend

From the repository root, start the offline API in one terminal:

```sh
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
npm --prefix web ci
npm --prefix web run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to the local FastAPI server.
After installing dependencies, the UI, fonts, and seeded API work without
internet access. The school list comes from `seed/manifest.json`; selectable
majors and all financial results come from the API. No financial formulas
are reimplemented in the frontend. Input defaults mirror the existing core.

## Checks

```sh
npm --prefix web run build
npm --prefix web exec -- playwright install chromium
npm --prefix web test
```

Browser tests start the API and Vite automatically. They exercise the real
seeded API, with controlled responses for unavailable coverage and low income.
The browser suite blocks non-local requests. Reduced-motion mode is tested.

React handles form/result state; TypeScript checks the response contract.
Vite builds and proxies the API; Tailwind supplies layout utilities alongside
the disclosure-specific stylesheet. Fontsource bundles the Google Fonts
Archivo variable font (including the expanded width axis) and Newsreader.
Playwright is a development dependency for responsive browser checks.

Comparisons display the API's three scenarios, including borrowed amount,
annual median earnings, monthly take-home, monthly payment, take-home share,
total repaid, and verdict. Their identities, private debt and annual-limit flags,
unavailable reasons, cost assumptions, and borrowing by year accompany the table.
The table scrolls horizontally on narrow screens; alternate verdicts stay neutral
so only the primary verdict uses a verdict color. No deployment is included.

Integration references: [Tailwind Vite setup](https://tailwindcss.com/docs/installation/using-vite)
and [Fontsource variable fonts](https://fontsource.org/docs/getting-started/variable).
