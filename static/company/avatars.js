/**
 * Avatar System - Cute cat avatars representing sessions
 * Each avatar is procedurally drawn with unique colors and accessories
 * Inspired by the kawaii office cat aesthetic
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    // ==================== Avatar Color Schemes ====================
    const CAT_PALETTES = [
        { name: 'tabby',    body: 0xE8C07A, belly: 0xFAE8C8, stripes: 0xC9996A, ears: 0xE8B060, nose: 0xF0A0A0 },
        { name: 'gray',     body: 0x8899AA, belly: 0xBBCCDD, stripes: 0x667788, ears: 0x8090A0, nose: 0xF0A0A0 },
        { name: 'orange',   body: 0xE8964A, belly: 0xFADCB8, stripes: 0xD0783A, ears: 0xE08840, nose: 0xF0A0A0 },
        { name: 'white',    body: 0xF0EDE8, belly: 0xFAFAFA, stripes: 0xE0DDD5, ears: 0xFFBBCC, nose: 0xFFAAAA },
        { name: 'black',    body: 0x3D3D4D, belly: 0x555565, stripes: 0x2D2D3D, ears: 0x353545, nose: 0xF0A0A0 },
        { name: 'calico',   body: 0xF0DCC0, belly: 0xFAEED8, stripes: 0xE08840, ears: 0xE8C8A0, nose: 0xF0A0A0 },
        { name: 'siamese',  body: 0xF0E0CC, belly: 0xFAF0E4, stripes: 0x8B7355, ears: 0x6B5340, nose: 0xDDA0A0 },
        { name: 'tuxedo',   body: 0x2D2D3D, belly: 0xF0F0F0, stripes: 0x222233, ears: 0x252535, nose: 0xF0A0A0 },
        { name: 'ginger',   body: 0xE8783A, belly: 0xFAC8A0, stripes: 0xD06020, ears: 0xD87030, nose: 0xF0A0A0 },
        { name: 'blue',     body: 0x7899BB, belly: 0xAABBDD, stripes: 0x5878A0, ears: 0x7090B0, nose: 0xEEAAAA },
    ];

    // Accessories
    const ACCESSORIES = [
        'none', 'glasses', 'bow', 'hat', 'headphones', 'scarf', 'crown'
    ];

    const SHIRT_COLORS = [
        0x5B9BD5, 0x6BBF6B, 0xE88BA8, 0xE5C95B, 0x9B7ED5,
        0xE8964A, 0x5BBCE5, 0xCC6666, 0x66B2A0, 0xBB88CC,
    ];

    // ==================== Avatar Sprite Generator ====================

    /**
     * Create a unique cat avatar for a session
     * @param {string} sessionId - Used to deterministically generate appearance
     * @param {string} sessionName - Displayed name
     * @returns {PIXI.Container} Avatar container
     */
    function createAvatar(sessionId, sessionName) {
        const hash = simpleHash(sessionId);
        const paletteIdx = hash % CAT_PALETTES.length;
        const palette = CAT_PALETTES[paletteIdx];
        const accessoryIdx = (hash >> 4) % ACCESSORIES.length;
        const accessory = ACCESSORIES[accessoryIdx];
        const shirtColor = SHIRT_COLORS[(hash >> 8) % SHIRT_COLORS.length];

        const container = new PIXI.Container();
        container._avatarData = {
            palette,
            accessory,
            shirtColor,
            sessionId,
            sessionName,
            animFrame: 0,
            animState: 'idle',   // idle, walking, working, thinking
            direction: 'down',   // up, down, left, right
            bobOffset: 0,
        };

        // Build the cat
        const catSprite = drawCat(palette, accessory, shirtColor, 'idle', 'down');
        catSprite.name = 'catBody';
        container.addChild(catSprite);

        // Name label
        const nameLabel = createNameLabel(sessionName || sessionId.substring(0, 6));
        nameLabel.name = 'nameLabel';
        nameLabel.y = -52;
        container.addChild(nameLabel);

        // Status bubble (hidden by default)
        const statusBubble = createStatusBubble();
        statusBubble.name = 'statusBubble';
        statusBubble.x = 16;
        statusBubble.y = -48;
        statusBubble.visible = false;
        container.addChild(statusBubble);

        // Shadow
        const shadow = new PIXI.Graphics();
        shadow.beginFill(0x000000, 0.12);
        shadow.drawEllipse(0, 4, 11, 5);
        shadow.endFill();
        shadow.name = 'shadow';
        container.addChildAt(shadow, 0);

        // Interaction area
        container.interactive = true;
        container.buttonMode = true;
        container.hitArea = new PIXI.Rectangle(-14, -48, 28, 56);

        return container;
    }

    /**
     * Draw the actual cat character
     */
    function drawCat(palette, accessory, shirtColor, animState, direction) {
        const g = new PIXI.Graphics();

        // ---- Body / Shirt ----
        // Rounded body (like a bean shape)
        g.beginFill(shirtColor);
        g.drawRoundedRect(-11, -4, 22, 18, 8);
        g.endFill();

        // Shirt collar detail
        g.beginFill(shirtColor === 0xF0EDE8 ? 0xDDDDDD : lightenColor(shirtColor, 30), 0.6);
        g.drawEllipse(0, -2, 7, 3);
        g.endFill();

        // ---- Head ----
        // Main head shape (round, slightly squished)
        g.beginFill(palette.body);
        g.drawEllipse(0, -18, 14, 12);
        g.endFill();

        // Cheeks (slightly wider at bottom)
        g.beginFill(palette.body);
        g.drawEllipse(-8, -14, 6, 5);
        g.endFill();
        g.beginFill(palette.body);
        g.drawEllipse(8, -14, 6, 5);
        g.endFill();

        // Belly/face patch
        g.beginFill(palette.belly);
        g.drawEllipse(0, -16, 8, 7);
        g.endFill();

        // ---- Ears ----
        // Left ear
        g.beginFill(palette.body);
        g.moveTo(-12, -26);
        g.lineTo(-6, -30);
        g.lineTo(-4, -22);
        g.closePath();
        g.endFill();
        // Inner ear
        g.beginFill(palette.ears);
        g.moveTo(-10, -26);
        g.lineTo(-7, -28);
        g.lineTo(-5, -23);
        g.closePath();
        g.endFill();

        // Right ear
        g.beginFill(palette.body);
        g.moveTo(12, -26);
        g.lineTo(6, -30);
        g.lineTo(4, -22);
        g.closePath();
        g.endFill();
        // Inner ear
        g.beginFill(palette.ears);
        g.moveTo(10, -26);
        g.lineTo(7, -28);
        g.lineTo(5, -23);
        g.closePath();
        g.endFill();

        // ---- Stripe Markings ----
        if (palette.name !== 'white' && palette.name !== 'tuxedo') {
            g.beginFill(palette.stripes, 0.25);
            // Forehead stripes
            g.drawRect(-1, -24, 2, 4);
            g.drawRect(-5, -23, 2, 3);
            g.drawRect(3, -23, 2, 3);
            g.endFill();
        }

        // Tuxedo special: white chest/face
        if (palette.name === 'tuxedo') {
            g.beginFill(0xF0F0F0);
            g.drawEllipse(0, -14, 5, 6);
            g.endFill();
        }

        // Calico spots
        if (palette.name === 'calico') {
            g.beginFill(0xE08840, 0.4);
            g.drawCircle(-6, -20, 4);
            g.endFill();
            g.beginFill(0x3D3D4D, 0.3);
            g.drawCircle(6, -16, 3);
            g.endFill();
        }

        // ---- Face ----
        // Eyes
        if (animState === 'working') {
            // Happy squint (like ^^)
            g.lineStyle(1.5, 0x333333);
            g.arc(-5, -18, 2.5, Math.PI * 0.2, Math.PI * 0.8);
            g.arc(5, -18, 2.5, Math.PI * 0.2, Math.PI * 0.8);
            g.lineStyle(0);
        } else {
            // Normal eyes
            g.beginFill(0x333333);
            g.drawCircle(-5, -18, 2.2);
            g.drawCircle(5, -18, 2.2);
            g.endFill();

            // Eye highlights
            g.beginFill(0xFFFFFF);
            g.drawCircle(-4.2, -19, 0.9);
            g.drawCircle(5.8, -19, 0.9);
            g.endFill();
        }

        // Nose
        g.beginFill(palette.nose);
        g.moveTo(0, -15);
        g.lineTo(-1.5, -13.5);
        g.lineTo(1.5, -13.5);
        g.closePath();
        g.endFill();

        // Mouth
        g.lineStyle(0.8, 0x777777, 0.5);
        g.moveTo(0, -13.5);
        g.lineTo(-2, -12);
        g.moveTo(0, -13.5);
        g.lineTo(2, -12);
        g.lineStyle(0);

        // Blush marks
        g.beginFill(0xFFAAAA, 0.25);
        g.drawEllipse(-9, -15, 3, 2);
        g.drawEllipse(9, -15, 3, 2);
        g.endFill();

        // Whiskers
        g.lineStyle(0.5, 0x999999, 0.3);
        // Left whiskers
        g.moveTo(-8, -15);
        g.lineTo(-18, -17);
        g.moveTo(-8, -14);
        g.lineTo(-17, -13);
        // Right whiskers
        g.moveTo(8, -15);
        g.lineTo(18, -17);
        g.moveTo(8, -14);
        g.lineTo(17, -13);
        g.lineStyle(0);

        // ---- Arms ----
        g.beginFill(palette.body);
        // Left arm
        g.drawRoundedRect(-14, -2, 5, 10, 2.5);
        // Right arm
        g.drawRoundedRect(9, -2, 5, 10, 2.5);
        g.endFill();

        // Paw pads
        g.beginFill(palette.belly, 0.7);
        g.drawCircle(-11.5, 7, 2);
        g.drawCircle(11.5, 7, 2);
        g.endFill();

        // ---- Tail ----
        g.lineStyle(3, palette.body);
        g.moveTo(10, 10);
        g.bezierCurveTo(18, 6, 20, -2, 16, -6);
        g.lineStyle(0);

        // Tail tip (stripe)
        if (palette.name !== 'white') {
            g.lineStyle(3, palette.stripes, 0.5);
            g.moveTo(17, -3);
            g.bezierCurveTo(18, -4, 17, -5, 16, -6);
            g.lineStyle(0);
        }

        // ---- Accessory ----
        drawAccessory(g, accessory, palette);

        return g;
    }

    /**
     * Draw accessory on the cat
     */
    function drawAccessory(g, accessory, palette) {
        switch (accessory) {
            case 'glasses':
                g.lineStyle(1.2, 0x4A4A4A);
                g.drawCircle(-5, -18, 3.5);
                g.drawCircle(5, -18, 3.5);
                g.moveTo(-1.5, -18);
                g.lineTo(1.5, -18);
                g.moveTo(-8.5, -18);
                g.lineTo(-12, -19);
                g.moveTo(8.5, -18);
                g.lineTo(12, -19);
                g.lineStyle(0);
                break;

            case 'bow':
                g.beginFill(0xFF6B8A);
                // Left loop
                g.moveTo(-3, -28);
                g.bezierCurveTo(-8, -32, -10, -25, -3, -26);
                // Right loop
                g.moveTo(3, -28);
                g.bezierCurveTo(8, -32, 10, -25, 3, -26);
                g.endFill();
                // Center knot
                g.beginFill(0xE55580);
                g.drawCircle(0, -27, 1.5);
                g.endFill();
                break;

            case 'hat':
                // Cowboy-ish hat
                g.beginFill(0xC9996A);
                g.drawEllipse(0, -28, 14, 4);
                g.endFill();
                g.beginFill(0xD4A574);
                g.drawRoundedRect(-7, -36, 14, 10, 4);
                g.endFill();
                // Hatband
                g.beginFill(0xA87642);
                g.drawRect(-7, -30, 14, 2);
                g.endFill();
                break;

            case 'headphones':
                g.lineStyle(2, 0x444444);
                g.arc(0, -22, 12, Math.PI * 1.15, Math.PI * 1.85);
                g.lineStyle(0);
                // Ear pads
                g.beginFill(0x555555);
                g.drawRoundedRect(-15, -22, 5, 8, 2);
                g.drawRoundedRect(10, -22, 5, 8, 2);
                g.endFill();
                // Cushions
                g.beginFill(0x888888);
                g.drawRoundedRect(-14, -21, 3, 6, 1);
                g.drawRoundedRect(11, -21, 3, 6, 1);
                g.endFill();
                break;

            case 'scarf':
                g.beginFill(0xE55B5B);
                g.drawRoundedRect(-10, -5, 20, 6, 2);
                g.endFill();
                // Scarf tail
                g.beginFill(0xE55B5B);
                g.drawRoundedRect(7, -3, 4, 10, 2);
                g.endFill();
                // Stripes
                g.beginFill(0xF0F0F0, 0.3);
                g.drawRect(-8, -3, 16, 2);
                g.endFill();
                break;

            case 'crown':
                g.beginFill(0xFFD700);
                g.moveTo(-6, -28);
                g.lineTo(-8, -24);
                g.lineTo(-4, -26);
                g.lineTo(0, -22);
                g.lineTo(4, -26);
                g.lineTo(8, -24);
                g.lineTo(6, -28);
                g.closePath();
                g.endFill();
                // Gems
                g.beginFill(0xFF3333);
                g.drawCircle(0, -25, 1.2);
                g.endFill();
                g.beginFill(0x3399FF);
                g.drawCircle(-4, -26.5, 0.8);
                g.endFill();
                g.beginFill(0x33CC33);
                g.drawCircle(4, -26.5, 0.8);
                g.endFill();
                break;
        }
    }

    /**
     * Create name label background pill
     */
    function createNameLabel(name) {
        const container = new PIXI.Container();

        // Text
        const text = new PIXI.Text(name, {
            fontFamily: 'Inter, Arial, sans-serif',
            fontSize: 9,
            fill: 0xFFFFFF,
            align: 'center',
            fontWeight: '600',
        });
        text.anchor.set(0.5, 0.5);

        // Background pill
        const padding = 4;
        const bg = new PIXI.Graphics();
        bg.beginFill(0x000000, 0.55);
        bg.drawRoundedRect(
            -text.width / 2 - padding,
            -text.height / 2 - 2,
            text.width + padding * 2,
            text.height + 4,
            6
        );
        bg.endFill();

        container.addChild(bg);
        container.addChild(text);

        return container;
    }

    /**
     * Create a thought/status bubble
     */
    function createStatusBubble() {
        const container = new PIXI.Container();

        const bg = new PIXI.Graphics();
        bg.beginFill(0xFFFFFF, 0.9);
        bg.drawRoundedRect(-12, -10, 24, 18, 6);
        bg.endFill();

        // Bubble tail
        bg.beginFill(0xFFFFFF, 0.9);
        bg.moveTo(-8, 8);
        bg.lineTo(-12, 14);
        bg.lineTo(-4, 8);
        bg.closePath();
        bg.endFill();

        // Outline
        bg.lineStyle(1, 0xCCCCCC, 0.5);
        bg.drawRoundedRect(-12, -10, 24, 18, 6);
        bg.lineStyle(0);

        container.addChild(bg);

        // Placeholder icon (will be changed per-status)
        const icon = new PIXI.Text('💻', {
            fontSize: 10,
        });
        icon.anchor.set(0.5, 0.5);
        icon.name = 'bubbleIcon';
        container.addChild(icon);

        return container;
    }

    /**
     * Update avatar's displayed status
     */
    function setAvatarStatus(avatarContainer, status) {
        const bubble = avatarContainer.getChildByName('statusBubble');
        if (!bubble) return;

        const data = avatarContainer._avatarData;

        let icon = '';
        let showBubble = true;

        switch (status) {
            case 'running':
                icon = '💻';
                data.animState = 'working';
                break;
            case 'thinking':
                icon = '💭';
                data.animState = 'working';
                break;
            case 'error':
                icon = '❌';
                data.animState = 'idle';
                break;
            case 'idle':
                showBubble = false;
                data.animState = 'idle';
                break;
            case 'success':
                icon = '✅';
                data.animState = 'idle';
                break;
            default:
                showBubble = false;
                data.animState = 'idle';
        }

        bubble.visible = showBubble;
        if (showBubble) {
            const iconText = bubble.getChildByName('bubbleIcon');
            if (iconText) {
                iconText.text = icon;
            }
        }
    }

    // ==================== Utility ====================

    function simpleHash(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        return Math.abs(hash);
    }

    function lightenColor(color, amount) {
        const r = Math.min(255, ((color >> 16) & 0xFF) + amount);
        const g = Math.min(255, ((color >> 8) & 0xFF) + amount);
        const b = Math.min(255, (color & 0xFF) + amount);
        return (r << 16) | (g << 8) | b;
    }

    // ==================== Export ====================
    window.CompanyView.Avatars = {
        createAvatar,
        setAvatarStatus,
        CAT_PALETTES,
        ACCESSORIES,
    };

})();
