# Maintaining the GitHub Pages site

The published documentation lives in `site/`:

- `index.html`: installation, CLI and configuration reference.
- `usage.html`: runnable application examples and troubleshooting.
- `styles.css`: shared responsive styles, including dark mode.

The site uses static HTML and CSS, with no build dependencies. Use relative links
so navigation also works under the repository's GitHub Pages URL prefix.

## Preview and validation

Run from the repository root:

```bash
python3 -m http.server 8000 --directory site --bind 127.0.0.1
```

Open <http://localhost:8000/> or <http://localhost:8000/usage.html>.

In another terminal, validate links, duplicate IDs and Python snippet syntax:

```bash
mkdir -p artifacts/logs
python3 scripts/check_site.py > artifacts/logs/site-check.log 2>&1
```

The checker uses only Python's standard library (Python 3.10+). It does not
check external URLs or execute the snippets. When changing runnable examples,
also run them in a temporary project with NavConfig installed.

## Publishing

1. In repository **Settings → Pages → Build and deployment**, select **GitHub Actions**
   as the source.
2. Merge the site changes into `main`. The **Deploy GitHub Pages** workflow validates
   the site, uploads only `site/` and deploys it to the `github-pages` environment.
3. Open the URL reported by the deployment job. For this repository, the README
   uses <https://phenobarbital.github.io/navconfig/>; use the URL GitHub reports if
   repository capitalization or Pages configuration differs.

Pull requests validate the site without deployment permissions. You can also run
the workflow manually from **Actions → Deploy GitHub Pages → Run workflow**;
select `main` to publish. Other branches only run validation. If the repository
uses environment protection rules, `github-pages` must allow deployments from `main`.

See GitHub's [custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
for repository setup and deployment requirements.
