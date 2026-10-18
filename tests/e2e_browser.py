"""Прогон пилота в браузере (Playwright, Chromium) со скриншотами.

    python tests/e2e_browser.py http://localhost:8000/?t=<токен> --admin admin:<пароль> --out shots/

Сервер должен быть запущен с собранным фронтом (backend/static) и LLM_PROVIDER=demo.
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

DEMO = Path(__file__).resolve().parent.parent / "demo" / "agrosensor"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("invite")
    ap.add_argument("--admin", default="admin:admin")
    ap.add_argument("--out", default="shots")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    base = a.invite.split("/?")[0]
    errors = []

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1280, "height": 900}, locale="ru-RU")
        page.on("pageerror", lambda e: errors.append(str(e)))
        # 422 — ожидаемый ответ на отправку с пустыми обязательными полями (шаг 4)
        page.on("console", lambda m: m.type == "error" and "422" not in m.text and errors.append(m.text))

        # 1. вход по приглашению
        page.goto(a.invite)
        expect(page.get_by_text("Карточка 1: с автозаполнением")).to_be_visible()
        assert "?t=" not in page.url
        page.screenshot(path=out / "01_home.png", full_page=True)

        # 2. карточка с ИИ: загрузка → автозаполнение
        page.get_by_role("button", name="Начать").click()
        expect(page.get_by_text("Шаг 1. Загрузите материалы")).to_be_visible()
        page.locator("input[type=file]").set_input_files([str(f) for f in sorted(DEMO.iterdir())])
        expect(page.get_by_text("spec.docx")).to_be_visible()
        expect(page.get_by_text("presentation.pdf")).to_be_visible()
        page.screenshot(path=out / "02_upload.png", full_page=True)
        page.get_by_role("button", name="Заполнить карточку автоматически").click()
        expect(page.get_by_text("ИИ заполнил")).to_be_visible(timeout=30000)
        page.screenshot(path=out / "03_filled.png", full_page=True)

        # 3. правка: теги, проблема, преимущества, технологии
        tags = page.locator("#root_tags")
        tags.click()
        for t in ("датчики", "влажность почвы", "lorawan"):
            page.keyboard.type(t)
            page.keyboard.press("Enter")
        page.locator("#root_problem").fill("Неравномерный полив и позднее обнаружение пересыхания почвы.")
        page.locator("#root_advantages").fill("Датчик работает 3 года без замены батареи.")
        page.wait_for_timeout(1200)
        expect(page.get_by_text("Сохранено")).to_be_visible()

        # 4. попытка отправки: не хватает «Используемые технологии»
        page.get_by_role("button", name="Отправить на модерацию").click()
        expect(page.locator("#field-technologies .field-problem")).to_have_text("обязательное поле")
        page.screenshot(path=out / "04_problems.png")
        page.locator("#root_technologies").fill("LoRaWAN, прогноз влажности моделью машинного обучения.")
        page.wait_for_timeout(1200)
        expect(page.locator("#field-technologies .field-problem")).to_have_count(0)
        page.get_by_role("button", name="Отправить на модерацию").click()
        expect(page.get_by_text("Карточка отправлена на модерацию")).to_be_visible()
        page.screenshot(path=out / "05_submitted.png", full_page=True)

        # 5. вторая карточка — вручную
        page.get_by_text("Мои карточки").click()
        page.get_by_role("button", name="Начать").click()
        expect(page.get_by_text("Эта карточка заполняется вручную")).to_be_visible()
        page.screenshot(path=out / "06_manual.png")

        # 6. модератор
        user, pwd = a.admin.split(":", 1)
        page.goto(base + "/admin")
        page.get_by_label("Пароль").fill(pwd)
        page.get_by_label("Логин").fill(user)
        page.get_by_role("button", name="Войти").click()
        expect(page.get_by_text("Ждут модерации")).to_be_visible()
        page.screenshot(path=out / "07_admin_list.png")
        page.locator("tr.ant-table-row").first.click()
        expect(page.get_by_text("Решение")).to_be_visible()
        page.screenshot(path=out / "08_admin_card.png", full_page=True)
        for cb in page.locator(".side .ant-checkbox-wrapper").all():
            cb.click()
        page.get_by_role("button", name="Принять").click()
        expect(page.get_by_text("принята", exact=True)).to_be_visible()

        # 7. выгрузка
        page.goto(base + "/admin")
        with page.expect_download() as dl:
            page.get_by_role("button", name="Выгрузка для КПЭ (Excel)").click()
        dl.value.save_as(out / "export.xlsx")

        # 8. телефон
        m = b.new_page(viewport={"width": 390, "height": 844}, locale="ru-RU")
        m.goto(a.invite)
        m.get_by_text("Карточка 1").click()
        expect(m.get_by_text("Карточка принята модератором")).to_be_visible()
        m.screenshot(path=out / "10_mobile.png", full_page=False)
        b.close()

    if errors:
        print("Ошибки в консоли браузера:", *errors, sep="\n  ")
        sys.exit(1)
    print("OK, скриншоты:", out)


if __name__ == "__main__":
    main()
