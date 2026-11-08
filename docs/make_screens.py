"""Скриншоты кабинета организации и видео-демо заполнения карточки — для презентаций.

Нужен запущенный сервер (лучше с демо-провайдером и чистой базой) и пароль модератора:

    LLM_PROVIDER=demo ADMIN_PASSWORD=demo DATA_DIR=/tmp/tt-demo PUBLIC_URL=http://localhost:8010 \\
        uvicorn backend.main:app --port 8010
    python docs/make_screens.py http://localhost:8010 demo out/screens

Организация — вымышленная (демо-комплект demo/agrosensor). Скриншоты — 1600×900 в двойной плотности
и два с телефона; видео — demo.mp4, 1920×1080: кадры Chrome (screencast), склейка ffmpeg (нужен в PATH).
Свой Chromium — переменная CHROMIUM.
"""
import os
import base64
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

BASE, ADMIN_PW, OUT = sys.argv[1].rstrip("/"), sys.argv[2], Path(sys.argv[3])
ADMIN = (os.environ.get("ADMIN_USER", "admin"), ADMIN_PW)
DEMO = Path(__file__).resolve().parent.parent / "demo" / "agrosensor"
FILES = [str(DEMO / "presentation.pdf"), str(DEMO / "spec.docx")]
ORG = "ООО «Агросенсор»"
W, H = 1600, 900

# чего демо-извлечение не находит — «организация» дописывает по своим же материалам
MANUAL = {
    "tags": ["мониторинг почвы", "LoRaWAN", "точное земледелие"],
    "problem": "Хозяйства теряют до 20% урожая из-за неравномерного полива: о пересыхании почвы агроном "
               "узнаёт с опозданием на 3–5 дней.",
    "advantages": "Датчик работает 3 года без замены батареи; комплект на 100 га на 40% дешевле импортных систем; "
                  "отечественная элементная база.",
    "technologies": "Беспроводная сеть LoRaWAN, машинное обучение: прогноз влажности почвы на 72 часа.",
}
STEPS = [
    ("Ссылка-приглашение", "Организация открывает персональную ссылку — без регистрации и паролей."),
    ("Загрузка материалов", "Презентация, техописание, буклет — PDF, DOCX, PPTX, сканы и фото."),
    ("ИИ заполняет карточку", "Поля заполняются по материалам за несколько секунд."),
    ("Источник у каждого значения", "Под полем — цитата из материалов: видно, откуда взято."),
    ("Организация дописывает", "Что ИИ не нашёл, отмечено — заполняется вручную."),
    ("Отправка на модерацию", "Модератор проверяет по чек-листу и принимает или возвращает с комментарием."),
]

# видео: условный курсор (запись браузера курсор не показывает), подсветка клика, подпись шага на левом поле
OVERLAY = r"""
(() => {
  const css = `
    #__cur{position:fixed;left:-40px;top:-40px;z-index:2147483647;pointer-events:none;width:24px;height:24px}
    .__tap{position:fixed;z-index:2147483646;pointer-events:none;width:30px;height:30px;margin:-15px 0 0 -15px;
      border-radius:50%;background:rgba(244,178,35,.55);transition:transform .45s ease-out,opacity .45s ease-out}
    #__step{position:fixed;left:32px;top:100px;width:280px;z-index:2147483645;pointer-events:none;
      font-family:'Golos Text','Segoe UI',sans-serif;color:#1d2733;background:#fff;border:1px solid #e3e8ef;
      border-radius:10px;padding:16px 18px;box-shadow:0 6px 24px rgba(20,40,70,.08);transition:opacity .3s}
    #__step small{display:flex;align-items:center;gap:8px;color:#5f6b7b;font-size:13px}
    #__step small i{width:9px;height:9px;border-radius:50%;background:#f4b223;display:inline-block}
    #__step b{display:block;margin:6px 0 4px;font-size:19px;line-height:1.25}
    #__step span{display:block;font-size:14px;line-height:1.45;color:#3c4858}`;
  const add = () => {
    if (document.getElementById('__cur')) return;
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    const c = document.createElement('div'); c.id = '__cur';
    c.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24"><path d="M4 2.5l6.5 18 2.6-7.4 7.4-2.6z" fill="#1d2733" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
    const s = document.createElement('div'); s.id = '__step'; s.style.opacity = 0; document.body.appendChild(s);
    addEventListener('mousemove', e => { c.style.left = (e.clientX - 4) + 'px'; c.style.top = (e.clientY - 3) + 'px'; }, true);
    addEventListener('mousedown', e => {
      const t = document.createElement('div'); t.className = '__tap'; t.style.left = e.clientX + 'px'; t.style.top = e.clientY + 'px';
      document.body.appendChild(t); requestAnimationFrame(() => { t.style.transform = 'scale(2)'; t.style.opacity = 0; });
      setTimeout(() => t.remove(), 500);
    }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', add); else add();
  window.__step = (n, total, title, text) => {
    const s = document.getElementById('__step');
    s.innerHTML = `<small><i></i>Шаг ${n} из ${total}</small><b>${title}</b><span>${text}</span>`; s.style.opacity = 1;
  };
})();
"""


