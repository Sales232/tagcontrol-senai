(() => {
    const cameraSelect = document.getElementById("camera-select");
    const startButton = document.getElementById("start-scanner");
    const stopButton = document.getElementById("stop-scanner");
    const scanAgainButton = document.getElementById("scan-again");
    const retryButton = document.getElementById("retry-scan");
    const manualForm = document.getElementById("manual-scan-form");
    const manualCode = document.getElementById("manual-scan-code");
    const status = document.getElementById("scanner-status");
    const result = document.getElementById("scan-result");
    const scannedCode = document.getElementById("scanned-code");
    const readerElement = document.getElementById("reader");
    const pedidoProgressValue = document.getElementById("pedido-progress-value");
    const pedidoProgressPercent = document.getElementById("pedido-progress-percent");
    const pedidoProgressStatus = document.getElementById("pedido-progress-status");
    const pedidoProgressTrack = document.querySelector(".pedido-progress-track");
    const pedidoProgressFill = document.getElementById("pedido-progress-fill");
    const pedidoItemProgressList = document.getElementById("pedido-item-progress-list");
    const conferenceLink = document.getElementById("conference-link");
    const scannerInputs = document.getElementById("scanner-inputs");
    const emptyOrderGuidance = document.getElementById("empty-order-guidance");
    const pedidoId = document.querySelector("main[data-pedido-id]")?.dataset.pedidoId;

    if (!cameraSelect || !startButton || !stopButton || !scanAgainButton ||
        !retryButton || !manualForm || !manualCode || !status || !result ||
        !scannedCode || !readerElement || !pedidoItemProgressList ||
        !scannerInputs || !emptyOrderGuidance || !pedidoId) {
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

    const renderItemProgress = (items) => {
        if (!Array.isArray(items)) {
            return;
        }
        const rows = items.map((item) => {
            const row = document.createElement("li");
            row.dataset.pecaId = String(item.peca.id);

            const description = document.createElement("div");
            const code = document.createElement("strong");
            code.textContent = item.peca.codigo;
            const name = document.createElement("span");
            name.textContent = item.peca.descricao;
            description.append(code, name);

            const quantity = document.createElement("span");
            quantity.className = "pedido-item-quantity";
            quantity.textContent = `${item.quantidade_validada} / ${item.quantidade_necessaria} · ${item.percentual}%`;
            row.append(description, quantity);
            return row;
        });
        pedidoItemProgressList.replaceChildren(...rows);
    };

    const updateProgress = (progress, progressByItem) => {
        if (!progress || !pedidoProgressValue || !pedidoProgressPercent) {
            return;
        }
        pedidoProgressValue.textContent = `${progress.quantidade_validada} / ${progress.total_necessario} itens`;
        pedidoProgressPercent.textContent = `(${progress.percentual}%)`;
        if (pedidoProgressTrack) {
            pedidoProgressTrack.setAttribute("aria-valuenow", String(progress.percentual));
        }
        if (pedidoProgressFill) {
            pedidoProgressFill.style.width = `${progress.percentual}%`;
        }
        renderItemProgress(progressByItem);
        if (pedidoProgressStatus) {
            const progressMessages = {
                finalizado: "Separação finalizada",
                em_andamento: "Separação em andamento",
                sem_itens: "Pedido sem itens",
            };
            pedidoProgressStatus.textContent = progressMessages[progress.status] || "Estado do pedido indisponível";
            pedidoProgressStatus.dataset.state = progress.status || "erro";
        }
        if (conferenceLink) {
            conferenceLink.hidden = progress.status !== "finalizado";
        }
    };

    const showEmptyOrderGuidance = async () => {
        if (running && !await stopScanner(true)) {
            emptyOrderGuidance.hidden = false;
            return;
        }
        scannerInputs.hidden = true;
        emptyOrderGuidance.hidden = false;
    };

    const createIdempotencyKey = () => {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
            return window.crypto.randomUUID();
        }
        if (!window.crypto || typeof window.crypto.getRandomValues !== "function") {
            throw new Error("Este navegador não oferece geração segura de identificadores.");
        }

        const bytes = window.crypto.getRandomValues(new Uint8Array(16));
        bytes[6] = (bytes[6] & 0x0f) | 0x40;
        bytes[8] = (bytes[8] & 0x3f) | 0x80;
        const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    };

    let scanner = null;
    let running = false;
    let startPending = false;
    let validationInFlight = false;
    let scanStartedAt = 0;
    let noCodeStatusShown = false;
    let pendingScan = null;

    const updateControls = () => {
        startButton.hidden = running || startPending || Boolean(pendingScan) || validationInFlight;
        stopButton.hidden = !running;
        scanAgainButton.hidden = running || startPending || validationInFlight ||
            Boolean(pendingScan) || !scannedCode.textContent;
        retryButton.hidden = !pendingScan || validationInFlight;
        cameraSelect.disabled = running || startPending || cameraSelect.options.length < 2;
        manualCode.disabled = validationInFlight || Boolean(pendingScan);
        manualForm.querySelector("button[type='submit']").disabled = validationInFlight || Boolean(pendingScan);
    };

    const stopScanner = async (preserveFeedback = false) => {
        if (!running) {
            return true;
        }
        try {
            await scanner.stop();
            running = false;
            if (!preserveFeedback) {
                setStatus("Câmera parada.");
                setResultState("");
            }
            return true;
        } catch (error) {
            setStatus("Não foi possível parar a câmera corretamente. Feche esta página para encerrar o acesso.", "erro");
            console.error("Falha ao parar o scanner:", error);
            return false;
        } finally {
            updateControls();
        }
    };

    const showUncertainResult = (code, idempotencyKey, message) => {
        pendingScan = { code, idempotencyKey };
        scannedCode.textContent = code;
        result.hidden = false;
        setStatus(message, "erro");
        setResultState("erro");
        updateControls();
    };

    const validateCode = async (code, idempotencyKey) => {
        if (validationInFlight) {
            return;
        }
        validationInFlight = true;
        scannedCode.textContent = code;
        result.hidden = false;
        setResultState("");
        setStatus("Validando QR Code no pedido...");
        updateControls();

        try {
            const response = await fetch(`/pedidos/${pedidoId}/scanner/validar`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ codigo: code, idempotency_key: idempotencyKey }),
            });

            let payload;
            try {
                payload = await response.json();
            } catch (error) {
                console.error("Resposta inválida ao validar código:", error);
                showUncertainResult(
                    code,
                    idempotencyKey,
                    "Não foi possível confirmar a resposta do servidor. Tente novamente para verificar sem duplicar a leitura.",
                );
                return;
            }

            const knownStatuses = [
                "sucesso",
                "duplicada",
                "fora_do_pedido",
                "nao_cadastrado",
                "pedido_sem_itens",
                "erro",
            ];
            if (!payload || !knownStatuses.includes(payload.status) || typeof payload.message !== "string") {
                showUncertainResult(
                    code,
                    idempotencyKey,
                    "O servidor retornou uma resposta inesperada. Tente novamente para verificar o resultado da leitura.",
                );
                return;
            }

            if (response.status >= 500) {
                showUncertainResult(
                    code,
                    idempotencyKey,
                    "O servidor não confirmou a leitura. Tente novamente para verificar sem duplicá-la.",
                );
                return;
            }

            pendingScan = null;
            setStatus(payload.message, response.ok ? payload.status : "erro");
            setResultState(response.ok ? payload.status : "erro");
            updateProgress(payload.progress, payload.progress_by_item);

            const resultLabels = {
                sucesso: "OK",
                duplicada: "DUPLICADA",
                fora_do_pedido: "FORA DO PEDIDO",
                nao_cadastrado: "NÃO CADASTRADO",
                pedido_sem_itens: "PEDIDO SEM ITENS",
            };
            if (resultLabels[payload.status]) {
                scannedCode.textContent = `${code} · ${resultLabels[payload.status]}`;
            }
            if (payload.status === "pedido_sem_itens") {
                await showEmptyOrderGuidance();
            }
        } catch (error) {
            console.error("Falha ao validar código lido:", error);
            showUncertainResult(
                code,
                idempotencyKey,
                "Não foi possível confirmar a leitura. Verifique sua conexão e tente novamente sem duplicá-la.",
            );
        } finally {
            validationInFlight = false;
            updateControls();
        }
    };

    const submitNewCode = async (value) => {
        const code = value.trim();
        if (!code || validationInFlight || pendingScan) {
            return;
        }
        try {
            await validateCode(code, createIdempotencyKey());
        } catch (error) {
            console.error("Não foi possível preparar a leitura:", error);
            setStatus(error.message, "erro");
        }
    };

    const startScanner = async () => {
        if (startPending || running || pendingScan || validationInFlight) {
            return;
        }
        if (typeof Html5Qrcode === "undefined" || typeof Html5QrcodeSupportedFormats === "undefined") {
            setStatus("A biblioteca do scanner não foi carregada. Atualize a página e tente novamente.", "erro");
            return;
        }
        if (!window.TagControlQrScanner) {
            setStatus("A configuração do scanner não foi carregada. Atualize a página e tente novamente.", "erro");
            return;
        }
        if (!window.isSecureContext ||
            !navigator.mediaDevices ||
            !navigator.mediaDevices.getUserMedia) {
            setStatus(window.TagControlQrScanner.getCameraErrorMessage(), "erro");
            return;
        }

        startPending = true;
        result.hidden = true;
        setResultState("");
        scannedCode.textContent = "";
        updateControls();
        setStatus("Solicitando acesso à câmera...");

        try {
            scanner = window.TagControlQrScanner.createScanner("reader");
            running = true;
            scanStartedAt = Date.now();
            noCodeStatusShown = false;
            await window.TagControlQrScanner.start(
                scanner,
                cameraSelect,
                async (decodedText) => {
                    const code = decodedText.trim();
                    if (!code || !running || validationInFlight || pendingScan) {
                        return;
                    }
                    let idempotencyKey;
                    try {
                        idempotencyKey = createIdempotencyKey();
                    } catch (error) {
                        console.error("Não foi possível preparar a leitura:", error);
                        setStatus(error.message, "erro");
                        return;
                    }
                    if (!await stopScanner(true)) {
                        showUncertainResult(
                            code,
                            idempotencyKey,
                            "A câmera ainda está ativa. Pare-a antes de confirmar a leitura.",
                        );
                        return;
                    }
                    await validateCode(code, idempotencyKey);
                },
                () => {
                    if (running && !noCodeStatusShown && Date.now() - scanStartedAt >= 10000) {
                        noCodeStatusShown = true;
                        setStatus("Nenhum QR Code válido foi detectado. Ajuste a posição, o foco e a iluminação e evite reflexos.", "erro");
                    }
                },
            );
            if (running) {
                setStatus("Câmera ativa. Centralize o QR Code no retângulo de leitura.");
            }
        } catch (error) {
            running = false;
            console.error("Falha ao iniciar o scanner:", error);
            setStatus(window.TagControlQrScanner.getCameraErrorMessage(error), "erro");
        } finally {
            startPending = false;
            updateControls();
        }
    };

    startButton.addEventListener("click", startScanner);
    stopButton.addEventListener("click", () => stopScanner());
    scanAgainButton.addEventListener("click", startScanner);
    retryButton.addEventListener("click", async () => {
        if (!pendingScan || validationInFlight) {
            return;
        }
        if (running && !await stopScanner(true)) {
            setStatus("A câmera ainda está ativa. Pare-a antes de tentar novamente.", "erro");
            return;
        }
        const { code, idempotencyKey } = pendingScan;
        pendingScan = null;
        await validateCode(code, idempotencyKey);
    });
    manualForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        await submitNewCode(manualCode.value);
    });
    updateControls();
})();
