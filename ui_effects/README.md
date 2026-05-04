# ui-effects

Generic, framework-agnostic CSS keyframes + JavaScript helpers for terminal /
matrix style web UIs. Drop the static folder into any project, or mount it as a
Flask blueprint.

## What's inside

- `static/css/animations.css` — every reusable `@keyframes` (prefixed `uix-`)
  plus a few `.uix-anim-*` utility classes. Honours `prefers-reduced-motion`.
- `static/css/transitions.css` — minimal styles for `UIEffects.pageTransition()`
  (no markup needed in the host HTML; the helper injects it).
- `static/js/ui-effects.js` — exposes `window.UIEffects`:
  - `matrixRain(canvas, options) -> { stop }`
  - `pageTransition(options) -> { play(text, signature) }`
  - `typewriter(target, text, options) -> Promise`

## Use it from Flask

```python
import sys
from pathlib import Path

# Make the sibling package importable (adjust to point at the parent that
# contains the ui_effects/ folder)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ui_effects
app.register_blueprint(ui_effects.create_blueprint())  # served at /ui-effects
```

Then in templates:

```html
<link rel="stylesheet" href="{{ url_for('ui_effects.static', filename='css/animations.css') }}">
<link rel="stylesheet" href="{{ url_for('ui_effects.static', filename='css/transitions.css') }}">
<script src="{{ url_for('ui_effects.static', filename='js/ui-effects.js') }}"></script>
```

## Use it from any other project

Just copy or symlink `static/` into the host project's static tree, then:

```html
<link rel="stylesheet" href="/static/ui-effects/css/animations.css">
<script src="/static/ui-effects/js/ui-effects.js"></script>
```

## API examples

```js
// 1. Background matrix rain in a <canvas id="rain">
const rain = UIEffects.matrixRain('#rain', { color: '#00ff41', speed: 33 });
// rain.stop() to halt

// 2. Animated route transition before navigating
const trans = UIEffects.pageTransition({ duration: 1200 });
document.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', e => {
        if (a.target === '_blank') return;
        e.preventDefault();
        trans.play('NAVIGATING...', '// uix').then(() => {
            window.location.href = a.href;
        });
    });
});

// 3. Typewriter effect
UIEffects.typewriter('#splashLine', 'INITIALIZING SYSTEM ...', { delay: 22 });
```

## Animation names (CSS)

All keyframes are prefixed `uix-` so they cannot collide:
`uix-soft-pulse`, `uix-notif-pulse`, `uix-phase-in`, `uix-page-enter`,
`uix-intel-expand`, `uix-terminal-line-in`, `uix-hex-pulse`, `uix-hex-spin`,
`uix-splash-glow`, `uix-splash-glow-text`, `uix-splash-type`,
`uix-splash-blink`, `uix-brand-line-in`, `uix-brand-sub-in`,
`uix-brand-glitch`, `uix-welcome-line-in`, `uix-welcome-fade`,
`uix-trans-text-glitch`, `uix-trans-flash`, `uix-scanline-move`,
`uix-scanline-flicker`, `uix-docs-scan`.

## Reduced motion

`prefers-reduced-motion: reduce` disables the JS rain/transition/typewriter
helpers (they resolve immediately) and zeros all `.uix-anim-*` utility classes.
Define your own animations directly on selectors if you want finer-grained
control.
