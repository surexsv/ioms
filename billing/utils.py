from decimal import Decimal, ROUND_HALF_UP


def split_gst(gst_amount):
    """Split total GST equally into CGST and SGST (intra-state)."""
    half = (Decimal(gst_amount) / 2).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return half, half


def _normalize_words(text):
    return ' '.join(text.replace(',', '').replace('-', ' ').split()).title()


def amount_in_words_indian(amount):
    """Convert amount to Indian currency words (rupees and paise)."""
    try:
        from num2words import num2words
        value = Decimal(str(amount))
        rupees = int(value)
        paise = int((value - rupees) * 100)
        words = _normalize_words(num2words(rupees, lang='en_IN'))
        if paise:
            pwords = _normalize_words(num2words(paise, lang='en_IN'))
            return f"{words} and paise {pwords} only"
        return f"{words} only"
    except ImportError:
        return f"Rupees {amount:,.2f} only"
