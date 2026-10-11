"""
gozaresh-jame-padash-hamkadeh-mehr/render.py

One PDF (an HTML page screenshotted to PNG, then wrapped in a PDF - same
mechanism as gozaresh-jame-rotbebandi-hamkadeh) sent only to
عرفان زمانی (مدیر ارشد فروش).

Sections (user-approved layout 2026-10-04): همکده logo header, overall
همکده وصولی growth (the 6 سرپرست teams vs the same elapsed time of the
reference window), budget cards, key points, then one table per reward.

Digits: W_yekan's Persian digits sit at uneven heights (user 2026-10-04:
"ارقام بالا و پایین افتادن"), so the page font "Y" maps every digit /
number punctuation code point to Tahoma via unicode-range and everything
else to W_yekan - one font family on the whole page, consistent digits
everywhere.
"""

import base64
import os

import img2pdf
from playwright.sync_api import sync_playwright

from Senders.message import OutboundMessage

# user 2026-10-05: also the group "گزارشات پاداش". Three directory entries share
# that alias (2 channels + 1 group), so the group is addressed by its unique
# username - an exact Username match resolves to exactly one entry.
RECIPIENTS = [
    "عرفان زمانی (مدیر ارشد فروش)",
    "group-smrezvanmadani-1789890446796",  # گروه «گزارشات پاداش»
]

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_HERE, "outputs")
_LOGO_PATH = os.path.join(_HERE, "assets", "logo_icon.png")
_FONTS = r"C:\Windows\Fonts"
_DIGIT_RANGE = "U+0030-0039,U+06F0-06F9,U+0660-0669,U+066A-066C,U+0025,U+002B-002E,U+003A,U+2212"

SARPARAST_BUDGET_MILLION = 210

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
MONTH_NAMES = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def fa(x):
    return str(x).translate(_FA)


def num(x, d=0):
    return fa(f"{x:,.{d}f}")


def pct(x, d=1, sign=True):
    s = f"{x:+.{d}f}" if sign else f"{x:.{d}f}"
    if "." in s and not sign:
        s = s.rstrip("0").rstrip(".")
    return f"<span dir='ltr'>{fa(s)}٪</span>"


def growth_words(x):
    return f"{pct(abs(x), 1, False)} {'رشد' if x >= 0 else 'افت'}"


def clean(name):
    return " ".join(str(name).replace("*", " ").split())


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _sarparast_section(s, contacts):
    rows = []
    for _, r in s["teams"].iterrows():
        who = contacts.get(r["sarparast"], "").split("(")[0].strip()
        rows.append(
            f"<tr class='{'win' if r['prize_million'] else ''}'><td>{fa(int(r['rank']))}</td>"
            f"<td class='n'>{clean(r['sarparast'])}</td><td class='n'>{who}</td>"
            f"<td>{num(r['expected_million'], 1)}</td><td>{num(r['actual_million'], 1)}</td>"
            f"<td class='{'up' if r['growth_pct'] >= 0 else 'down'}'>{pct(r['growth_pct'])}</td>"
            f"<td>{fa(int(r['prize_million'])) if r['prize_million'] else '—'}</td></tr>"
        )
    return f"""
<h2>🏆 پاداش ویژه سرپرستان فروش همکده</h2>
<p class='note'>رتبه‌بندی بر اساس رشد وصولی نسبت به بازه قبل است؛ بازه قبل از ۲۱ شهریور شروع می‌شود و همان تعداد روز و تا همان ساعت را در بر می‌گیرد.<br>
رشد برابر است با وصولی جاری منهای وصولی بازه قبل، تقسیم بر وصولی بازه قبل. مبالغ به میلیون تومان است.</p>
<table><thead><tr><th>رتبه</th><th>تیم</th><th>سرپرست</th><th>وصولی بازه قبل</th><th>وصولی جاری</th><th>رشد</th><th>پاداش</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>"""


