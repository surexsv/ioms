/**
 * PM observation capture — reuses IOMS GPS helper and optional site camera snapshot.
 */
(function () {
    'use strict';

    var stream = null;

    function setAccuracy(value) {
        document.querySelectorAll('input[name="gps_accuracy"]').forEach(function (el) {
            el.value = value || '';
        });
    }

    function updateGpsStatus(lat, lng, err) {
        var el = document.getElementById('gpsStatus');
        if (!el) return;
        if (lat && lng) el.textContent = 'GPS ready: ' + lat + ', ' + lng;
        else el.textContent = err ? ('GPS unavailable: ' + err) : 'Waiting for GPS…';
    }

    function startCamera(videoEl, statusEl) {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            if (statusEl) statusEl.textContent = 'Camera not supported — upload a photo below.';
            return;
        }
        navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: 'environment' } },
            audio: false,
        }).then(function (s) {
            stream = s;
            videoEl.srcObject = s;
            if (statusEl) statusEl.textContent = 'Camera ready — capture a site snapshot.';
        }).catch(function () {
            if (statusEl) statusEl.textContent = 'Camera access denied — upload a photo below.';
        });
    }

    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(function (t) { t.stop(); });
            stream = null;
        }
    }

    function firstEmptyFileInput(form) {
        var inputs = form.querySelectorAll('input[type="file"]');
        for (var i = 0; i < inputs.length; i += 1) {
            if (!inputs[i].files || !inputs[i].files.length) return inputs[i];
        }
        return inputs.length ? inputs[0] : null;
    }

    function captureSnapshot(videoEl, canvasEl, fileInput, previewEl, statusEl) {
        if (!videoEl.videoWidth || !fileInput) return;
        canvasEl.width = videoEl.videoWidth;
        canvasEl.height = videoEl.videoHeight;
        canvasEl.getContext('2d').drawImage(videoEl, 0, 0);
        canvasEl.toBlob(function (blob) {
            if (!blob) return;
            var file = new File([blob], 'pm_snapshot.jpg', { type: 'image/jpeg' });
            var dt = new DataTransfer();
            dt.items.add(file);
            fileInput.files = dt.files;
            if (previewEl) {
                previewEl.src = canvasEl.toDataURL('image/jpeg');
                previewEl.style.display = 'block';
            }
            if (statusEl) statusEl.textContent = 'Snapshot captured.';
        }, 'image/jpeg', 0.9);
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.getElementById('pmObservationForm');
        if (!form) return;

        if (window.IOMSGps) {
            IOMSGps.capture(function (lat, lng, err) {
                updateGpsStatus(lat, lng, err);
            });
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(function (pos) {
                    if (pos.coords && pos.coords.accuracy) {
                        setAccuracy(pos.coords.accuracy.toFixed(2));
                    }
                }, function () {}, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
            }
        }

        var video = document.getElementById('pmVideo');
        var canvas = document.getElementById('pmCanvas');
        var preview = document.getElementById('pmPreview');
        var statusEl = document.getElementById('cameraStatus');
        var captureBtn = document.getElementById('pmCaptureBtn');
        if (video) startCamera(video, statusEl);
        if (captureBtn) {
            captureBtn.addEventListener('click', function () {
                captureSnapshot(video, canvas, firstEmptyFileInput(form), preview, statusEl);
            });
        }
        form.addEventListener('submit', stopCamera);
        window.addEventListener('beforeunload', stopCamera);
    });
})();
