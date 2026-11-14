// ========================================
// Modal Functions
// ========================================
function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
    document.body.style.overflow = '';
}

function splitmateInviteGroups() {
    return window.splitmateInviteGroupData || [];
}

function splitmateFindInviteGroup(groupId) {
    return splitmateInviteGroups().find(group => Number(group.id) === Number(groupId));
}

function updateSelectedGroupInviteButton(groupId) {
    const button = document.getElementById('inviteSelectedGroupBtn');
    if (!button) return;

    const group = splitmateFindInviteGroup(groupId);
    const isAdmin = group && Number(group.admin_id) === Number(window.splitmateCurrentUserId);
    button.hidden = !isAdmin;
    button.disabled = !isAdmin;
    if (isAdmin) {
        button.dataset.groupId = group.id;
    }
}

function openInviteMemberModal(groupId) {
    const group = splitmateFindInviteGroup(groupId);
    if (!group) return;

    document.getElementById('inviteGroupName').textContent = group.name;
    document.getElementById('inviteMemberForm').action = `/group/${group.id}/invites`;
    document.getElementById('inviteEmail').value = '';
    document.getElementById('inviteResult').hidden = true;
    document.getElementById('inviteLink').value = '';
    document.getElementById('sendInviteBtn').disabled = false;
    document.getElementById('sendInviteBtn').textContent = 'Send Invite';
    openModal('inviteMemberModal');
}

async function copyInviteLink() {
    const input = document.getElementById('inviteLink');
    const button = document.getElementById('copyInviteLinkBtn');
    if (!input || !input.value) return;

    try {
        await navigator.clipboard.writeText(input.value);
        button.textContent = 'Copied';
    } catch (error) {
        input.select();
        document.execCommand('copy');
        button.textContent = 'Copied';
    }

    window.setTimeout(() => {
        button.textContent = 'Copy';
    }, 1800);
}

async function copySplitmateInviteLink() {
    const input = document.getElementById('splitmateInviteLink');
    const button = document.getElementById('copySplitmateInviteLinkBtn');
    if (!input || !input.value) return;

    try {
        await navigator.clipboard.writeText(input.value);
        button.textContent = 'Copied';
    } catch (error) {
        input.select();
        document.execCommand('copy');
        button.textContent = 'Copied';
    }

    window.setTimeout(() => {
        button.textContent = 'Copy';
    }, 1800);
}

document.addEventListener('submit', async event => {
    if (event.target.id !== 'inviteMemberForm') return;

    event.preventDefault();
    const form = event.target;
    const button = document.getElementById('sendInviteBtn');
    const result = document.getElementById('inviteResult');
    const resultTitle = document.getElementById('inviteResultTitle');
    const resultText = document.getElementById('inviteResultText');
    const linkInput = document.getElementById('inviteLink');

    button.disabled = true;
    button.textContent = 'Sending...';
    result.hidden = true;

    try {
        const response = await fetch(form.action, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'fetch'
            },
            body: new FormData(form)
        });
        const data = await response.json();

        result.hidden = false;
        result.classList.toggle('invite-result-error', !response.ok);
        resultTitle.textContent = response.ok
            ? (data.already_member ? 'Already a member' : (data.email_sent ? 'Invite sent' : 'Invite link ready'))
            : 'Invite failed';
        resultText.textContent = data.message || data.error || 'Could not create this invite.';
        linkInput.value = data.invite_url || '';
        linkInput.parentElement.hidden = !data.invite_url;

        if (response.ok && data.invite_url) {
            form.reset();
        }
    } catch (error) {
        result.hidden = false;
        result.classList.add('invite-result-error');
        resultTitle.textContent = 'Invite failed';
        resultText.textContent = 'Could not create this invite right now.';
        linkInput.value = '';
        linkInput.parentElement.hidden = true;
    } finally {
        button.disabled = false;
        button.textContent = 'Send Invite';
    }
});

