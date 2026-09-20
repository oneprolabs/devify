"""Prompt for structured invoice extraction."""

EXTRACTION_PROMPT = """\
You extract structured data from Chinese invoices and travel receipts.

Return a single JSON object and nothing else. Use this shape exactly:

{
  "is_invoice": true,
  "invoice_type": "vat_special|vat_normal|vat_electronic|train|
                   flight_itinerary|coach|taxi|hotel|quota|other",
  "invoice_no": "",
  "invoice_code": "",
  "issue_date": "YYYY-MM-DD",
  "seller_name": "",
  "seller_tax_id": "",
  "buyer_name": "",
  "buyer_tax_id": "",
  "total_amount": 0,
  "tax_amount": 0,
  "amount_excl_tax": 0,
  "currency": "CNY",
  "city": "",
  "category": "transport_long|transport_local|accommodation|meals|
               entertainment|office|communication|training|other",
  "items": [{"name": "", "quantity": 0, "unit_price": 0, "amount": 0}],
  "ticket_details": {},
  "confidence": 0.0
}

Rules:
- Decide "is_invoice" first. If the document is not an invoice, a receipt or
  a travel itinerary, return {"is_invoice": false} and stop. Do not guess.
- Some documents arrive next to an invoice but cannot be claimed in its
  place. Return {"is_invoice": false} for a hotel 结账单 / 水单 / 预授权单 /
  账单明细, for a 订单详情 or 支付凭证, and for any 对账单. A hotel's claimable
  document is its 增值税发票, which usually arrives in the same email; the
  folio repeats the same money and would be counted twice. Note that an
  itinerary is not in this group: 航空运输电子客票行程单 and the railway's
  电子客票 are themselves what gets claimed.
- "total_amount" is the amount actually paid (价税合计 on a VAT invoice).
- Leave a field as "" or 0 when the document does not show it. Never invent
  a value, and never carry a number over from a different field.
- Non-standard tickets have no invoice number or tax fields. Put their
  specifics in "ticket_details" instead:
  - train: train_no, from_station, to_station, depart_at, seat_class,
    passenger
  - flight_itinerary: flight_no, from_city, to_city, depart_at, cabin,
    passenger, fuel_fee, caac_fee
  - taxi: city, start_at, end_at, distance
  - hotel: city, check_in, check_out, nights
- "city" is where the expense happened, which is what trip grouping uses.
  For a train or flight, use the destination. Read "to_station" carefully
  too: a train's city is looked up from the station where the station is
  known, and falls back to your "city" where it is not.
- "confidence" is how certain you are that the fields are read correctly.
"""

CONTEXT_TEMPLATE = """\
The document arrived as an email attachment. Context that may help:
Subject: {subject}
Sender: {sender}
Received: {received_at}
Filename: {filename}
"""


LINK_PICK_PROMPT = """\
You are given the links found in one email, each with the words it was
shown as. Decide which of them download an invoice, a receipt or a travel
itinerary.

Return a single JSON object and nothing else:

{{"invoice_links": [0, 2]}}

The numbers are the indexes of the links to follow, in the list below.

Rules:
- Most billing emails carry advertisements, help pages, app download
  banners and unsubscribe links alongside the one that matters. Return
  only the links that fetch the document itself.
- The words a person would have clicked are the strongest signal:
  「下载发票」「查看行程单」「发票下载」「点击下载」 name a document,
  while 「立即领取」「下载APP」「查看详情」「退订」 do not.
- When the email says the invoice is attached and no link fetches one,
  return an empty list. Guessing costs a download and gets a web page.
- Return an empty list rather than a link you are unsure about.

Email subject: {subject}

Links:
{links}
"""
