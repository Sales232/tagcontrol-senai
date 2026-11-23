(() => {
    const supportedFormats = [Html5QrcodeSupportedFormats.QR_CODE];

    // Preenche o select com as câmeras disponíveis.
    // Retorna o id da câmera apenas se o usuário já havia escolhido uma antes;
    // caso contrário retorna null, para que o facingMode "environment" decida.
    const chooseCamera = (cameraSelect, cameras, previousCameraId) => {
        if (!cameras.length) {
            throw new DOMException("Nenhuma câmera encontrada.", "NotFoundError");
        }

        cameraSelect.replaceChildren();
        cameras.forEach((camera, index) => {
            const option = document.createElement("option");
            option.value = camera.id;
            option.textContent = camera.label || `Câmera ${index + 1}`;
            cameraSelect.append(option);
        });

        if (previousCameraId && cameras.some((camera) => camera.id === previousCameraId)) {
            cameraSelect.value = previousCameraId;
            return previousCameraId;
        }
        return null;
    };

    const getScanRegion = (viewfinderWidth, viewfinderHeight) => {
        const size = Math.floor(Math.min(viewfinderWidth, viewfinderHeight) * 0.75);
        return {
            width: size,
            height: size,
        };
    };

    const getCameraErrorMessage = (error) => {
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

    const start = async (scanner, cameraSelect, onDecoded, onDecodeFailure) => {
        const cameras = await Html5Qrcode.getCameras();
        const previousCameraId = cameraSelect.value;
        const chosenCameraId = chooseCamera(cameraSelect, cameras, previousCameraId);

        // Escolha da câmera: id específico (menu) ou traseira (padrão).
        const cameraConstraint = chosenCameraId
            ? { deviceId: { exact: chosenCameraId } }
            : { facingMode: { ideal: "environment" } };

        const config = {
            fps: 10,
            qrbox: getScanRegion,
            // IMPORTANTE: a biblioteca usa este objeto no lugar do 1º argumento
            // do start(), então a câmera precisa estar aqui dentro.
            videoConstraints: {
                ...cameraConstraint,
                width: { ideal: 1280 },
                height: { ideal: 720 },
            },
        };

        await scanner.start(cameraConstraint, config, onDecoded, onDecodeFailure);

        // Sincroniza o select com a câmera que realmente abriu.
        const runningId = scanner.getRunningTrackSettings().deviceId;
        if (runningId && [...cameraSelect.options].some((option) => option.value === runningId)) {
            cameraSelect.value = runningId;
        }
        return cameraSelect.value;
    };

    // Use quando o usuário trocar a câmera no menu suspenso.
    const switchCamera = async (scanner, cameraSelect, onDecoded, onDecodeFailure) => {
        if (scanner.isScanning) {
            await scanner.stop();
        }
        return start(scanner, cameraSelect, onDecoded, onDecodeFailure);
    };

    window.TagControlQrScanner = Object.freeze({
        getCameraErrorMessage,

        createScanner: (elementId) => new Html5Qrcode(elementId, {
            formatsToSupport: supportedFormats,
        }),

        start,
        switchCamera,
    });
})();