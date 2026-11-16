"""
pdfwriter.py — Générateur PDF autonome (aucune dépendance externe).

Produit un PDF valide (PDF 1.4) où chaque page contient une image JPEG
intégrée telle quelle (filtre DCTDecode) : fichier léger et qualité intacte.

Auteur : VideoFramesPDF
"""

from datetime import datetime

# ---------------------------------------------------------------- Tailles page
PAGE_SIZES = {
    "A4 portrait": (595.276, 841.890),
    "A4 paysage": (841.890, 595.276),
    "A4 paysage (plein)": (841.890, 595.276),
    "Letter portrait": (612.000, 792.000),
    "Letter paysage": (792.000, 612.000),
}

# ------------------------------------------------------- Largeurs des polices
# (table AFM Helvetica / Helvetica-Bold, en 1/1000 em) pour un centrage exact.
_W_REG = (
    "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 "
    "556 556 556 556 556 556 556 556 556 556 278 278 584 584 584 556 "
    "1015 667 667 722 722 667 611 778 722 278 500 667 556 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 278 278 278 469 556 "
    "333 556 556 500 556 556 278 556 556 222 222 500 222 833 556 556 "
    "556 556 333 500 278 556 500 722 500 500 500 334 260 334 584"
)
_W_BOLD = (
    "278 333 474 556 556 889 722 238 333 333 389 584 278 333 278 278 "
    "556 556 556 556 556 556 556 556 556 556 333 333 584 584 584 611 "
    "975 722 722 722 722 667 611 778 722 278 556 722 611 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 333 278 333 584 556 "
    "333 556 611 556 611 556 333 611 611 278 278 556 278 889 611 611 "
    "611 611 389 556 333 611 556 778 556 556 500 389 280 389 584"
)


def _widths(table):
    return [int(x) for x in table.split()]


_W_REG = _widths(_W_REG)
_W_BOLD = _widths(_W_BOLD)


def _esc(text):
    """Échappe une chaîne pour un littéral PDF (encodage WinAnsi)."""
    data = text.encode("cp1252", "replace")
    return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def text_width(text, size, bold=False):
    """Largeur approximative exacte d'un texte Helvetica (en points)."""
    table = _W_BOLD if bold else _W_REG
    total = 0
    for ch in text:
        code = ord(ch)
        if 32 <= code <= 126:
            total += table[code - 32]
        else:
            total += 556
    return total * size / 1000.0


