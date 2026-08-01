/**
 * GIL CLINIC — Universal WhatsApp Sanitizer & Link Engine
 * 
 * Ensures phone numbers are properly sanitized and formatted with country code (+91)
 * before generating wa.me links. Resolves invalid number / Iran (+98) default bugs.
 */

/**
 * Sanitizes phone numbers for WhatsApp integration.
 * @param {string|number} phone Raw phone number input
 * @returns {string|null} Sanitized number with country code (e.g., 919876543210) or null if invalid
 */
function sanitizePhoneNumber(phone) {
  if (!phone) return null;
  // Strip all non-numeric characters (spaces, dashes, parens, plus sign)
  let cleaned = String(phone).replace(/\D/g, '');

  // 10 digits -> Indian mobile number (e.g. 9876543210 -> 919876543210)
  if (cleaned.length === 10) {
    return '91' + cleaned;
  }

  // 11 digits starting with 0 -> Indian mobile with leading zero (e.g. 09876543210 -> 919876543210)
  if (cleaned.length === 11 && cleaned.startsWith('0')) {
    return '91' + cleaned.substring(1);
  }

  // 12 digits starting with 91 -> Indian mobile with country code (e.g. 919876543210)
  if (cleaned.length === 12 && cleaned.startsWith('91')) {
    return cleaned;
  }

  // Generic international fallback (10 to 15 digits)
  if (cleaned.length >= 10 && cleaned.length <= 15) {
    return cleaned;
  }

  return null;
}

/**
 * Builds a valid wa.me URL.
 * @param {string} phone Phone number
 * @param {string} message Pre-filled WhatsApp message
 * @returns {string} Fully encoded wa.me URL
 */
function buildWhatsAppUrl(phone, message) {
  const sanitized = sanitizePhoneNumber(phone);
  const encodedMsg = encodeURIComponent(message || '');
  if (sanitized) {
    return `https://wa.me/${sanitized}?text=${encodedMsg}`;
  }
  return `https://wa.me/?text=${encodedMsg}`;
}

/**
 * Safely opens WhatsApp in a new tab/app window.
 * @param {string} phone Phone number
 * @param {string} message Pre-filled WhatsApp message
 * @returns {boolean} Success status
 */
function openWhatsApp(phone, message) {
  const sanitized = sanitizePhoneNumber(phone);
  if (!sanitized && phone) {
    const errorMsg = '⚠️ Invalid phone number format: ' + phone;
    if (typeof showToast === 'function') {
      showToast(errorMsg, 'warning');
    } else {
      alert(errorMsg);
    }
    return false;
  }
  const url = buildWhatsAppUrl(phone, message);
  window.open(url, '_blank');
  if (typeof showToast === 'function') {
    showToast('📱 WhatsApp opened', 'success');
  }
  return true;
}

// Make functions available globally on window
window.sanitizePhoneNumber = sanitizePhoneNumber;
window.buildWhatsAppUrl = buildWhatsAppUrl;
window.openWhatsApp = openWhatsApp;
