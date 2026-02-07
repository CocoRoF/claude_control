/**
 * Avatar System - Kenney 스프라이트 기반 캐릭터 시스템
 * kenney_mini-characters 사용
 * 12가지 캐릭터 (female-a~f, male-a~f)
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    // ==================== 캐릭터 설정 ====================
    const CHARACTER_CONFIG = {
        scale: 1.0,              // 캐릭터 스케일
        animationSpeed: 0.15,    // 애니메이션 속도 (미사용)
        bobAmount: 2,            // idle 상태 흔들림
        shadowOpacity: 0.2,      // 그림자 투명도
        variants: 12,            // female-a~f, male-a~f
    };

    // ==================== 애니메이션 정의 ====================
    const ANIMATIONS = {
        idle: { frames: 1, loop: false },  // 정적 이미지
    };

    // ==================== 이름 색상 팔레트 ====================
    const NAME_COLORS = [
        0x5B9BD5, // 블루
        0x6BBF6B, // 그린
        0xE88BA8, // 핑크
        0xE5C95B, // 옐로우
        0x9B7ED5, // 퍼플
        0xE8964A, // 오렌지
        0x5BBCE5, // 시안
        0xCC6666, // 레드
    ];

    // ==================== 유틸리티 함수 ====================
    /**
     * 세션 ID를 기반으로 해시 생성
     */
    function simpleHash(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash);
    }

    // ==================== 아바타 생성 ====================
    /**
     * Kenney 스프라이트 기반 아바타 생성
     * @param {string} sessionId - 세션 ID (외형 결정에 사용)
     * @param {string} sessionName - 표시 이름
     * @returns {PIXI.Container}
     */
    function createAvatar(sessionId, sessionName) {
        const hash = simpleHash(sessionId);
        const characterVariant = hash % CHARACTER_CONFIG.variants;
        const nameColor = NAME_COLORS[hash % NAME_COLORS.length];

        const container = new PIXI.Container();

        // 아바타 데이터 저장
        container._avatarData = {
            sessionId,
            sessionName,
            characterVariant,
            nameColor,
            animState: 'idle',
            animFrame: 0,
            animTimer: 0,
            direction: 'S',
            bobOffset: 0,
            bobPhase: Math.random() * Math.PI * 2,
        };

        // 그림자
        const shadow = createShadow();
        shadow.name = 'shadow';
        container.addChild(shadow);

        // 캐릭터 스프라이트 (sessionId 전달하여 3D 애니메이터 사용)
        const characterSprite = createCharacterSprite(characterVariant, 'idle', 0, sessionId);
        characterSprite.name = 'character';
        container.addChild(characterSprite);

        // 이름 라벨
        const nameLabel = createNameLabel(sessionName || sessionId.substring(0, 8), nameColor);
        nameLabel.name = 'nameLabel';
        nameLabel.y = -characterSprite.height - 10;
        container.addChild(nameLabel);

        // 상태 버블
        const statusBubble = createStatusBubble();
        statusBubble.name = 'statusBubble';
        statusBubble.x = 20;
        statusBubble.y = -characterSprite.height - 5;
        statusBubble.visible = false;
        container.addChild(statusBubble);

        // 인터랙션 설정
        container.interactive = true;
        container.buttonMode = true;
        container.cursor = 'pointer';

        return container;
    }

    // ==================== 캐릭터 스프라이트 ====================
    /**
     * 캐릭터 스프라이트 생성
     * 3D 애니메이터 우선 사용 (실시간 애니메이션)
     * 폴백으로 정적 3D 렌더러 또는 2D 스프라이트 사용
     */
    function createCharacterSprite(variant, animation, frame, sessionId) {
        const CharacterAnimator3D = window.CompanyView.CharacterAnimator3D;
        const CharacterRenderer3D = window.CompanyView.CharacterRenderer3D;
        const AssetManager = window.CompanyView.AssetManager;

        // 3D 애니메이터 사용 (실시간 애니메이션)
        if (CharacterAnimator3D && CharacterAnimator3D.ready && sessionId) {
            // 캐릭터 인스턴스 생성
            const charData = CharacterAnimator3D.createCharacter(sessionId, variant);
            if (charData) {
                const texture = CharacterAnimator3D.getTexture(sessionId);
                if (texture) {
                    const sprite = new PIXI.Sprite(texture);
                    sprite.scale.set(CHARACTER_CONFIG.scale);
                    sprite.anchor.set(0.5, 1);
                    sprite._uses3DAnimator = true;
                    sprite._sessionId = sessionId;
                    return sprite;
                }
            }
        }

        // 정적 3D 렌더러 폴백
        if (CharacterRenderer3D && CharacterRenderer3D.ready) {
            const texture = CharacterRenderer3D.getCharacterTexture(variant);
            if (texture) {
                const sprite = new PIXI.Sprite(texture);
                sprite.scale.set(CHARACTER_CONFIG.scale);
                sprite.anchor.set(0.5, 1);
                return sprite;
            }
        }

        // 2D 스프라이트 폴백
        const sprite = AssetManager.createCharacterSprite(variant, animation, frame);

        if (sprite) {
            sprite.scale.set(CHARACTER_CONFIG.scale);
            sprite.anchor.set(0.5, 1);
            return sprite;
        }

        // 최종 폴백: Graphics 캐릭터
        return createFallbackCharacter(variant);
    }

    /**
     * 폴백 캐릭터 (스프라이트 로드 실패 시)
     */
    function createFallbackCharacter(variant) {
        const g = new PIXI.Graphics();
        const colors = [
            0x4A90D9, 0x50C878, 0xE74C3C, 0xF39C12,
            0x9B59B6, 0x1ABC9C, 0xE67E22, 0x34495E
        ];
        const color = colors[variant % colors.length];

        // 몸통
        g.beginFill(color);
        g.drawRoundedRect(-12, -48, 24, 32, 6);
        g.endFill();

        // 머리
        g.beginFill(0xFFDBB4);
        g.drawCircle(0, -56, 12);
        g.endFill();

        // 얼굴
        g.beginFill(0x333333);
        g.drawCircle(-4, -58, 2);
        g.drawCircle(4, -58, 2);
        g.endFill();

        // 다리
        g.beginFill(0x333333);
        g.drawRoundedRect(-10, -16, 8, 16, 3);
        g.drawRoundedRect(2, -16, 8, 16, 3);
        g.endFill();

        return g;
    }

    // ==================== 그림자 ====================
    function createShadow() {
        const g = new PIXI.Graphics();
        g.beginFill(0x000000, CHARACTER_CONFIG.shadowOpacity);
        g.drawEllipse(0, 0, 14, 6);
        g.endFill();
        return g;
    }

    // ==================== 이름 라벨 ====================
    function createNameLabel(name, accentColor = 0x5B9BD5) {
        const container = new PIXI.Container();

        // 배경 필 (둥근 라벨)
        const padding = 6;
        const textStyle = new PIXI.TextStyle({
            fontFamily: 'Arial, sans-serif',
            fontSize: 11,
            fontWeight: 'bold',
            fill: 0xFFFFFF,
            align: 'center',
        });

        const text = new PIXI.Text(name, textStyle);
        text.anchor.set(0.5, 0.5);
        text.resolution = 2;

        const bgWidth = text.width + padding * 2;
        const bgHeight = text.height + padding;

        const bg = new PIXI.Graphics();
        bg.beginFill(accentColor, 0.9);
        bg.drawRoundedRect(-bgWidth / 2, -bgHeight / 2, bgWidth, bgHeight, bgHeight / 2);
        bg.endFill();

        // 테두리
        bg.lineStyle(1, 0xFFFFFF, 0.3);
        bg.drawRoundedRect(-bgWidth / 2, -bgHeight / 2, bgWidth, bgHeight, bgHeight / 2);

        container.addChild(bg);
        container.addChild(text);

        return container;
    }

    // ==================== 상태 버블 ====================
    function createStatusBubble() {
        const container = new PIXI.Container();

        const bg = new PIXI.Graphics();
        bg.beginFill(0xFFFFFF, 0.95);
        bg.drawRoundedRect(-14, -14, 28, 28, 6);
        bg.endFill();
        bg.lineStyle(2, 0xE0E0E0, 1);
        bg.drawRoundedRect(-14, -14, 28, 28, 6);

        // 말풍선 꼬리
        bg.beginFill(0xFFFFFF, 0.95);
        bg.moveTo(-6, 14);
        bg.lineTo(0, 20);
        bg.lineTo(6, 14);
        bg.closePath();
        bg.endFill();

        container.addChild(bg);

        // 상태 아이콘 (기본: thinking)
        const icon = new PIXI.Text('💭', {
            fontSize: 16,
        });
        icon.anchor.set(0.5, 0.5);
        icon.name = 'icon';
        container.addChild(icon);

        return container;
    }

    // ==================== 아바타 업데이트 ====================
    /**
     * 아바타 상태 업데이트
     * @param {PIXI.Container} avatar
     * @param {string} status - working, idle, thinking, away
     */
    function setAvatarStatus(avatar, status) {
        const bubble = avatar.getChildByName('statusBubble');
        if (!bubble) return;

        const iconMap = {
            working: '💻',
            thinking: '💭',
            idle: '☕',
            away: '💤',
            success: '✨',
            error: '❌',
        };

        const icon = bubble.getChildByName('icon');
        if (icon) {
            icon.text = iconMap[status] || '💭';
        }

        bubble.visible = status !== 'none';
    }

    /**
     * 아바타 애니메이션 상태 변경
     * @param {PIXI.Container} avatar
     * @param {string} animState - idle, run, sit, thinking, stretch, wave, dance
     */
    function setAvatarAnimation(avatar, animState) {
        const data = avatar._avatarData;
        if (!data || data.animState === animState) return;

        data.animState = animState;
        data.animFrame = 0;
        data.animTimer = 0;

        // 3D 애니메이터에 상태 전달
        const CharacterAnimator3D = window.CompanyView.CharacterAnimator3D;
        if (CharacterAnimator3D && CharacterAnimator3D.ready) {
            CharacterAnimator3D.setAnimState(data.sessionId, animState);
        }
    }

    /**
     * 아바타 프레임 업데이트 (게임 루프에서 호출)
     * @param {PIXI.Container} avatar
     * @param {number} delta - 델타 타임 (초)
     */
    function updateAvatar(avatar, delta) {
        const data = avatar._avatarData;
        if (!data) return;

        const CharacterAnimator3D = window.CompanyView.CharacterAnimator3D;
        const character = avatar.getChildByName('character');

        // 3D 애니메이터 사용 중인 경우 텍스처 업데이트
        if (character && character._uses3DAnimator && CharacterAnimator3D) {
            const texture = CharacterAnimator3D.getTexture(data.sessionId);
            if (texture && character.texture !== texture) {
                character.texture = texture;
            }
        }

        // 기본 bobbing 애니메이션 (3D 애니메이터 미사용 시)
        if (!character || !character._uses3DAnimator) {
            if (data.animState === 'idle') {
                data.bobPhase += delta * 2;
                data.bobOffset = Math.sin(data.bobPhase) * CHARACTER_CONFIG.bobAmount;

                if (character) {
                    character.y = data.bobOffset;
                }
            }
        }
    }

    /**
     * 아바타 이름 변경
     */
    function setAvatarName(avatar, newName) {
        const data = avatar._avatarData;
        if (!data) return;

        data.sessionName = newName;

        // 기존 라벨 제거
        const oldLabel = avatar.getChildByName('nameLabel');
        if (oldLabel) {
            avatar.removeChild(oldLabel);
            oldLabel.destroy();
        }

        // 새 라벨 생성
        const newLabel = createNameLabel(newName, data.nameColor);
        newLabel.name = 'nameLabel';
        newLabel.y = -50;
        avatar.addChild(newLabel);
    }

    /**
     * 아바타 클린업
     */
    function destroyAvatar(avatar) {
        if (avatar) {
            // 3D 애니메이터에서 캐릭터 제거
            const data = avatar._avatarData;
            if (data) {
                const CharacterAnimator3D = window.CompanyView.CharacterAnimator3D;
                if (CharacterAnimator3D) {
                    CharacterAnimator3D.removeCharacter(data.sessionId);
                }
            }
            avatar.destroy({ children: true });
        }
    }

    // ==================== Export ====================
    window.CompanyView.Avatars = {
        createAvatar,
        setAvatarStatus,
        setAvatarAnimation,
        updateAvatar,
        setAvatarName,
        destroyAvatar,
        CHARACTER_CONFIG,
        ANIMATIONS,
    };

})();
