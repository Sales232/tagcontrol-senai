(() => {
    const cameraSelect = document.getElementById("camera-select");
    const startButton = document.getElementById("start-scanner");
    const stopButton = document.getElementById("stop-scanner");
    const scanAgainButton = document.getElementById("scan-again");
    const status = document.getElementById("scanner-status");
    const result = document.getElementById("scan-result");
    const scannedCode = document.getElementById("scanned-code");
    const readerElement = document.getElementById("reader");
    const pedidoProgressValue = document.getElementById("pedido-progress-value");
    const pedidoProgressPercent = document.getElementById("pedido-progress-percent");
    const pedidoProgressStatus = document.getElementById("pedido-progress-status");
    const pedidoId = document.querySelector("main[data-pedido-id]")?.dataset.pedidoId;

    if (!cameraSelect || !startButton || !stopButton || !scanAgainButton ||
        !status || !result || !scannedCode || !readerElement) {
        return;
    }

    const setStatus = (message, state = "") => {
        status.textContent = message;
        if (state) {
            status.dataset.state = state;
        } else {
            delete status.dataset.state;
        }
    };

    const setResultState = (state) => {
        if (state) {
            result.dataset.state = state;
        } else {
            delete result.dataset.state;
        }
    };

    const updateProgress = (progress) => {
        if (!progress || !pedidoProgressValue || !pedidoProgressPercent) {
            return;
        }
        pedidoProgressValue.textContent = `${progress.quantidade_validada} / ${progress.total_necessario} itens`;
        pedidoProgressPercent.textContent = `(${progress.percentual}%)`;
        if (pedidoProgressStatus) {
            const progressMessages = {
                finalizado: "Separação finalizada",
                em_andamento: "Separação em andamento",
                sem_itens: "Pedido sem itens",
            };
            pedidoProgressStatus.textContent = progressMessages[progress.status] || "Estado do pedido indisponível";
            pedidoProgressStatus.dataset.state = progress.status || "erro";
        }
    };

    const scannerErrorMessage = (error) => {
        if (!window.isSecureContext) {
            return "A câmera exige uma conexão segura. Use HTTPS ou localhost.";
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            return "Este navegador não oferece acesso à câmera. Tente um navegador atualizado.";
        }
        if (error && (error.name === "NotAllowedError" || error.name === "PermissionDeniedError")) {
            return "Permissão da câmera negada. Autorize o acesso nas configurações do navegador e tente novamente.";
        }
        if (error && (error.name === "NotFoundError" || error.name === "DevicesNotFoundError")) {
            return "Nenhuma câmera foi encontrada neste dispositivo.";
        }
        if (error && (error.name === "NotReadableError" || error.name === "TrackStartError")) {
            return "A câmera não está disponível. Feche outros aplicativos que possam estar usando-a.";
        }
        if (error && error.name === "OverconstrainedError") {
            return "A câmera selecionada não está disponível. Escolha outra câmera e tente novamente.";
        }
        return "Não foi possível iniciar a câmera. Verifique as permissões e tente novamente.";
    };

    let scanner = null;
    let running = false;
    let startPending = false;
    let scanInFlight = false;
    let scanStartedAt = 0;
    let noCodeStatusShown = false;

    const updateControls = () => {
        startButton.hidden = running || startPending;
        stopButton.hidden = !running;
        scanAgainButton.hidden = running || startPending || !scannedCode.textContent;
        cameraSelect.disabled = running || startPending || cameraSelect.options.length < 2;
    };

    const stopScanner = async (preserveFeedback = false) => {
        if (!running) {
            return;
        }
        try {
            await scanner.stop();
            running = false;
            if (!preserveFeedback) {
                setStatus("Câmera parada.");
                setResultState("");
            }
        } catch (error) {
            setStatus("Não foi possível parar a câmera corretamente. Feche esta página para encerrar o acesso.", "erro");
            console.error("Falha ao parar o scanner:", error);
        } finally {
            updateControls();
        }
    };

    const startScanner = async () => {
        if (startPending || running) {
            return;
        }
        if (typeof Html5Qrcode === "undefined" || typeof Html5QrcodeSupportedFormats === "undefined") {
            setStatus("A biblioteca do scanner não foi carregada. Atualize a página e tente novamente.", "erro");
            return;
        }
        if (!window.isSecureContext ||
            !navigator.mediaDevices ||
            !navigator.mediaDevices.getUserMedia) {
            setStatus(scannerErrorMessage(), "erro");
            return;
        }

        startPending = true;
        scanInFlight = false;
        result.hidden = true;
        setResultState("");
        scannedCode.textContent = "";
        updateControls();
        setStatus("Solicitando acesso à câmera...");

        try {
            scanner = new Html5Qrcode("reader", {
                formatsToSupport: [
                    Html5QrcodeSupportedFormats.EAN_13,
                    Html5QrcodeSupportedFormats.EAN_8,
                    Html5QrcodeSupportedFormats.UPC_A,
                    Html5QrcodeSupportedFormats.UPC_E,
                    Html5QrcodeSupportedFormats.CODE_128,
                    Html5QrcodeSupportedFormats.CODE_39,
                    Html5QrcodeSupportedFormats.ITF,
                ],
            });
            const cameras = await Html5Qrcode.getCameras();
            if (!cameras.length) {
                throw new DOMException("Nenhuma câmera encontrada.", "NotFoundError");
            }

            const previousCameraId = cameraSelect.value;
            cameraSelect.replaceChildren();
            cameras.forEach((camera, index) => {
                const option = document.createElement("option");
                option.value = camera.id;
                option.textContent = camera.label || `Câmera ${index + 1}`;
                cameraSelect.append(option);
            });

            if (cameras.some((camera) => camera.id === previousCameraId)) {
                cameraSelect.value = previousCameraId;
            } else {
                const rearCamera = cameras.find((camera) => /back|rear|environment|traseir/i.test(camera.label));
                cameraSelect.value = rearCamera ? rearCamera.id : cameras[0].id;
            }

            const cameraId = cameraSelect.value;
            running = true;
            scanStartedAt = Date.now();
            noCodeStatusShown = false;
            await scanner.start(
                cameraId,
                { fps: 10, qrbox: { width: 280, height: 140 } },
                async (decodedText) => {
                    const code = decodedText.trim();
                    if (!code || !running || scanInFlight) {
                        return;
                    }

                    scanInFlight = true;
                    scannedCode.textContent = code;
                    result.hidden = false;
                    setStatus("Validando código no pedido...");

                    try {
                        const response = await fetch(`/pedidos/${pedidoId}/scanner/validar`, {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({ codigo: code }),
                        });

                        const payload = await response.json();
                        if (!response.ok && payload && payload.message) {
                            setStatus(payload.message, "erro");
                            setResultState("erro");
                        } else if (payload && payload.message) {
                            setStatus(payload.message, payload.status);
                            updateProgress(payload.progress);
                            setResultState(payload.status);
                        } else {
                            setStatus("Código validado, mas a resposta do servidor não retornou o status esperado.", "erro");
                            setResultState("erro");
                        }

                        if (payload && payload.status === "sucesso") {
                            scannedCode.textContent = `${code} · OK`;
                        } else if (payload && payload.status === "duplicada") {
                            scannedCode.textContent = `${code} · DUPLICADA`;
                        } else if (payload && payload.status === "fora_do_pedido") {
                            scannedCode.textContent = `${code} · FORA DO PEDIDO`;
                        }
                    } catch (error) {
                        console.error("Falha ao validar código lido:", error);
                        setStatus("Não foi possível validar o código. Verifique sua conexão e tente novamente.", "erro");
                        setResultState("erro");
                    }

                    await stopScanner(true);
                },
                () => {
                    if (!noCodeStatusShown && Date.now() - scanStartedAt >= 10000) {
                        noCodeStatusShown = true;
                        setStatus("Nenhum código válido foi detectado. Ajuste o foco, aproxime o código e tente outra vez.", "erro");
                    }
                },
            );
            setStatus("Câmera ativa. Centralize o código de barras na área de leitura.");
        } catch (error) {
            running = false;
            setStatus(scannerErrorMessage(error), "erro");
        } finally {
            startPending = false;
            updateControls();
        }
    };

    startButton.addEventListener("click", startScanner);
    stopButton.addEventListener("click", stopScanner);
    scanAgainButton.addEventListener("click", startScanner);
    updateControls();
})();
