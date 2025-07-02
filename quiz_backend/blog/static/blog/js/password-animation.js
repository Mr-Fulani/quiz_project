// Removed ES6 imports - using global GSAP variables instead
// import { gsap } from "https://cdn.skypack.dev/gsap";
// import { ScrambleTextPlugin } from "https://cdn.skypack.dev/gsap/ScrambleTextPlugin";
// import { MorphSVGPlugin } from "https://cdn.skypack.dev/gsap/MorphSVGPlugin";

// Wait for GSAP and plugins to be loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if GSAP is available
    if (typeof gsap === 'undefined') {
        console.error('GSAP is not loaded');
        return;
    }

    // Register plugins if they exist
    if (typeof ScrambleTextPlugin !== 'undefined') {
        gsap.registerPlugin(ScrambleTextPlugin);
    }

    const BLINK_SPEED = 0.075;
    const TOGGLE_SPEED = 0.125;
    const REVEAL_SPEED = 0.05; // Speed of character reveal animation

    let busy = false;

    const EYE = document.querySelector('.eye');
    const TOGGLE = document.querySelector('.password-toggle');
    const INPUT = document.querySelector('#password');
    const PROXY = document.createElement('div');
    const LID_UPPER = document.querySelector('.lid--upper');
    const LID_LOWER = document.querySelector('.lid--lower');

    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789`~,.<>?/;":][}{+_)(*&^%$#@!±=-§';

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

    // Only start blinking if elements exist
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

    // Simple character reveal animation
    function animatePasswordReveal(input, realValue, isRevealing) {
        return new Promise((resolve) => {
            if (isRevealing) {
                // Show real password characters one by one
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
                // Hide password characters one by one
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
                // Show password - open eye
                if (blinkTl) blinkTl.kill();

                // Animate eye opening
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

                // Change input type and animate reveal
                INPUT.type = 'text';
                await animatePasswordReveal(INPUT, val, true);
                
                busy = false;
                BLINK();
            } else {
                // Hide password - close eye
                if (blinkTl) blinkTl.kill();

                // Animate eye closing
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

                // Animate hiding and change input type
                await animatePasswordReveal(INPUT, val, false);
                INPUT.type = 'password';
                INPUT.value = val; // Restore original value
                
                busy = false;
            }
        });
    }
});