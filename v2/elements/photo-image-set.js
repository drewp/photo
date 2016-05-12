Polymer({
    is: 'photo-image-set',
    properties: {
        status: { type: String },
        out: {
            type: Object,
            value: function () {
                return { images: [] };
            },
            notify: true
        },
        limit: { type: String, notify: true, observer: 'paramChanged' },
        seed: { type: String, notify: true, observer: 'paramChanged'},
        onlyTagged: {
            // support is incomplete. this should take space-separated tags.
            type: String,
            notify: true,
            observer: 'paramChanged'
        },
        sort: { type: String, notify: true, observer: 'paramChanged' },
        type: { type: String, notify: true, observer: 'paramChanged' },
        time: { type: String, notify: true, observer: 'paramChanged' },
    },
    paramChanged: function () {
        this.debounce('reloadSet', this.reloadSet.bind(this), 100);
    },
    makeQueryParams: function() {
        var self = this;
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
        return params;
    },
    reloadSet: function () {
        var self = this;
        // if status==loading AND all params match, we could return here
        self.status = 'loading';
        var params = self.makeQueryParams();
        $.getJSON('https://photo.bigasterisk.com/imageSet/set.json', params, function (js) {
            // Note: because of debounce, reloadSet might not have
            // even been called yet on the current params.
            if (!_.isEqual(params, self.makeQueryParams())) {
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