document.addEventListener('submit', async event => {
    if (event.target.id !== 'inviteSplitmateForm') return;

    event.preventDefault();
    const form = event.target;
    const button = document.getElementById('sendSplitmateInviteBtn');
    const result = document.getElementById('splitmateInviteResult');
    const resultTitle = document.getElementById('splitmateInviteResultTitle');
    const resultText = document.getElementById('splitmateInviteResultText');
    const linkInput = document.getElementById('splitmateInviteLink');

    button.disabled = true;
    button.textContent = 'Sending...';
    result.hidden = true;

    try {
        const response = await fetch(form.action, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'fetch'
            },
            body: new FormData(form)
        });
        const data = await response.json();

        result.hidden = false;
        result.classList.toggle('invite-result-error', !response.ok);
        resultTitle.textContent = response.ok
            ? (data.already_user ? 'Already on Splitmate' : (data.email_sent ? 'Invite sent' : 'Invite link ready'))
            : 'Invite failed';
        resultText.textContent = data.message || data.error || 'Could not create this invite.';
        linkInput.value = data.invite_url || '';
        linkInput.parentElement.hidden = !data.invite_url;

        if (response.ok && data.invite_url) {
            form.reset();
        }
    } catch (error) {
        result.hidden = false;
        result.classList.add('invite-result-error');
        resultTitle.textContent = 'Invite failed';
        resultText.textContent = 'Could not create this invite right now.';
        linkInput.value = '';
        linkInput.parentElement.hidden = true;
    } finally {
        button.disabled = false;
        button.textContent = 'Send Invite';
    }
});

document.addEventListener('click', event => {
    if (event.target.id === 'copyInviteLinkBtn') {
        copyInviteLink();
    }

    if (event.target.id === 'copySplitmateInviteLinkBtn') {
        copySplitmateInviteLink();
    }
});

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
        document.body.style.overflow = '';
    }

    document.querySelectorAll('.account-menu[open]').forEach(menu => {
        if (!menu.contains(e.target)) {
            menu.removeAttribute('open');
        }
    });
});

// Close modal with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(modal => {
            modal.classList.remove('active');
        });
        document.querySelectorAll('.account-menu[open]').forEach(menu => {
            menu.removeAttribute('open');
        });
        document.body.style.overflow = '';
    }
});

// ========================================
// Flash Message Auto-dismiss
// ========================================
document.querySelectorAll('.flash-message').forEach(msg => {
    setTimeout(() => {
        msg.style.opacity = '0';
        msg.style.transform = 'translateY(-10px)';
        setTimeout(() => msg.remove(), 300);
    }, 5000);
});

// ========================================
// Mobile Sidebar Toggle
// ========================================
function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('open');
}

// ========================================
// Form Validation Helpers
// ========================================
const EMAIL_MAX_LENGTH = 120;
const EMAIL_PATTERN = /^[^\s@]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
let generatedFieldId = 0;

function hasRealisticEmailDomain(email) {
    const parts = String(email || '').toLowerCase().split('@');
    if (parts.length !== 2) {
        return false;
    }

    const labels = parts[1].split('.');
    if (labels.length < 2) {
        return false;
    }

    const tld = labels[labels.length - 1];
    const domainLabels = labels.slice(0, -1);
    return /^[a-z]{2,}$/.test(tld) && domainLabels.some(label => /[a-z]/.test(label));
}