def invite(plan):
    r = requests.post(f"{BASE}/api/admin/invites", json={"org_label": ORG, "plan": plan}, auth=ADMIN, timeout=30)
    r.raise_for_status()
    return r.json()["url"]


def moderate(card_id, verdict, comment):
    checklist = {k: True for k in ("Наименование", "Отрасль", "Организация", "ТТХ", "Без лишнего", "Без ошибок")}
    r = requests.post(f"{BASE}/api/admin/cards/{card_id}/moderation", auth=ADMIN, timeout=30,
                      json={"verdict": verdict, "checklist": checklist, "comment": comment})
    r.raise_for_status()


def fill_manual(page, typing_delay=0):
    """Дописать четыре поля, которых нет в автозаполнении, — как это сделал бы человек."""
    tags = page.locator("#root_tags")
    for tag in MANUAL["tags"]:
        tags.click()
        tags.press_sequentially(tag, delay=typing_delay)
        tags.press("Enter")
    for key in ("problem", "advantages", "technologies"):
        box = page.locator(f"#root_{key}")
        box.scroll_into_view_if_needed()
        box.click()
        box.press_sequentially(MANUAL[key], delay=typing_delay)
    page.wait_for_timeout(1200)  # автосохранение


def screenshots(browser):
    n = 0

    def shot(page, name, full=False, toast=False):
        nonlocal n
        n += 1
        if not toast:  # всплывающее уведомление закрывает шапку — ждём, пока исчезнет
            page.locator(".ant-message-notice").first.wait_for(state="detached", timeout=8000)
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / f"{n:02d}-{name}.png", full_page=full)

    ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=2)
    page = ctx.new_page()
    page.goto(invite(["ai", "manual"]))
    page.get_by_role("button", name="Начать").wait_for()
    shot(page, "glavnaya")

    page.get_by_role("button", name="Начать").click()
    page.get_by_text("Шаг 1. Загрузите материалы").wait_for()
    card_id = int(page.url.rstrip("/").split("/")[-1])
    page.locator("input[type=file]").set_input_files(FILES)
    page.locator(".files").get_by_text("spec.docx").wait_for()
    shot(page, "zagruzka-materialov")

    page.get_by_role("button", name="Заполнить карточку автоматически").click()
    page.get_by_text("Читаем материалы и заполняем карточку").wait_for()
    page.wait_for_timeout(1100)  # счётчик секунд — не ноль
    shot(page, "ii-chitaet-materialy")
    page.locator("#root_product_name").wait_for(timeout=60000)
    page.mouse.move(W - 10, H - 10)  # чтобы не висела подсказка от наведения
    shot(page, "kartochka-zapolnena")

    page.evaluate("document.getElementById('field-tech_params').closest('.section').scrollIntoView({block: 'start'});"
                  "scrollBy(0, -84)")  # с заголовком секции, под шапкой
    shot(page, "harakteristiki-s-istochnikom")

    # человек поправил значение ИИ — у поля метка «исправлено»
    dep = page.locator("#root_deployments_count")
    dep.fill("3 пилотных внедрения в Тамбовской и Липецкой областях")
    page.evaluate("document.getElementById('field-deployments_count').scrollIntoView({block: 'center'})")
    shot(page, "ispravleno-chelovekom")

    page.get_by_role("button", name="Отправить на модерацию").click()
    page.get_by_text("Поправьте поля перед отправкой").wait_for()
    page.wait_for_timeout(800)  # плавная прокрутка к первому пустому полю
    shot(page, "ne-zapolneno-obyazatelnoe", toast=True)

    fill_manual(page)
    page.get_by_role("button", name="Отправить на модерацию").click()
    page.get_by_text("Карточка отправлена на модерацию").first.wait_for()
    page.evaluate("scrollTo(0, 0)")
    shot(page, "otpravleno-na-moderaciyu")

    page.goto(BASE + "/")
    page.get_by_role("button", name="Начать").click()  # вторая карточка по плану — вручную
    page.get_by_text("Эта карточка заполняется вручную").wait_for()
    page.mouse.move(W - 10, H - 10)
    shot(page, "ruchnaya-kartochka")

    page.goto(BASE + "/")
    page.get_by_text("Ещё одна разработка").wait_for()
    shot(page, "glavnaya-statusy")

    moderate(card_id, "returned", "Уточните срок внедрения: в материалах указано «ввод в эксплуатацию — до 2 недель».")
    page.goto(f"{BASE}/cards/{card_id}")
    page.get_by_text("Модератор вернул карточку на доработку").wait_for()
    shot(page, "vozvrat-s-kommentariem")

    page.locator("#root_implementation_time").fill("До 2 недель с момента монтажа")
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="Отправить на модерацию").click()
    page.get_by_text("Карточка отправлена на модерацию").first.wait_for()
    moderate(card_id, "accepted", "Спасибо! Карточка опубликована на Витрине.")
    page.goto(f"{BASE}/cards/{card_id}")
    page.get_by_text("Карточка принята модератором").wait_for()
    shot(page, "prinyata")
    page.goto(BASE + "/")
    page.get_by_text("Ещё одна разработка").wait_for()
    shot(page, "glavnaya-prinyata")
    ctx.close()

    phone = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    p2 = phone.new_page()
    p2.goto(invite(["ai"]))
    p2.get_by_role("button", name="Начать").click()
    p2.get_by_text("Шаг 1. Загрузите материалы").wait_for()
    p2.locator("input[type=file]").set_input_files(FILES)
    p2.locator(".files").get_by_text("spec.docx").wait_for()
    p2.get_by_role("button", name="Заполнить карточку автоматически").click()
    p2.locator("#root_product_name").wait_for(timeout=60000)
    shot(p2, "telefon-kartochka")
    p2.goto(BASE + "/")
    p2.get_by_text("Ещё одна разработка").wait_for()
    shot(p2, "telefon-glavnaya")
    phone.close()
    return n


