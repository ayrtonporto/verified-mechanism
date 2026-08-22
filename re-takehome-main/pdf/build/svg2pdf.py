#!/usr/bin/env python3
"""Convert the Verified Mechanisms logo SVG to a single-page vector PDF.

The mark is a contour trace: three <path> elements whose `d` uses only M, L and Z, filled
even-odd. That is little enough that we can write the PDF by hand, which keeps the output free
of the unembedded Helvetica that general-purpose PDF libraries leave in the page resources.

    python3 svg2pdf.py logo-light.svg logo-light.pdf
"""

import re
import sys


def path_ops(d, x0, y0, height, scale):
    """SVG path data (M/L/Z only, absolute) to PDF path operators."""
    out = []
    for cmd, arg in re.findall(r'([MLZ])([\d.\- ]*)', d):
        if cmd == 'Z':
            out.append('h')
            continue
        nums = [float(v) for v in arg.replace('-', ' -').split()]
        for i in range(0, len(nums), 2):
            # SVG y grows downward, PDF y grows upward.
            px = (nums[i] - x0) * scale
            py = (height - (nums[i + 1] - y0)) * scale
            out.append('%.3f %.3f %s' % (px, py, 'm' if (cmd == 'M' and i == 0) else 'l'))
    return out


def convert(src, dst, size=100.0):
    svg = open(src).read()
    x0, y0, w, h = (float(v) for v in re.search(r'viewBox="([\d.\-\s]+)"', svg).group(1).split())
    scale = size / w
    page_w, page_h = w * scale, h * scale

    stream = []
    for tag in re.findall(r'<path\b[^>]*>', svg):
        fill = re.search(r'fill="#([0-9A-Fa-f]{6})"', tag).group(1)
        r, g, b = (int(fill[i:i + 2], 16) / 255 for i in (0, 2, 4))
        stream.append('%.4f %.4f %.4f rg' % (r, g, b))
        stream += path_ops(re.search(r'\sd="([^"]+)"', tag).group(1), x0, y0, h, scale)
        stream.append('f*')          # even-odd, so the traced holes stay open
    content = '\n'.join(stream).encode('latin-1')

    objs = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        ('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.3f %.3f] /Resources << >> '
         '/Contents 4 0 R >>' % (page_w, page_h)).encode('latin-1'),
        b'<< /Length %d >>\nstream\n' % len(content) + content + b'\nendstream',
    ]

    pdf = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(pdf))
        pdf += b'%d 0 obj\n' % i + body + b'\nendobj\n'

    xref_at = len(pdf)
    pdf += b'xref\n0 %d\n' % (len(objs) + 1)
    pdf += b'0000000000 65535 f \n'
    for off in offsets:
        pdf += b'%010d 00000 n \n' % off
    pdf += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, xref_at)

    open(dst, 'wb').write(pdf)
    print('wrote %s (%d bytes)' % (dst, len(pdf)))


if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2])