// Mirrors app/email_validation.py: big providers people mistype or cut short (name@gmail.c, name@gmial.com).
const SINGLE_DOMAIN_PROVIDERS = { gmail: 'gmail.com', googlemail: 'googlemail.com', icloud: 'icloud.com' };
const REGIONAL_PROVIDERS = ['yahoo', 'hotmail', 'outlook', 'live', 'aol', 'msn'];
const MISTYPED_PROVIDERS = {
    gmial: 'gmail.com', gmai: 'gmail.com', gamil: 'gmail.com', gnail: 'gmail.com', gmaill: 'gmail.com',
    gmal: 'gmail.com', gmeil: 'gmail.com', gmali: 'gmail.com', hotmial: 'hotmail.com', hotmal: 'hotmail.com',
    hotmil: 'hotmail.com', outlok: 'outlook.com', outllok: 'outlook.com', yaho: 'yahoo.com',
    yahooo: 'yahoo.com', yhoo: 'yahoo.com', iclod: 'icloud.com', icoud: 'icloud.com'
};
const MISTYPED_COM = ['c', 'co', 'cm', 'cmo', 'con', 'om', 'comm', 'coom', 'cpm', 'xom', 'vom'];

function suggestedEmailDomain(email) {
    const parts = String(email || '').toLowerCase().split('@');
    if (parts.length !== 2) {
        return null;
    }
    const domain = parts[1];
    const labels = domain.split('.');
    const provider = labels[0];
    if (SINGLE_DOMAIN_PROVIDERS[provider]) {
        return domain !== SINGLE_DOMAIN_PROVIDERS[provider] ? SINGLE_DOMAIN_PROVIDERS[provider] : null;
    }
    if (MISTYPED_PROVIDERS[provider]) {
        return MISTYPED_PROVIDERS[provider];
    }
    if (REGIONAL_PROVIDERS.includes(provider) && labels.length === 2 && MISTYPED_COM.includes(labels[1])) {
        return `${provider}.com`;
    }
    return null;
}

function validateEmail(email) {
    const normalizedEmail = String(email || '').trim();
    return normalizedEmail.length <= EMAIL_MAX_LENGTH
        && EMAIL_PATTERN.test(normalizedEmail)
        && hasRealisticEmailDomain(normalizedEmail)
        && !suggestedEmailDomain(normalizedEmail);
}

function validatePassword(password) {
    return password.length >= 8 && /[A-Z]/.test(password) && /[a-z]/.test(password)
        && /[0-9]/.test(password) && /[^A-Za-z0-9]/.test(password);
}

function ensureElementId(element, prefix) {
    if (!element.id) {
        generatedFieldId += 1;
        element.id = `${prefix}_${generatedFieldId}`;
    }
    return element.id;
}

function emailValidationMessage(input) {
    const email = input.value.trim();

    if (!email) {
        return input.required ? 'Email is required.' : '';
    }

    if (email.length > EMAIL_MAX_LENGTH) {
        return `Email must be ${EMAIL_MAX_LENGTH} characters or fewer.`;
    }

    const suggestion = suggestedEmailDomain(email);
    if (suggestion) {
        return `Check the email address. Did you mean ${email.split('@')[0]}@${suggestion}?`;
    }

    if ((input.validity && input.validity.typeMismatch) || !validateEmail(email)) {
        return 'Enter a real email address like name@gmail.com, name@hotmail.com, or name@yahoo.com.';
    }

    return '';
}

