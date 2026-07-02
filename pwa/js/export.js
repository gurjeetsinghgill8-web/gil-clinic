/**
 * CardioQueue — CSV Export Module
 * Exports patient + test data to CSV file for sharing/email.
 */

async function exportPatientsCSV() {
    const patients = await getAllPatients();

    if (patients.length === 0) {
        alert("⚠️ कोई डेटा नहीं है / No data to export.");
        return;
    }

    // Build CSV header
    const headers = [
        "Patient ID", "Name", "Mobile", "Age", "Gender",
        "Registration Date", "Test", "Status", "Token #",
        "Room", "Called At", "Started At", "Completed At",
        "Report Ready At", "Delivered At"
    ];

    const rows = [headers.join(",")];

    for (const p of patients) {
        const tests = await getTestsForPatient(p.patientId);
        if (tests.length === 0) {
            rows.push([
                `"${p.patientId}"`, `"${p.name}"`, `"${p.mobile}"`,
                p.age, `"${p.gender}"`, p.registrationDate,
                "", "", "", "", "", "", "", "", ""
            ].join(","));
        } else {
            for (const t of tests) {
                rows.push([
                    `"${p.patientId}"`, `"${p.name}"`, `"${p.mobile}"`,
                    p.age, `"${p.gender}"`, p.registrationDate,
                    `"${t.testName}"`, `"${t.status}"`, t.tokenNumber,
                    `"${t.room}"`, t.calledAt || "", t.startedAt || "",
                    t.completedAt || "", t.reportReadyAt || "", t.deliveredAt || ""
                ].join(","));
            }
        }
    }

    const csvContent = rows.join("\n");
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const filename = `CardioQueue_Export_${new Date().toISOString().slice(0, 10)}.csv`;

    // Try native share first (mobile friendly)
    if (navigator.share && navigator.canShare && navigator.canShare({ files: [new File([blob], filename, { type: "text/csv" })] })) {
        try {
            await navigator.share({
                title: "CardioQueue Export",
                text: "Patient data export from CardioQueue",
                files: [new File([blob], filename, { type: "text/csv" })]
            });
            return;
        } catch(e) {
            // User cancelled or share failed — fallback to download
        }
    }

    // Fallback: download link
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

async function exportTodayCSV() {
    const patients = await getTodayPatients();
    if (patients.length === 0) {
        alert("⚠️ आज का कोई डेटा नहीं है / No data for today.");
        return;
    }

    const headers = [
        "Patient ID", "Name", "Mobile", "Age", "Gender",
        "Test", "Status", "Token #", "Room"
    ];

    const rows = [headers.join(",")];

    for (const p of patients) {
        const tests = await getTestsForPatient(p.patientId);
        if (tests.length === 0) {
            rows.push([
                `"${p.patientId}"`, `"${p.name}"`, `"${p.mobile}"`,
                p.age, `"${p.gender}"`, "", "", "", ""
            ].join(","));
        } else {
            for (const t of tests) {
                rows.push([
                    `"${p.patientId}"`, `"${p.name}"`, `"${p.mobile}"`,
                    p.age, `"${p.gender}"`,
                    `"${t.testName}"`, `"${t.status}"`, t.tokenNumber,
                    `"${t.room}"`
                ].join(","));
            }
        }
    }

    const csvContent = rows.join("\n");
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const filename = `CardioQueue_Today_${new Date().toISOString().slice(0, 10)}.csv`;

    if (navigator.share && navigator.canShare && navigator.canShare({ files: [new File([blob], filename, { type: "text/csv" })] })) {
        try {
            await navigator.share({
                title: "CardioQueue Today Export",
                text: "Today's patient data",
                files: [new File([blob], filename, { type: "text/csv" })]
            });
            return;
        } catch(e) {}
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
