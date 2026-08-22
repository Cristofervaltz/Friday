# 🌟 Friday v1.5.0 — Big UI Overhaul & Skills System

This is the most significant release since Friday's launch. I've completely rethought how the app looks and feels, given you the power to extend it however you like — and laid the foundation for autonomous multi-agent sessions coming in v2.0.

---

## 🎨 New Interface — Cleaner, Smarter, More Alive

Friday no longer looks like a prototype. I've removed every hardcoded emoji and replaced the entire visual language with a unified **Lucide React** icon system — crisp vector icons that look great on any screen and in any theme.

But the bigger story is how the interface now *reacts to context*. The send button is no longer just a button:

- 🔴 **Stop** — appears while Friday is generating a response or running tools. One click and she halts instantly.
- 📋 **Queue** — if you start typing your next thought while Friday is still busy, the button becomes a Queue. Your message will be held and sent the moment she finishes.

The chat is now a live workspace, not just an input field.

---

## 🧠 Skills — Make Friday Yours

The most requested feature. You can now literally *teach* Friday to be whatever you need — a code reviewer, an architect, a technical writer, or anything else.

**How it works:**

1. Create a .md file in ~/.friday/skills/
2. Write any system instructions inside — role, tone, context
3. Friday detects the file automatically and adds it to the menu

**The / menu is here** — type / in the chat input and you'll see all your available skills. Select one and its instructions are injected into the agent's context instantly.

Skills work out of the box with no app restart and no code changes required.

---

## ⚡ Under the Hood — Serious Work

While the interface was getting prettier, I wasn't sitting still on the backend:

- **Background Tasks** — overhauled background processing architecture. The UI stays fully responsive even during long-running agent sessions.
- **Swarm Foundation** — infrastructure for DelegateTask and parallel agent sessions has been laid in preparation for v2.0.
- **Stability** — fixed WebSocket disconnect edge cases, corrected memory truncation logic, added thread-safe locks for concurrent settings I/O.
- **Strict Typing** — the entire backend now passes full mypy and 
uff checks.

---

## 📦 Installation

1. Download **Friday_1.5.0_x64_en-US.msi** or **.exe** below
2. Run the installer — it will correctly upgrade your previous version
3. Open Friday, type / in the chat input and explore the built-in skills

---

*Thank you for being here. If Friday makes your work better — drop a ⭐ on GitHub, it means a lot to the project.*

---

<details>
<summary>🇷🇺 Описание на русском языке</summary>

<br>

## 🌟 Friday v1.5.0 — Большое обновление интерфейса и система навыков

Это самый значимый релиз Friday со дня запуска. Я полностью переосмыслил то, как выглядит и ощущается приложение, дал вам возможность расширять его под себя — и заложил фундамент для автономных агентных сессий в v2.0.

### 🎨 Новый интерфейс — чище, умнее, живее

Friday больше не выглядит как прототип. Я избавился от разрозненных эмодзи и заменил весь визуальный язык приложения на единую систему иконок **Lucide React** — чёткие векторные значки, которые одинаково красиво выглядят на любом экране и в любой теме.

Но главное — интерфейс теперь реагирует на контекст. Кнопка отправки больше не просто кнопка:

- 🔴 **Stop** — появляется, пока Friday генерирует ответ или выполняет инструменты. Один клик — и она мгновенно останавливается.
- 📋 **Queue** — если вы начинаете печатать следующую мысль, пока Friday ещё занята, кнопка превращается в Queue. Ваше сообщение встанет в очередь и будет отправлено сразу после завершения текущей задачи.

### 🧠 Навыки (Skills) — сделайте Friday своей

1. Создайте .md-файл в папке ~/.friday/skills/
2. Напишите в нём любые системные инструкции — роль, стиль ответов, контекст
3. Friday автоматически обнаружит файл и добавит его в меню

Введите / в поле чата — появится меню со всеми доступными навыками. Выберите нужный, и его инструкции мгновенно вливаются в контекст агента.

### ⚡ Под капотом

- Переработана архитектура фоновой обработки — UI остаётся отзывчивым при любых задачах
- Заложена инфраструктура для агентного роя (DelegateTask) в v2.0
- Устранены краевые случаи с WebSocket, исправлена логика усечения памяти
- Весь бэкенд проходит полную проверку mypy и 
uff

### 📦 Установка

1. Скачайте **Friday_1.5.0_x64_en-US.msi** или **.exe** ниже
2. Запустите установщик — он корректно обновит предыдущую версию
3. Откройте Friday, введите / в поле чата и изучите встроенные навыки

*Спасибо за вашу поддержку! Если Friday делает вашу работу лучше — поставьте ⭐ на GitHub, это очень много значит для проекта.*

</details>