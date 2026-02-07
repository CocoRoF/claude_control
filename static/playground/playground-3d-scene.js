/**
 * City 3D Scene Manager
 * Full 3D city rendering with buildings and roads
 */
(function() {
    'use strict';

    window.Playground = window.Playground || {};

    const DEBUG = true;
    function debugLog(...args) {
        if (DEBUG) console.log('[City3DScene]', ...args);
    }

    // ==================== Scene Configuration ====================
    const SCENE_CONFIG = {
        backgroundColor: 0x87CEEB,  // Sky blue
        groundColor: 0x3a5f3a,      // Dark green grass
        ambientLightIntensity: 0.7,
        directionalLightIntensity: 0.9,
        cameraFov: 45,
        cameraNear: 0.1,
        cameraFar: 200
    };

    // ==================== PlaygroundScene3D Class ====================
    class PlaygroundScene3D {
        constructor() {
            // Core Three.js components
            this.renderer = null;
            this.scene = null;
            this.camera = null;

            // Systems
            this.assetLoader = null;
            this.avatarSystem = null;

            // Scene elements
            this.groundTiles = [];
            this.roads = [];
            this.buildings = [];
            this.natureItems = [];

            // State
            this.running = false;
            this.container = null;
            this.animationFrameId = null;
            this.lastFrameTime = 0;

            // Camera control state
            this.cameraAngle = Math.PI / 4;      // 45 degrees horizontal
            this.cameraPitch = Math.PI / 5;      // ~36 degrees vertical
            this.cameraDistance = 32;            // Increased for larger city
            this.cameraTarget = new THREE.Vector3(8, 0, 8);  // Center of 17x17 city

            // Pan drag (left mouse)
            this.isPanning = false;
            this._panStart = { x: 0, y: 0 };
            this._targetStart = new THREE.Vector3();

            // Rotation drag (right mouse)
            this.isRotating = false;
            this._rotateStart = { x: 0, y: 0 };
            this._angleStart = 0;
            this._pitchStart = 0;

            // For app.js compatibility
            this.isInitialized = false;

            debugLog('PlaygroundScene3D instance created');
        }

        static getInstance() {
            return window.Playground.Scene;
        }

        async mount(container) {
            debugLog('Mounting City 3D scene...');

            this.container = container;
            const width = container.clientWidth;
            const height = container.clientHeight;

            // Create WebGL Renderer
            this.renderer = new THREE.WebGLRenderer({
                antialias: true,
                alpha: false
            });
            this.renderer.setSize(width, height);
            this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            this.renderer.shadowMap.enabled = true;
            this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            container.appendChild(this.renderer.domElement);

            // Create Scene
            this.scene = new THREE.Scene();
            this.scene.background = new THREE.Color(SCENE_CONFIG.backgroundColor);

            // Add fog for atmosphere
            this.scene.fog = new THREE.Fog(SCENE_CONFIG.backgroundColor, 30, 80);

            // Setup camera
            this._setupCamera(width, height);

            // Setup lighting
            this._setupLighting();

            // Create ground plane
            this._createGround();

            // Initialize asset loader
            this.assetLoader = new window.Playground.Asset3DLoader();
            this.assetLoader.init();

            // Load essential assets
            await this.assetLoader.loadEssential((loaded, total) => {
                debugLog(`Loading: ${loaded}/${total}`);
            });
            debugLog('Assets loaded');

            // Build the city
            this._buildCity();

            // Initialize avatar system
            await this._initAvatarSystem();

            // Setup input handlers
            this._setupInputHandlers();

            // Add resize handler
            this._resizeHandler = () => this._onResize();
            window.addEventListener('resize', this._resizeHandler);

            // Prevent context menu on right-click
            this.renderer.domElement.addEventListener('contextmenu', (e) => e.preventDefault());

            // Start render loop
            this.running = true;
            this.lastFrameTime = performance.now();
            this._gameLoop(this.lastFrameTime);

            this.isInitialized = true;
            debugLog('City scene mounted and running');
        }

        _setupCamera(width, height) {
            const aspect = width / height;

            this.camera = new THREE.PerspectiveCamera(
                SCENE_CONFIG.cameraFov,
                aspect,
                SCENE_CONFIG.cameraNear,
                SCENE_CONFIG.cameraFar
            );

            this._updateCameraPosition();
            debugLog('Camera setup complete');
        }

        _updateCameraPosition() {
            const x = this.cameraTarget.x + this.cameraDistance * Math.cos(this.cameraPitch) * Math.sin(this.cameraAngle);
            const y = this.cameraTarget.y + this.cameraDistance * Math.sin(this.cameraPitch);
            const z = this.cameraTarget.z + this.cameraDistance * Math.cos(this.cameraPitch) * Math.cos(this.cameraAngle);

            this.camera.position.set(x, y, z);
            this.camera.lookAt(this.cameraTarget);
        }

        _setupLighting() {
            // Ambient light
            const ambient = new THREE.AmbientLight(0xffffff, SCENE_CONFIG.ambientLightIntensity);
            this.scene.add(ambient);

            // Main directional light (sun)
            const sun = new THREE.DirectionalLight(0xfffaf0, SCENE_CONFIG.directionalLightIntensity);
            sun.position.set(15, 25, 15);
            sun.castShadow = true;

            // Shadow settings
            sun.shadow.mapSize.width = 4096;
            sun.shadow.mapSize.height = 4096;
            sun.shadow.camera.near = 1;
            sun.shadow.camera.far = 60;
            sun.shadow.camera.left = -20;
            sun.shadow.camera.right = 20;
            sun.shadow.camera.top = 20;
            sun.shadow.camera.bottom = -20;
            sun.shadow.bias = -0.0005;

            this.scene.add(sun);

            // Hemisphere light for sky/ground color
            const hemi = new THREE.HemisphereLight(0x87CEEB, 0x3a5f3a, 0.3);
            this.scene.add(hemi);

            debugLog('Lighting setup complete');
        }

        _createGround() {
            // Large ground plane
            const groundGeometry = new THREE.PlaneGeometry(50, 50);
            const groundMaterial = new THREE.MeshLambertMaterial({
                color: SCENE_CONFIG.groundColor
            });
            const ground = new THREE.Mesh(groundGeometry, groundMaterial);
            ground.rotation.x = -Math.PI / 2;
            ground.position.set(4.5, -0.01, 4.5);  // Slightly below zero to avoid z-fighting
            ground.receiveShadow = true;
            this.scene.add(ground);
        }

        _buildCity() {
            const Layout = window.Playground.Layout3D;
            if (!Layout) {
                console.error('Layout3D not available');
                return;
            }

            debugLog('Building city...');

            // Build ground tiles (under buildings/parks)
            this._buildGroundTiles(Layout);

            // Build roads
            this._buildRoads(Layout);

            // Build buildings
            this._buildBuildings(Layout);

            // Build nature
            this._buildNature(Layout);

            debugLog('City build complete');
        }

        _buildGroundTiles(Layout) {
            const tiles = Layout.getGroundTiles();

            for (const tile of tiles) {
                const model = this.assetLoader.getModel(tile.type, tile.name);
                if (model) {
                    model.position.set(tile.gx, 0, tile.gz);
                    model.receiveShadow = true;
                    this.scene.add(model);
                    this.groundTiles.push(model);
                }
            }

            debugLog(`Created ${this.groundTiles.length} ground tiles`);
        }

        _buildRoads(Layout) {
            const roads = Layout.getRoads();

            for (const road of roads) {
                const model = this.assetLoader.getModel(road.type, road.name);
                if (model) {
                    model.position.set(road.gx, 0, road.gz);
                    model.rotation.y = road.rotation || 0;
                    model.receiveShadow = true;
                    this.scene.add(model);
                    this.roads.push(model);
                }
            }

            debugLog(`Created ${this.roads.length} road segments`);
        }

        _buildBuildings(Layout) {
            const buildings = Layout.BUILDINGS;

            for (let i = 0; i < buildings.length; i++) {
                const building = buildings[i];
                const model = this.assetLoader.getModel(building.type, building.name);
                if (model) {
                    model.position.set(building.gx, 0, building.gz);
                    model.rotation.y = building.rotation || 0;
                    model.castShadow = true;
                    model.receiveShadow = true;
                    this.scene.add(model);
                    this.buildings.push(model);
                }
            }

            debugLog(`Created ${this.buildings.length} buildings`);
        }

        _buildNature(Layout) {
            const nature = Layout.NATURE;

            for (const item of nature) {
                const model = this.assetLoader.getModel(item.type, item.name);
                if (model) {
                    model.position.set(item.gx, 0, item.gz);
                    model.rotation.y = item.rotation || 0;
                    model.castShadow = true;
                    model.receiveShadow = true;
                    this.scene.add(model);
                    this.natureItems.push(model);
                }
            }

            debugLog(`Created ${this.natureItems.length} nature items`);
        }

        _setupInputHandlers() {
            const canvas = this.renderer.domElement;

            // Mouse down
            this._onPointerDown = (e) => {
                if (e.button === 0) {
                    // Left mouse - pan
                    this.isPanning = true;
                    this._panStart = { x: e.clientX, y: e.clientY };
                    this._targetStart.copy(this.cameraTarget);
                    canvas.style.cursor = 'move';
                } else if (e.button === 2) {
                    // Right mouse - rotate
                    this.isRotating = true;
                    this._rotateStart = { x: e.clientX, y: e.clientY };
                    this._angleStart = this.cameraAngle;
                    this._pitchStart = this.cameraPitch;
                    canvas.style.cursor = 'grabbing';
                }
            };

            // Mouse move
            this._onPointerMove = (e) => {
                if (this.isRotating) {
                    const dx = e.clientX - this._rotateStart.x;
                    const dy = e.clientY - this._rotateStart.y;

                    this.cameraAngle = this._angleStart - dx * 0.005;
                    this.cameraPitch = Math.max(0.1, Math.min(Math.PI / 2.2, this._pitchStart + dy * 0.005));

                    this._updateCameraPosition();
                }

                if (this.isPanning) {
                    const dx = e.clientX - this._panStart.x;
                    const dy = e.clientY - this._panStart.y;

                    // Calculate pan direction based on camera angle
                    const panSpeed = 0.02 * (this.cameraDistance / 15);

                    // Right vector (perpendicular to camera direction in XZ plane)
                    const rightX = Math.cos(this.cameraAngle);
                    const rightZ = -Math.sin(this.cameraAngle);

                    // Forward vector (in XZ plane)
                    const forwardX = Math.sin(this.cameraAngle);
                    const forwardZ = Math.cos(this.cameraAngle);

                    this.cameraTarget.x = this._targetStart.x - dx * rightX * panSpeed - dy * forwardX * panSpeed;
                    this.cameraTarget.z = this._targetStart.z - dx * rightZ * panSpeed - dy * forwardZ * panSpeed;

                    this._updateCameraPosition();
                }
            };

            // Mouse up
            this._onPointerUp = (e) => {
                if (e.button === 0) {
                    this.isPanning = false;
                } else if (e.button === 2) {
                    this.isRotating = false;
                }

                if (!this.isRotating && !this.isPanning) {
                    canvas.style.cursor = 'grab';
                }
            };

            // Mouse leave
            this._onPointerLeave = () => {
                this.isRotating = false;
                this.isPanning = false;
                canvas.style.cursor = 'grab';
            };

            // Mouse wheel - zoom
            this._onWheel = (e) => {
                e.preventDefault();
                const zoomDelta = e.deltaY > 0 ? 1.1 : 0.9;
                this.cameraDistance = Math.max(8, Math.min(40, this.cameraDistance * zoomDelta));
                this._updateCameraPosition();
            };

            // Set initial cursor
            canvas.style.cursor = 'grab';

            // Add event listeners
            canvas.addEventListener('mousedown', this._onPointerDown);
            canvas.addEventListener('mousemove', this._onPointerMove);
            canvas.addEventListener('mouseup', this._onPointerUp);
            canvas.addEventListener('mouseleave', this._onPointerLeave);
            canvas.addEventListener('wheel', this._onWheel, { passive: false });

            debugLog('Input handlers setup complete');
        }

        _onResize() {
            if (!this.container) return;

            const width = this.container.clientWidth;
            const height = this.container.clientHeight;

            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();

            this.renderer.setSize(width, height);
        }

        _gameLoop(timestamp) {
            if (!this.running) return;

            const deltaTime = timestamp - this.lastFrameTime;
            this.lastFrameTime = timestamp;

            // Update avatar system
            if (this.avatarSystem) {
                this.avatarSystem.update(deltaTime);
            }

            // Render
            this.renderer.render(this.scene, this.camera);

            // Next frame
            this.animationFrameId = requestAnimationFrame((t) => this._gameLoop(t));
        }

        async _initAvatarSystem() {
            if (!window.Playground.AvatarSystem) {
                console.warn('[City3DScene] AvatarSystem not available');
                return;
            }

            this.avatarSystem = new window.Playground.AvatarSystem();
            await this.avatarSystem.init(this.scene);
            debugLog('Avatar system initialized');
        }

        // ==================== Public API ====================

        syncSessions(sessions) {
            if (!this.isInitialized) return;

            // Sync with avatar system
            if (this.avatarSystem) {
                this.avatarSystem.syncSessions(sessions);
            }

            debugLog(`syncSessions called with ${sessions.length} sessions`);
        }

        notifyRequestStart(sessionId) {
            debugLog(`Request started for ${sessionId.substring(0, 8)}`);

            // Mark avatar as processing
            if (this.avatarSystem) {
                this.avatarSystem.setProcessing(sessionId, true);
            }
        }

        notifyRequestComplete(sessionId) {
            debugLog(`Request completed for ${sessionId.substring(0, 8)}`);

            // Mark avatar as done processing
            if (this.avatarSystem) {
                this.avatarSystem.setProcessing(sessionId, false);
            }
        }

        notifyRequestEnd(sessionId, success) {
            debugLog(`Request ended for ${sessionId.substring(0, 8)}: ${success ? 'success' : 'failed'}`);

            // Mark avatar as done processing
            if (this.avatarSystem) {
                this.avatarSystem.setProcessing(sessionId, false);
            }
        }

        zoomIn() {
            this.cameraDistance = Math.max(8, this.cameraDistance * 0.8);
            this._updateCameraPosition();
        }

        zoomOut() {
            this.cameraDistance = Math.min(40, this.cameraDistance * 1.2);
            this._updateCameraPosition();
        }

        resetView() {
            this.cameraAngle = Math.PI / 4;
            this.cameraPitch = Math.PI / 5;
            this.cameraDistance = 18;
            this.cameraTarget.set(4.5, 0, 4.5);
            this._updateCameraPosition();
        }

        destroy() {
            this.running = false;

            if (this.animationFrameId) {
                cancelAnimationFrame(this.animationFrameId);
            }

            window.removeEventListener('resize', this._resizeHandler);

            // Remove input handlers
            if (this.renderer && this.renderer.domElement) {
                const canvas = this.renderer.domElement;
                canvas.removeEventListener('mousedown', this._onPointerDown);
                canvas.removeEventListener('mousemove', this._onPointerMove);
                canvas.removeEventListener('mouseup', this._onPointerUp);
                canvas.removeEventListener('mouseleave', this._onPointerLeave);
                canvas.removeEventListener('wheel', this._onWheel);
            }

            // Dispose scene objects
            const disposeList = [...this.groundTiles, ...this.roads, ...this.buildings, ...this.natureItems];
            for (const obj of disposeList) {
                this._disposeObject(obj);
            }
            this.groundTiles = [];
            this.roads = [];
            this.buildings = [];
            this.natureItems = [];

            // Dispose asset loader
            if (this.assetLoader) {
                this.assetLoader.dispose();
            }

            // Dispose avatar system
            if (this.avatarSystem) {
                this.avatarSystem.dispose();
                this.avatarSystem = null;
            }

            // Dispose renderer
            if (this.renderer) {
                this.renderer.dispose();
                if (this.container && this.renderer.domElement) {
                    this.container.removeChild(this.renderer.domElement);
                }
            }

            this.isInitialized = false;
            debugLog('City scene destroyed');
        }

        _disposeObject(object) {
            this.scene.remove(object);
            object.traverse((child) => {
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

    // Create singleton instance
    window.Playground.Scene = new PlaygroundScene3D();
    window.Playground.PlaygroundScene3D = PlaygroundScene3D;

    debugLog('City3DScene module loaded');

})();
