/**
 * IOMS browser GPS capture — attaches lat/lng to forms automatically.
 */
(function (global) {
    'use strict';

    function fillGpsFields(lat, lng) {
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
                var lat = pos.coords.latitude.toFixed(6);
                var lng = pos.coords.longitude.toFixed(6);
                fillGpsFields(lat, lng);
                if (callback) callback(lat, lng, null);
            },
            function (err) {
                if (callback) callback(null, null, err.message);
            },
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
        );
    }

    function attachToForms(selector) {
        document.querySelectorAll(selector || 'form[data-gps-capture]').forEach(function (form) {
            captureGps();
            form.addEventListener('submit', function () {
                captureGps();
            });
        });
    }

    global.IOMSGps = {
        capture: captureGps,
        attach: attachToForms,
        fill: fillGpsFields,
    };

    document.addEventListener('DOMContentLoaded', function () {
        attachToForms('form[data-gps-capture]');
    });
})(window);
