(function(requirejs, require, define) {

// VideoVolumeControl module.
define(
    'video/07_video_volume_control.js', [],
    function() {
        "use strict";
        /**
         * Video speed control module.
         * @exports video/08_video_speed_control.js
         * @constructor
         * @param {object} state The object containing the state of the video player.
         */
        var VolumeControl = function(state) {
            if (!(this instanceof VolumeControl)) {
                return new VolumeControl(state);
            }

            this.state = state;
            this.state.videoVolumeControl = this;
            this.initialize();

            return $.Deferred().resolve().promise();
        };

        VolumeControl.prototype = {
            min: 0,
            max: 100,
            step: 5,

            initialize: function() {
                this.el = this.state.el.find('div.volume');

                if (this.state.isTouch) {
                    // iOS doesn't support volume change
                    this.el.remove();
                    return false;
                }

                this.state.el.find('iframe').attr('tabindex', -1);
                this.button = this.el.children('a');
                this.setVolume(Cookie.getVolume(), true, true);
                this.mute(Cookie.getMute());
                this.render();
                this.bindHandlers();
            },

            render: function() {
                var container = this.el.find('.volume-slider'),
                    button = this.button,
                    min = this.min,
                    max = this.max,
                    sliderElement;

                this.volumeSlider = container.slider({
                    orientation: 'vertical',
                    range: 'min',
                    min: this.min,
                    max: this.max,
                    value: this.getVolume(),
                    change: this.onChangeHandler.bind(this),
                    slide: this.onSlideHandler.bind(this)
                });

                // Let screen readers know that this anchor, representing the slider
                // handle, behaves as a slider named 'volume'.
                sliderElement = container.find('.ui-slider-handle');
                container.find('a').attr('tabindex', -1);

                this.a11y = new VolumeA11y(sliderElement, button, min, max);
                this.a11y.update(this.getVolume());
            },

            /** Bind any necessary function callbacks to DOM events. */
            bindHandlers: function() {
                this.state.el.on({
                    'keydown': this.keyDownHandler.bind(this),
                    'initialize': this.updateState.bind(this),
                    'play': _.once(this.updateState.bind(this))
                });
                this.el.on({
                    'mouseenter': this.openMenu.bind(this),
                    'mouseleave': this.closeMenu.bind(this)
                });
                this.button.on({
                    'mousedown': this.toggleMuteHandler.bind(this),
                    'keydown': this.keyDownButtonHandler.bind(this),
                    'focus': this.openMenu.bind(this),
                    'blur': this.closeMenu.bind(this)
                });
            },

            updateState: function() {
                this.setVolume(this.getVolume());
                this.mute(this.isMuted);
            },

            getVolume: function() {
                return this.volume;
            },

            setVolume: function(volume, withoutSlider, withoutCookie) {
                this.volume = volume;

                if (this.getVolume() <= this.min) {
                    this.updateButtonView(true);
                } else if (this.isMuted) {
                    this.mute(false)
                } else {
                    this.updateButtonView(false);
                }

                if (!withoutSlider) {
                    this.volumeSlider.slider('value', volume);
                    this.a11y.update(this.getVolume());
                }

                if (!withoutCookie) {
                    Cookie.setVolume(this.getVolume());
                }
            },

            increaseVolume: function() {
                var current = this.getVolume(),
                    volume = current + this.step,
                    max = this.max;

                volume = (volume <= max) ? volume : max;
                this.setVolume(volume);
            },

            decreaseVolume: function() {
                var current = this.getVolume(),
                    volume = current - this.step,
                    min = this.min;

                volume = (volume >= min) ? volume : min;
                this.setVolume(volume);
            },

            mute: function(enable) {
                Cookie.setMute(enable);
                this.isMuted = enable;
                this.updateButtonView(enable);
                this.state.el.trigger('mute', [enable]);
            },

            updateButtonView: function(isMuted) {
                var action = isMuted ? 'addClass' : 'removeClass';
                // @TODO FIX class name
                this.el[action]('muted');
            },

            openMenu: function() {
                // @TODO move to closeMenu, FIX class name
                this.el.addClass('open');
            },

            closeMenu: function() {
                // @TODO move to closeMenu, FIX class name
                this.el.removeClass('open');
            },

            toggleMute: function() {
                if (this.isMuted) {
                    this.mute(false);
                } else {
                    this.mute(true);
                }
            },

            keyDownHandler: function(event) {
                // ALT key is used to change (alternate) the function of
                // other pressed keys. In this case, do nothing.
                if (event.altKey) {
                    return true;
                }

                if ($(event.target).hasClass('ui-slider-handle')) {
                    return true;
                }

                var KEY = $.ui.keyCode,
                    keyCode = event.keyCode;

                switch (keyCode) {
                    case KEY.UP:
                        // Shift + Arrows keyboard shortcut might be used by
                        // screen readers. In this case, do nothing.
                        if (event.shiftKey) {
                            return true;
                        }

                        this.increaseVolume();
                        return false;
                    case KEY.DOWN:
                        // Shift + Arrows keyboard shortcut might be used by
                        // screen readers. In this case, do nothing.
                        if (event.shiftKey) {
                            return true;
                        }

                        this.decreaseVolume();
                        return false;
                }

                return true;
            },

            keyDownButtonHandler: function(event) {
                // ALT key is used to change (alternate) the function of
                // other pressed keys. In this case, do nothing.
                if (event.altKey) {
                    return true;
                }

                var KEY = $.ui.keyCode,
                    keyCode = event.keyCode;

                switch (keyCode) {
                    case KEY.ENTER:
                    case KEY.SPACE:
                        this.toggleMute();

                        return false;
                }

                return true;
            },

            onSlideHandler: function(event, ui) {
                this.setVolume(ui.value, true, true);
                this.state.el.trigger('volumechange', [this.getVolume()]);
            },

            onChangeHandler: function(event, ui) {
                this.setVolume(ui.value, true);
                this.state.el.trigger('volumechange', [this.getVolume()]);
            },

            toggleMuteHandler: function(event) {
                this.toggleMute()
                event.preventDefault();
            },
        };

        var VolumeA11y = function (slider, button, min, max) {
            this.min = min;
            this.max = max;
            this.slider = slider;
            this.button = button;
            this.initialize();
        };


        VolumeA11y.prototype = {
            initialize: function() {
                this.slider.attr({
                    'role': 'slider',
                    'title': gettext('Volume'),
                    'aria-disabled': false,
                    'aria-valuemin': this.min,
                    'aria-valuemax': this.max
                });
            },

            update: function(volume) {
                this.slider.attr({
                    'aria-valuenow': volume,
                    'aria-valuetext': this.getDescription(volume)
                });

                // We add the aria-label attribute because the title attribute
                // cannot be read.
                this.button.attr(
                    'aria-label',
                    gettext((volume > 0) ? 'Volume' : 'Volume muted')
                );
            },

            // Returns a string describing the level of volume.
            getDescription: function(volume) {
                if (volume === 0) {
                    // Translators: Volume level equals 0%.
                    return gettext('Muted');
                } else if (volume <= 20) {
                    // Translators: Volume level in range (0,20]%
                    return gettext('Very low');
                } else if (volume <= 40) {
                    // Translators: Volume level in range (20,40]%
                    return gettext('Low');
                } else if (volume <= 60) {
                    // Translators: Volume level in range (40,60]%
                    return gettext('Average');
                } else if (volume <= 80) {
                    // Translators: Volume level in range (60,80]%
                    return gettext('Loud');
                } else if (volume <= 99) {
                    // Translators: Volume level in range (80,100)%
                    return gettext('Very loud');
                }

                // Translators: Volume level equals 100%.
                return gettext('Maximum');
            }
        };


        var Cookie = {
            cookies: {
                volume: 'video_player_volume_level',
                mute: 'video_player_is_muted'
            },

            getVolume: function() {
                var cookies = Cookie.cookies,
                    volume = parseInt($.cookie(cookies['volume']), 10);

                return isFinite(volume) ? volume : 100;
            },

            setVolume: function(value) {
                var cookies = Cookie.cookies;

                $.cookie(cookies['volume'], value, {
                    expires: 3650,
                    path: '/'
                });
            },

            getMute: function() {
                var cookies = Cookie.cookies;

                return $.cookie(cookies['mute']) || false;
            },

            setMute: function(value) {
                var cookies = Cookie.cookies;

                $.cookie(cookies['mute'], value, {
                    expires: 3650,
                    path: '/'
                });
            }
        };

        return VolumeControl;
    });
}(RequireJS.requirejs, RequireJS.require, RequireJS.define));
