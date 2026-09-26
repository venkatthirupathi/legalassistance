# ClauseShield

ClauseShield is a Netlify-native legal information assistant. It helps people turn agreements and policies into plain-language explanations, review clauses and obligations, ask grounded questions, compare two versions, and prepare a focused brief for a legal professional.

It provides legal information, not legal advice. The product consistently asks users to consult a qualified professional for decisions with legal or financial consequences.

## Architecture

- `public/` contains the accessible, responsive browser experience.
- `netlify/functions/analyze.mts` handles analysis through Netlify AI Gateway.
- The supported OpenAI `gpt-5.4-mini` model provides document-grounded responses.
- Documents are kept in browser memory and submitted only when the user requests an analysis. No application database is used.

## Local development

Install dependencies with `npm install`, then run:

```sh
/opt/buildhome/node-deps/node_modules/.bin/netlify dev --port 8889
```

Open `http://localhost:8889`. AI Gateway inference becomes available after the site has a production deploy and requires an eligible Netlify credit-based plan.

## Deployment

The included `netlify.toml` publishes `public` and bundles functions from `netlify/functions`. Netlify injects AI Gateway credentials into the modern function runtime; no client-side key is used.
