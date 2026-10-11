"""
Shared helpers for Rewards/{id}/ builders and renders (added 1405/07/19,
user decision) - the same few functions had been copy-pasted into many
reward folders (Persian digits in 13 files, the collection-date rule in 9,
HTML -> PNG -> PDF rendering in 12).

Optional by design: a reward folder MAY import from here, nothing forces it,
and the 4-file reward contract is unchanged. Rewards that were already live
when this module was added were deliberately NOT migrated mid-campaign (a
refactor must never move a prize amount while people are competing); new
rewards should use these instead of copying another folder's private copy.
"""

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_fa_digits(value) -> str:
    """123 -> '۱۲۳' (any value, via str())."""
    return str(value).translate(FA_DIGITS)


def norm_name(name) -> str:
    """Collapses all whitespace runs to single spaces and strips - the
    normalisation every reward applies before comparing person names."""
    return " ".join(str(name).split())


# ---------------------------------------------------------------------------
# Collection date ("تاریخ وصول") of an invoice - user rule 2026-10-10, applies
# to every reward: the moment the money was actually paid, by payment type,
# NOT the finance acceptance time the panels filter on server-side.
#   آنلاین       -> "تاریخ پرداخت"
#   کارت به کارت -> "زمان ثبت اطلاعات واریزی"
# Existing rewards disagree on any OTHER payment type: some fall back to the
# acceptance time, some drop the invoice. That choice is therefore explicit
# here (fallback_col) instead of silently picking one.
# ---------------------------------------------------------------------------

PAY_TYPE_COL = "نوع پرداخت"
ONLINE_PAID_COL = "تاریخ پرداخت"
CARD_DEPOSIT_COL = "زمان ثبت اطلاعات واریزی"
ACCEPTANCE_COL = "زمان بررسی اطلاعات واریزی"


def collection_time(df, fallback_col=None):
    """
    df: an FCP-style invoice DataFrame. Returns a string Series of each
    invoice's collection time ("YYYY/MM/DD HH:MM:SS" as the panel exports it,
    so plain string comparison with the same format works for windows).

    fallback_col=None  -> other payment types get "" (excluded by any window)
    fallback_col=ACCEPTANCE_COL (or any column) -> other types use that column
    """
    import pandas as pd

    kind = df[PAY_TYPE_COL].astype(str).str.strip()
    if fallback_col is None:
        out = pd.Series("", index=df.index, dtype=object)
    else:
        out = df[fallback_col].astype(str).str.strip()
    out = out.mask(kind == "آنلاین", df[ONLINE_PAID_COL].astype(str).str.strip())
    return out.mask(kind == "کارت به کارت", df[CARD_DEPOSIT_COL].astype(str).str.strip())


# ---------------------------------------------------------------------------
# HTML -> PNG (-> PDF) rendering, the technique every image/PDF report uses.
# ---------------------------------------------------------------------------

def render_html_to_png(html, png_path, selector=".wrap", scale=3, image_type="png", quality=None):
    """Renders `html` in headless Chrome and screenshots `selector` to
    png_path. image_type="jpeg" + quality (e.g. 85) for smaller images."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        try:
            page = browser.new_page(device_scale_factor=scale)
            page.set_content(html)
            kwargs = {"path": png_path, "type": image_type}
            if quality is not None:
                kwargs["quality"] = quality
            page.locator(selector).screenshot(**kwargs)
        finally:
            browser.close()
    return png_path


def render_html_to_pdf(html, png_path, pdf_path, selector=".wrap", scale=3):
    """Same as render_html_to_png, then wraps the PNG losslessly in a PDF
    (img2pdf) - what the comprehensive manager reports send."""
    import img2pdf

    render_html_to_png(html, png_path, selector=selector, scale=scale)
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(png_path))
    return pdf_path
