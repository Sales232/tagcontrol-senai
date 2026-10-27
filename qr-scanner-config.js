(() => {
    const supportedFormats = [Html5QrcodeSupportedFormats.QR_CODE];

    const chooseCamera = (cameraSelect, cameras) => {
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
        return cameraSelect.value;
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

    window.TagControlQrScanner = Object.freeze({
        getCameraErrorMessage,

        createScanner: (elementId) => new Html5Qrcode(elementId, {
            formatsToSupport: supportedFormats,
        }),

        start: async (scanner, cameraSelect, onDecoded, onDecodeFailure) => {
            const cameraId = chooseCamera(cameraSelect, await Html5Qrcode.getCameras());
            await scanner.start(
                cameraId,
                {
                    fps: 10,
                    qrbox: getScanRegion,
                    videoConstraints: {
                        audio: false,
                        video: {
                            deviceId: { exact: cameraId },
                            width: { ideal: 1280 },
                            height: { ideal: 720 },
                        },
                    },
                },
                onDecoded,
                onDecodeFailure,
            );
            return cameraId;
        },
    });
})();
