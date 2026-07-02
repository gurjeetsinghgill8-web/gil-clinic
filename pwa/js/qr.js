/**
 * CardioQueue — QR Code Module
 * Generates QR codes inline using QRCode.js (no API, no network).
 */

function generateQR(containerId, text, size) {
    size = size || 180;
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = "";

    try {
        new QRCode(container, {
            text: text,
            width: size,
            height: size,
            colorDark: "#000000",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.H
        });
    } catch(e) {
        container.innerHTML = `<p style="color:red;font-size:0.8rem;">QR Error: ${e.message}</p>`;
    }
}
