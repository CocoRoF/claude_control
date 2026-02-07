/**
 * Company View - Main Scene Manager
 * Orchestrates the isometric office scene: room rendering, avatar management,
 * pathfinding integration, animations, and session sync
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    const ISO = window.CompanyView.ISO;
    const IsometricCamera = window.CompanyView.IsometricCamera;
    const DepthSortedContainer = window.CompanyView.DepthSortedContainer;
    const Assets = window.CompanyView.Assets;
    const WindowAssets = window.CompanyView.WindowAssets;
    const Avatars = window.CompanyView.Avatars;
    const Layout = window.CompanyView.Layout;
    const PathfindingGrid = window.CompanyView.PathfindingGrid;
    const Pathfinder = window.CompanyView.Pathfinder;
    const TweenManager = window.CompanyView.TweenManager;
    const AvatarAnimator = window.CompanyView.AvatarAnimator;
    const ParticleEmitter = window.CompanyView.ParticleEmitter;
    const AmbientEffects = window.CompanyView.AmbientEffects;

    // ==================== Main Scene ====================
    class CompanyScene {
        constructor() {
            this.app = null;
            this.camera = null;
            this.world = null;          // Root container for the isometric world
            this.floorLayer = null;     // Floor tiles
            this.wallLayer = null;      // Walls
            this.objectLayer = null;    // Furniture + avatars (depth sorted)
            this.effectsLayer = null;   // Particles & effects
            this.uiLayer = null;        // UI overlays

            this.tweens = new TweenManager();
            this.animator = new AvatarAnimator();
            this.particles = null;
            this.ambient = null;

            this.pathGrid = null;
            this.pathfinder = null;

            this.avatars = new Map();          // sessionId -> avatar container
            this.seatAssignments = new Map();  // seatIndex -> sessionId
            this.avatarTargets = new Map();    // sessionId -> { gridX, gridY }
            this.avatarPaths = new Map();      // sessionId -> path array
            this.avatarPathIdx = new Map();    // sessionId -> current path index

            this._mounted = false;
            this._container = null;
            this._resizeObserver = null;
            this._lastTime = 0;
            this._particleTimer = 0;
            this._initialized = false;
        }

        /**
         * Mount the PixiJS application into a DOM element
         * @param {HTMLElement} container
         */
        async mount(container) {
            if (this._mounted) return;
            this._container = container;
            this._mounted = true;

            const rect = container.getBoundingClientRect();
            const w = rect.width || 800;
            const h = rect.height || 600;

            // Create PIXI Application
            this.app = new PIXI.Application({
                width: w,
                height: h,
                backgroundColor: 0x1a1a2e,
                antialias: true,
                resolution: Math.min(window.devicePixelRatio || 1, 2),
                autoDensity: true,
            });

            container.appendChild(this.app.view);

            // Ensure canvas fills the container
            const canvas = this.app.view;
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            canvas.style.display = 'block';

            // Initialize layers
            this._initLayers();

            // Initialize camera
            this.camera = new IsometricCamera();
            this.camera.centerOn(
                Layout.ROOM.WIDTH / 2,
                Layout.ROOM.HEIGHT / 2,
                this.app.screen.width,
                this.app.screen.height
            );
            this.camera.targetY -= 30; // slight upward offset
            this.camera.targetZoom = 1.3;

            // Build the room
            this._buildRoom();

            // Initialize pathfinding
            this._initPathfinding();

            // Initialize particles
            this.particles = new ParticleEmitter(this.effectsLayer);
            this.ambient = new AmbientEffects(this.effectsLayer);

            // Input handling
            this._initInput();

            // Resize handling
            this._resizeObserver = new ResizeObserver(() => this._handleResize());
            this._resizeObserver.observe(container);

            // Start game loop
            this.app.ticker.add((delta) => this._update(delta));

            this._initialized = true;
        }

        /**
         * Unmount and destroy
         */
        destroy() {
            if (!this._mounted) return;
            this._mounted = false;
            this._initialized = false;

            if (this._resizeObserver) {
                this._resizeObserver.disconnect();
            }

            if (this.app) {
                this.app.destroy(true, { children: true, texture: true });
            }

            this.avatars.clear();
            this.seatAssignments.clear();
            this.avatarTargets.clear();
            this.avatarPaths.clear();
            this.avatarPathIdx.clear();

            if (this._container && this._container.firstChild) {
                this._container.innerHTML = '';
            }
        }

        // ==================== Layer Setup ====================

        _initLayers() {
            this.world = new PIXI.Container();
            this.app.stage.addChild(this.world);

            this.floorLayer = new PIXI.Container();
            this.wallLayer = new PIXI.Container();
            this.objectLayer = new DepthSortedContainer();
            this.effectsLayer = new PIXI.Container();
            this.uiLayer = new PIXI.Container();

            this.world.addChild(this.floorLayer);
            this.world.addChild(this.wallLayer);
            this.world.addChild(this.objectLayer);
            this.world.addChild(this.effectsLayer);
            this.world.addChild(this.uiLayer);
        }

        // ==================== Room Building ====================

        _buildRoom() {
            this._drawFloor();
            this._drawWalls();
            this._placeFurniture();
        }

        _drawFloor() {
            const { WIDTH, HEIGHT } = Layout.ROOM;

            for (let gy = 0; gy < HEIGHT; gy++) {
                for (let gx = 0; gx < WIDTH; gx++) {
                    const pos = ISO.gridToScreen(gx, gy);

                    // Main floor
                    const tile = Assets.createFloorTile(
                        Assets.PALETTE.floor.tile1,
                        Assets.PALETTE.floor.tile2,
                        gx, gy
                    );
                    tile.x = pos.x;
                    tile.y = pos.y;
                    this.floorLayer.addChild(tile);
                }
            }

            // Carpet area under desks (center area)
            for (let gy = 1; gy < 8; gy++) {
                for (let gx = 1; gx < WIDTH - 2; gx++) {
                    const pos = ISO.gridToScreen(gx, gy);
                    const carpet = Assets.createCarpetTile(gx - 1, gy - 1, WIDTH - 3, 7);
                    carpet.x = pos.x;
                    carpet.y = pos.y;
                    this.floorLayer.addChild(carpet);
                }
            }
        }

        _drawWalls() {
            const { WIDTH, HEIGHT } = Layout.ROOM;
            const wallHeight = 65;

            // Back wall (along y=0, going along x-axis)
            const backWall = Assets.createBackWall(WIDTH);
            this.wallLayer.addChild(backWall);

            // Side wall (along x=0, going along y-axis)
            const sideWall = Assets.createSideWall(HEIGHT);
            this.wallLayer.addChild(sideWall);

            // Wall corner cap - at the intersection of back and side walls
            const corner = new PIXI.Graphics();
            const cornerPos = ISO.gridToScreen(0, 0);
            // Corner is at the top corner of tile (0,0)
            const cornerX = cornerPos.x;
            const cornerY = cornerPos.y - ISO.TILE_H / 2;
            corner.beginFill(Assets.PALETTE.wall.trim);
            corner.drawRect(cornerX - 2, cornerY - wallHeight, 4, wallHeight);
            corner.endFill();
            this.wallLayer.addChild(corner);

            // Exterior wall tops (decorative) - gives 3D depth to walls
            const topCap = new PIXI.Graphics();
            topCap.beginFill(Assets.PALETTE.wall.trim, 0.8);
            // Back wall top - follows top corners of y=0 tiles
            for (let i = 0; i < WIDTH; i++) {
                const p1 = ISO.gridToScreen(i, 0);
                const p2 = ISO.gridToScreen(i + 1, 0);
                // Use top corners
                const x1 = p1.x, y1 = p1.y - ISO.TILE_H / 2;
                const x2 = p2.x, y2 = p2.y - ISO.TILE_H / 2;
                topCap.moveTo(x1, y1 - wallHeight);
                topCap.lineTo(x2, y2 - wallHeight);
                topCap.lineTo(x2 - 3, y2 - wallHeight - 3);
                topCap.lineTo(x1 - 3, y1 - wallHeight - 3);
                topCap.closePath();
            }
            topCap.endFill();

            // Side wall top - follows top corners of x=0 tiles
            topCap.beginFill(Assets.PALETTE.wallPink.trim, 0.8);
            for (let j = 0; j < HEIGHT; j++) {
                const p1 = ISO.gridToScreen(0, j);
                const p2 = ISO.gridToScreen(0, j + 1);
                // Use top corners
                const x1 = p1.x, y1 = p1.y - ISO.TILE_H / 2;
                const x2 = p2.x, y2 = p2.y - ISO.TILE_H / 2;
                topCap.moveTo(x1, y1 - wallHeight);
                topCap.lineTo(x2, y2 - wallHeight);
                topCap.lineTo(x2 + 3, y2 - wallHeight - 3);
                topCap.lineTo(x1 + 3, y1 - wallHeight - 3);
                topCap.closePath();
            }
            topCap.endFill();
            this.wallLayer.addChild(topCap);

            // Add windows on the back wall (top-right wall, y=0) - 2 windows
            const backWindow1 = WindowAssets.createBackWallWindow(3);
            const backWindow2 = WindowAssets.createBackWallWindow(8);
            this.wallLayer.addChild(backWindow1);
            this.wallLayer.addChild(backWindow2);

            // Add windows on the side wall (top-left wall, x=0) - 2 windows
            const sideWindow1 = WindowAssets.createSideWallWindow(2);
            const sideWindow2 = WindowAssets.createSideWallWindow(5);
            this.wallLayer.addChild(sideWindow1);
            this.wallLayer.addChild(sideWindow2);
        }

        _placeFurniture() {
            const ConferenceTable = window.CompanyView.ConferenceTable;
            const ChairAssets = window.CompanyView.ChairAssets;

            // 가구 배치
            for (const furniture of Layout.FURNITURE) {
                if (furniture.type === 'conferenceTable') {
                    const table = ConferenceTable.createConferenceTable(
                        furniture.gridX,
                        furniture.gridY
                    );
                    this.objectLayer.addChild(table);
                } else if (furniture.type === 'chair') {
                    const chair = ChairAssets.createChair(
                        furniture.gridX,
                        furniture.gridY,
                        furniture.facing || 'SW'
                    );
                    // 의자 base(다리+좌석)와 backrest(등받이)를 별도로 추가
                    this.objectLayer.addChild(chair.base);
                    this.objectLayer.addChild(chair.backrest);
                } else if (furniture.type === 'sideChair') {
                    const SideChairAssets = window.CompanyView.SideChairAssets;
                    const sideChair = SideChairAssets.createSideChair(
                        furniture.gridX,
                        furniture.gridY,
                        furniture.facing || 'SW'
                    );
                    this.objectLayer.addChild(sideChair.base);
                    this.objectLayer.addChild(sideChair.backrest);
                }
            }

            this.objectLayer.markDirty();
        }

        // ==================== Pathfinding ====================

        _initPathfinding() {
            const walkMap = Layout.generateWalkableMap();
            this.pathGrid = new PathfindingGrid(Layout.ROOM.WIDTH, Layout.ROOM.HEIGHT);

            for (let y = 0; y < Layout.ROOM.HEIGHT; y++) {
                for (let x = 0; x < Layout.ROOM.WIDTH; x++) {
                    this.pathGrid.setWalkable(x, y, walkMap[y][x]);
                }
            }

            this.pathfinder = new Pathfinder(this.pathGrid);
        }

        // ==================== Avatar Management ====================

        /**
         * Sync avatars with session data from the dashboard
         * @param {Array} sessions - Array of session objects
         */
        syncSessions(sessions) {
            if (!this._initialized) return;

            const currentIds = new Set(sessions.map(s => s.session_id));
            const existingIds = new Set(this.avatars.keys());

            // Remove avatars for deleted sessions
            for (const id of existingIds) {
                if (!currentIds.has(id)) {
                    this._removeAvatar(id);
                }
            }

            // Add/update avatars for current sessions
            for (const session of sessions) {
                if (!existingIds.has(session.session_id)) {
                    this._addAvatar(session);
                } else {
                    this._updateAvatar(session);
                }
            }
        }

        _addAvatar(session) {
            const avatar = Avatars.createAvatar(session.session_id, session.session_name);

            // Find available seat
            const seatIdx = this._findFreeSeat();
            let targetGridX, targetGridY;

            if (seatIdx !== -1) {
                const seat = Layout.SEAT_POSITIONS[seatIdx];
                targetGridX = seat.gridX;
                targetGridY = seat.gridY;
                this.seatAssignments.set(seatIdx, session.session_id);
            } else {
                // No free seats - use idle position
                const idle = Layout.IDLE_POSITIONS[this.avatars.size % Layout.IDLE_POSITIONS.length];
                targetGridX = idle.gridX;
                targetGridY = idle.gridY;
            }

            // Place avatar at entrance first, then walk to seat
            const entranceX = 5;
            const entranceY = Layout.ROOM.HEIGHT - 1;
            const entrancePos = ISO.gridToScreen(entranceX, entranceY);
            avatar.x = entrancePos.x;
            avatar.y = entrancePos.y;
            avatar.zIndex = ISO.depthKey(entranceX, entranceY, 1);
            avatar._avatarData.currentGridX = entranceX;
            avatar._avatarData.currentGridY = entranceY;

            // Scale up entrance animation
            avatar.scale.set(0);
            this.tweens.add(avatar.scale, { x: 1, y: 1 }, 400, 'elasticOut');

            this.objectLayer.addChild(avatar);
            this.avatars.set(session.session_id, avatar);

            // Set up walking to seat
            this._moveAvatarTo(session.session_id, targetGridX, targetGridY);

            // Set initial status
            Avatars.setAvatarStatus(avatar, session.status || 'idle');

            // Interaction
            avatar.on('pointerdown', () => {
                this._onAvatarClick(session.session_id);
            });
            avatar.on('pointerover', () => {
                avatar.getChildByName('nameLabel').visible = true;
                if (!this.tweens.hasTweens(avatar.scale)) {
                    this.tweens.add(avatar.scale, { x: 1.1, y: 1.1 }, 200, 'easeOut');
                }
            });
            avatar.on('pointerout', () => {
                // Keep name visible but scale back
                this.tweens.cancelFor(avatar.scale);
                this.tweens.add(avatar.scale, { x: 1, y: 1 }, 200, 'easeOut');
            });

            this.objectLayer.markDirty();
        }

        _removeAvatar(sessionId) {
            const avatar = this.avatars.get(sessionId);
            if (!avatar) return;

            // Free up seat
            for (const [seatIdx, sId] of this.seatAssignments.entries()) {
                if (sId === sessionId) {
                    this.seatAssignments.delete(seatIdx);
                    break;
                }
            }

            // Fade out and remove
            this.tweens.add(avatar, { alpha: 0 }, 300, 'easeIn', () => {
                this.objectLayer.removeChild(avatar);
                avatar.destroy({ children: true });
            });
            this.tweens.add(avatar.scale, { x: 0, y: 0 }, 300, 'easeIn');

            this.avatars.delete(sessionId);
            this.avatarTargets.delete(sessionId);
            this.avatarPaths.delete(sessionId);
            this.avatarPathIdx.delete(sessionId);
        }

        _updateAvatar(session) {
            const avatar = this.avatars.get(session.session_id);
            if (!avatar) return;

            Avatars.setAvatarStatus(avatar, session.status || 'idle');

            // Update name if changed
            const nameLabel = avatar.getChildByName('nameLabel');
            if (nameLabel && session.session_name) {
                // Rebuild name label
                const idx = avatar.getChildIndex(nameLabel);
                avatar.removeChild(nameLabel);
                nameLabel.destroy({ children: true });

                const newLabel = Avatars.createAvatar._createNameLabel
                    ? Avatars.createAvatar._createNameLabel(session.session_name)
                    : null;

                // We can't easily call internal function, so just leave it
            }
        }

        _findFreeSeat() {
            for (let i = 0; i < Layout.SEAT_POSITIONS.length; i++) {
                if (!this.seatAssignments.has(i)) {
                    return i;
                }
            }
            return -1;
        }

        _moveAvatarTo(sessionId, targetGX, targetGY) {
            const avatar = this.avatars.get(sessionId);
            if (!avatar) return;

            const data = avatar._avatarData;
            const startX = Math.round(data.currentGridX);
            const startY = Math.round(data.currentGridY);
            const endX = Math.round(targetGX);
            const endY = Math.round(targetGY);

            // Use pathfinding to find a route
            const path = this.pathfinder.findPath(startX, startY, endX, endY);

            if (path.length > 1) {
                data.animState = 'walking';
                this.avatarPaths.set(sessionId, path);
                this.avatarPathIdx.set(sessionId, 0);
                this.avatarTargets.set(sessionId, { gridX: targetGX, gridY: targetGY });
            } else {
                // Direct placement if no path or already there
                const pos = ISO.gridToScreen(targetGX, targetGY);
                avatar.x = pos.x;
                avatar.y = pos.y;
                data.currentGridX = targetGX;
                data.currentGridY = targetGY;
                avatar.zIndex = ISO.depthKey(targetGX, targetGY, 1);
                data.animState = data.animState === 'walking' ? 'idle' : data.animState;
                this.objectLayer.markDirty();
            }
        }

        _onAvatarClick(sessionId) {
            // Dispatch event for the main app to handle
            const event = new CustomEvent('company-avatar-click', {
                detail: { sessionId }
            });
            document.dispatchEvent(event);

            // Visual feedback
            const avatar = this.avatars.get(sessionId);
            if (avatar) {
                this.particles.emitSuccess(avatar.x, avatar.y);
            }
        }

        // ==================== Input ====================

        _initInput() {
            const view = this.app.view;

            // Panning
            view.addEventListener('pointerdown', (e) => {
                if (e.button === 0 || e.button === 1) { // Left or middle click
                    this.camera.startDrag(e.clientX, e.clientY);
                }
            });

            view.addEventListener('pointermove', (e) => {
                if (this.camera.isDragging) {
                    this.camera.moveDrag(e.clientX, e.clientY);
                }
            });

            view.addEventListener('pointerup', () => {
                this.camera.endDrag();
            });

            view.addEventListener('pointerleave', () => {
                this.camera.endDrag();
            });

            // Zooming
            view.addEventListener('wheel', (e) => {
                e.preventDefault();
                const factor = e.deltaY > 0 ? 0.9 : 1.1;
                this.camera.zoomAt(
                    factor,
                    e.clientX - this._container.getBoundingClientRect().left,
                    e.clientY - this._container.getBoundingClientRect().top,
                    this.world.x,
                    this.world.y
                );
            }, { passive: false });

            // Touch zoom
            let lastTouchDist = 0;
            view.addEventListener('touchstart', (e) => {
                if (e.touches.length === 2) {
                    const dx = e.touches[0].clientX - e.touches[1].clientX;
                    const dy = e.touches[0].clientY - e.touches[1].clientY;
                    lastTouchDist = Math.sqrt(dx * dx + dy * dy);
                }
            }, { passive: true });

            view.addEventListener('touchmove', (e) => {
                if (e.touches.length === 2) {
                    const dx = e.touches[0].clientX - e.touches[1].clientX;
                    const dy = e.touches[0].clientY - e.touches[1].clientY;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (lastTouchDist > 0) {
                        const factor = dist / lastTouchDist;
                        const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
                        const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
                        const rect = this._container.getBoundingClientRect();
                        this.camera.zoomAt(factor, midX - rect.left, midY - rect.top, this.world.x, this.world.y);
                    }
                    lastTouchDist = dist;
                }
            }, { passive: true });
        }

        // ==================== Game Loop ====================

        _update(delta) {
            const dt = delta * (1000 / 60); // Convert PIXI delta to ms

            // Camera
            this.camera.update();
            this.camera.applyTo(this.world);

            // Tweens
            this.tweens.update(dt);

            // Avatar movement along paths
            this._updateAvatarPaths(dt);

            // Avatar animations
            for (const [, avatar] of this.avatars) {
                this.animator.update(avatar, dt);
            }

            // Particles
            this.particles.update(dt);
            this._particleTimer += dt;

            // Emit typing particles for working avatars
            if (this._particleTimer > 300) {
                this._particleTimer = 0;
                for (const [, avatar] of this.avatars) {
                    if (avatar._avatarData.animState === 'working') {
                        this.particles.emitTypingSparks(avatar.x, avatar.y);
                    }
                }
            }

            // Depth sort
            this.objectLayer.depthSort();
        }

        _updateAvatarPaths(dt) {
            const moveSpeed = 0.015; // Grid cells per ms

            for (const [sessionId, path] of this.avatarPaths) {
                const avatar = this.avatars.get(sessionId);
                if (!avatar) continue;

                let idx = this.avatarPathIdx.get(sessionId) || 0;
                if (idx >= path.length - 1) {
                    // Reached destination
                    const target = this.avatarTargets.get(sessionId);
                    if (target) {
                        const pos = ISO.gridToScreen(target.gridX, target.gridY);
                        avatar.x = pos.x;
                        avatar.y = pos.y;
                        avatar._avatarData.currentGridX = target.gridX;
                        avatar._avatarData.currentGridY = target.gridY;
                        avatar.zIndex = ISO.depthKey(target.gridX, target.gridY, 1);

                        // If session is running, switch to working. Otherwise idle.
                        if (avatar._avatarData.animState === 'walking') {
                            avatar._avatarData.animState =
                                avatar.getChildByName('statusBubble')?.visible ? 'working' : 'idle';
                        }
                    }
                    this.avatarPaths.delete(sessionId);
                    this.avatarPathIdx.delete(sessionId);
                    this.avatarTargets.delete(sessionId);
                    this.objectLayer.markDirty();
                    continue;
                }

                const data = avatar._avatarData;
                const current = path[idx];
                const next = path[idx + 1];

                // Interpolate
                const dx = next.x - data.currentGridX;
                const dy = next.y - data.currentGridY;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < moveSpeed * dt) {
                    data.currentGridX = next.x;
                    data.currentGridY = next.y;
                    this.avatarPathIdx.set(sessionId, idx + 1);
                } else {
                    const step = (moveSpeed * dt) / dist;
                    data.currentGridX += dx * step;
                    data.currentGridY += dy * step;
                }

                const screenPos = ISO.gridToScreen(data.currentGridX, data.currentGridY);
                avatar.x = screenPos.x;
                avatar.y = screenPos.y;
                avatar.zIndex = ISO.depthKey(data.currentGridX, data.currentGridY, 1);
                this.objectLayer.markDirty();

                // Set direction based on movement
                if (Math.abs(dx) > Math.abs(dy)) {
                    data.direction = dx > 0 ? 'right' : 'left';
                } else {
                    data.direction = dy > 0 ? 'down' : 'up';
                }
            }
        }

        // ==================== Resize ====================

        _handleResize() {
            if (!this.app || !this._container) return;
            const rect = this._container.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return;
            this.app.renderer.resize(rect.width, rect.height);
        }

        // ==================== Public API ====================

        get isInitialized() {
            return this._initialized;
        }

        centerCamera() {
            if (!this.camera) return;
            this.camera.centerOn(
                Layout.ROOM.WIDTH / 2,
                Layout.ROOM.HEIGHT / 2,
                this.app.screen.width,
                this.app.screen.height
            );
        }

        zoomIn() {
            if (!this.camera) return;
            this.camera.targetZoom = Math.min(this.camera.maxZoom, this.camera.targetZoom * 1.2);
        }

        zoomOut() {
            if (!this.camera) return;
            this.camera.targetZoom = Math.max(this.camera.minZoom, this.camera.targetZoom / 1.2);
        }

        resetView() {
            this.camera.targetZoom = 1.3;
            this.centerCamera();
            this.camera.targetY -= 30;
        }
    }

    // ==================== Singleton Instance ====================
    let _instance = null;

    function getInstance() {
        if (!_instance) {
            _instance = new CompanyScene();
        }
        return _instance;
    }

    function destroyInstance() {
        if (_instance) {
            _instance.destroy();
            _instance = null;
        }
    }

    // ==================== Export ====================
    window.CompanyView.CompanyScene = CompanyScene;
    window.CompanyView.getInstance = getInstance;
    window.CompanyView.destroyInstance = destroyInstance;

})();
