/**
 * Company View - Kenney 에셋 기반 스터디 룸 씬
 * 완전한 스프라이트 기반 렌더링
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    // ==================== Main Scene ====================
    class CompanyScene {
        constructor() {
            this.app = null;
            this.camera = null;
            this.world = null;
            this.floorLayer = null;
            this.wallLayer = null;
            this.objectLayer = null;
            this.effectsLayer = null;
            this.uiLayer = null;

            this.tweens = null;
            this.animator = null;
            this.particles = null;

            this.pathGrid = null;
            this.pathfinder = null;

            // 캐릭터 행동 관리자
            this.behaviorManager = null;

            this.avatars = new Map();
            this.seatAssignments = new Map();
            this.avatarTargets = new Map();
            this.avatarPaths = new Map();
            this.avatarPathIdx = new Map();

            this._mounted = false;
            this._container = null;
            this._resizeObserver = null;
            this._initialized = false;
            this._assetsLoaded = false;

            // 로딩 상태
            this._loadingScreen = null;
        }

        /**
         * Mount and initialize the scene
         */
        async mount(container) {
            if (this._mounted) return;
            this._container = container;
            this._mounted = true;

            const rect = container.getBoundingClientRect();
            const w = rect.width || 800;
            const h = rect.height || 600;

            // PIXI 앱 생성
            this.app = new PIXI.Application({
                width: w,
                height: h,
                backgroundColor: 0x2C1810, // 따뜻한 라이브러리 톤
                antialias: true,
                resolution: Math.min(window.devicePixelRatio || 1, 2),
                autoDensity: true,
            });

            container.appendChild(this.app.view);

            const canvas = this.app.view;
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            canvas.style.display = 'block';

            // 로딩 화면 표시
            this._showLoadingScreen();

            // 에셋 로딩
            await this._loadAssets();

            // 로딩 화면 제거
            this._hideLoadingScreen();

            // 레이어 초기화
            this._initLayers();

            // 의존성 가져오기
            const ISO = window.CompanyView.ISO;
            const IsometricCamera = window.CompanyView.IsometricCamera;
            const TweenManager = window.CompanyView.TweenManager;
            const AvatarAnimator = window.CompanyView.AvatarAnimator;
            const ParticleEmitter = window.CompanyView.ParticleEmitter;
            const Layout = window.CompanyView.Layout;
            const PathfindingGrid = window.CompanyView.PathfindingGrid;
            const Pathfinder = window.CompanyView.Pathfinder;

            // 카메라 초기화
            this.camera = new IsometricCamera();
            this.camera.centerOn(
                Layout.ROOM.WIDTH / 2,
                Layout.ROOM.HEIGHT / 2,
                this.app.screen.width,
                this.app.screen.height
            );
            this.camera.targetY -= 100;
            // 타일이 커졌으므로 줌 축소 (256x128 타일 기준)
            this.camera.targetZoom = 0.35;

            // 매니저 초기화
            this.tweens = new TweenManager();
            this.animator = new AvatarAnimator();
            this.particles = new ParticleEmitter(this.effectsLayer);

            // 룸 빌드
            this._buildRoom();

            // 패스파인딩 초기화
            this._initPathfinding();

            // 행동 관리자 초기화
            const CharacterBehaviorManager = window.CompanyView.CharacterBehaviorManager;
            if (CharacterBehaviorManager) {
                this.behaviorManager = new CharacterBehaviorManager(this);
                this.behaviorManager.init();
            }

            // 입력 처리
            this._initInput();

            // 리사이즈 처리
            this._resizeObserver = new ResizeObserver(() => this._handleResize());
            this._resizeObserver.observe(container);

            // 게임 루프 시작
            this.app.ticker.add((delta) => this._update(delta));

            this._initialized = true;
        }

        destroy() {
            if (!this._mounted) return;
            this._mounted = false;
            this._initialized = false;
            this._assetsLoaded = false;

            if (this._resizeObserver) {
                this._resizeObserver.disconnect();
            }

            if (this.app) {
                this.app.destroy(true, { children: true, texture: true });
            }

            this.avatars.clear();
            this.seatAssignments.clear();

            if (this._container) {
                this._container.innerHTML = '';
            }
        }

        // ==================== 로딩 화면 ====================

        _showLoadingScreen() {
            this._loadingScreen = new PIXI.Container();

            const bg = new PIXI.Graphics();
            bg.beginFill(0x2C1810);
            bg.drawRect(0, 0, this.app.screen.width, this.app.screen.height);
            bg.endFill();

            const loadingText = new PIXI.Text('📚 스터디 룸 로딩 중...', {
                fontFamily: 'Arial, sans-serif',
                fontSize: 24,
                fill: 0xF5E6D3,
                align: 'center',
            });
            loadingText.anchor.set(0.5);
            loadingText.x = this.app.screen.width / 2;
            loadingText.y = this.app.screen.height / 2 - 30;

            const progressBar = new PIXI.Graphics();
            progressBar.name = 'progressBar';
            progressBar.x = this.app.screen.width / 2 - 100;
            progressBar.y = this.app.screen.height / 2 + 20;

            this._loadingScreen.addChild(bg);
            this._loadingScreen.addChild(loadingText);
            this._loadingScreen.addChild(progressBar);

            this.app.stage.addChild(this._loadingScreen);
        }

        _updateLoadingProgress(progress) {
            if (!this._loadingScreen) return;

            const bar = this._loadingScreen.getChildByName('progressBar');
            if (bar) {
                bar.clear();
                // 배경
                bar.beginFill(0x4A3728);
                bar.drawRoundedRect(0, 0, 200, 20, 10);
                bar.endFill();
                // 진행률
                bar.beginFill(0x8B7355);
                bar.drawRoundedRect(2, 2, Math.max(0, (200 - 4) * progress), 16, 8);
                bar.endFill();
            }
        }

        _hideLoadingScreen() {
            if (this._loadingScreen) {
                this.app.stage.removeChild(this._loadingScreen);
                this._loadingScreen.destroy({ children: true });
                this._loadingScreen = null;
            }
        }

        // ==================== 에셋 로딩 ====================

        async _loadAssets() {
            const AssetManager = window.CompanyView.AssetManager;
            const CharacterRenderer3D = window.CompanyView.CharacterRenderer3D;
            const CharacterAnimator3D = window.CompanyView.CharacterAnimator3D;

            try {
                // 2D 에셋 로드
                await AssetManager.loadAll((progress) => {
                    this._updateLoadingProgress(progress * 0.4);  // 40%까지
                });
                this._assetsLoaded = true;
                console.log('[CompanyScene] 2D Assets loaded successfully');

                // 3D 애니메이터 초기화 및 로드 (우선)
                if (CharacterAnimator3D && typeof THREE !== 'undefined') {
                    const initSuccess = await CharacterAnimator3D.init();
                    if (initSuccess) {
                        await CharacterAnimator3D.loadAllTemplates((progress) => {
                            this._updateLoadingProgress(0.4 + progress * 0.4);  // 40~80%
                        });
                        console.log('[CompanyScene] 3D Animator loaded successfully');
                    }
                }

                // 정적 3D 렌더러 초기화 (폴백용)
                if (CharacterRenderer3D && typeof THREE !== 'undefined') {
                    const initSuccess = await CharacterRenderer3D.init();
                    if (initSuccess) {
                        await CharacterRenderer3D.loadAllCharacters((progress) => {
                            this._updateLoadingProgress(0.8 + progress * 0.2);  // 80~100%
                        });
                        console.log('[CompanyScene] 3D Renderer loaded successfully');
                    }
                } else {
                    console.warn('[CompanyScene] 3D renderer not available, using 2D fallback');
                    this._updateLoadingProgress(1);
                }
            } catch (error) {
                console.error('[CompanyScene] Asset loading failed:', error);
                // 폴백 모드로 진행
                this._assetsLoaded = false;
            }
        }

        // ==================== 레이어 설정 ====================

        _initLayers() {
            const DepthSortedContainer = window.CompanyView.DepthSortedContainer;

            this.world = new PIXI.Container();
            this.app.stage.addChild(this.world);

            this.floorLayer = new PIXI.Container();
            this.wallLayer = new PIXI.Container();
            this.wallLayer.sortableChildren = true;
            this.objectLayer = new DepthSortedContainer();
            this.effectsLayer = new PIXI.Container();
            this.uiLayer = new PIXI.Container();

            this.world.addChild(this.floorLayer);
            this.world.addChild(this.wallLayer);
            this.world.addChild(this.objectLayer);
            this.world.addChild(this.effectsLayer);
            this.world.addChild(this.uiLayer);
        }

        // ==================== 룸 빌드 ====================

        _buildRoom() {
            this._drawFloor();
            this._drawWalls();
            this._placeFurniture();
        }

        _drawFloor() {
            const ISO = window.CompanyView.ISO;
            const Layout = window.CompanyView.Layout;
            const Assets = window.CompanyView.Assets;
            const { WIDTH, HEIGHT } = Layout.ROOM;
            const CARPET = Layout.CARPET_AREA;

            // 1단계: 모든 바닥 타일을 돌 바닥으로 깔기
            for (let gy = 0; gy < HEIGHT; gy++) {
                for (let gx = 0; gx < WIDTH; gx++) {
                    const pos = ISO.gridToScreen(gx, gy);
                    const tile = Assets.createFloorTile(gx, gy, 'stone');

                    tile.x = pos.x;
                    tile.y = pos.y + ISO.TILE_H / 2;
                    this.floorLayer.addChild(tile);
                }
            }

            // 2단계: 카펫 영역에 카펫 오버레이
            if (CARPET) {
                for (let gy = CARPET.startY; gy < CARPET.startY + CARPET.height; gy++) {
                    for (let gx = CARPET.startX; gx < CARPET.startX + CARPET.width; gx++) {
                        const pos = ISO.gridToScreen(gx, gy);
                        const carpet = Assets.createFloorTile(gx, gy, 'carpet');

                        if (carpet) {
                            carpet.x = pos.x;
                            carpet.y = pos.y + ISO.TILE_H / 2;
                            this.floorLayer.addChild(carpet);
                        }
                    }
                }
            }
        }

        _drawWalls() {
            const ISO = window.CompanyView.ISO;
            const Layout = window.CompanyView.Layout;
            const Assets = window.CompanyView.Assets;
            const { WIDTH, HEIGHT } = Layout.ROOM;
            const wallStyle = Layout.WALLS?.style || 'stone';

            // 후면 벽 (gy=0 라인, gx 방향)
            for (const wallConfig of (Layout.WALLS?.back || [])) {
                const { gx, type, direction } = wallConfig;
                const wall = Assets.createWallSegment(wallStyle, type, direction);

                if (wall) {
                    const pos = ISO.gridToScreen(gx, 0);
                    wall.x = pos.x;
                    wall.y = pos.y + ISO.TILE_H / 2; // 바닥 위에 배치
                    // zIndex: gx가 클수록 앞에 (오른쪽 아래)
                    wall.zIndex = ISO.depthKey(gx, 0, 1);
                    this.wallLayer.addChild(wall);
                }
            }

            // 좌측 벽 (gx=0 라인, gy 방향)
            for (const wallConfig of (Layout.WALLS?.left || [])) {
                const { gy, type, direction } = wallConfig;
                const wall = Assets.createWallSegment(wallStyle, type, direction);

                if (wall) {
                    const pos = ISO.gridToScreen(0, gy);
                    wall.x = pos.x;
                    wall.y = pos.y + ISO.TILE_H / 2;
                    // 코너(gy=0)는 가장 뒤로, gy가 클수록 앞에
                    wall.zIndex = ISO.depthKey(0, gy, 1);
                    this.wallLayer.addChild(wall);
                }
            }
        }

        _placeFurniture() {
            const ISO = window.CompanyView.ISO;
            const Layout = window.CompanyView.Layout;
            const Assets = window.CompanyView.Assets;

            for (const furniture of Layout.FURNITURE) {
                const sprite = Assets.createFurnitureFromLayout(furniture);

                if (sprite) {
                    const pos = ISO.gridToScreen(furniture.gridX, furniture.gridY);
                    sprite.x = pos.x;
                    sprite.y = pos.y + ISO.TILE_H / 2; // 타일 하단에 배치

                    // 깊이 정렬용 zIndex
                    sprite.zIndex = ISO.depthKey(furniture.gridX, furniture.gridY, 1);

                    this.objectLayer.addChild(sprite);
                }
            }

            this.objectLayer.markDirty();
        }

        // ==================== 패스파인딩 ====================

        _initPathfinding() {
            const Layout = window.CompanyView.Layout;
            const PathfindingGrid = window.CompanyView.PathfindingGrid;
            const Pathfinder = window.CompanyView.Pathfinder;

            const walkMap = Layout.generateWalkableMap();
            this.pathGrid = new PathfindingGrid(Layout.ROOM.WIDTH, Layout.ROOM.HEIGHT);

            for (let y = 0; y < Layout.ROOM.HEIGHT; y++) {
                for (let x = 0; x < Layout.ROOM.WIDTH; x++) {
                    this.pathGrid.setWalkable(x, y, walkMap[y][x]);
                }
            }

            this.pathfinder = new Pathfinder(this.pathGrid);
        }

        // ==================== 아바타 관리 ====================

        syncSessions(sessions) {
            if (!this._initialized) return;

            const currentIds = new Set(sessions.map(s => s.session_id));
            const existingIds = new Set(this.avatars.keys());

            // 삭제된 세션 처리
            for (const id of existingIds) {
                if (!currentIds.has(id)) {
                    this._removeAvatar(id);
                }
            }

            // 새 세션 추가/업데이트
            for (const session of sessions) {
                if (!existingIds.has(session.session_id)) {
                    this._addAvatar(session);
                } else {
                    this._updateAvatar(session);
                }
            }
        }

        _addAvatar(session) {
            const ISO = window.CompanyView.ISO;
            const Layout = window.CompanyView.Layout;
            const Avatars = window.CompanyView.Avatars;

            const avatar = Avatars.createAvatar(session.session_id, session.session_name);

            // 좌석 찾기
            const seatIdx = this._findFreeSeat();
            let targetGridX, targetGridY;

            if (seatIdx !== -1) {
                const seat = Layout.SEAT_POSITIONS[seatIdx];
                targetGridX = seat.gridX;
                targetGridY = seat.gridY;
                this.seatAssignments.set(seatIdx, session.session_id);
            } else {
                const idle = Layout.IDLE_POSITIONS[this.avatars.size % Layout.IDLE_POSITIONS.length];
                targetGridX = idle.gridX;
                targetGridY = idle.gridY;
            }

            // 입구에서 시작
            const entranceX = Layout.ROOM.WIDTH / 2;
            const entranceY = Layout.ROOM.HEIGHT - 1;
            const entrancePos = ISO.gridToScreen(entranceX, entranceY);
            avatar.x = entrancePos.x;
            avatar.y = entrancePos.y;
            avatar.zIndex = ISO.depthKey(entranceX, entranceY, 1);
            avatar._avatarData.currentGridX = entranceX;
            avatar._avatarData.currentGridY = entranceY;

            // 등장 애니메이션
            avatar.scale.set(0);
            this.tweens.add(avatar.scale, { x: 1, y: 1 }, 400, 'elasticOut');

            this.objectLayer.addChild(avatar);
            this.avatars.set(session.session_id, avatar);

            // 행동 관리자에 등록
            if (this.behaviorManager) {
                this.behaviorManager.registerCharacter(session.session_id, avatar);
                this.behaviorManager.setPosition(session.session_id, entranceX, entranceY);
                console.log('[CompanyScene DEBUG] Character registered:', session.session_id.substring(0, 8), 'at entrance:', entranceX, entranceY);
            }

            // 좌석으로 이동
            this._moveAvatarTo(session.session_id, targetGridX, targetGridY);
            console.log('[CompanyScene DEBUG] Moving to seat:', targetGridX, targetGridY);

            // 상태 설정
            Avatars.setAvatarStatus(avatar, session.status || 'idle');

            // 인터랙션
            avatar.on('pointerdown', () => this._onAvatarClick(session.session_id));
            avatar.on('pointerover', () => {
                this.tweens.add(avatar.scale, { x: 1.1, y: 1.1 }, 150, 'easeOut');
            });
            avatar.on('pointerout', () => {
                this.tweens.add(avatar.scale, { x: 1, y: 1 }, 150, 'easeOut');
            });

            this.objectLayer.markDirty();
        }

        _removeAvatar(sessionId) {
            const avatar = this.avatars.get(sessionId);
            if (!avatar) return;

            for (const [seatIdx, sId] of this.seatAssignments.entries()) {
                if (sId === sessionId) {
                    this.seatAssignments.delete(seatIdx);
                    break;
                }
            }

            this.tweens.add(avatar, { alpha: 0 }, 300, 'easeIn', () => {
                this.objectLayer.removeChild(avatar);
                avatar.destroy({ children: true });
            });
            this.tweens.add(avatar.scale, { x: 0, y: 0 }, 300, 'easeIn');

            this.avatars.delete(sessionId);
            this.avatarTargets.delete(sessionId);
            this.avatarPaths.delete(sessionId);
            this.avatarPathIdx.delete(sessionId);

            // 행동 관리자에서 해제
            if (this.behaviorManager) {
                this.behaviorManager.unregisterCharacter(sessionId);
            }
        }

        _updateAvatar(session) {
            const avatar = this.avatars.get(session.session_id);
            if (!avatar) return;

            const Avatars = window.CompanyView.Avatars;
            Avatars.setAvatarStatus(avatar, session.status || 'idle');
        }

        _findFreeSeat() {
            const Layout = window.CompanyView.Layout;
            for (let i = 0; i < Layout.SEAT_POSITIONS.length; i++) {
                if (!this.seatAssignments.has(i)) {
                    return i;
                }
            }
            return -1;
        }

        _moveAvatarTo(sessionId, targetGX, targetGY) {
            const ISO = window.CompanyView.ISO;
            const avatar = this.avatars.get(sessionId);
            if (!avatar) return;

            const data = avatar._avatarData;
            const startX = Math.round(data.currentGridX);
            const startY = Math.round(data.currentGridY);
            const endX = Math.round(targetGX);
            const endY = Math.round(targetGY);

            let path = this.pathfinder.findPath(startX, startY, endX, endY);
            let finalTarget = { gridX: targetGX, gridY: targetGY };

            // 목적지가 walkable이 아닌 경우, 가장 가까운 walkable 위치까지 경로 생성
            if (path.length <= 1) {
                const nearest = this.pathfinder.findNearestWalkable(endX, endY);
                if (nearest && (nearest.x !== startX || nearest.y !== startY)) {
                    path = this.pathfinder.findPath(startX, startY, nearest.x, nearest.y);
                    // 경로 마지막에 실제 목적지 추가 (짧은 거리라서 직접 이동)
                    if (path.length > 0) {
                        path.push({ x: endX, y: endY });
                    }
                }
            }

            if (path.length > 1) {
                data.animState = 'walk';
                const Avatars = window.CompanyView.Avatars;
                Avatars.setAvatarAnimation(avatar, 'walk');

                this.avatarPaths.set(sessionId, path);
                this.avatarPathIdx.set(sessionId, 0);
                this.avatarTargets.set(sessionId, finalTarget);

                // behavior manager 상태를 WALKING으로 변경
                if (this.behaviorManager) {
                    const behaviorData = this.behaviorManager.getBehaviorData(sessionId);
                    if (behaviorData) {
                        behaviorData.state = window.CompanyView.BehaviorState.WALKING;
                        behaviorData.isSitting = false;
                        behaviorData.idleTimer = 0;
                    }
                }

                // 3D 애니메이터에 walk 상태 전달
                const CharacterAnimator3D = window.CompanyView.CharacterAnimator3D;
                if (CharacterAnimator3D && CharacterAnimator3D.ready) {
                    CharacterAnimator3D.setAnimState(sessionId, 'walk');
                }
            } else {
                const pos = ISO.gridToScreen(targetGX, targetGY);
                avatar.x = pos.x;
                avatar.y = pos.y;
                data.currentGridX = targetGX;
                data.currentGridY = targetGY;
                avatar.zIndex = ISO.depthKey(targetGX, targetGY, 1);
                this.objectLayer.markDirty();
            }
        }

        _onAvatarClick(sessionId) {
            const event = new CustomEvent('company-avatar-click', {
                detail: { sessionId }
            });
            document.dispatchEvent(event);

            const avatar = this.avatars.get(sessionId);
            if (avatar) {
                this.particles.emitSuccess(avatar.x, avatar.y);
            }
        }

        // ==================== 입력 처리 ====================

        _initInput() {
            const view = this.app.view;

            view.addEventListener('pointerdown', (e) => {
                if (e.button === 0 || e.button === 1) {
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

            view.addEventListener('wheel', (e) => {
                e.preventDefault();
                const factor = e.deltaY > 0 ? 0.9 : 1.1;
                const rect = this._container.getBoundingClientRect();
                this.camera.zoomAt(
                    factor,
                    e.clientX - rect.left,
                    e.clientY - rect.top,
                    this.world.x,
                    this.world.y
                );
            }, { passive: false });
        }

        // ==================== 게임 루프 ====================

        _update(delta) {
            const dt = delta * (1000 / 60);

            // 카메라
            this.camera.update();
            this.camera.applyTo(this.world);

            // 트윈
            this.tweens.update(dt);

            // 아바타 경로 이동
            this._updateAvatarPaths(dt);

            // 3D 애니메이터 업데이트 (모든 캐릭터 애니메이션)
            const CharacterAnimator3D = window.CompanyView.CharacterAnimator3D;
            if (CharacterAnimator3D && CharacterAnimator3D.ready) {
                CharacterAnimator3D.update(dt);
                CharacterAnimator3D.renderAll();
            }

            // 아바타 애니메이션 (텍스처 업데이트)
            const Avatars = window.CompanyView.Avatars;
            for (const [, avatar] of this.avatars) {
                Avatars.updateAvatar(avatar, dt / 1000);
            }

            // 파티클
            this.particles.update(dt);

            // 행동 관리자 업데이트
            if (this.behaviorManager) {
                this.behaviorManager.update(dt);
            }

            // 깊이 정렬
            this.objectLayer.depthSort();
        }

        _updateAvatarPaths(dt) {
            const ISO = window.CompanyView.ISO;
            const Avatars = window.CompanyView.Avatars;
            const moveSpeed = 0.0004;  // 0.1 grids per second

            for (const [sessionId, path] of this.avatarPaths) {
                const avatar = this.avatars.get(sessionId);
                if (!avatar) continue;

                let idx = this.avatarPathIdx.get(sessionId) || 0;
                if (idx >= path.length - 1) {
                    // 도착
                    const target = this.avatarTargets.get(sessionId);
                    if (target) {
                        const pos = ISO.gridToScreen(target.gridX, target.gridY);
                        avatar.x = pos.x;
                        avatar.y = pos.y;
                        avatar._avatarData.currentGridX = target.gridX;
                        avatar._avatarData.currentGridY = target.gridY;
                        avatar.zIndex = ISO.depthKey(target.gridX, target.gridY, 1);

                        // idle 애니메이션으로 전환
                        Avatars.setAvatarAnimation(avatar, 'idle');

                        // 행동 관리자에 위치 동기화
                        if (this.behaviorManager) {
                            this.behaviorManager.setPosition(sessionId, target.gridX, target.gridY);
                            const behaviorData = this.behaviorManager.getBehaviorData(sessionId);
                            if (behaviorData) {
                                behaviorData.isSitting = true;
                                behaviorData.state = window.CompanyView.BehaviorState.SITTING;
                                behaviorData.idleTimer = 0;
                                console.log('[CompanyScene DEBUG] Walk completed:', sessionId.substring(0, 8), 'now SITTING at', target.gridX, target.gridY);
                            }
                        }
                    }
                    this.avatarPaths.delete(sessionId);
                    this.avatarPathIdx.delete(sessionId);
                    this.avatarTargets.delete(sessionId);
                    this.objectLayer.markDirty();
                    continue;
                }

                const data = avatar._avatarData;
                const next = path[idx + 1];

                const dx = next.x - data.currentGridX;
                const dy = next.y - data.currentGridY;
                const dist = Math.sqrt(dx * dx + dy * dy);

                // 이동 방향 계산 및 3D 애니메이터에 전달
                const direction = this._calculateDirection(dx, dy);
                const CharacterAnimator3D = window.CompanyView.CharacterAnimator3D;
                if (CharacterAnimator3D && CharacterAnimator3D.ready) {
                    CharacterAnimator3D.setDirection(sessionId, direction);
                }

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

                // 행동 관리자에 이동 중 위치 동기화
                if (this.behaviorManager) {
                    this.behaviorManager.setPosition(sessionId, data.currentGridX, data.currentGridY);
                }
            }
        }

        // ==================== 리사이즈 ====================

        /**
         * 이동 방향 계산 (isometric 좌표계 기준)
         */
        _calculateDirection(dx, dy) {
            // isometric: gx++ → SE, gy++ → SW
            const angle = Math.atan2(dy, dx);
            const deg = angle * 180 / Math.PI;

            // 8방향 결정
            if (deg >= -22.5 && deg < 22.5) return 'SE';      // dx+, dy~0
            if (deg >= 22.5 && deg < 67.5) return 'S';        // dx+, dy+
            if (deg >= 67.5 && deg < 112.5) return 'SW';      // dx~0, dy+
            if (deg >= 112.5 && deg < 157.5) return 'W';      // dx-, dy+
            if (deg >= 157.5 || deg < -157.5) return 'NW';    // dx-, dy~0
            if (deg >= -157.5 && deg < -112.5) return 'N';    // dx-, dy-
            if (deg >= -112.5 && deg < -67.5) return 'NE';    // dx~0, dy-
            if (deg >= -67.5 && deg < -22.5) return 'E';      // dx+, dy-
            return 'SW';  // 기본값
        }

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
            const Layout = window.CompanyView.Layout;
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
            this.camera.targetZoom = 1.5;
            this.centerCamera();
            this.camera.targetY -= 20;
        }

        /**
         * 세션에 요청이 시작됨을 알림
         * @param {string} sessionId
         */
        notifyRequestStart(sessionId) {
            if (this.behaviorManager) {
                this.behaviorManager.startWorking(sessionId);
            }
        }

        /**
         * 세션 요청이 완료됨을 알림
         * @param {string} sessionId
         * @param {boolean} success
         */
        notifyRequestEnd(sessionId, success = true) {
            if (this.behaviorManager) {
                this.behaviorManager.stopWorking(sessionId, success);
            }
        }

        /**
         * 캐릭터 행동 상태 가져오기
         * @param {string} sessionId
         */
        getCharacterState(sessionId) {
            if (this.behaviorManager) {
                return this.behaviorManager.getBehaviorData(sessionId);
            }
            return null;
        }
    }

    // ==================== 싱글톤 ====================
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
