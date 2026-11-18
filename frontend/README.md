# DemandIQ Web Frontend

This is the Stage 1 React + TypeScript + Vite product-shell implementation. It is intentionally separate from the existing Streamlit MVP.

## Requirements

- Node.js 20.19+ or 22.12+
- npm

## Run locally

From this directory:

```powershell
npm install
npm run dev
```

Open the local URL printed by Vite (normally http://localhost:5173).

## Available routes

- `/` — public DemandIQ landing page
- `/login` — authentication interface preview
- `/signup` — account creation interface preview

## Stage 1 boundaries

- Login and sign-up screens are visual previews only. They do not authenticate users, create accounts, or store credentials.
- Dashboard metrics in the landing-page product mockup are illustrative sample values.
- No customer data, database, Supabase, or backend API is connected yet.
- Authentication, workspace isolation, database policies, and PWA installation are later stages.

The existing Streamlit application at the repository root remains unchanged.