def _supervisor_section(rep, b, title):
    t = rep["teams"]
    rows = []
    for _, r in t.iterrows():
        ok = bool(r["eligible"])
        cls = "win" if r["prize_million"] else ("out" if not ok else "")
        rows.append(
            f"<tr class='{cls}'><td>{fa(int(r['rank'])) if ok else 'حذف'}</td><td class='n'>{clean(r['supervisor'])}</td>"
            f"<td>{fa(int(r['base_count']))}</td><td>{num(r['paid_toman'] / 1e6, 1)}</td>"
            f"<td>{num(r['avg_toman'] / 1e6, 2)}</td><td>{num(r['team_coe'], 1)}</td>"
            f"<td class='{'up' if r['coe_vs_overall_pct'] >= 0 else 'down'}'>{pct(r['coe_vs_overall_pct'])}</td>"
            f"<td>{fa(int(r['prize_million'])) if r['prize_million'] else '—'}</td></tr>"
        )
    n_out = int((~t["eligible"]).sum())
    return f"""
<h2>🏅 {title}</h2>
<p class='note'>{b.GROUP_DESC}؛ رتبه‌بندی بر اساس میانگین وصولی کل هر کارشناس مبنا است.<br>
شرط دریافت پاداش: افت ضریب وصولی تیم حداکثر ۶ درصد نسبت به ضریب کل همکده. ضریب کل همکده {num(rep['overall_coe'], 1)} و حد مجاز {num(rep['min_coe'], 1)} است.<br>
{fa(n_out)} تیم به‌دلیل افت ضریب از رتبه‌بندی حذف شده‌اند. مبالغ به میلیون تومان است.</p>
<table><thead><tr><th>رتبه</th><th>سوپروایزر</th><th>کارشناس مبنا</th><th>وصولی کل</th><th>میانگین هر کارشناس</th><th>ضریب تیم</th><th>اختلاف با کل</th><th>پاداش</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>"""


def _karshenas_section(k, kb):
    kt = k["table"]
    tier_rows = []
    prev = 0
    for last, inc in kb.TIERS:
        part = kt[(kt["rank"] > prev) & (kt["rank"] <= last)]
        tier_rows.append(
            f"<tr><td>{fa(prev + 1)} تا {fa(last)}</td><td>{pct(inc, 0, False)}</td>"
            f"<td>{pct(kb.final_commission_pct(inc), 1, False)}</td><td>{fa(len(part))}</td>"
            f"<td>{num(part['paid_coe'].min(), 0) if len(part) else '—'}</td></tr>"
        )
        prev = last
    top_rows = "".join(
        f"<tr class='win'><td>{fa(int(r['rank']))}</td><td class='n'>{r['کارشناس']}</td><td>{num(r['paid_coe'], 0)}</td>"
        f"<td>{num(r['paid'], 1)}</td><td>{pct(r['final_commission_pct'], 1, False)}</td></tr>"
        for _, r in kt.sort_values("rank").head(10).iterrows()
    )
    return f"""
<h2>📈 طرح رقابت ویژه ضریب وصولی کارشناسان همکده</h2>
<p class='note'>بازه طرح ۱۱ تا ۲۵ مهر است و رتبه‌بندی بر اساس ضریب وصولی انجام می‌شود.<br>
۲۵۰ نفر اول روی پورسانت پایه ۲۰ درصد افزایش پورسانت می‌گیرند. تعداد کارشناسان فعال در رتبه‌بندی: {fa(len(kt))} نفر.</p>
<div class='two'>
<table><thead><tr><th>پله رتبه</th><th>افزایش</th><th>پورسانت نهایی</th><th>تعداد</th><th>حداقل ضریب پله</th></tr></thead><tbody>{''.join(tier_rows)}</tbody></table>
<table><thead><tr><th>رتبه</th><th>کارشناس</th><th>ضریب وصولی</th><th>وصولی کل</th><th>پورسانت</th></tr></thead><tbody>{top_rows}</tbody></table>
</div>"""


