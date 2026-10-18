# Paper — The Right-to-Repair Board Rescuer Deck

Build (no LaTeX needed, pure Python):

```bash
python3 make_figures.py    # -> figures/*.png   (matplotlib, 300 dpi)
python3 make_paper.py      # -> Board-Rescuer-Deck.pdf
```

| File | What |
|---|---|
| `Board-Rescuer-Deck.pdf` | the paper (7 pages, single-column A4) |
| `original-submission.pdf` | the one-page abstract as submitted |
| `make_figures.py` | generates every figure (circuit, architecture, pipeline, LUT) |
| `make_paper.py` | typesets the PDF (reportlab) |
| `figures/` | Fig. 1-6 generated diagrams |
| `photos/` | Fig. 7-8, real captures pulled from the VPS gallery |

Fonts used: DejaVu Serif (body) / DejaVu Sans (headings), so text matches the figures.
To change the title or authors, edit the top of `make_paper.py` and re-run.
