Polymer({
    is: 'photo-image-set',
    properties: {
        limit: { type: String, notify: true, observer: 'paramChanged' },
        out: {
            type: Object,
            value: function () {
                return { images: [{ uri: 'one' }] };
            },
            notify: true
        },
        seed: {
            type: String,
            notify: true,
            observer: 'paramChanged'
        },
        onlyTagged: {
            // support is incomplete. this should take space-separated tags.
            type: String,
            notify: true,
            observer: 'paramChanged'
        },
        sort: { type: String, notify: true, observer: 'paramChanged' },
        type: { type: String, notify: true, observer: 'paramChanged' },
        time: { type: String, notify: true, observer: 'paramChanged' },
        status: {type: String}
    },
    paramChanged: function () {
        if (this.timer) {
            clearTimeout(this.timer);
        }
        this.timer = setTimeout(this.reloadSet.bind(this), 50);
    },
    reloadSet: function () {
        this.timer = null;
        var self = this;
        // if status==loading AND all params match, we could return here
        self.status = 'loading';
        var params = {};
        [
            'limit',
            'sort',
            'time',
            'type',
            'onlyTagged' // should turn into repeated param
        ].forEach(function (a) {
            if (self[a]) {
                // todo: onlyTagged='' has a meaning
                params[a] = self[a];
            }
        });
        if (self.seed && params.sort == 'random') {
            params.sort = 'random ' + self.seed;
        }
       
        this.latestParams = params;
        $.getJSON('https://photo.bigasterisk.com/imageSet/set.json', params, function (js) {
            if (!_.isEqual(params, self.latestParams)) {
                return;
            }
            self.out = js;
            var i = 0;
            self.out.images.forEach(function (img) {
                img.i = i;
                i++;
            });
            self.status = 'ok';
        });
    },
    ready: function () {
        this.xhr = null;
        this.reloadSet();
    }
});