class PdfBuilder:
    """Construit un PDF page par page (images JPEG + texte)."""

    def __init__(self, page_size=(595.276, 841.890), margin=24.0,
                 title="", author="VideoFramesPDF"):
        self.page_w, self.page_h = page_size
        self.margin = margin
        self.title = title
        self.author = author
        self.pages = []          # liste de dicts décrivant chaque page

    # ------------------------------------------------------------- Contenu
    def add_image(self, jpeg_bytes, width_px, height_px, caption=None):
        """Ajoute une page contenant l'image JPEG, redimensionnée à la page."""
        self.pages.append({
            "kind": "image",
            "jpeg": jpeg_bytes,
            "w": width_px,
            "h": height_px,
            "caption": caption or "",
        })

    def add_text_page(self, lines, background=(0.12, 0.12, 0.14)):
        """lines = [(texte, taille, gras, couleur RGB ou None), ...]"""
        self.pages.append({"kind": "text", "lines": lines, "bg": background})

    def add_cover(self, title, subtitle="", footer=""):
        """Page de garde sombre avec titre centré."""
        self.pages.append({
            "kind": "cover",
            "title": title,
            "subtitle": subtitle,
            "footer": footer,
        })

    # --------------------------------------------------------------- Rendu
    def _image_page_content(self, page):
        cap = page["caption"]
        cap_h = 18.0 if cap else 0.0
        avail_w = self.page_w - 2 * self.margin
        avail_h = self.page_h - 2 * self.margin - cap_h
        iw, ih = float(page["w"]), float(page["h"])
        scale = min(avail_w / iw, avail_h / ih)
        draw_w, draw_h = iw * scale, ih * scale
        tx = (self.page_w - draw_w) / 2.0
        ty = self.margin + cap_h + (avail_h - draw_h) / 2.0

        out = ["q", "%.3f 0 0 %.3f %.3f %.3f cm" % (draw_w, draw_h, tx, ty),
               "/Im0 Do", "Q"]
        if cap:
            size = 10.0
            w = text_width(cap, size)
            out.append("BT /F1 %.1f Tf 1 0 0 1 %.3f %.3f Tm (%s) Tj ET"
                       % (size, (self.page_w - w) / 2.0, self.margin + 4.0,
                          _esc(cap).decode("latin-1")))
        return "\n".join(out)

    def _text_page_content(self, page):
        out = []
        y = self.page_h - self.margin - 40
        for item in page["lines"]:
            text, size, bold, color = (list(item) + [None])[:4]
            font = "F2" if bold else "F1"
            if color:
                out.append("%.3f %.3f %.3f rg" % color)
            w = text_width(text, size, bold)
            out.append("BT /%s %.1f Tf 1 0 0 1 %.3f %.3f Tm (%s) Tj ET"
                       % (font, size, (self.page_w - w) / 2.0, y,
                          _esc(text).decode("latin-1")))
            y -= size * 1.6
        return "\n".join(out)

    def _cover_content(self, page):
        out = []
        title = page["title"]
        sub = page["subtitle"]
        foot = page["footer"]
        size = min(34.0, max(16.0, (self.page_w - 2 * self.margin) /
                             max(1, len(title)) * 1.6))
        w = text_width(title, size, True)
        out.append("BT /F2 %.1f Tf 1 0 0 1 %.3f %.3f Tm (%s) Tj ET"
                   % (size, (self.page_w - w) / 2.0, self.page_h * 0.46,
                      _esc(title).decode("latin-1")))
        if sub:
            s = 13.0
            w = text_width(sub, s)
            out.append("BT /F1 %.1f Tf 1 0 0 1 %.3f %.3f Tm (%s) Tj ET"
                       % (s, (self.page_w - w) / 2.0, self.page_h * 0.46 - size - 12,
                          _esc(sub).decode("latin-1")))
        if foot:
            s = 9.0
            w = text_width(foot, s)
            out.append("0.55 0.55 0.58 rg")
            out.append("BT /F1 %.1f Tf 1 0 0 1 %.3f %.3f Tm (%s) Tj ET"
                       % (s, (self.page_w - w) / 2.0, self.margin + 20,
                          _esc(foot).decode("latin-1")))
        return "\n".join(out)

    # --------------------------------------------------------------- Écriture
    def save(self, path):
        """Écrit le PDF sur le disque. Retourne le chemin écrit."""
        page_defs = self.pages
        n = len(page_defs)

        # Attribution des numéros d'objet
        nums = []
        cur = 5
        for p in page_defs:
            if p["kind"] == "image":
                nums.append((cur, cur + 1, cur + 2))
                cur += 3
            else:
                nums.append((cur, cur + 1))
                cur += 2

        kids = " ".join("%d 0 R" % nums[i][0] for i in range(n))

        objs = {}

        objs[1] = (b"<< /Type /Catalog /Pages 2 0 R >>")
        objs[2] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n)).encode()
        objs[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        objs[4] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"

        for i, p in enumerate(page_defs):
            if p["kind"] == "image":
                page_num, cont_num, img_num = nums[i]
                stream = self._image_page_content(p)
                data = stream.encode("latin-1")
                objs[cont_num] = (("<< /Length %d >>\nstream\n" % len(data)).encode("latin-1")
                                  + data + b"\nendstream")
                objs[page_num] = (
                    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.3f %.3f] "
                    "/Resources << /XObject << /Im0 %d 0 R >> /Font << /F1 3 0 R /F2 4 0 R >> >> "
                    "/Contents %d 0 R >>" % (self.page_w, self.page_h, img_num, cont_num)
                ).encode("latin-1")
                jpeg = p["jpeg"]
                objs[img_num] = (
                    b"<< /Type /XObject /Subtype /Image /Width " + str(p["w"]).encode() +
                    b" /Height " + str(p["h"]).encode() +
                    b" /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode"
                    b" /Length " + str(len(jpeg)).encode() + b" >>\nstream\n"
                    + jpeg + b"\nendstream"
                )
            else:
                page_num, cont_num = nums[i]
                if p["kind"] == "cover":
                    stream = self._cover_content(p)
                    bg = ("0.09 0.09 0.11 rg 0 0 %.3f %.3f re f"
                          % (self.page_w, self.page_h))
                    stream = bg + "\n" + stream
                else:
                    stream = self._text_page_content(p)
                data = stream.encode("latin-1")
                objs[cont_num] = (("<< /Length %d >>\nstream\n" % len(data)).encode("latin-1")
                                  + data + b"\nendstream")
                objs[page_num] = (
                    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.3f %.3f] "
                    "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                    "/Contents %d 0 R >>" % (self.page_w, self.page_h, cont_num)
                ).encode("latin-1")

        info_num = cur
        stamp = "D:" + datetime.now().strftime("%Y%m%d%H%M%S")
        objs[info_num] = (
            "<< /Title (%s) /Producer (%s) /Creator (%s) /CreationDate (%s) >>"
            % (_esc(self.title).decode("latin-1"), _esc(self.author).decode("latin-1"),
               _esc(self.author).decode("latin-1"), stamp)
        ).encode("latin-1")

        max_obj = info_num

        out = bytearray()
        out += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offsets = {}
        for num in range(1, max_obj + 1):
            body = objs.get(num)
            if body is None:
                body = b"<< >>"
            offsets[num] = len(out)
            out += ("%d 0 obj\n" % num).encode()
            out += body
            out += b"\nendobj\n"

        xref_pos = len(out)
        out += ("xref\n0 %d\n" % (max_obj + 1)).encode()
        out += b"0000000000 65535 f \n"
        for num in range(1, max_obj + 1):
            out += ("%010d 00000 n \n" % offsets[num]).encode()

        doc_id = ("%08X" % (abs(hash(self.title)) & 0xFFFFFFFF))
        out += ("trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R /ID [<%s> <%s>] >>\n"
                % (max_obj + 1, info_num, doc_id, doc_id)).encode()
        out += ("startxref\n%d\n%%%%EOF\n" % xref_pos).encode()

        with open(path, "wb") as f:
            f.write(bytes(out))
        return path
