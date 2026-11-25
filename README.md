# ЛР3 — Sequence-діаграми бібліотечної системи

**Тема:** взаємодія компонентів під час оформлення видачі фізичного примірника. **Мета:** узгодити поведінку UC-05 із п’ятьма сутностями бібліотечної ER-моделі та Gherkin-сценаріями попередньої роботи.

## Передумови та джерела

- [ЛР1 — ER-модель бібліотеки](https://github.com/Alex9011/Lab1_KPI2/blob/master/spec.md)
- [ЛР2 — UC та Gherkin](https://github.com/Alex9011/Lab2-KPI2/blob/master/spec.md)
- [Поточний PR №1](https://github.com/Alex9011/KPI2-Lab3/pull/1)
- [Коротка специфікація](spec.md) · [Gherkin-сценарії](scenarios.md) · [DEFENSE](DEFENSE.md)

## Сценарії UC-05

| ID | Сценарій | Діаграма |
|---|---|---|
| S-01 | Перша успішна видача | [SVG](render/S-01-first-loan.svg) · [MMD](sequence/S-01-first-loan.mmd) |
| S-02 | Повторна видача після повернення | [SVG](render/S-02-repeat-loan.svg) · [MMD](sequence/S-02-repeat-loan.mmd) |
| S-03 | Примірник уже виданий | [SVG](render/S-03-already-loaned.svg) · [MMD](sequence/S-03-already-loaned.mmd) |
| S-04 | Недопустимий строк повернення | [SVG](render/S-04-invalid-due-date.svg) · [MMD](sequence/S-04-invalid-due-date.mmd) |
| S-05 | Читача не знайдено | [SVG](render/S-05-member-missing.svg) · [MMD](sequence/S-05-member-missing.mmd) |
| S-06 | Примірника не знайдено | [SVG](render/S-06-copy-missing.svg) · [MMD](sequence/S-06-copy-missing.mmd) |
| S-07 | Два паралельні запити на один примірник | [SVG](render/S-07-concurrent-requests.svg) · [MMD](sequence/S-07-concurrent-requests.mmd) |
| S-08 | Користувач не має прав | [SVG](render/S-08-unauthorized.svg) · [MMD](sequence/S-08-unauthorized.mmd) |

Зведений перегляд: [`render/index.html`](render/index.html). Mermaid-файли `.mmd` — канонічні; SVG генеруються з них.

## Структура

- `sequence/` — 8 джерел Mermaid.
- `render/` — 8 SVG та оглядова HTML-сторінка.
- `scenarios.md` — повні сценарії Gherkin, звірені з ЛР2.
- `spec.md`, `DEFENSE.md` — короткий опис і матеріал захисту.
- `adr/0001-loan-consistency.md` — рішення щодо транзакційної узгодженості видач.
- `ai/audit.md`, `ai/prompt.md`, `ai/check.py` — аудит, справжній слід взаємодії та перевірка.

## Рендер і перевірка

Потрібні Node.js/npm, PowerShell 5.1+ та Python 3.11+. Встановіть офіційний Mermaid CLI версії 12.2.0 і згенеруйте SVG:

```powershell
npm install --global @mermaid-js/mermaid-cli@12.2.0
powershell -NoProfile -File ai/render.ps1
python ai/check.py
```

`ai/check.py` перевіряє 8 сценаріїв і джерел, фрагменти, активації, відповіді, відповідність ключовим умовам Gherkin, SVG, локальні посилання та синтаксис усіх `.mmd` через Mermaid CLI. На середовищах із окремими налаштуваннями Chromium можна передати CLI Puppeteer-конфіг через змінну `PUPPETEER_CONFIG`.

## Аудит і рішення

- [Результати аудиту](ai/audit.md)
- [ADR-0001: узгодженість видач](adr/0001-loan-consistency.md)
- [Рекомендації студенту для власного перегляду](ai/STUDENT_REVIEW.md)
