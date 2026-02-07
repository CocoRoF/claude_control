/**
 * 3D Character Renderer - Three.js 기반 GLB 캐릭터 렌더링
 * kenney_mini-characters GLB 모델을 isometric 뷰로 렌더링
 * 렌더링 결과를 PixiJS 텍스처로 변환하여 사용
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    // ==================== 설정 ====================
    const CONFIG = {
        // 렌더링 해상도
        renderWidth: 128,
        renderHeight: 128,

        // 카메라 설정 (isometric)
        cameraDistance: 3,
        cameraAngle: Math.PI / 6,  // 30도 (isometric)

        // 조명
        ambientIntensity: 0.6,
        directionalIntensity: 0.8,

        // 모델 경로
        modelBasePath: '/static/assets/kenney_mini-characters/Models/GLB format/',

        // 캐릭터 목록
        characters: [
            'character-female-a', 'character-female-b', 'character-female-c',
            'character-female-d', 'character-female-e', 'character-female-f',
            'character-male-a', 'character-male-b', 'character-male-c',
            'character-male-d', 'character-male-e', 'character-male-f',
        ],
    };

    // ==================== Character Renderer 클래스 ====================
    class CharacterRenderer3D {
        constructor() {
            this.renderer = null;
            this.scene = null;
            this.camera = null;
            this.models = new Map();        // 로드된 GLB 모델
            this.textures = new Map();      // 렌더링된 PixiJS 텍스처
            this.loader = null;
            this.ready = false;
        }

        /**
         * Three.js 초기화
         */
        async init() {
            if (typeof THREE === 'undefined') {
                console.error('[CharacterRenderer3D] Three.js not loaded');
                return false;
            }

            // WebGL 렌더러 생성 (오프스크린)
            this.renderer = new THREE.WebGLRenderer({
                alpha: true,
                antialias: true,
                preserveDrawingBuffer: true,
            });
            this.renderer.setSize(CONFIG.renderWidth, CONFIG.renderHeight);
            this.renderer.setPixelRatio(1);
            this.renderer.outputColorSpace = THREE.SRGBColorSpace;

            // 씬 생성
            this.scene = new THREE.Scene();

            // Isometric 카메라 설정 (OrthographicCamera)
            const aspect = CONFIG.renderWidth / CONFIG.renderHeight;
            const frustumSize = 2;
            this.camera = new THREE.OrthographicCamera(
                -frustumSize * aspect / 2,
                frustumSize * aspect / 2,
                frustumSize / 2,
                -frustumSize / 2,
                0.1,
                100
            );

            // Isometric 뷰 각도 설정
            this._setupIsometricCamera();

            // 조명 설정
            this._setupLighting();

            // GLTFLoader 설정
            this.loader = new THREE.GLTFLoader();

            console.log('[CharacterRenderer3D] Initialized');
            return true;
        }

        /**
         * Isometric 카메라 위치 설정
         */
        _setupIsometricCamera() {
            const distance = CONFIG.cameraDistance;
            const angle = CONFIG.cameraAngle;

            // Isometric 뷰: 45도 회전, 30도 기울기
            this.camera.position.set(
                distance * Math.cos(Math.PI / 4),
                distance * Math.sin(angle),
                distance * Math.sin(Math.PI / 4)
            );
            this.camera.lookAt(0, 0.5, 0);  // 캐릭터 중심
        }

        /**
         * 조명 설정
         */
        _setupLighting() {
            // 앰비언트 라이트
            const ambient = new THREE.AmbientLight(0xffffff, CONFIG.ambientIntensity);
            this.scene.add(ambient);

            // 디렉셔널 라이트 (태양광)
            const directional = new THREE.DirectionalLight(0xffffff, CONFIG.directionalIntensity);
            directional.position.set(5, 10, 7);
            directional.castShadow = false;
            this.scene.add(directional);

            // 보조 라이트 (그림자 완화)
            const fill = new THREE.DirectionalLight(0xffffff, 0.3);
            fill.position.set(-3, 5, -5);
            this.scene.add(fill);
        }

        /**
         * 모든 캐릭터 모델 로드
         */
        async loadAllCharacters(onProgress) {
            const total = CONFIG.characters.length;
            let loaded = 0;

            const loadPromises = CONFIG.characters.map(async (name, index) => {
                try {
                    const model = await this._loadModel(name);
                    this.models.set(index, model);

                    // 모델 렌더링하여 텍스처 생성
                    const texture = this._renderCharacterToTexture(model);
                    this.textures.set(index, texture);

                    loaded++;
                    if (onProgress) {
                        onProgress(loaded / total);
                    }
                } catch (error) {
                    console.warn(`[CharacterRenderer3D] Failed to load ${name}:`, error);
                    loaded++;
                    if (onProgress) {
                        onProgress(loaded / total);
                    }
                }
            });

            await Promise.all(loadPromises);
            this.ready = true;
            console.log(`[CharacterRenderer3D] Loaded ${this.models.size}/${total} characters`);
        }

        /**
         * GLB 모델 로드
         */
        _loadModel(name) {
            return new Promise((resolve, reject) => {
                const url = CONFIG.modelBasePath + name + '.glb';

                this.loader.load(
                    url,
                    (gltf) => {
                        const model = gltf.scene;

                        // 모델 중심 조정
                        const box = new THREE.Box3().setFromObject(model);
                        const center = box.getCenter(new THREE.Vector3());
                        model.position.sub(center);
                        model.position.y = -box.min.y;  // 바닥에 배치

                        // 스케일 조정
                        const size = box.getSize(new THREE.Vector3());
                        const maxDim = Math.max(size.x, size.y, size.z);
                        const scale = 1.5 / maxDim;
                        model.scale.setScalar(scale);

                        resolve(model);
                    },
                    undefined,
                    reject
                );
            });
        }

        /**
         * 캐릭터를 렌더링하여 PixiJS 텍스처로 변환
         */
        _renderCharacterToTexture(model) {
            // 씬에 모델 추가
            this.scene.add(model);

            // 렌더링
            this.renderer.render(this.scene, this.camera);

            // 씬에서 모델 제거
            this.scene.remove(model);

            // 캔버스에서 텍스처 생성
            const canvas = this.renderer.domElement;

            // PixiJS 텍스처 생성
            if (typeof PIXI !== 'undefined') {
                const texture = PIXI.Texture.from(canvas, {
                    scaleMode: PIXI.SCALE_MODES.LINEAR,
                });
                // 복사본 생성 (같은 캔버스 공유 방지)
                const copyCanvas = document.createElement('canvas');
                copyCanvas.width = CONFIG.renderWidth;
                copyCanvas.height = CONFIG.renderHeight;
                const ctx = copyCanvas.getContext('2d');
                ctx.drawImage(canvas, 0, 0);

                return PIXI.Texture.from(copyCanvas);
            }

            return null;
        }

        /**
         * 특정 캐릭터의 PixiJS 텍스처 가져오기
         * @param {number} variant - 캐릭터 인덱스 (0-11)
         */
        getCharacterTexture(variant) {
            return this.textures.get(variant) || null;
        }

        /**
         * 특정 방향으로 캐릭터 렌더링 (동적)
         * @param {number} variant - 캐릭터 인덱스
         * @param {string} direction - 'N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW'
         */
        renderCharacterWithDirection(variant, direction) {
            const model = this.models.get(variant);
            if (!model) return null;

            // 방향에 따른 모델 회전
            const rotations = {
                'S': 0,
                'SW': Math.PI / 4,
                'W': Math.PI / 2,
                'NW': Math.PI * 3 / 4,
                'N': Math.PI,
                'NE': Math.PI * 5 / 4,
                'E': Math.PI * 3 / 2,
                'SE': Math.PI * 7 / 4,
            };

            const rotation = rotations[direction] || 0;
            model.rotation.y = rotation;

            return this._renderCharacterToTexture(model);
        }

        /**
         * 리소스 정리
         */
        dispose() {
            // 텍스처 정리
            for (const texture of this.textures.values()) {
                if (texture && texture.destroy) {
                    texture.destroy(true);
                }
            }
            this.textures.clear();

            // 모델 정리
            for (const model of this.models.values()) {
                if (model && model.traverse) {
                    model.traverse((child) => {
                        if (child.geometry) child.geometry.dispose();
                        if (child.material) {
                            if (Array.isArray(child.material)) {
                                child.material.forEach(m => m.dispose());
                            } else {
                                child.material.dispose();
                            }
                        }
                    });
                }
            }
            this.models.clear();

            // 렌더러 정리
            if (this.renderer) {
                this.renderer.dispose();
            }

            this.ready = false;
        }
    }

    // ==================== 싱글톤 인스턴스 ====================
    const characterRenderer = new CharacterRenderer3D();

    // Export
    window.CompanyView.CharacterRenderer3D = characterRenderer;
    window.CompanyView.CHARACTER_3D_CONFIG = CONFIG;

})();
