/* ui-effects.js — generic, dependency-free helpers for terminal/matrix UIs.
 *
 * Exposes window.UIEffects with:
 *   - matrixRain(canvas, options) -> { stop }
 *   - pageTransition(options)     -> { play(text, signature) }
 *   - typewriter(target, text, options) -> Promise
 *
 * Designed to be opt-in: it does nothing until you call one of these.
 */

(function (root) {
    'use strict';

    function reducedMotion() {
        return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function resolveCanvas(input) {
        if (!input) return null;
        if (typeof input === 'string') return document.querySelector(input);
        if (input instanceof HTMLCanvasElement) return input;
        return null;
    }

    /* ------------------------------------------------------------------
     * matrixRain(canvas, options)
     *   - canvas: HTMLCanvasElement or selector
     *   - options.alphabet: string of glyphs to rain (default: katakana + 0-9)
     *   - options.fontSize: px (default 14)
     *   - options.color: trail head color (default '#00ff41')
     *   - options.fadeColor: rgba bg fade per frame (default 'rgba(0,0,0,0.05)')
     *   - options.speed: ms per frame (default 33)
     * ------------------------------------------------------------------ */
    function matrixRain(canvas, options) {
        const cv = resolveCanvas(canvas);
        if (!cv || reducedMotion()) {
            return { stop: function () {} };
        }
        const opts = Object.assign({
            alphabet: 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ0123456789',
            fontSize: 14,
            color: '#00ff41',
            fadeColor: 'rgba(0,0,0,0.05)',
            speed: 33,
        }, options || {});

        const ctx = cv.getContext('2d');
        let drops = [];
        let columns = 0;
        let timer = null;

        function resize() {
            cv.width = cv.offsetWidth || cv.parentElement.clientWidth;
            cv.height = cv.offsetHeight || cv.parentElement.clientHeight;
            columns = Math.max(1, Math.floor(cv.width / opts.fontSize));
            drops = new Array(columns).fill(1);
        }

        function draw() {
            ctx.fillStyle = opts.fadeColor;
            ctx.fillRect(0, 0, cv.width, cv.height);
            ctx.fillStyle = opts.color;
            ctx.font = opts.fontSize + 'px monospace';
            for (let i = 0; i < drops.length; i++) {
                const ch = opts.alphabet.charAt(Math.floor(Math.random() * opts.alphabet.length));
                ctx.fillText(ch, i * opts.fontSize, drops[i] * opts.fontSize);
                if (drops[i] * opts.fontSize > cv.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        }

        resize();
        window.addEventListener('resize', resize);
        timer = setInterval(draw, opts.speed);

        return {
            stop: function () {
                if (timer) clearInterval(timer);
                window.removeEventListener('resize', resize);
            },
        };
    }

    /* ------------------------------------------------------------------
     * pageTransition(options)
     *   Mounts (or reuses) an overlay with a glitching text + matrix rain.
     *   Call returned .play(text, signature) just before navigation.
     * ------------------------------------------------------------------ */
    function pageTransition(options) {
        const opts = Object.assign({
            overlayId: 'uix-transition-overlay',
            duration: 1400,
            phrases: [
                'ROUTING REQUEST...',
                'SYNCHRONIZING...',
                'NAVIGATING...',
                'LOADING SECTOR...',
                'DECRYPTING PAYLOAD...',
            ],
        }, options || {});

        let overlay = document.getElementById(opts.overlayId);
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = opts.overlayId;
            overlay.className = 'uix-transition-overlay';
            overlay.innerHTML = ''
                + '<canvas class="uix-transition-canvas"></canvas>'
                + '<div class="uix-transition-flash"></div>'
                + '<div class="uix-transition-center">'
                + '  <div class="uix-transition-text"></div>'
                + '  <div class="uix-transition-sig"></div>'
                + '</div>';
            document.body.appendChild(overlay);
        }

        const canvas = overlay.querySelector('canvas');
        const textEl = overlay.querySelector('.uix-transition-text');
        const sigEl = overlay.querySelector('.uix-transition-sig');

        let activeRain = null;

        function play(text, signature) {
            if (reducedMotion()) {
                return Promise.resolve();
            }
            const phrase = text || opts.phrases[Math.floor(Math.random() * opts.phrases.length)];
            textEl.textContent = phrase;
            sigEl.textContent = signature || '';
            overlay.classList.add('uix-transition-active');
            if (activeRain) activeRain.stop();
            activeRain = matrixRain(canvas, { speed: 28 });
            return new Promise(function (resolve) {
                setTimeout(function () {
                    overlay.classList.remove('uix-transition-active');
                    if (activeRain) {
                        activeRain.stop();
                        activeRain = null;
                    }
                    resolve();
                }, opts.duration);
            });
        }

        return { play: play };
    }

    /* ------------------------------------------------------------------
     * typewriter(target, text, options) -> Promise
     *   Types text one character at a time into target element.
     * ------------------------------------------------------------------ */
    function typewriter(target, text, options) {
        const el = typeof target === 'string' ? document.querySelector(target) : target;
        if (!el) return Promise.resolve();
        const opts = Object.assign({ delay: 22, append: false }, options || {});
        if (!opts.append) el.textContent = '';
        if (reducedMotion()) {
            el.textContent += text;
            return Promise.resolve();
        }
        return new Promise(function (resolve) {
            let i = 0;
            (function tick() {
                if (i >= text.length) {
                    resolve();
                    return;
                }
                el.textContent += text.charAt(i++);
                setTimeout(tick, opts.delay);
            })();
        });
    }

    root.UIEffects = {
        matrixRain: matrixRain,
        pageTransition: pageTransition,
        typewriter: typewriter,
        reducedMotion: reducedMotion,
    };
})(window);
