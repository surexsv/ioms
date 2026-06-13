/**
 * IOMS Attendance — mandatory GPS + webcam/mobile camera capture.
 */
(function (global) {
    'use strict';

    var stream = null;

    function fillGps(lat, lng) {
        document.querySelectorAll('input[name="latitude"]').forEach(function (el) {
            el.value = lat;
        });
        document.querySelectorAll('input[name="longitude"]').forEach(function (el) {
            el.value = lng;
        });
    }

    function captureGps(callback) {
        if (!navigator.geolocation) {
            if (callback) callback(null, null, 'Geolocation not supported');
            return;
        }
        navigator.geolocation.getCurrentPosition(
            function (pos) {
                var lat = pos.coords.latitude.toFixed(7);
                var lng = pos.coords.longitude.toFixed(7);
                fillGps(lat, lng);
                if (callback) callback(lat, lng, null);
            },
            function (err) {
                if (callback) callback(null, null, err.message);
            },
            { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
        );
    }

    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(function (t) { t.stop(); });
            stream = null;
        }
    }

    function startCamera(videoEl, statusEl) {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            if (statusEl) statusEl.textContent = 'Camera not supported — use file upload below.';
            return;
        }
        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
            .then(function (s) {
                stream = s;
                videoEl.srcObject = s;
                if (statusEl) statusEl.textContent = 'Camera ready — capture your photo.';
            })
            .catch(function () {
                if (statusEl) statusEl.textContent = 'Camera access denied — use file upload below.';
            });
    }

    function capturePhoto(videoEl, canvasEl, fileInput, previewEl) {
        if (!videoEl.videoWidth) return false;
        canvasEl.width = videoEl.videoWidth;
        canvasEl.height = videoEl.videoHeight;
        canvasEl.getContext('2d').drawImage(videoEl, 0, 0);
        return new Promise(function (resolve) {
            canvasEl.toBlob(function (blob) {
                if (!blob) { resolve(false); return; }
                var file = new File([blob], 'attendance_capture.jpg', { type: 'image/jpeg' });
                var dt = new DataTransfer();
                dt.items.add(file);
                fileInput.files = dt.files;
                if (previewEl) {
                    previewEl.src = canvasEl.toDataURL('image/jpeg');
                    previewEl.style.display = 'block';
                }
                resolve(true);
            }, 'image/jpeg', 0.92);
        });
    }

    function initAttendanceForm(formId) {
        var form = document.getElementById(formId);
        if (!form) return;

        var video = document.getElementById('attVideo');
        var canvas = document.getElementById('attCanvas');
        var fileInput = document.getElementById('id_photo');
        var preview = document.getElementById('attPreview');
        var gpsStatus = document.getElementById('gpsStatus');
        var captureBtn = document.getElementById('capturePhotoBtn');

        captureGps(function (lat, lng, err) {
            if (gpsStatus) {
                if (lat && lng) gpsStatus.textContent = 'GPS ready: ' + lat + ', ' + lng;
                else gpsStatus.textContent = 'GPS required: ' + (err || 'unavailable');
            }
        });

        if (video) startCamera(video, document.getElementById('cameraStatus'));

        if (captureBtn && video && canvas && fileInput) {
            captureBtn.addEventListener('click', function () {
                capturePhoto(video, canvas, fileInput, preview).then(function (ok) {
                    if (ok && document.getElementById('cameraStatus')) {
                        document.getElementById('cameraStatus').textContent = 'Photo captured.';
                    }
                });
            });
        }

        form.addEventListener('submit', function (e) {
            var lat = form.querySelector('input[name="latitude"]');
            var lng = form.querySelector('input[name="longitude"]');
            if (!lat || !lng || !lat.value || !lng.value) {
                e.preventDefault();
                alert('GPS location is mandatory. Please allow location access and try again.');
                captureGps();
                return;
            }
            if (fileInput && !fileInput.files.length) {
                e.preventDefault();
                alert('Photo is mandatory. Capture a photo or upload from camera.');
                return;
            }
            stopCamera();
        });

        window.addEventListener('beforeunload', stopCamera);
    }

    global.IOMSAttendance = {
        init: initAttendanceForm,
        captureGps: captureGps,
        stopCamera: stopCamera,
    };
})(window);
