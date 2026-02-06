/**
 * Animation System - Handles avatar animations, bobbing, working effects, particles
 * Manages the game loop animations and special effects
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    const ISO = window.CompanyView.ISO;

    // ==================== Easing Functions ====================
    const Easing = {
        linear: t => t,
        easeInOut: t => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t,
        easeOut: t => t * (2 - t),
        easeIn: t => t * t,
        bounce: t => {
            if (t < 1 / 2.75) return 7.5625 * t * t;
            if (t < 2 / 2.75) { t -= 1.5 / 2.75; return 7.5625 * t * t + 0.75; }
            if (t < 2.5 / 2.75) { t -= 2.25 / 2.75; return 7.5625 * t * t + 0.9375; }
            t -= 2.625 / 2.75;
            return 7.5625 * t * t + 0.984375;
        },
        elasticOut: t => {
            if (t === 0 || t === 1) return t;
            return Math.pow(2, -10 * t) * Math.sin((t - 0.1) * 5 * Math.PI) + 1;
        }
    };

    // ==================== Tween Manager ====================
    class TweenManager {
        constructor() {
            this.tweens = [];
        }

        /**
         * Create a tween
         * @param {object} target - Object to tween
         * @param {object} props - Properties to tween { x: 100, y: 200 }
         * @param {number} duration - Duration in ms
         * @param {string} easing - Easing function name
         * @param {function} onComplete - Callback on complete
         */
        add(target, props, duration, easing = 'easeInOut', onComplete = null) {
            const tween = {
                target,
                startProps: {},
                endProps: props,
                duration,
                elapsed: 0,
                easing: Easing[easing] || Easing.easeInOut,
                onComplete,
                done: false,
            };

            for (const key in props) {
                tween.startProps[key] = target[key];
            }

            this.tweens.push(tween);
            return tween;
        }

        update(dt) {
            for (let i = this.tweens.length - 1; i >= 0; i--) {
                const tween = this.tweens[i];
                tween.elapsed += dt;

                const t = Math.min(1, tween.elapsed / tween.duration);
                const easedT = tween.easing(t);

                for (const key in tween.endProps) {
                    tween.target[key] = tween.startProps[key] +
                        (tween.endProps[key] - tween.startProps[key]) * easedT;
                }

                if (t >= 1) {
                    tween.done = true;
                    if (tween.onComplete) tween.onComplete();
                    this.tweens.splice(i, 1);
                }
            }
        }

        clear() {
            this.tweens = [];
        }

        hasTweens(target) {
            return this.tweens.some(t => t.target === target);
        }

        cancelFor(target) {
            this.tweens = this.tweens.filter(t => t.target !== target);
        }
    }

    // ==================== Avatar Animator ====================
    class AvatarAnimator {
        constructor() {
            this.time = 0;
        }

        /**
         * Update avatar idle/working animations
         * @param {PIXI.Container} avatar - Avatar container
         * @param {number} dt - Delta time in ms
         */
        update(avatar, dt) {
            if (!avatar._avatarData) return;

            this.time += dt;
            const data = avatar._avatarData;
            data.animFrame += dt;

            const catBody = avatar.getChildByName('catBody');
            if (!catBody) return;

            switch (data.animState) {
                case 'idle':
                    this._animateIdle(avatar, catBody, data);
                    break;
                case 'working':
                    this._animateWorking(avatar, catBody, data);
                    break;
                case 'walking':
                    this._animateWalking(avatar, catBody, data);
                    break;
            }

            // Animate status bubble float
            const bubble = avatar.getChildByName('statusBubble');
            if (bubble && bubble.visible) {
                bubble.y = -48 + Math.sin(data.animFrame / 400) * 2;
            }
        }

        _animateIdle(avatar, catBody, data) {
            // Gentle breathing bob
            const breathe = Math.sin(data.animFrame / 800) * 0.8;
            catBody.y = breathe;

            // Occasional ear twitch (every ~3 seconds)
            const twitch = Math.sin(data.animFrame / 120) > 0.98;
            catBody.rotation = twitch ? 0.02 : 0;
        }

        _animateWorking(avatar, catBody, data) {
            // Faster typing bob
            const typeBob = Math.sin(data.animFrame / 200) * 0.5;
            catBody.y = typeBob;

            // Subtle body sway (concentrating)
            catBody.rotation = Math.sin(data.animFrame / 600) * 0.015;
        }

        _animateWalking(avatar, catBody, data) {
            // Walking bounce
            const walkBob = Math.abs(Math.sin(data.animFrame / 100)) * 2.5;
            catBody.y = -walkBob;

            // Walking sway
            catBody.rotation = Math.sin(data.animFrame / 100) * 0.04;
        }
    }

    // ==================== Particle System ====================
    class ParticleEmitter {
        constructor(container) {
            this.container = container;
            this.particles = [];
            this.pool = [];
        }

        _getParticle() {
            if (this.pool.length > 0) {
                return this.pool.pop();
            }
            const g = new PIXI.Graphics();
            return g;
        }

        _releaseParticle(p) {
            p.visible = false;
            this.pool.push(p);
        }

        /**
         * Emit typing sparkle particles near an avatar
         */
        emitTypingSparks(x, y) {
            for (let i = 0; i < 3; i++) {
                const p = this._getParticle();
                p.clear();
                const colors = [0x5B9BD5, 0x6BBF6B, 0xE5C95B, 0xE88BA8];
                const color = colors[Math.floor(Math.random() * colors.length)];
                p.beginFill(color, 0.8);
                p.drawCircle(0, 0, 1 + Math.random() * 1.5);
                p.endFill();

                p.x = x + (Math.random() - 0.5) * 16;
                p.y = y - 5 + Math.random() * 6;
                p.visible = true;
                p.alpha = 1;
                p._vx = (Math.random() - 0.5) * 0.5;
                p._vy = -0.5 - Math.random() * 0.8;
                p._life = 0;
                p._maxLife = 500 + Math.random() * 500;

                this.container.addChild(p);
                this.particles.push(p);
            }
        }

        /**
         * Emit success confetti
         */
        emitSuccess(x, y) {
            for (let i = 0; i < 12; i++) {
                const p = this._getParticle();
                p.clear();
                const colors = [0xFFD700, 0xFF6B8A, 0x5B9BD5, 0x6BBF6B, 0xE5C95B];
                const color = colors[Math.floor(Math.random() * colors.length)];
                p.beginFill(color);
                if (Math.random() > 0.5) {
                    p.drawRect(-1, -2, 2, 4);
                } else {
                    p.drawCircle(0, 0, 1.5);
                }
                p.endFill();

                p.x = x;
                p.y = y - 20;
                p.visible = true;
                p.alpha = 1;
                p.rotation = Math.random() * Math.PI * 2;
                p._vx = (Math.random() - 0.5) * 3;
                p._vy = -2 - Math.random() * 3;
                p._gravity = 0.05;
                p._rotSpeed = (Math.random() - 0.5) * 0.2;
                p._life = 0;
                p._maxLife = 800 + Math.random() * 400;

                this.container.addChild(p);
                this.particles.push(p);
            }
        }

        update(dt) {
            for (let i = this.particles.length - 1; i >= 0; i--) {
                const p = this.particles[i];
                p._life += dt;

                if (p._life >= p._maxLife) {
                    this.container.removeChild(p);
                    this._releaseParticle(p);
                    this.particles.splice(i, 1);
                    continue;
                }

                p.x += (p._vx || 0);
                p.y += (p._vy || 0);
                if (p._gravity) {
                    p._vy += p._gravity;
                }
                if (p._rotSpeed) {
                    p.rotation += p._rotSpeed;
                }

                const lifeRatio = p._life / p._maxLife;
                p.alpha = 1 - lifeRatio;
            }
        }
    }

    // ==================== Ambient Effects ====================
    class AmbientEffects {
        constructor(container) {
            this.container = container;
            this.time = 0;
            this.lights = [];
        }

        /**
         * Create subtle ambient lighting overlay
         */
        createLighting(width, height) {
            // Warm ambient light from window direction
            const light = new PIXI.Graphics();
            light.beginFill(0xFFF5DD, 0.04);
            light.drawRect(-width / 2, -height / 2, width * 0.6, height);
            light.endFill();

            // Diagonal light streak
            light.beginFill(0xFFFFFF, 0.02);
            light.moveTo(-width * 0.3, -height / 2);
            light.lineTo(-width * 0.1, -height / 2);
            light.lineTo(width * 0.2, height / 2);
            light.lineTo(0, height / 2);
            light.closePath();
            light.endFill();

            this.container.addChild(light);
            return light;
        }

        update(dt) {
            this.time += dt;
        }
    }

    // ==================== Export ====================
    window.CompanyView.Easing = Easing;
    window.CompanyView.TweenManager = TweenManager;
    window.CompanyView.AvatarAnimator = AvatarAnimator;
    window.CompanyView.ParticleEmitter = ParticleEmitter;
    window.CompanyView.AmbientEffects = AmbientEffects;

})();