function emailErrorElement(input) {
    const inputId = ensureElementId(input, 'email_field');
    const errorId = `${inputId}_error`;
    let error = document.getElementById(errorId);

    if (!error) {
        error = document.createElement('small');
        error.id = errorId;
        error.className = 'field-error email-field-error';
        error.setAttribute('aria-live', 'polite');
        error.hidden = true;
        input.insertAdjacentElement('afterend', error);
    }

    const describedBy = new Set((input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
    describedBy.add(errorId);
    input.setAttribute('aria-describedby', Array.from(describedBy).join(' '));

    return error;
}

function setEmailValidationState(input, showMessage = false) {
    const message = emailValidationMessage(input);
    const error = emailErrorElement(input);

    input.setCustomValidity(message);
    input.classList.toggle('is-invalid', Boolean(message) && showMessage);
    input.classList.toggle('is-valid', !message && showMessage && Boolean(input.value.trim()));

    if (message && showMessage) {
        error.textContent = message;
        error.hidden = false;
        input.setAttribute('aria-invalid', 'true');
    } else {
        error.textContent = '';
        error.hidden = true;
        input.removeAttribute('aria-invalid');
    }

    return !message;
}

function initializeEmailValidation() {
    const emailInputs = Array.from(document.querySelectorAll('input[type="email"]'));

    emailInputs.forEach(input => {
        input.setAttribute('inputmode', 'email');
        input.setAttribute('spellcheck', 'false');
        input.setAttribute('title', 'Enter a real email address like name@gmail.com, name@hotmail.com, or name@yahoo.com.');
        setEmailValidationState(input, false);

        input.addEventListener('input', () => {
            const shouldShowMessage = input.dataset.emailTouched === '1' || Boolean(input.value.trim());
            setEmailValidationState(input, shouldShowMessage);
        });

        input.addEventListener('blur', () => {
            input.dataset.emailTouched = '1';
            input.value = input.value.trim();
            setEmailValidationState(input, true);
        });
    });

    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', event => {
            const formEmailInputs = Array.from(form.querySelectorAll('input[type="email"]'));
            let firstInvalidEmail = null;

            formEmailInputs.forEach(input => {
                input.dataset.emailTouched = '1';
                input.value = input.value.trim();

                if (!setEmailValidationState(input, true) && !firstInvalidEmail) {
                    firstInvalidEmail = input;
                }
            });

            if (firstInvalidEmail) {
                event.preventDefault();
                firstInvalidEmail.focus();
                if (typeof firstInvalidEmail.reportValidity === 'function') {
                    firstInvalidEmail.reportValidity();
                }
            }
        });
    });
}

