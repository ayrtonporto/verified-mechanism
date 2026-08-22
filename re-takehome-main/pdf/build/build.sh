#!/bin/bash
# Build the take-home PDF and publish it one level up. Run from this directory.
set -e
cd "$(dirname "$0")"

# Regenerate the vector mark if the vendored SVG has moved on.
# logo-light.svg is a copy of verifiedmechanisms.github.io/assets/logo-light.svg.
if [ logo-light.svg -nt logo-light.pdf ]; then
  python3 svg2pdf.py logo-light.svg logo-light.pdf
fi

pdflatex -interaction=nonstopmode -halt-on-error take-home.tex > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error take-home.tex > /dev/null
rm -f take-home.aux take-home.log take-home.out take-home.toc
# cp keeps ../take-home.pdf's inode so PDF viewers watching the file refresh;
# mv would swap the inode out from under them.
cp take-home.pdf ../take-home.pdf
rm take-home.pdf
if command -v pdfinfo > /dev/null 2>&1; then
  echo "Published: ../take-home.pdf ($(pdfinfo ../take-home.pdf | awk '/^Pages:/ {print $2}') pages)"
else
  echo "Published: ../take-home.pdf"
fi
