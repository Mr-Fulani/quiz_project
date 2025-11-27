// Removed ES6 imports - using global GSAP variables instead
// import { gsap } from "https://cdn.skypack.dev/gsap";
// import { ScrambleTextPlugin } from "https://cdn.skypack.dev/gsap/ScrambleTextPlugin";
// import { MorphSVGPlugin } from "https://cdn.skypack.dev/gsap/MorphSVGPlugin";

// Wait for GSAP and plugins to be loaded
function initPasswordAnimation() {
    if (typeof gsap === 'undefined') {
        console.error('GSAP is not loaded');
        return;
    }

    if (typeof ScrambleTextPlugin !== 'undefined') {
        gsap.registerPlugin(ScrambleTextPlugin);
    }

    const BLINK_SPEED = 0.075;
    const TOGGLE_SPEED = 0.125;
    const REVEAL_SPEED = 0.05;

    let busy = false;
    const EYE = document.querySelector('.eye');
    const TOGGLE = document.querySelector('.password-toggle');
    const INPUT = document.querySelector('#password');
    const LID_UPPER = document.querySelector('.lid--upper');
    const LID_LOWER = document.querySelector('.lid--lower');

    let blinkTl;
    const BLINK = () => {
        if (!LID_UPPER || !LID_LOWER || !EYE) return;

        const delay = gsap.utils.random(2, 8);
        const duration = BLINK_SPEED;
        const repeat = Math.random() > 0.5 ? 3 : 1;

        blinkTl = gsap.timeline({
            delay,
            onComplete: () => BLINK(),
            repeat,
            yoyo: true
        })
        .to(LID_UPPER, {
            scaleY: 0.1,
            transformOrigin: "center bottom",
            duration
        })
        .to(EYE, {
            scaleY: 0.1,
            transformOrigin: "center",
            duration
        }, 0);
    };

    if (LID_UPPER && LID_LOWER && EYE) {
        BLINK();
    }

    const posMapper = gsap.utils.mapRange(-100, 100, 30, -30);
    let reset;

    const MOVE_EYE = ({ x, y }) => {
        if (!EYE) return;
        if (reset) reset.kill();
        reset = gsap.delayedCall(2, () => {
            gsap.to('.eye', {
                xPercent: 0,
                yPercent: 0,
                duration: 0.2
            });
        });
        const BOUNDS = EYE.getBoundingClientRect();
        gsap.set('.eye', {
            xPercent: gsap.utils.clamp(-30, 30, posMapper(BOUNDS.x - x)),
            yPercent: gsap.utils.clamp(-30, 30, posMapper(BOUNDS.y - y))
        });
    };

    window.addEventListener('pointermove', MOVE_EYE);

    function animatePasswordReveal(input, realValue, isRevealing) {
        return new Promise((resolve) => {
            if (isRevealing) {
                let currentIndex = 0;
                const chars = realValue.split('');
                const totalChars = chars.length;

                const revealNext = () => {
                    if (currentIndex < totalChars) {
                        const visiblePart = chars.slice(0, currentIndex + 1).join('');
                        const hiddenPart = '•'.repeat(totalChars - currentIndex - 1);
                        input.value = visiblePart + hiddenPart;
                        currentIndex++;
                        gsap.delayedCall(REVEAL_SPEED, revealNext);
                    } else {
                        input.value = realValue;
                        resolve();
                    }
                };

                revealNext();
            } else {
                let currentIndex = realValue.length - 1;
                const chars = realValue.split('');

                const hideNext = () => {
                    if (currentIndex >= 0) {
                        const visiblePart = chars.slice(0, currentIndex).join('');
                        const hiddenPart = '•'.repeat(realValue.length - currentIndex);
                        input.value = visiblePart + hiddenPart;
                        currentIndex--;
                        gsap.delayedCall(REVEAL_SPEED, hideNext);
                    } else {
                        input.value = '•'.repeat(realValue.length);
                        resolve();
                    }
                };

                hideNext();
            }
        });
    }

    if (TOGGLE && INPUT) {
        TOGGLE.addEventListener('click', async () => {
            if (busy) return;

            const isPasswordType = INPUT.type === 'password';
            const val = INPUT.value;
            busy = true;
            TOGGLE.setAttribute('aria-pressed', !isPasswordType);
            const duration = TOGGLE_SPEED;

            if (isPasswordType) {
                if (blinkTl) blinkTl.kill();
                gsap.timeline()
                    .to(LID_UPPER, {
                        scaleY: 1,
                        transformOrigin: "center bottom",
                        duration
                    })
                    .to(EYE, {
                        scaleY: 1,
                        transformOrigin: "center",
                        duration
                    }, 0);

                INPUT.type = 'text';
                await animatePasswordReveal(INPUT, val, true);
                busy = false;
                BLINK();
            } else {
                if (blinkTl) blinkTl.kill();
                gsap.timeline()
                    .to(LID_UPPER, {
                        scaleY: 0,
                        transformOrigin: "center bottom",
                        duration
                    })
                    .to(EYE, {
                        scaleY: 0,
                        transformOrigin: "center",
                        duration
                    }, 0);

                await animatePasswordReveal(INPUT, val, false);
                INPUT.type = 'password';
                INPUT.value = val;
                busy = false;
            }
        });
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPasswordAnimation);
} else {
    initPasswordAnimation();
}