def video(browser):
    if not shutil.which("ffmpeg"):
        print("видео пропущено: нет ffmpeg")
        return None
    # кадры — screencast Chrome (JPEG 92, 1920×1080 при вёрстке 1600×900): чётче встроенной записи Playwright
    ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1.2)
    ctx.add_init_script(OVERLAY)
    page = ctx.new_page()
    total = len(STEPS)
    frames, cdp = [], ctx.new_cdp_session(page)

    def on_frame(f):
        frames.append((f["metadata"]["timestamp"], f["data"]))
        cdp.send("Page.screencastFrameAck", {"sessionId": f["sessionId"]})

    cdp.on("Page.screencastFrame", on_frame)

    def step(i):
        page.evaluate("([n, t, a, b]) => window.__step(n, t, a, b)", [i, total, *STEPS[i - 1]])

    def go(locator, steps=28):
        box = locator.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)
        page.wait_for_timeout(250)

    def click(locator):
        go(locator)
        locator.click()

    def glide(locator, top=170):
        """Плавная прокрутка, пока элемент не окажется в top px от верха."""
        dist = locator.bounding_box()["y"] - top
        n = max(1, int(abs(dist) / 45))
        for _ in range(n):
            page.mouse.wheel(0, dist / n)
            page.wait_for_timeout(18)
        page.wait_for_timeout(500)

    page.goto(invite(["ai"]))
    page.get_by_role("button", name="Начать").wait_for()
    page.mouse.move(W / 2, H / 2)
    cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920, "maxHeight": 1080})
    step(1)
    page.wait_for_timeout(2600)
    click(page.get_by_role("button", name="Начать"))

    page.get_by_text("Шаг 1. Загрузите материалы").wait_for()
    step(2)
    page.wait_for_timeout(1500)
    go(page.locator(".ant-upload-drag"))
    page.locator("input[type=file]").set_input_files(FILES)
    page.locator(".files").get_by_text("spec.docx").wait_for()
    page.wait_for_timeout(1800)

    step(3)
    click(page.get_by_role("button", name="Заполнить карточку автоматически"))
    page.locator("#root_product_name").wait_for(timeout=60000)
    page.wait_for_timeout(2600)

    step(4)
    go(page.locator("#field-product_name .quote"))
    page.wait_for_timeout(2200)
    glide(page.locator("#field-industry"))
    page.wait_for_timeout(1400)
    glide(page.locator("#field-org_name"))
    page.wait_for_timeout(1600)
    glide(page.locator("#field-tech_params"))
    page.wait_for_timeout(2200)

    step(5)
    glide(page.locator("#field-tags"), top=220)
    page.wait_for_timeout(1400)
    tags = page.locator("#root_tags")
    click(tags)
    for tag in MANUAL["tags"]:
        tags.press_sequentially(tag, delay=45)
        tags.press("Enter")
        page.wait_for_timeout(250)
    for key in ("problem", "advantages", "technologies"):
        box = page.locator(f"#root_{key}")
        glide(box, top=300)
        click(box)
        box.press_sequentially(MANUAL[key], delay=18)
        page.wait_for_timeout(500)
    page.wait_for_timeout(1500)

    step(6)
    click(page.get_by_role("button", name="Отправить на модерацию"))
    page.get_by_text("Карточка отправлена на модерацию").first.wait_for()
    page.wait_for_timeout(600)
    page.mouse.wheel(0, -4000)
    page.wait_for_timeout(3500)
    cdp.send("Page.stopScreencast")
    page.wait_for_timeout(300)
    ctx.close()

    # кадры приходят, только когда страница меняется: длительность кадра — до следующего, последний — 2 с
    mp4 = OUT / "demo.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        lines = []
        for i, (ts, data) in enumerate(frames):
            name = f"f{i:05d}.jpg"
            Path(tmp, name).write_bytes(base64.b64decode(data))
            dur = (frames[i + 1][0] - ts) if i + 1 < len(frames) else 2.0
            lines += [f"file '{name}'", f"duration {max(dur, 0.001):.4f}"]
        lines.append(f"file 'f{len(frames) - 1:05d}.jpg'")  # concat берёт длительность последнего так
        Path(tmp, "list.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        # MP4 (H.264) открывается в PowerPoint и Keynote
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
                        "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-crf", "18",
                        "-preset", "slow", "-movflags", "+faststart", str(mp4.resolve())], check=True, cwd=tmp)
    return mp4


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None)
        print("скриншотов:", screenshots(browser))
        print("видео:", video(browser))
        browser.close()