def _html(report, contacts):
    k, g1, g2, s = report["karshenas"], report["group1"], report["group2"], report["sarparast"]
    mods = report["modules"]
    kb, g1b, g2b = mods["karshenas"], mods["group1"], mods["group2"]
    end = report["period_end"]
    when = f"۱۱ مهر تا {fa(end.day)} {MONTH_NAMES[end.month]} ساعت {fa(end.strftime('%H:%M'))}"
    kt = k["table"]
    st = s["teams"]

    tot_prev, tot_cur = st["expected_million"].sum(), st["actual_million"].sum()
    tot_g = (tot_cur - tot_prev) / tot_prev * 100 if tot_prev else 0.0
    growth_html = f"""
<div class='growth'><div class='gt'>📊 رشد کل وصولی همکده</div>
<div class='gv {'up' if tot_g >= 0 else 'down'}'>{pct(tot_g)}</div>
<div class='gs'>وصولی ۶ تیم سرپرستی تا این لحظه <b>{num(tot_cur, 1)}</b> میلیون تومان
در برابر <b>{num(tot_prev, 1)}</b> میلیون تومان در همین مدت از بازه قبل که از ۲۱ شهریور شروع می‌شود</div></div>"""

    def card(title, value, sub):
        return f"<div class='card'><div class='t'>{title}</div><div class='v'>{value}</div><div class='s'>{sub}</div></div>"

    def eligible(rep):
        return f"{fa(int(rep['teams']['eligible'].sum()))} تیم از {fa(len(rep['teams']))} تیم واجد شرایط"

    cards = "<div class='cards'>" + "".join([
        card("سرپرستان", f"{fa(int(st['prize_million'].sum()))} از {fa(SARPARAST_BUDGET_MILLION)}",
             "میلیون تومان تخصیص فعلی از بودجه"),
        card("سوپروایزر گروه اول", f"{fa(int(g1['teams']['prize_million'].sum()))} از {fa(sum(g1b.PRIZES_MILLION_TOMAN))}",
             f"میلیون تومان<br>{eligible(g1)}"),
        card("سوپروایزر گروه دوم", f"{fa(int(g2['teams']['prize_million'].sum()))} از {fa(sum(g2b.PRIZES_MILLION_TOMAN))}",
             f"میلیون تومان<br>{eligible(g2)}"),
        card("کارشناسان", f"{fa(min(250, len(kt)))} نفر",
             f"مشمول افزایش پورسانت<br>ضریب کل همکده {num(g1['overall_coe'], 1)}"),
    ]) + "</div>"

    s1, s2, slast = st.iloc[0], st.iloc[1], st.iloc[-1]
    t1, t2 = g1["teams"].iloc[0], g2["teams"].iloc[0]
    in250 = kt[kt["rank"] <= 250]["paid_coe"].min()
    points = [
        f"وصولی کل همکده نسبت به همین مدت از بازه قبل {growth_words(tot_g)} داشته است.",
        f"سرپرستان: <b>{clean(s1['sarparast'])}</b> با {growth_words(s1['growth_pct'])} در صدر است و "
        f"<b>{clean(s2['sarparast'])}</b> با {growth_words(s2['growth_pct'])} در رتبه دوم قرار دارد؛ "
        f"<b>{clean(slast['sarparast'])}</b> با {growth_words(slast['growth_pct'])} تنها تیم بدون پاداش است.",
        f"سوپروایزر گروه اول: صدر با <b>{clean(t1['supervisor'])}</b> و میانگین وصولی {num(t1['avg_toman'] / 1e6, 2)} "
        f"میلیون تومان برای هر کارشناس؛ {eligible(g1).replace(' واجد شرایط', '')} شرط ضریب را دارند.",
        f"سوپروایزر گروه دوم: صدر با <b>{clean(t2['supervisor'])}</b> و میانگین {num(t2['avg_toman'] / 1e6, 2)} "
        f"میلیون تومان؛ {eligible(g2).replace(' واجد شرایط', '')} شرط ضریب را دارند.",
        f"کارشناسان: ضریب وصولی کل همکده {num(g1['overall_coe'], 1)} است و برای ورود به جمع ۲۵۰ نفر برتر "
        f"فعلاً ضریب حداقل {num(in250, 0)} لازم است.",
    ]
    keys_html = "<div class='keys'><div class='kt'>💡 نکات کلیدی</div><ul>" + "".join(f"<li>{x}</li>" for x in points) + "</ul></div>"

    sections = (
        _sarparast_section(s, contacts)
        + _supervisor_section(g1, g1b, "پاداش ویژه سوپروایزرهای فروش همکده - گروه اول")
        + _supervisor_section(g2, g2b, "پاداش ویژه سوپروایزرهای فروش همکده - گروه دوم")
        + _karshenas_section(k, kb)
    )

    yekan, yekan_bold = _b64(os.path.join(_FONTS, "W_yekan.ttf")), _b64(os.path.join(_FONTS, "W_yekan Bold.ttf"))
    tahoma, tahoma_bold = _b64(os.path.join(_FONTS, "tahoma.ttf")), _b64(os.path.join(_FONTS, "tahomabd.ttf"))
    return f"""<!DOCTYPE html><html dir='rtl' lang='fa'><head><meta charset='utf-8'><style>
@font-face{{font-family:Y;src:url(data:font/ttf;base64,{yekan})}}
@font-face{{font-family:Y;font-weight:bold;src:url(data:font/ttf;base64,{yekan_bold})}}
@font-face{{font-family:Y;src:url(data:font/ttf;base64,{tahoma});unicode-range:{_DIGIT_RANGE}}}
@font-face{{font-family:Y;font-weight:bold;src:url(data:font/ttf;base64,{tahoma_bold});unicode-range:{_DIGIT_RANGE}}}
body{{margin:0;font-family:Y,sans-serif;background:#fff;color:#222}}
.wrap{{width:1120px;padding-bottom:24px}}
.band{{background:linear-gradient(135deg,#cf2547,#a31a37);color:#fff;text-align:center;padding:26px 30px}}
.band h1{{margin:0;font-size:30px}}
.br{{display:flex;align-items:center;justify-content:center;gap:14px}}
.logo{{background:#fff;border-radius:16px;padding:8px 16px;box-shadow:0 2px 8px rgba(0,0,0,.18)}}
.logo img{{height:38px;display:block}}
.band .p{{margin-top:12px;display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.4);border-radius:30px;padding:7px 22px;font-size:16px}}
.sec{{padding:0 30px}}
h2{{color:#a31a37;font-size:21px;margin:26px 0 6px;border-bottom:2px solid #cf2547;padding-bottom:6px}}
.note{{font-size:13.5px;color:#555;margin:6px 0 10px;line-height:1.9}}
table{{width:100%;border-collapse:collapse;font-size:14.5px}}
th{{background:#fdeef1;color:#a31a37;padding:9px 6px;border-bottom:2px solid #cf2547}}
td{{padding:7px 6px;text-align:center;border-bottom:1px solid #eee}}
td.n{{text-align:right}}
tr.win td{{background:#eef6f0}} tr.out td{{color:#999;background:#fafafa}}
.up{{color:#2e7d4f;font-weight:bold}} .down{{color:#c62828;font-weight:bold}}
.growth{{margin:20px 30px 0;border:2px solid #cf2547;border-radius:14px;padding:14px;text-align:center;background:#fff6f7}}
.growth .gt{{font-weight:bold;color:#a31a37;font-size:18px}} .growth .gv{{font-size:34px;margin:4px 0}} .growth .gs{{font-size:14px;color:#444}}
.cards{{display:flex;gap:12px;padding:20px 30px 0}}
.card{{flex:1;border:1px solid #f1c7d0;border-radius:12px;padding:12px;text-align:center;background:#fff6f7}}
.card .t{{font-weight:bold;color:#a31a37}} .card .v{{font-size:24px;font-weight:bold;margin:6px 0}} .card .s{{font-size:12px;color:#666}}
.keys{{margin-top:22px;border-right:5px solid #cf2547;background:#fdf7f8;border-radius:10px;padding:12px 18px}}
.keys .kt{{font-weight:bold;color:#a31a37;font-size:19px}} .keys li{{font-size:15px;line-height:2.1}}
.two{{display:flex;gap:16px;align-items:flex-start}}
.foot{{margin:28px 30px 0;padding-top:12px;border-top:2px solid #cf2547;text-align:center;font-size:15px;color:#a31a37}}
</style></head><body><div class='wrap'>
<div class='band'><div class='br'><div class='logo'><img src='data:image/png;base64,{_b64(_LOGO_PATH)}'></div>
<h1>گزارش جامع طرح‌های پاداش فروش همکده 🏆</h1></div><div class='p'>عملکرد از {when}</div></div>
{growth_html}
{cards}
<div class='sec'>{keys_html}{sections}</div>
<div class='foot'>واحد سازنده گزارش: <b>واحد آنالیز گزارشات</b></div>
</div></body></html>""", when


def render(report, reward_id, slot):
    from importlib import import_module
    contacts = import_module("Rewards.padash-sarparast-hamkadeh-11-30mehr.render").CONTACTS

    html, when = _html(report, contacts)
    label = report["slot_jdt"].strftime("%Y_%m_%d_%H%M")
    out_dir = os.path.join(_OUTPUT_DIR, label)
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, "گزارش جامع پاداش‌های همکده")
    with open(base + ".html", "w", encoding="utf-8") as f:
        f.write(html)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(device_scale_factor=2)
        page.set_content(html)
        page.locator(".wrap").screenshot(path=base + ".png", type="png")
        browser.close()
    with open(base + ".pdf", "wb") as f:
        f.write(img2pdf.convert(base + ".png"))

    return [OutboundMessage(
        reward_id=reward_id,
        slot=slot,
        panel_user_id=recipient,
        chat_user_id="",
        contact=recipient,
        text=f"گزارش جامع طرح‌های پاداش فروش همکده - عملکرد از {when}",
        image=base + ".pdf",
    ) for recipient in RECIPIENTS]
