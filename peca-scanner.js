(() => {
    const cameraSelect = document.getElementById("piece-camera-select");
    const startButton = document.getElementById("piece-start-scanner");
    const stopButton = document.getElementById("piece-stop-scanner");
    const scanAgainButton = document.getElementById("piece-scan-again");
    const status = document.getElementById("piece-scanner-status");
    const result = document.getElementById("piece-scan-result");
    const scannedCode = document.getElementById("piece-scanned-code");
    const qrInput = document.getElementById("piece-qr-input");

    if (!cameraSelect || !startButton || !stopButton || !scanAgainButton ||
        !status || !result || !scannedCode || !qrInput) {
        return;
    }

    let scanner = null;
    let running = false;
    let startPending = false;
    let scanCaptured = false;
    let scanStartedAt = 0;
    let noCodeStatusShown = false;

    const setStatus = (message, isError = false) => {
        status.textContent = message;
        status.dataset.state = isError ? "erro" : "";
    };

    const updateControls = () => {
        startButton.hidden = running || startPending;
        stopButton.hidden = !running;
        scanAgainButton.hidden = running || startPending || !scannedCode.textContent;
        cameraSelect.disabled = running || startPending || cameraSelect.options.length < 2;
    };

    const stopScanner = async (preserveFeedback = false) => {
        if (!running) {
            return true;
        }

        running = false;
        try {
            await scanner.stop();
            if (!preserveFeedback) {
                setStatus("Câmera parada.");
            }
            return true;
        } catch (error) {
            running = true;
            setStatus("Não foi possível parar a câmera corretamente. Feche esta página para encerrar o acesso.", true);
            console.error("Falha ao parar o scanner de peças:", error);
            return false;
        } finally {
            updateControls();
        }
    };

    const handleDecodedCode = async (decodedText) => {
        const code = decodedText.trim();
        if (!code || !running || scanCaptured) {
            return;
        }

        scanCaptured = true;
        qrInput.value = code;
        qrInput.dispatchEvent(new Event("input", { bubbles: true }));
        scannedCode.textContent = code;
        result.hidden = false;
        qrInput.focus();
        setStatus("QR Code preenchido. Informe o código interno e a descrição.");
        await stopScanner(true);
    };

    const startCamera = async () => {
        running = true;
        try {
            scanStartedAt = Date.now();
            noCodeStatusShown = false;
            await window.TagControlQrScanner.start(
                scanner,
                cameraSelect,
                handleDecodedCode,
                () => {
                    if (!noCodeStatusShown && Date.now() - scanStartedAt >= 10000) {
                        noCodeStatusShown = true;
                        setStatus("Ainda não detectei o QR Code. Ajuste a distância, o foco e a iluminação e evite reflexos.", true);
                    }
                },
            );
            if (!scanCaptured) {
                setStatus("Câmera ativa. Centralize o QR Code na área de leitura.");
            }
        } catch (error) {
            running = false;
            throw error;
        }
    };

    const startScanner = async () => {
        if (startPending || running) {
            return;
        }
        if (typeof Html5Qrcode === "undefined" || typeof Html5QrcodeSupportedFormats === "undefined") {
            setStatus("A biblioteca do scanner não foi carregada. Atualize a página e tente novamente.", true);
            return;
        }
        if (!window.TagControlQrScanner) {
            setStatus("A configuração do scanner não foi carregada. Atualize a página e tente novamente.", true);
            return;
        }
        if (!window.isSecureContext ||
            !navigator.mediaDevices ||
            !navigator.mediaDevices.getUserMedia) {
            setStatus(window.TagControlQrScanner.getCameraErrorMessage(), true);
            return;
        }

        startPending = true;
        scanCaptured = false;
        result.hidden = true;
        scannedCode.textContent = "";
        updateControls();
        setStatus("Solicitando acesso à câmera...");

        try {
            scanner = window.TagControlQrScanner.createScanner("piece-reader");
            await startCamera();
        } catch (error) {
            running = false;
            console.error("Falha ao iniciar o scanner de peças:", error);
            setStatus(window.TagControlQrScanner.getCameraErrorMessage(error), true);
        } finally {
            startPending = false;
            updateControls();
        }
    };

    startButton.addEventListener("click", startScanner);
    stopButton.addEventListener("click", () => stopScanner());
    scanAgainButton.addEventListener("click", startScanner);
    updateControls();
})();