// ========================================
// Number Formatting
// ========================================
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// ========================================
// Date Formatting
// ========================================
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatDateTime(dateString) {
    return new Date(dateString).toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// ========================================
// Notification Settings
// ========================================
const SPLITMATE_NOTIFICATIONS_KEY = 'splitmate-notifications-enabled';

function splitmateNotificationsSupported() {
    return 'Notification' in window;
}

function splitmateNotificationsEnabled() {
    try {
        return localStorage.getItem(SPLITMATE_NOTIFICATIONS_KEY) === 'true';
    } catch (error) {
        return false;
    }
}

function splitmateSetNotificationsStorage(enabled) {
    try {
        localStorage.setItem(SPLITMATE_NOTIFICATIONS_KEY, enabled ? 'true' : 'false');
    } catch (error) {
        return;
    }
}

function splitmateNotificationPermission() {
    if (!splitmateNotificationsSupported()) {
        return 'unsupported';
    }
    return Notification.permission;
}

function splitmateCanShowTaskNotifications() {
    return splitmateNotificationsEnabled() && splitmateNotificationPermission() === 'granted';
}

function splitmateNotificationStatusText() {
    const permission = splitmateNotificationPermission();

    if (permission === 'unsupported') {
        return 'Not supported';
    }

    if (permission === 'denied') {
        return 'Blocked';
    }

    if (splitmateNotificationsEnabled() && permission === 'granted') {
        return 'On';
    }

    if (splitmateNotificationsEnabled() && permission === 'default') {
        return 'Needs permission';
    }

    return 'Off';
}

function splitmatePermissionStatusText() {
    const permission = splitmateNotificationPermission();
    const labels = {
        unsupported: 'Not supported',
        default: 'Not requested',
        granted: 'Allowed',
        denied: 'Blocked'
    };

    return labels[permission] || 'Not requested';
}

function splitmateUpdateNotificationControls() {
    const permission = splitmateNotificationPermission();
    const unsupported = permission === 'unsupported';
    const blocked = permission === 'denied';
    const enabled = splitmateNotificationsEnabled() && !unsupported && !blocked;

    if (enabled !== splitmateNotificationsEnabled()) {
        splitmateSetNotificationsStorage(false);
    }

    document.querySelectorAll('[data-notification-toggle]').forEach(toggle => {
        toggle.checked = enabled;
        toggle.disabled = unsupported || blocked;
    });

    document.querySelectorAll('[data-notification-status]').forEach(status => {
        status.textContent = splitmateNotificationStatusText();
    });

    document.querySelectorAll('[data-notification-permission-status]').forEach(status => {
        status.textContent = splitmatePermissionStatusText();
    });

    document.querySelectorAll('[data-notification-permission]').forEach(button => {
        button.disabled = unsupported || permission === 'granted' || blocked;
        button.textContent = permission === 'granted' ? 'Allowed' : 'Allow';
        if (blocked) {
            button.textContent = 'Blocked';
        }
        if (unsupported) {
            button.textContent = 'Unavailable';
        }
    });
}

async function splitmateSetNotificationsEnabled(enabled) {
    if (enabled && !splitmateNotificationsSupported()) {
        splitmateSetNotificationsStorage(false);
        splitmateUpdateNotificationControls();
        return false;
    }

    if (enabled && Notification.permission === 'default') {
        await Notification.requestPermission();
    }

    const canEnable = enabled && Notification.permission === 'granted';
    splitmateSetNotificationsStorage(canEnable);
    splitmateUpdateNotificationControls();
    document.dispatchEvent(new CustomEvent('splitmate:notification-setting-changed', {
        detail: { enabled: canEnable }
    }));
    return canEnable;
}

function initializeNotificationSettings() {
    document.querySelectorAll('[data-notification-toggle]').forEach(toggle => {
        toggle.addEventListener('change', async () => {
            await splitmateSetNotificationsEnabled(toggle.checked);
        });
    });

    document.querySelectorAll('[data-notification-permission]').forEach(button => {
        button.addEventListener('click', async () => {
            await splitmateSetNotificationsEnabled(true);
        });
    });

    splitmateUpdateNotificationControls();
}

window.splitmateNotificationsEnabled = splitmateNotificationsEnabled;
window.splitmateCanShowTaskNotifications = splitmateCanShowTaskNotifications;

// ========================================
// Support Chat
// ========================================
function splitmateSupportReply(message) {
    const text = String(message || '').toLowerCase();

    if (!text.trim()) {
        return 'Tell me what is happening and I will point you to the right place.';
    }

    if (/(invite|join|member|friend|email)/.test(text)) {
        return 'For invite issues, open the group, use Group Invite, and copy the invite link if email sending is not working. Check that the email address is typed correctly.';
    }

    if (/(group|create|admin|nickname|remove)/.test(text)) {
        return 'For group issues, go to Home, choose Your Groups, then use + Group or Manage. Only the group admin can invite, rename nicknames, or remove members.';
    }

    if (/(split|expense|owe|owed|payment|settle|amount|receipt)/.test(text)) {
        return 'For split issues, choose a group on Split, add the expense amount, payer, and split method, then check balances. If a payment looks wrong, use the payment history before adding another settlement.';
    }

    if (/(task|reminder|calendar|due|notify|notification)/.test(text)) {
        return 'For task reminders, add a reminder time on Tasks, then turn on Task Notifications in Settings and allow browser permission. Notifications only show when permission is allowed.';
    }

    if (/(note|notes|grocery|price|list|compare)/.test(text)) {
        return 'Notes can be plain text. Compare Prices only appears for grocery, shopping, or list-style notes, so rent or normal reminders stay clean.';
    }

    if (/(theme|dark|light|color|logo)/.test(text)) {
        return 'Theme is now in Profile & Settings. Toggle it there, and Splitmate will remember your light or dark choice on this browser.';
    }

    if (/(point|points|reward|gift|redeem|cash|money)/.test(text)) {
        return 'Earning Splitmate Points is paused for now. Points you already have are kept, and rewards become available when your points reach the listed tier.';
    }

    if (/(premium|membership|member|subscribe|subscription|plus|ads|ad)/.test(text)) {
        return 'Membership is in Profile & Settings. Free keeps the core app, while Plus is planned for an ad-light experience, richer grocery price tools, and advanced insights after store billing is connected.';
    }

    if (/(launch|android|ios|store|app store|play store)/.test(text)) {
        return 'For launch, the biggest items are rebuilding the mobile app package, adding app-store billing where needed, testing payments and rewards, privacy policy, screenshots, and store review submission.';
    }

    if (/(profile|password|qr|account|login)/.test(text)) {
        return 'For account issues, open Profile. You can edit details, change your password, download your profile QR, and update settings from that page.';
    }

    if (/(safari|https|http|phone|mobile|laptop|local|server)/.test(text)) {
        return 'For local testing, use the exact local address shown by the server. If Safari blocks HTTP, temporarily allow HTTP warnings or test with Chrome/Firefox on the same Wi-Fi.';
    }

    return 'I can help with groups, invites, splits, notes, tasks, notifications, theme, profile, and local testing. Try describing which page you are on and what you clicked.';
}

function splitmateAddSupportMessage(role, text) {
    const log = document.getElementById('supportChatLog');
    if (!log) return;

    const bubble = document.createElement('div');
    bubble.className = `support-chat-message support-chat-${role}`;
    bubble.textContent = text;
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
}

function initializeSupportChat() {
    const form = document.getElementById('supportChatForm');
    const input = document.getElementById('supportChatInput');
    const log = document.getElementById('supportChatLog');

    if (!form || !input || !log) {
        return;
    }

    if (!log.children.length) {
        splitmateAddSupportMessage('bot', 'Hi, I can help troubleshoot Splitmate. Tell me what is not working.');
    }

    form.addEventListener('submit', event => {
        event.preventDefault();
        const message = input.value.trim();
        if (!message) return;

        splitmateAddSupportMessage('user', message);
        input.value = '';

        window.setTimeout(() => {
            splitmateAddSupportMessage('bot', splitmateSupportReply(message));
        }, 250);
    });
}

// ========================================
// Initialize
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    initializeEmailValidation();
    initializeNotificationSettings();
    initializeSupportChat();

    const passwordIcons = {
        eye: `
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"></path>
                <circle cx="12" cy="12" r="3"></circle>
            </svg>
        `,
        eyeOff: `
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path d="M3 3l18 18"></path>
                <path d="M10.6 10.6A2 2 0 0 0 13.4 13.4"></path>
                <path d="M9.9 4.2A10.6 10.6 0 0 1 12 4c6.5 0 10 8 10 8a17.8 17.8 0 0 1-3.2 4.3"></path>
                <path d="M6.6 6.6C3.6 8.7 2 12 2 12s3.5 8 10 8a10.5 10.5 0 0 0 5.4-1.5"></path>
            </svg>
        `
    };

    function setPasswordToggleIcon(toggle, isVisible) {
        toggle.innerHTML = isVisible ? passwordIcons.eyeOff : passwordIcons.eye;
        toggle.setAttribute('aria-label', isVisible ? 'Hide password' : 'Show password');
        toggle.setAttribute('title', isVisible ? 'Hide password' : 'Show password');
    }

    document.querySelectorAll('input[type="password"]').forEach(input => {
        if (input.closest('.password-field')) {
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'password-field';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'password-toggle';
        setPasswordToggleIcon(toggle, false);

        toggle.addEventListener('click', () => {
            const shouldShow = input.type === 'password';
            input.type = shouldShow ? 'text' : 'password';
            setPasswordToggleIcon(toggle, shouldShow);
        });

        wrapper.appendChild(toggle);
    });

    // Set minimum date for datetime inputs to now
    const now = new Date();
    const localDatetime = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16);

    document.querySelectorAll('input[type="datetime-local"]').forEach(input => {
        if (!input.value) {
            input.min = localDatetime;
        }
    });
});


