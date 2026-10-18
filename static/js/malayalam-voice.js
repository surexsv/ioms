/**
 * Malayalam speech on an IOMS note.
 * Chrome (including Android) hears ml-IN. The English line is prepared on the server.
 */
(function () {
    'use strict';

    function csrfToken() {
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input && input.value) return input.value;
        var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function setStatus(panel, text) {
        var el = panel.querySelector('.ml-status');
        if (el) el.textContent = text || '';
    }

    function orderId(panel) {
        if (panel.dataset.orderId) return panel.dataset.orderId;
        if (!panel.dataset.orderSelect) return '';
        var select = document.getElementById(panel.dataset.orderSelect);
        return select ? select.value : '';
    }

    function selectedKind(panel) {
        if (panel.dataset.kind) return panel.dataset.kind;
        var checked = panel.querySelector('input[name="kind"]:checked');
        return checked ? checked.value : '';
    }

    function prepareEnglish(panel) {
        var original = panel.querySelector('.ml-original');
        var english = panel.querySelector('.ml-english');
        var text = original ? original.value.trim() : '';
        if (!text) {
            setStatus(panel, 'Speak or type the Malayalam note first.');
            return;
        }
        setStatus(panel, 'Preparing English…');
        fetch(panel.dataset.translateUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify({ text: text }),
        }).then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        }).then(function (result) {
            if (!result.ok) {
                setStatus(panel, (result.data && result.data.error) || 'English could not be prepared. Type it, then confirm.');
                return;
            }
            if (english) english.value = result.data.english || '';
            setStatus(panel, result.data.engine === 'ai'
                ? 'Review the English, then confirm.'
                : 'Review the English. You can edit it before confirming.');
        }).catch(function () {
            setStatus(panel, 'English could not be prepared. Type the English version, then confirm.');
        });
    }

    function useEnglish(panel) {
        var english = panel.querySelector('.ml-english');
        var original = panel.querySelector('.ml-original');
        var text = english ? english.value.trim() : '';
        var malayalam = original ? original.value.trim() : '';
        if (!text) {
            setStatus(panel, 'Prepare or type the English first.');
            return;
        }
        if (panel.dataset.target) {
            var target = document.querySelector(panel.dataset.target);
            if (target) target.value = text;
        }
        var id = orderId(panel);
        var kind = selectedKind(panel);
        if (!panel.dataset.saveUrl || !id || !kind || !malayalam) {
            setStatus(panel, 'English added to the note. Save the form to keep it.');
            return;
        }
        var body = new FormData();
        body.append('kind', kind);
        body.append('malayalam_text', malayalam);
        body.append('english_text', text);
        var saveUrl = (panel.dataset.saveUrl || '').replace('/0/voice/', '/' + id + '/voice/');
        fetch(saveUrl, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: body,
        }).then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        }).then(function (result) {
            if (!result.ok) {
                setStatus(panel, (result.data && result.data.error) || 'English added to the note. Save the form to keep it.');
                return;
            }
            setStatus(panel, 'English added, and the Malayalam note is saved on the order.');
        }).catch(function () {
            setStatus(panel, 'English added to the note. Save the form to keep it.');
        });
    }

    function bindSpeech(panel) {
        var button = panel.querySelector('.ml-speak');
        var original = panel.querySelector('.ml-original');
        var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!button) return;
        if (!Recognition) {
            setStatus(panel, 'This browser cannot hear Malayalam. Type the Malayalam, then prepare the English. Chrome on a phone can use the microphone.');
            return;
        }
        var recognition = new Recognition();
        recognition.lang = 'ml-IN';
        recognition.interimResults = true;
        recognition.continuous = true;
        var listening = false;
        var committed = '';

        recognition.onresult = function (event) {
            var interim = '';
            for (var i = event.resultIndex; i < event.results.length; i++) {
                var piece = event.results[i][0].transcript;
                if (event.results[i].isFinal) committed += piece + ' ';
                else interim += piece;
            }
            if (original) original.value = (committed + interim).trim();
        };
        recognition.onerror = function (event) {
            if (event.error === 'not-allowed') {
                setStatus(panel, 'Allow the microphone, then tap Speak in Malayalam again.');
            } else if (event.error !== 'aborted' && event.error !== 'no-speech') {
                setStatus(panel, 'The microphone stopped. Speak again, or type the Malayalam.');
            }
        };
        recognition.onend = function () {
            if (listening) {
                try { recognition.start(); } catch (err) { listening = false; }
                return;
            }
            button.classList.remove('is-listening');
            button.innerHTML = '<i class="bi bi-mic"></i> Speak in Malayalam';
            if (original && original.value.trim()) prepareEnglish(panel);
        };

        button.addEventListener('click', function () {
            if (listening) {
                listening = false;
                recognition.stop();
                return;
            }
            committed = original && original.value.trim() ? original.value.trim() + ' ' : '';
            listening = true;
            button.classList.add('is-listening');
            button.textContent = 'Stop';
            setStatus(panel, 'Listening in Malayalam… tap Stop when you finish.');
            try {
                recognition.start();
            } catch (err) {
                listening = false;
                setStatus(panel, 'The microphone is already in use. Wait a moment and try again.');
            }
        });
    }

    function init(panel) {
        if (panel.dataset.mlReady) return;
        panel.dataset.mlReady = '1';
        bindSpeech(panel);
        var prepare = panel.querySelector('.ml-prepare');
        if (prepare) prepare.addEventListener('click', function () { prepareEnglish(panel); });
        var use = panel.querySelector('.ml-use');
        if (use) use.addEventListener('click', function () { useEnglish(panel); });
    }

    document.querySelectorAll('[data-ml-voice]').forEach(init);
})();
