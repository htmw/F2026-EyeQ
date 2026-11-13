# Editing the DUAL technical paper

Open `paper.tex` to edit the manuscript. It uses the IEEEtran conference class on A4 paper. Tables are ordinary LaTeX tables. References are numbered through the bibliography at the end of the file. Keep each citation key stable when editing a reference. The original figure files are in `figures/`.

Compile from this directory with:

```sh
latexmk -pdf paper.tex
```

For Overleaf, upload the contents of this directory, keep the figures folder, and select `paper.tex` as the main document. The manuscript was transcribed from the team's v0.11 PDF. Its pending notes are preserved. The team revision log is in `version-history.tex`; the final input line in `paper.tex` controls whether it appears in the PDF.

Use inline math for short expressions such as `\(p\)`. For a numbered formula, insert an `equation` environment in the relevant section, give it a label, and refer to it with `\eqref`. For example, the uncertainty band described in Section VII can be written as:

```latex
\begin{equation}
  |p-t| \leq m
  \label{eq:uncertain-band}
\end{equation}
```

Here \(p\) is the calibrated probability, \(t\) is the threshold, and \(m\) is the margin.

### Save both copies in VS Code

Open the repository folder in VS Code with LaTeX Workshop installed. Save
`paper.tex` or `version-history.tex` to rebuild `paper.pdf` and `paper.docx`
beside the manuscript. Edit the TeX source because the next build replaces the Word copy.

For a new macOS or Linux checkout, set up the Word exporter once from this directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install python-docx
```

The exporter supports the manuscript's current LaTeX structure. Check the Word
rendering when introducing new LaTeX commands, especially equations.
