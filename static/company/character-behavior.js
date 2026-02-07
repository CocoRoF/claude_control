/**
 * Character Behavior System - 캐릭터 행동 상태 머신
 *
 * 상태:
 * - idle: 기본 대기 상태 (서있거나 앉아있음)
 * - walking: 이동 중
 * - sitting: 앉아있음 (작업 중 또는 대기)
 * - working: 요청 처리 중 (앉아서 말풍선 표시)
 * - special: 특수 행동 중
 *
 * 유휴 이벤트:
 * - 5~30초마다 랜덤하게 발생
 * - 걸어서 이동, 앉기, 특수 행동
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    // ==================== 디버그 설정 ====================
    const DEBUG = true;  // 디버그 로그 활성화

    function debugLog(...args) {
        if (DEBUG) {
            console.log('[BehaviorManager DEBUG]', ...args);
        }
    }

    // ==================== 행동 설정 ====================
    const BEHAVIOR_CONFIG = {
        // 유휴 이벤트 타이머 (밀리초)
        idleEventMinTime: 5000,      // 5초
        idleEventMaxTime: 15000,     // 15초

        // 이동 속도
        walkSpeed: 0.02,             // 그리드 단위/ms

        // 특수 행동 지속 시간
        specialActionDuration: 3000, // 3초

        // 말풍선 표시 시간
        thinkingBubbleDuration: 0,   // 0 = 요청 완료까지 유지

        // 특수 행동 목록
        specialActions: [
            'stretch',   // 기지개
            'wave',      // 손 흔들기
            'look',      // 주변 둘러보기
            'dance',     // 춤추기
            'yawn',      // 하품
        ],
    };

    // ==================== 행동 상태 정의 ====================
    const BehaviorState = {
        IDLE: 'idle',
        WALKING: 'walking',
        SITTING: 'sitting',
        WORKING: 'working',
        SPECIAL: 'special',
    };

    // ==================== 특수 행동 이모지 ====================
    const SPECIAL_ACTION_EMOJIS = {
        stretch: '🙆',
        wave: '👋',
        look: '👀',
        dance: '💃',
        yawn: '😪',
        reading: '📖',
        coffee: '☕',
        chatting: '💬',
    };

    // ==================== 캐릭터 행동 관리자 ====================
    class CharacterBehaviorManager {
        constructor(scene) {
            this.scene = scene;

            // 캐릭터별 행동 데이터
            this.behaviors = new Map();

            // 이동 가능 영역 캐시
            this.walkablePositions = [];

            // 좌석 위치 캐시
            this.seatPositions = [];

            // 유휴 위치 캐시
            this.idlePositions = [];

            this._initialized = false;
            this._debugTimer = 0;
        }

        /**
         * 초기화
         */
        init() {
            if (this._initialized) return;

            const Layout = window.CompanyView.Layout;

            // 좌석 위치 캐시
            this.seatPositions = [...Layout.SEAT_POSITIONS];

            // 유휴 위치 캐시
            this.idlePositions = [...Layout.IDLE_POSITIONS];

            // 이동 가능 영역 계산
            this._calculateWalkablePositions();

            this._initialized = true;
            console.log('[BehaviorManager] Initialized with', this.walkablePositions.length, 'walkable positions');
        }

        /**
         * 이동 가능 영역 계산
         */
        _calculateWalkablePositions() {
            const Layout = window.CompanyView.Layout;
            const walkableMap = Layout.generateWalkableMap();

            this.walkablePositions = [];

            for (let y = 0; y < Layout.ROOM.HEIGHT; y++) {
                for (let x = 0; x < Layout.ROOM.WIDTH; x++) {
                    if (walkableMap[y][x]) {
                        this.walkablePositions.push({ x, y });
                    }
                }
            }
        }

        /**
         * 캐릭터 등록
         */
        registerCharacter(sessionId, avatar) {
            debugLog('Registering character:', sessionId, 'Avatar:', !!avatar);

            const behaviorData = {
                sessionId,
                avatar,
                state: BehaviorState.IDLE,
                previousState: null,

                // 현재 위치
                currentGridX: 0,
                currentGridY: 0,

                // 목표 위치
                targetGridX: null,
                targetGridY: null,

                // 이동 경로
                path: [],
                pathIndex: 0,

                // 앉아있는 좌석
                currentSeatId: null,
                isSitting: false,

                // 유휴 이벤트 타이머
                idleTimer: 0,
                nextIdleEventTime: this._getRandomIdleTime(),

                // 특수 행동 타이머
                specialTimer: 0,
                specialAction: null,

                // 작업 상태 (세션 요청)
                isWorking: false,
                workStartTime: 0,

                // 애니메이션 상태
                animationPhase: Math.random() * Math.PI * 2,
            };

            this.behaviors.set(sessionId, behaviorData);
            debugLog('Character registered. Total characters:', this.behaviors.size);
            debugLog('Initial idle event time:', behaviorData.nextIdleEventTime, 'ms');
            return behaviorData;
        }

        /**
         * 캐릭터 해제
         */
        unregisterCharacter(sessionId) {
            this.behaviors.delete(sessionId);
        }

        /**
         * 랜덤 유휴 이벤트 시간
         */
        _getRandomIdleTime() {
            const { idleEventMinTime, idleEventMaxTime } = BEHAVIOR_CONFIG;
            return idleEventMinTime + Math.random() * (idleEventMaxTime - idleEventMinTime);
        }

        /**
         * 캐릭터 위치 설정
         */
        setPosition(sessionId, gridX, gridY) {
            const data = this.behaviors.get(sessionId);
            if (data) {
                data.currentGridX = gridX;
                data.currentGridY = gridY;
            }
        }

        /**
         * 작업 시작 (세션 요청 받음)
         */
        startWorking(sessionId) {
            const data = this.behaviors.get(sessionId);
            if (!data) return;

            // 현재 상태 저장
            data.previousState = data.state;
            data.state = BehaviorState.WORKING;
            data.isWorking = true;
            data.workStartTime = Date.now();

            // 말풍선 표시 (...)
            this._showThinkingBubble(data.avatar);

            // 3D 애니메이터에 상태 전달
            this._setAnimatorState(sessionId, 'thinking');

            // 유휴 타이머 중지
            data.idleTimer = 0;

            console.log(`[BehaviorManager] Character ${sessionId} started working`);
        }

        /**
         * 작업 완료
         */
        stopWorking(sessionId, success = true) {
            const data = this.behaviors.get(sessionId);
            if (!data) return;

            data.isWorking = false;
            data.state = data.isSitting ? BehaviorState.SITTING : BehaviorState.IDLE;

            // 결과 말풍선 표시
            this._showResultBubble(data.avatar, success);

            // 3D 애니메이터에 상태 전달
            this._setAnimatorState(sessionId, data.isSitting ? 'sit' : 'idle');

            // 유휴 타이머 리셋
            data.idleTimer = 0;
            data.nextIdleEventTime = this._getRandomIdleTime();

            console.log(`[BehaviorManager] Character ${sessionId} stopped working (success: ${success})`);
        }

        /**
         * 생각 중 말풍선 표시
         */
        _showThinkingBubble(avatar) {
            const Avatars = window.CompanyView.Avatars;
            if (Avatars && Avatars.setAvatarStatus) {
                Avatars.setAvatarStatus(avatar, 'thinking');
            }

            // 말풍선 텍스트를 '...'로 변경
            const bubble = avatar.getChildByName('statusBubble');
            if (bubble) {
                const icon = bubble.getChildByName('icon');
                if (icon) {
                    icon.text = '💭';
                }
                bubble.visible = true;
            }
        }

        /**
         * 결과 말풍선 표시 (잠시 후 숨김)
         */
        _showResultBubble(avatar, success) {
            const Avatars = window.CompanyView.Avatars;
            if (Avatars && Avatars.setAvatarStatus) {
                Avatars.setAvatarStatus(avatar, success ? 'success' : 'error');
            }

            // 3초 후 숨기기
            setTimeout(() => {
                if (Avatars && Avatars.setAvatarStatus) {
                    Avatars.setAvatarStatus(avatar, 'none');
                }
            }, 3000);
        }

        /**
         * 특수 행동 말풍선 표시
         */
        _showSpecialActionBubble(avatar, action) {
            const bubble = avatar.getChildByName('statusBubble');
            if (bubble) {
                const icon = bubble.getChildByName('icon');
                if (icon) {
                    icon.text = SPECIAL_ACTION_EMOJIS[action] || '✨';
                }
                bubble.visible = true;
            }
        }

        /**
         * 말풍선 숨기기
         */
        _hideBubble(avatar) {
            const bubble = avatar.getChildByName('statusBubble');
            if (bubble) {
                bubble.visible = false;
            }
        }

        /**
         * 캐릭터를 특정 위치로 이동
         * scene의 기존 이동 시스템 사용
         */
        moveToPosition(sessionId, targetX, targetY, callback) {
            const data = this.behaviors.get(sessionId);
            if (!data) {
                debugLog(`[${sessionId}] moveToPosition: No behavior data found!`);
                return false;
            }

            // 작업 중이면 이동 불가
            if (data.isWorking) {
                debugLog(`[${sessionId}] moveToPosition: Cannot move - working`);
                return false;
            }

            // 현재 위치와 같으면 무시
            const startX = Math.floor(data.currentGridX);
            const startY = Math.floor(data.currentGridY);

            debugLog(`[${sessionId}] moveToPosition: From (${startX},${startY}) to (${targetX},${targetY})`);

            if (startX === targetX && startY === targetY) {
                debugLog(`[${sessionId}] moveToPosition: Already at target`);
                if (callback) callback(true);
                return true;
            }

            // scene의 기존 이동 시스템 사용
            if (this.scene._moveAvatarTo) {
                debugLog(`[${sessionId}] moveToPosition: Using scene._moveAvatarTo`);
                data.state = BehaviorState.WALKING;
                data.isSitting = false;
                data.currentSeatId = null;
                data.moveCallback = callback;
                data.targetGridX = targetX;
                data.targetGridY = targetY;

                // 3D 애니메이터에 걸기 애니메이션 상태 전달
                this._setAnimatorState(sessionId, 'walk');

                this.scene._moveAvatarTo(sessionId, targetX, targetY);
                return true;
            } else {
                debugLog(`[${sessionId}] moveToPosition: scene._moveAvatarTo not available!`);
            }

            if (callback) callback(false);
            return false;
        }

        /**
         * 캐릭터를 좌석으로 이동하고 앉기
         */
        moveToSeatAndSit(sessionId, seatIndex, callback) {
            const data = this.behaviors.get(sessionId);
            if (!data) return false;

            const Layout = window.CompanyView.Layout;
            const seat = Layout.SEAT_POSITIONS[seatIndex];

            if (!seat) return false;

            // 좌석 위치로 이동
            const targetX = Math.floor(seat.gridX);
            const targetY = Math.floor(seat.gridY);

            return this.moveToPosition(sessionId, targetX, targetY, (success) => {
                if (success) {
                    data.isSitting = true;
                    data.currentSeatId = seat.seatId;
                    data.state = BehaviorState.SITTING;
                }
                if (callback) callback(success);
            });
        }

        /**
         * 랜덤 이동 가능 위치 선택
         */
        getRandomWalkablePosition() {
            if (this.walkablePositions.length === 0) return null;
            const idx = Math.floor(Math.random() * this.walkablePositions.length);
            return this.walkablePositions[idx];
        }

        /**
         * 랜덤 빈 좌석 선택
         */
        getRandomFreeSeat() {
            const Layout = window.CompanyView.Layout;
            const occupiedSeats = new Set();

            // 현재 앉아있는 좌석 수집
            for (const [, data] of this.behaviors) {
                if (data.isSitting && data.currentSeatId) {
                    occupiedSeats.add(data.currentSeatId);
                }
            }

            // 빈 좌석 필터
            const freeSeats = Layout.SEAT_POSITIONS.filter((seat, idx) => {
                return !occupiedSeats.has(seat.seatId) &&
                       !this.scene.seatAssignments.has(idx);
            });

            if (freeSeats.length === 0) return null;

            const idx = Math.floor(Math.random() * freeSeats.length);
            return {
                seat: freeSeats[idx],
                index: Layout.SEAT_POSITIONS.indexOf(freeSeats[idx])
            };
        }

        /**
         * 랜덤 특수 행동 선택
         */
        getRandomSpecialAction() {
            const { specialActions } = BEHAVIOR_CONFIG;
            const idx = Math.floor(Math.random() * specialActions.length);
            return specialActions[idx];
        }

        /**
         * 유휴 이벤트 실행
         */
        _executeIdleEvent(data) {
            // 작업 중이면 무시
            if (data.isWorking) {
                debugLog(`[${data.sessionId}] Idle event skipped - working`);
                return;
            }

            // 랜덤하게 행동 선택 (가중치)
            const rand = Math.random();
            debugLog(`[${data.sessionId}] Executing idle event. Random: ${rand.toFixed(2)}`);

            if (rand < 0.3) {
                // 30%: 랜덤 위치로 이동
                const pos = this.getRandomWalkablePosition();
                debugLog(`[${data.sessionId}] Action: WALK, Target pos:`, pos);
                if (pos) {
                    const moveResult = this.moveToPosition(data.sessionId, pos.x, pos.y);
                    debugLog(`[${data.sessionId}] Move initiated: ${moveResult}`);
                } else {
                    debugLog(`[${data.sessionId}] No walkable position found!`);
                }
            } else if (rand < 0.6) {
                // 30%: 빈 좌석으로 이동하고 앉기
                const freeSeat = this.getRandomFreeSeat();
                debugLog(`[${data.sessionId}] Action: SIT, Free seat:`, freeSeat);
                if (freeSeat) {
                    this.moveToSeatAndSit(data.sessionId, freeSeat.index);
                } else {
                    debugLog(`[${data.sessionId}] No free seat found!`);
                }
            } else {
                // 40%: 특수 행동
                const action = this.getRandomSpecialAction();
                debugLog(`[${data.sessionId}] Action: SPECIAL - ${action}`);
                this._startSpecialAction(data, action);
            }
        }

        /**
         * 특수 행동 시작
         */
        _startSpecialAction(data, action) {
            data.state = BehaviorState.SPECIAL;
            data.specialAction = action;
            data.specialTimer = 0;

            this._showSpecialActionBubble(data.avatar, action);

            // 3D 애니메이터에 애니메이션 상태 전달
            this._setAnimatorState(data.sessionId, action);
        }

        /**
         * 특수 행동 종료
         */
        _endSpecialAction(data) {
            data.state = data.isSitting ? BehaviorState.SITTING : BehaviorState.IDLE;
            data.specialAction = null;
            data.specialTimer = 0;

            this._hideBubble(data.avatar);

            // 3D 애니메이터에 애니메이션 상태 전달
            this._setAnimatorState(data.sessionId, data.isSitting ? 'sit' : 'idle');
        }

        /**
         * 3D 애니메이터 상태 설정
         */
        _setAnimatorState(sessionId, animState) {
            const CharacterAnimator3D = window.CompanyView.CharacterAnimator3D;
            if (CharacterAnimator3D && CharacterAnimator3D.ready) {
                CharacterAnimator3D.setAnimState(sessionId, animState);
            }
        }

        /**
         * 프레임 업데이트
         */
        update(deltaTime) {
            if (!this._initialized) {
                debugLog('Update called but not initialized!');
                return;
            }

            // 10초마다 전체 상태 요약 로그
            this._debugTimer = (this._debugTimer || 0) + deltaTime;
            if (this._debugTimer >= 10000) {
                this._debugTimer = 0;
                this._logAllStates();
            }

            const ISO = window.CompanyView.ISO;

            for (const [sessionId, data] of this.behaviors) {
                // 애니메이션 페이즈 업데이트
                data.animationPhase += deltaTime * 0.003;

                switch (data.state) {
                    case BehaviorState.IDLE:
                    case BehaviorState.SITTING:
                        this._updateIdleState(data, deltaTime);
                        break;

                    case BehaviorState.WALKING:
                        this._updateWalkingState(data, deltaTime);
                        break;

                    case BehaviorState.WORKING:
                        this._updateWorkingState(data, deltaTime);
                        break;

                    case BehaviorState.SPECIAL:
                        this._updateSpecialState(data, deltaTime);
                        break;
                }

                // 캐릭터 위치 애니메이션 (미세한 움직임)
                this._animateCharacter(data, deltaTime);
            }
        }

        /**
         * 유휴 상태 업데이트
         */
        _updateIdleState(data, deltaTime) {
            // 작업 중이면 타이머 중지
            if (data.isWorking) {
                debugLog(`[${data.sessionId}] Idle update skipped - working`);
                return;
            }

            const prevTimer = data.idleTimer;
            data.idleTimer += deltaTime;

            // 5초마다 또는 이벤트 발생시 로그
            if (Math.floor(prevTimer / 5000) !== Math.floor(data.idleTimer / 5000)) {
                debugLog(`[${data.sessionId}] State: ${data.state}, IdleTimer: ${Math.floor(data.idleTimer)}/${data.nextIdleEventTime.toFixed(0)}ms`);
            }

            if (data.idleTimer >= data.nextIdleEventTime) {
                debugLog(`[${data.sessionId}] IDLE EVENT TRIGGERED! Timer: ${data.idleTimer}, Threshold: ${data.nextIdleEventTime}`);
                data.idleTimer = 0;
                data.nextIdleEventTime = this._getRandomIdleTime();
                debugLog(`[${data.sessionId}] Next idle event in: ${data.nextIdleEventTime}ms`);
                this._executeIdleEvent(data);
            }
        }

        /**
         * 이동 상태 업데이트
         * scene의 _updateAvatarPaths가 실제 이동 처리
         * 여기서는 상태 모니터링만
         */
        _updateWalkingState(data, deltaTime) {
            // scene._updateAvatarPaths가 실제 이동 처리
            // 이동 완료 여부는 scene에서 setPosition 호출로 알게 됨

            // path가 scene에서 삭제되면 이동 완료
            if (this.scene.avatarPaths && !this.scene.avatarPaths.has(data.sessionId)) {
                // 이동 완료됨
                if (data.state === BehaviorState.WALKING) {
                    const prevState = data.state;

                    // 콜백 먼저 호출 (isSitting 설정을 위해)
                    if (data.moveCallback) {
                        data.moveCallback(true);
                        data.moveCallback = null;
                    }

                    // 콜백 후 상태 결정 (isSitting이 콜백에서 설정될 수 있음)
                    data.state = data.isSitting ? BehaviorState.SITTING : BehaviorState.IDLE;

                    debugLog(`[${data.sessionId}] Walk completed. State: ${prevState} -> ${data.state}, isSitting=${data.isSitting}`);

                    // 3D 애니메이터에 상태 전달
                    this._setAnimatorState(data.sessionId, data.isSitting ? 'sit' : 'idle');

                    // 유휴 타이머 리셋
                    data.idleTimer = 0;
                    data.nextIdleEventTime = this._getRandomIdleTime();
                    debugLog(`[${data.sessionId}] Next idle event in: ${data.nextIdleEventTime}ms`);
                }
            }
        }

        /**
         * 작업 상태 업데이트
         */
        _updateWorkingState(data, deltaTime) {
            // 말풍선 강조 애니메이션
            const bubble = data.avatar?.getChildByName('statusBubble');
            if (bubble && bubble.visible) {
                const scale = 1 + Math.sin(data.animationPhase * 2) * 0.05;
                bubble.scale.set(scale);
            }
        }

        /**
         * 특수 행동 상태 업데이트
         */
        _updateSpecialState(data, deltaTime) {
            data.specialTimer += deltaTime;

            if (data.specialTimer >= BEHAVIOR_CONFIG.specialActionDuration) {
                this._endSpecialAction(data);
            } else {
                // 특수 행동 애니메이션
                this._animateSpecialAction(data, deltaTime);
            }
        }

        /**
         * 캐릭터 미세 애니메이션
         */
        _animateCharacter(data, deltaTime) {
            const character = data.avatar?.getChildByName('character');
            if (!character) return;

            switch (data.state) {
                case BehaviorState.IDLE:
                case BehaviorState.SITTING:
                    // 숨쉬기 효과
                    character.y = Math.sin(data.animationPhase) * 1;
                    break;

                case BehaviorState.WALKING:
                    // 걷기 바운스
                    character.y = Math.abs(Math.sin(data.animationPhase * 8)) * -3;
                    break;

                case BehaviorState.WORKING:
                    // 작업 중 약간의 움직임
                    character.y = Math.sin(data.animationPhase * 3) * 0.5;
                    break;
            }
        }

        /**
         * 특수 행동 애니메이션
         */
        _animateSpecialAction(data, deltaTime) {
            const character = data.avatar?.getChildByName('character');
            if (!character) return;

            const progress = data.specialTimer / BEHAVIOR_CONFIG.specialActionDuration;

            switch (data.specialAction) {
                case 'stretch':
                    // 위로 뻗기
                    character.y = -Math.sin(progress * Math.PI) * 8;
                    break;

                case 'wave':
                    // 좌우 흔들기
                    character.x = Math.sin(progress * Math.PI * 6) * 3;
                    break;

                case 'look':
                    // 좌우 보기 (스케일로 표현)
                    character.scale.x = Math.cos(progress * Math.PI * 2) > 0 ? 1 : -1;
                    break;

                case 'dance':
                    // 춤추기
                    character.y = Math.abs(Math.sin(progress * Math.PI * 8)) * -5;
                    character.rotation = Math.sin(progress * Math.PI * 4) * 0.1;
                    break;

                case 'yawn':
                    // 스케일 늘리기
                    const yawnScale = 1 + Math.sin(progress * Math.PI) * 0.1;
                    character.scale.set(yawnScale);
                    break;
            }
        }

        /**
         * 애니메이션 리셋
         */
        resetCharacterAnimation(avatar) {
            const character = avatar?.getChildByName('character');
            if (character) {
                character.x = 0;
                character.y = 0;
                character.rotation = 0;
                character.scale.set(1);
            }
        }

        /**
         * 캐릭터 데이터 가져오기
         */
        getBehaviorData(sessionId) {
            return this.behaviors.get(sessionId);
        }

        /**
         * 디버그용 상태 로그
         */
        _logAllStates() {
            if (this.behaviors.size === 0) {
                debugLog('=== STATUS: No characters registered ===');
                return;
            }

            debugLog(`=== STATUS SUMMARY (${this.behaviors.size} characters) ===`);
            for (const [sessionId, data] of this.behaviors) {
                const shortId = sessionId.substring(0, 8);
                debugLog(`  ${shortId}: state=${data.state}, pos=(${data.currentGridX.toFixed(1)},${data.currentGridY.toFixed(1)}), sitting=${data.isSitting}, working=${data.isWorking}, idleTimer=${Math.floor(data.idleTimer)}/${data.nextIdleEventTime.toFixed(0)}ms`);
            }
        }

        /**
         * 모든 캐릭터의 현재 상태
         */
        getAllStates() {
            const states = {};
            for (const [sessionId, data] of this.behaviors) {
                states[sessionId] = {
                    state: data.state,
                    position: { x: data.currentGridX, y: data.currentGridY },
                    isSitting: data.isSitting,
                    isWorking: data.isWorking,
                };
            }
            return states;
        }
    }

    // ==================== Export ====================
    window.CompanyView.CharacterBehaviorManager = CharacterBehaviorManager;
    window.CompanyView.BehaviorState = BehaviorState;
    window.CompanyView.BEHAVIOR_CONFIG = BEHAVIOR_CONFIG;

})();
