/**
 * 3D Character Animator - Three.js 기반 프로그래매틱 애니메이션
 * GLB 모델을 실시간으로 애니메이션하고 렌더링
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    const DEBUG = true;

    function debugLog(...args) {
        if (DEBUG) {
            console.log('[CharacterAnimator3D DEBUG]', ...args);
        }
    }

    // ==================== 애니메이션 설정 ====================
    const ANIM_CONFIG = {
        // 렌더링 해상도
        renderWidth: 96,
        renderHeight: 96,

        // 카메라 설정 (isometric)
        cameraDistance: 2.5,
        frustumSize: 1.8,

        // 조명
        ambientIntensity: 0.7,
        directionalIntensity: 0.6,

        // 모델 경로
        modelBasePath: '/static/assets/kenney_mini-characters/Models/GLB format/',

        // 캐릭터 목록
        characters: [
            'character-female-a', 'character-female-b', 'character-female-c',
            'character-female-d', 'character-female-e', 'character-female-f',
            'character-male-a', 'character-male-b', 'character-male-c',
            'character-male-d', 'character-male-e', 'character-male-f',
        ],

        // 애니메이션 속도 (라디안/초)
        animSpeed: {
            idle: 2,
            walk: 10,
            run: 14,
            sit: 1.5,
            thinking: 2.5,
            stretch: 2,
            wave: 8,
            dance: 8,
        },

        // 본 애니메이션 설정 (라디안)
        boneAnim: {
            idle: {
                torso: { rotX: 0.05, rotZ: 0.02 },
                head: { rotX: 0.05, rotY: 0.08 },
                armLeft: { rotX: 0.1, rotZ: 0.8 },  // 팔 내리기
                armRight: { rotX: 0.1, rotZ: -0.8, phaseOffset: Math.PI },  // 팔 내리기
                legLeft: { rotX: 0.02 },
                legRight: { rotX: 0.02, phaseOffset: Math.PI },
            },
            walk: {
                torso: { rotX: 0.08, rotZ: 0.1 },
                head: { rotX: 0.05 },
                armLeft: { rotX: 0.8, rotZ: 0.5, phaseOffset: 0 },  // 큰 스윙 + 팔 내리기
                armRight: { rotX: 0.8, rotZ: -0.5, phaseOffset: Math.PI },
                legLeft: { rotX: 0.7, phaseOffset: Math.PI },  // 다리 크게
                legRight: { rotX: 0.7, phaseOffset: 0 },
            },
            run: {
                torso: { rotX: 0.15, rotZ: 0.15 },
                head: { rotX: 0.08 },
                armLeft: { rotX: 1.2, rotZ: 0.4, phaseOffset: 0 },
                armRight: { rotX: 1.2, rotZ: -0.4, phaseOffset: Math.PI },
                legLeft: { rotX: 1.0, phaseOffset: Math.PI },
                legRight: { rotX: 1.0, phaseOffset: 0 },
            },
            sit: {
                torso: { rotX: 0.15 },
                head: { rotX: 0.05, rotY: 0.08 },
                armLeft: { rotX: 0.3, rotZ: 0.4 },
                armRight: { rotX: 0.3, rotZ: -0.4 },
                legLeft: { rotX: -1.2 },  // 다리 구부리기
                legRight: { rotX: -1.2 },
            },
            thinking: {
                torso: { rotX: 0.1 },
                head: { rotX: 0.1, rotY: 0.2 },
                armLeft: { rotX: 0.3 },
                armRight: { rotX: 1.2, rotZ: 0.3 },  // 손을 턱에
                legLeft: { rotX: 0 },
                legRight: { rotX: 0 },
            },
            stretch: {
                torso: { rotX: -0.2 },
                head: { rotX: -0.2 },
                armLeft: { rotX: -2.5, rotZ: 0.3 },  // 팔 위로
                armRight: { rotX: -2.5, rotZ: -0.3 },
                legLeft: { rotX: 0 },
                legRight: { rotX: 0 },
            },
            wave: {
                torso: { rotZ: 0.05 },
                head: { rotX: 0.1 },
                armLeft: { rotX: 0.2 },
                armRight: { rotX: -2.0, rotZ: -0.4, animRotZ: 0.5 },  // 흔드는 팔
                legLeft: { rotX: 0 },
                legRight: { rotX: 0 },
            },
            dance: {
                torso: { rotX: 0.1, rotZ: 0.15, animY: 0.05 },
                head: { rotY: 0.2 },
                armLeft: { rotX: 0.4, rotZ: 0.8, phaseOffset: 0 },
                armRight: { rotX: 0.4, rotZ: -0.8, phaseOffset: Math.PI },
                legLeft: { rotX: 0.3, phaseOffset: Math.PI },
                legRight: { rotX: 0.3, phaseOffset: 0 },
            },
        },

        // 방향별 모델 회전 (Y축, 라디안)
        directionRotation: {
            'S': 0,
            'SW': Math.PI / 4,
            'W': Math.PI / 2,
            'NW': Math.PI * 3 / 4,
            'N': Math.PI,
            'NE': -Math.PI * 3 / 4,
            'E': -Math.PI / 2,
            'SE': -Math.PI / 4,
        },

        // FPS 제한
        targetFPS: 24,
    };

    // ==================== Character Animator 클래스 ====================
    class CharacterAnimator3D {
        constructor() {
            this.renderer = null;
            this.scene = null;
            this.camera = null;
            this.loader = null;

            // 캐릭터별 데이터
            this.characterData = new Map();  // sessionId -> { model, canvas, animState, phase }

            // 공유 모델 템플릿
            this.modelTemplates = new Map();  // variant -> gltf.scene (원본)

            this.ready = false;
            this._lastFrameTime = 0;
            this._frameInterval = 1000 / ANIM_CONFIG.targetFPS;
        }

        /**
         * Three.js 초기화
         */
        async init() {
            if (typeof THREE === 'undefined') {
                console.error('[CharacterAnimator3D] Three.js not loaded');
                return false;
            }

            // 오프스크린 렌더러 (캐릭터당 하나씩 렌더링)
            this.renderer = new THREE.WebGLRenderer({
                alpha: true,
                antialias: true,
                preserveDrawingBuffer: true,
            });
            this.renderer.setSize(ANIM_CONFIG.renderWidth, ANIM_CONFIG.renderHeight);
            this.renderer.setPixelRatio(1);
            this.renderer.setClearColor(0x000000, 0);

            // 씬 생성
            this.scene = new THREE.Scene();

            // Isometric 카메라
            const aspect = ANIM_CONFIG.renderWidth / ANIM_CONFIG.renderHeight;
            const size = ANIM_CONFIG.frustumSize;
            this.camera = new THREE.OrthographicCamera(
                -size * aspect / 2, size * aspect / 2,
                size / 2, -size / 2,
                0.1, 100
            );

            // Isometric 뷰 설정
            this._setupIsometricCamera();

            // 조명
            this._setupLighting();

            // GLTF 로더
            this.loader = new THREE.GLTFLoader();

            console.log('[CharacterAnimator3D] Initialized');
            return true;
        }

        _setupIsometricCamera() {
            const dist = ANIM_CONFIG.cameraDistance;
            // Isometric 뷰: 45도 회전, 35도 기울기
            const angleY = Math.PI / 4;
            const angleX = Math.PI / 6;

            this.camera.position.set(
                dist * Math.sin(angleY) * Math.cos(angleX),
                dist * Math.sin(angleX),
                dist * Math.cos(angleY) * Math.cos(angleX)
            );
            this.camera.lookAt(0, 0.3, 0);
        }

        _setupLighting() {
            const ambient = new THREE.AmbientLight(0xffffff, ANIM_CONFIG.ambientIntensity);
            this.scene.add(ambient);

            const directional = new THREE.DirectionalLight(0xffffff, ANIM_CONFIG.directionalIntensity);
            directional.position.set(3, 8, 5);
            this.scene.add(directional);

            const fill = new THREE.DirectionalLight(0xffffff, 0.25);
            fill.position.set(-2, 4, -3);
            this.scene.add(fill);
        }

        /**
         * 모든 캐릭터 템플릿 로드
         */
        async loadAllTemplates(onProgress) {
            const total = ANIM_CONFIG.characters.length;
            let loaded = 0;

            for (let i = 0; i < total; i++) {
                const name = ANIM_CONFIG.characters[i];
                try {
                    const gltf = await this._loadGLTF(name);
                    this.modelTemplates.set(i, gltf);
                    debugLog(`Loaded template ${i}: ${name}`);

                    // 첫 번째 모델의 구조 출력
                    if (i === 0 && DEBUG) {
                        console.log('[CharacterAnimator3D] Model structure:');
                        gltf.scene.traverse((child) => {
                            console.log(`  ${child.type}: ${child.name}`,
                                child.isMesh ? '(Mesh)' : '',
                                child.isSkinnedMesh ? '(SkinnedMesh)' : '');
                        });
                    }
                } catch (error) {
                    console.warn(`[CharacterAnimator3D] Failed to load ${name}:`, error);
                }
                loaded++;
                if (onProgress) onProgress(loaded / total);
            }

            this.ready = true;
            console.log(`[CharacterAnimator3D] Loaded ${this.modelTemplates.size}/${total} templates`);
        }

        _loadGLTF(name) {
            return new Promise((resolve, reject) => {
                const url = ANIM_CONFIG.modelBasePath + name + '.glb';
                this.loader.load(url, resolve, undefined, reject);
            });
        }

        /**
         * 캐릭터 인스턴스 생성
         */
        createCharacter(sessionId, variant) {
            if (!this.ready) {
                console.warn('[CharacterAnimator3D] Not ready');
                return null;
            }

            const template = this.modelTemplates.get(variant % this.modelTemplates.size);
            if (!template) {
                console.warn('[CharacterAnimator3D] Template not found:', variant);
                return null;
            }

            // 모델 복제
            const model = THREE.SkeletonUtils ?
                THREE.SkeletonUtils.clone(template.scene) :
                template.scene.clone();

            // 본 캐싱
            const bones = this._cacheBones(model);

            // 모델 중심/스케일 조정
            const box = new THREE.Box3().setFromObject(model);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());

            model.position.set(-center.x, -box.min.y, -center.z);

            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 1.2 / maxDim;
            model.scale.setScalar(scale);

            // 캔버스 생성 (개별 렌더링용)
            const canvas = document.createElement('canvas');
            canvas.width = ANIM_CONFIG.renderWidth;
            canvas.height = ANIM_CONFIG.renderHeight;

            const characterData = {
                model,
                canvas,
                variant,
                bones,  // 캐싱된 본 참조
                animState: 'idle',
                direction: 'SW',
                targetDirection: 'SW',
                phase: Math.random() * Math.PI * 2,
                basePosition: model.position.clone(),
                baseRotation: model.rotation.clone(),
                baseScale: model.scale.clone(),
                texture: null,  // PixiJS 텍스처
                dirty: true,    // 렌더링 필요 여부
            };

            this.characterData.set(sessionId, characterData);
            debugLog(`Created character: ${sessionId.substring(0, 8)}, variant: ${variant}`);

            // 초기 렌더링
            this._renderCharacter(sessionId);

            return characterData;
        }

        /**
         * 캐릭터 제거
         */
        removeCharacter(sessionId) {
            const data = this.characterData.get(sessionId);
            if (data) {
                if (data.texture && data.texture.destroy) {
                    data.texture.destroy(true);
                }
                this.characterData.delete(sessionId);
                debugLog(`Removed character: ${sessionId.substring(0, 8)}`);
            }
        }

        /**
         * 애니메이션 상태 설정
         */
        setAnimState(sessionId, state) {
            const data = this.characterData.get(sessionId);
            if (data && data.animState !== state) {
                data.animState = state;
                data.dirty = true;
                debugLog(`${sessionId.substring(0, 8)} animState: ${state}`);
            }
        }

        /**
         * 방향 설정
         */
        setDirection(sessionId, direction) {
            const data = this.characterData.get(sessionId);
            if (data) {
                data.targetDirection = direction;
                data.dirty = true;
            }
        }

        /**
         * 본 캐싱 - 모델에서 본 참조 저장
         */
        _cacheBones(model) {
            const bones = {
                root: null,
                torso: null,
                head: null,
                armLeft: null,
                armRight: null,
                legLeft: null,
                legRight: null,
                initialRotations: {},
            };

            model.traverse((child) => {
                if (child.isBone) {
                    const name = child.name.toLowerCase();
                    debugLog(`Found bone: ${child.name}`);
                    if (name === 'root') {
                        bones.root = child;
                        bones.initialRotations.root = child.rotation.clone();
                    } else if (name === 'torso') {
                        bones.torso = child;
                        bones.initialRotations.torso = child.rotation.clone();
                    } else if (name === 'head') {
                        bones.head = child;
                        bones.initialRotations.head = child.rotation.clone();
                    } else if (name === 'arm-left') {
                        bones.armLeft = child;
                        bones.initialRotations.armLeft = child.rotation.clone();
                    } else if (name === 'arm-right') {
                        bones.armRight = child;
                        bones.initialRotations.armRight = child.rotation.clone();
                    } else if (name === 'leg-left') {
                        bones.legLeft = child;
                        bones.initialRotations.legLeft = child.rotation.clone();
                    } else if (name === 'leg-right') {
                        bones.legRight = child;
                        bones.initialRotations.legRight = child.rotation.clone();
                    }
                }
            });

            const foundBones = Object.keys(bones).filter(k => k !== 'initialRotations' && bones[k]);
            debugLog('Cached bones:', foundBones.join(', '));
            if (foundBones.length === 0) {
                console.warn('[CharacterAnimator3D] No bones found in model!');
            }
            return bones;
        }

        /**
         * 프레임 업데이트 (모든 캐릭터)
         */
        update(deltaTime) {
            if (!this.ready) return;

            for (const [sessionId, data] of this.characterData) {
                this._updateCharacterAnimation(data, deltaTime);
            }
        }

        /**
         * 개별 캐릭터 애니메이션 업데이트 - 본 기반
         */
        _updateCharacterAnimation(data, deltaTime) {
            const { animState, model, bones, basePosition, baseRotation } = data;

            if (!bones) {
                console.warn('[CharacterAnimator3D] No bones in character data');
                return;
            }

            const dt = deltaTime * 0.001;  // ms -> seconds

            // 애니메이션 속도
            const speed = ANIM_CONFIG.animSpeed[animState] || ANIM_CONFIG.animSpeed.idle;
            data.phase += dt * speed;
            const t = data.phase;

            // 방향 부드럽게 전환
            const targetRotY = ANIM_CONFIG.directionRotation[data.targetDirection] || 0;
            const currentRotY = model.rotation.y;
            let rotDiff = targetRotY - currentRotY;
            // 최단 경로로 회전
            while (rotDiff > Math.PI) rotDiff -= Math.PI * 2;
            while (rotDiff < -Math.PI) rotDiff += Math.PI * 2;
            model.rotation.y = currentRotY + rotDiff * Math.min(dt * 8, 1);
            data.direction = data.targetDirection;

            // 본 애니메이션 설정 가져오기
            const boneAnim = ANIM_CONFIG.boneAnim[animState] || ANIM_CONFIG.boneAnim.idle;
            const initRot = bones.initialRotations || {};

            // 디폴트 Euler 생성
            const defaultEuler = { x: 0, y: 0, z: 0 };

            // 각 본 애니메이션 - 직접 회전값 설정
            if (bones.torso && boneAnim.torso) {
                const cfg = boneAnim.torso;
                const init = initRot.torso || defaultEuler;
                bones.torso.rotation.x = init.x + (cfg.rotX || 0) * Math.sin(t);
                bones.torso.rotation.z = init.z + (cfg.rotZ || 0) * Math.sin(t * 0.8);
                if (cfg.animY) {
                    bones.torso.position.y = cfg.animY * Math.abs(Math.sin(t * 2));
                }
            }

            if (bones.head && boneAnim.head) {
                const cfg = boneAnim.head;
                const init = initRot.head || defaultEuler;
                bones.head.rotation.x = init.x + (cfg.rotX || 0) * Math.sin(t * 1.2);
                bones.head.rotation.y = init.y + (cfg.rotY || 0) * Math.sin(t * 0.7);
            }

            // 팔 애니메이션 - 강화된 동작
            if (bones.armLeft && boneAnim.armLeft) {
                const cfg = boneAnim.armLeft;
                const init = initRot.armLeft || defaultEuler;
                const phase = t + (cfg.phaseOffset || 0);
                // X축 회전 (앞뒤 스윙)
                bones.armLeft.rotation.x = init.x + (cfg.rotX || 0) * Math.sin(phase);
                // Z축 회전 (팔 내리기 + 애니메이션)
                const baseZ = init.z + (cfg.rotZ || 0);
                const animZ = (cfg.animRotZ || 0) * Math.sin(phase * 2);
                bones.armLeft.rotation.z = baseZ + animZ;
            }

            if (bones.armRight && boneAnim.armRight) {
                const cfg = boneAnim.armRight;
                const init = initRot.armRight || defaultEuler;
                const phase = t + (cfg.phaseOffset || 0);
                // X축 회전 (앞뒤 스윙)
                bones.armRight.rotation.x = init.x + (cfg.rotX || 0) * Math.sin(phase);
                // Z축 회전 (팔 내리기 + 애니메이션)
                const baseZ = init.z + (cfg.rotZ || 0);
                const animZ = (cfg.animRotZ || 0) * Math.sin(phase * 2);
                bones.armRight.rotation.z = baseZ + animZ;
            }

            // 다리 애니메이션
            if (bones.legLeft && boneAnim.legLeft) {
                const cfg = boneAnim.legLeft;
                const init = initRot.legLeft || defaultEuler;
                const phase = t + (cfg.phaseOffset || 0);
                bones.legLeft.rotation.x = init.x + (cfg.rotX || 0) * Math.sin(phase);
            }

            if (bones.legRight && boneAnim.legRight) {
                const cfg = boneAnim.legRight;
                const init = initRot.legRight || defaultEuler;
                const phase = t + (cfg.phaseOffset || 0);
                bones.legRight.rotation.x = init.x + (cfg.rotX || 0) * Math.sin(phase);
            }

            data.dirty = true;
        }

        /**
         * 캐릭터 렌더링 (개별)
         */
        _renderCharacter(sessionId) {
            const data = this.characterData.get(sessionId);
            if (!data || !data.dirty) return null;

            // 씬에 모델 추가
            this.scene.add(data.model);

            // 렌더링
            this.renderer.render(this.scene, this.camera);

            // 씬에서 제거
            this.scene.remove(data.model);

            // 캔버스에 복사
            const ctx = data.canvas.getContext('2d');
            ctx.clearRect(0, 0, data.canvas.width, data.canvas.height);
            ctx.drawImage(this.renderer.domElement, 0, 0);

            data.dirty = false;

            return data.canvas;
        }

        /**
         * PixiJS 텍스처로 렌더링하고 반환
         */
        renderToTexture(sessionId) {
            const canvas = this._renderCharacter(sessionId);
            if (!canvas) return null;

            const data = this.characterData.get(sessionId);
            if (!data) return null;

            // 기존 텍스처 업데이트 또는 새로 생성
            if (data.texture) {
                data.texture.update();
            } else {
                data.texture = PIXI.Texture.from(data.canvas);
            }

            return data.texture;
        }

        /**
         * 모든 캐릭터 렌더링
         */
        renderAll() {
            for (const sessionId of this.characterData.keys()) {
                this.renderToTexture(sessionId);
            }
        }

        /**
         * 캐릭터 텍스처 가져오기
         */
        getTexture(sessionId) {
            const data = this.characterData.get(sessionId);
            if (!data) return null;

            if (!data.texture) {
                this.renderToTexture(sessionId);
            }

            return data.texture;
        }

        /**
         * 정리
         */
        dispose() {
            for (const [sessionId, data] of this.characterData) {
                if (data.texture && data.texture.destroy) {
                    data.texture.destroy(true);
                }
            }
            this.characterData.clear();
            this.modelTemplates.clear();

            if (this.renderer) {
                this.renderer.dispose();
            }

            this.ready = false;
        }
    }

    // ==================== 싱글톤 ====================
    const animator = new CharacterAnimator3D();

    window.CompanyView.CharacterAnimator3D = animator;
    window.CompanyView.ANIM_3D_CONFIG = ANIM_CONFIG;

})();
