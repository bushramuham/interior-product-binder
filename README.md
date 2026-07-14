# AI Interior Product Binder Generator

This tool turns a list of interior products into a polished **product selections
binder PDF** — a cover page, a table of contents, and one page per product with
its details and photo. For each product you give it a spec-sheet PDF or a
product webpage; it reads the source, uses AI (Anthropic's Claude) to pull out
the useful information (name, manufacturer, dimensions, materials, finishes,
etc.), and lays it all out for you.

If several products share one spec sheet (say a vanity cabinet, its countertop,
and its sink on one manufacturer cut sheet), they're automatically combined onto
a single binder page.

There are two ways to use it:

- **The notebook** — a simple point-and-click form. **Start here** if you're not
  comfortable with the command line.
- **The command line** — for batch runs from an existing Excel schedule
  (see [Advanced: command-line usage](#advanced-command-line-usage)).

---

# Getting started with the notebook (recommended)

## Step 1 — Install the prerequisites

You only do this once.

1. **Python 3.10 or newer** — download from
   [python.org/downloads](https://www.python.org/downloads/).
   On Windows, tick **"Add Python to PATH"** on the first screen of the
   installer.
2. **Visual Studio Code** — download from
   [code.visualstudio.com](https://code.visualstudio.com/).
3. **VS Code extensions** — open VS Code, click the Extensions icon on the left
   (the four squares), and install both:
   - **Python** (by Microsoft)
   - **Jupyter** (by Microsoft)

## Step 2 — Set up the project

Open the project folder in VS Code (**File → Open Folder…**), then open a
terminal inside it (**Terminal → New Terminal**) and run these commands one at a
time.

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m ipykernel install --user --name ipb-venv --display-name "Interior Binder (.venv)"
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name ipb-venv --display-name "Interior Binder (.venv)"
```

What these do: create a private workspace for the tool's dependencies
(`.venv`), install them, and register a notebook "kernel" named
**Interior Binder (.venv)** so VS Code knows which Python to use.

## Step 3 — Add your Anthropic API key

The tool needs an API key to talk to Claude. Get one from the
[Anthropic Console](https://console.anthropic.com/settings/keys).

1. Make a copy of the file `.env.example` and name the copy `.env`.
2. Open `.env` and fill in your details:

   ```env
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   COMPANY_NAME=Your Firm Name
   ```

   `COMPANY_NAME` appears on the "PREPARED BY" line of the cover page. Your key
   is kept private — `.env` is never shared or committed.

## Step 4 — Open and run the notebook

1. In VS Code, open **`binder_builder.ipynb`**.
2. In the **top-right corner**, click the kernel button and choose
   **Interior Binder (.venv)**. (If it isn't offered, choose *Select Another
   Kernel → Jupyter Kernel → Interior Binder (.venv)*.)
3. Click **Run All** at the top. The first cell prints
   `ANTHROPIC_API_KEY set: True` when everything is ready.

## Step 5 — Build your binder

A form appears under the last cell:

1. **Project details** — type your project name and who it's prepared by, and
   tick or untick **Draft binder**. Draft (the default) adds the diagonal
   DRAFT watermark on the cover and the red "DRAFT {date} - NOT FOR
   CONSTRUCTION" line on every page; unticking produces a clean final binder.
2. **Products** — pick a mode:
   - **Manual entry** — for each product, type a **KEY** (e.g. `U-36`) and a
     **Description**, set the **Source** (click **Browse…** for a PDF, or
     paste a webpage link, or leave blank for an OWNER INPUT NEEDED page),
     then click **Add row**. Every row in the list has **Edit** and
     **Delete** buttons — Edit loads the row back into the form and the
     button becomes **Update row**. (Products with the same Source are
     grouped onto one page.)
   - **Import Excel** — browse to an existing schedule `.xlsx` that already
     has the KEY / DESCRIPTION / PATH columns populated; nothing to retype.
3. Click **Generate binder**. Progress prints below the button.

> PDF sources are embedded in the binder **unchanged** — the tool only adds
> the key notes, footer, and page number on top. Your original spec-sheet
> files are never modified.

Your finished binder is saved in the **`output/`** folder with a unique name
that includes the project, the firm, and the date/time, e.g.
`output/Palisades_Rebuild__DFH_Architects__20260703_212952.pdf`. Every run
creates a new file, so earlier binders are never overwritten. (The product list
you built is saved next to it as a matching `.xlsx` so you can reuse it later.)

## Notebook troubleshooting

- **Stuck on "connecting to kernel", or import errors like
  `No module named 'dotenv'`** — VS Code is using the wrong Python. Click the
  kernel button (top-right) and pick **Interior Binder (.venv)**, then
  *Run All* again.
- **The form/buttons don't appear** — make sure the **Jupyter** extension is
  installed, then reload VS Code (`Ctrl+Shift+P` → *Developer: Reload Window*).
- **"Permission denied" / "is locked"** — a file is open in another program.
  Each run already writes a brand-new, uniquely-named PDF, so this is rare; if
  it happens, it's usually the input spreadsheet being open in Excel — close it
  and click **Generate binder** again.
- **A product shows a red error box in the PDF** — its source couldn't be read
  (missing file or unreachable link) or the AI call failed. The other products
  still generate normally; check the progress log for the reason.
- **Windows "path too long" error while installing** — this project pins the
  notebook widgets to an older version to avoid it. If you still hit it, move
  the project to a short folder like `C:\ipb` and redo Step 2.

---

# The desktop app (.exe — no Python needed)

For users who shouldn't have to install anything: a windowed desktop app with
the same features as the notebook (manual rows with Edit/Delete, Excel import,
the Draft checkbox, one-click generate, an "Open binder" button).

**Using it:** double-click `DFH_Binder_Generator.exe`. Put a `.env` file
(copied from `.env.example`, with the API key and company name) **next to the
exe** — it's only required for webpage sources; binders built purely from PDF
spec sheets work without it. Binders are written to an `output/` folder created
next to the exe.

**Building it** (one-time, from the repo, inside the venv):

```bash
pip install pyinstaller
python scripts/build_exe.py
```

This produces `dist/DFH_Binder_Generator.exe` (~60 MB, self-contained). Ship
that single file plus a `.env`. Build artifacts (`build/`, `dist/`, `*.spec`)
are gitignored. You can also run the same app from source with
`python gui.py`.

---

# Advanced: command-line usage

If you already have an Excel schedule (or want to run in batch), you can skip the
notebook and use the command line.

## Try the built-in examples

The repo ships with ready-to-run example schedules in
[examples/](examples/README.md):

```bash
# Happy path: two products from local sample spec sheets
python main.py examples/example_basic.xlsx

# Multiple keys sharing one spec sheet -> one combined binder page
python main.py examples/example_grouping.xlsx --project-name "Demo Project"

# Local PDFs mixed with real product webpages (needs internet access)
python main.py examples/example_mixed_sources.xlsx

# Broken file path + unreachable URL -> error blocks in the PDF, run still completes
python main.py examples/example_errors.xlsx
```

Each run writes a uniquely-named PDF into `output/` (e.g.
`output/Demo_Project__DFH_Architects__20260703_212932.pdf`), so runs never
overwrite each other. Use `--output <path>` to set an exact filename instead.

## Run against your own schedule

```bash
python main.py path/to/schedule.xlsx --project-name "721 Example Ave" --prepared-by "Your Firm"
```

Your `.xlsx` needs a header row containing at least **KEY** and **PATH**
(matched case-insensitively). Recognized columns:

| Column | Required | Meaning |
| --- | --- | --- |
| `KEY` | yes | Schedule key, e.g. `U-36` |
| `PATH` (or `SOURCE`) | yes | Local path to a spec-sheet PDF, **or** an `http(s)://` product page URL |
| `DESCRIPTION` | no | Schedule description shown in the TOC and product page |
| `DESCRIPTION2`, `DESCRIPTION3` | no | Extra description text, passed to the AI as context |
| `PG` (or `PAGE`) | no | Kept for reference; page numbers are recalculated |

Notes:
- Local `PATH` values must be reachable from where you run the tool. Relative
  paths are resolved against the current directory first, then the
  spreadsheet's own folder.
- Rows with the same `PATH` are grouped into one binder page.
- Rows with a `KEY` but no `PATH` get an OWNER INPUT NEEDED page; rows missing
  `KEY` are skipped with a warning.

## CLI options

| Flag | Default | Purpose |
| --- | --- | --- |
| `--output` | auto: `output/<project>__<company>__<timestamp>.pdf` | Exact output PDF path |
| `--project-name` | `Untitled Project` | Cover page project name |
| `--prepared-by` | `COMPANY_NAME` from `.env` | Cover page "prepared by" line |
| `--max-images` | `3` | Max images extracted/sent per product |
| `--final` | off (draft) | Final binder: no DRAFT watermark, no NOT FOR CONSTRUCTION line, no `[DRAFT]` tag |

The command exits `0` even when individual products fail (they render as error
boxes), and prints a `N succeeded, M failed` summary.

---

# How it works

```
binder_builder.ipynb         Point-and-click notebook front-end
gui.py                       Desktop app (also packaged as the Windows exe)
scripts/build_exe.py         Builds dist/DFH_Binder_Generator.exe (PyInstaller)
main.py                      Command-line entry point
config.py                    Model name + limits
src/excel_reader.py          Schedule reading/writing + grouping by shared PATH
src/extraction/              PDF (PyMuPDF) and web (requests + BeautifulSoup) extractors
src/ai_client.py             Anthropic call: forced tool use + prompt caching
src/pdf_builder.py           ReportLab binder: cover, TOC, product pages
src/pipeline.py              Shared end-to-end pipeline (used by both front-ends)
scripts/make_examples.py     Regenerates everything in examples/
examples/                    Committed runnable example schedules + sample PDFs
```

This is a proof of concept per [specs/specs.md](specs/specs.md) — it favors
clarity over production hardening (no retries, minimal image-selection
heuristics).
