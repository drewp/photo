Polymer({
    is: 'photo-image-set',
    properties: {
        limit: { notify: true },
        out: {
            type: Object,
            value: function () {
                return { images: [{ uri: 'one' }] };
            },
            notify: true
        },
        seed: {
            notify: true,
            observer: 'seedChanged'
        },
        onlyTagged: {
            // support is incomplete. this should take space-separated tags.
            type: String,
            notify: true,
        },
        sort: { notify: true },
        time: { notify: true },
        status: {type: String}
    },
    seedChanged: function () {
        this.reloadSet();
    },
    reloadSet: function () {
        var self = this;
        self.status = 'loading';
        params = {};
        [
            'limit',
            'sort',
            'time',
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
        $.getJSON('/imageSet/set.json', params, function (js) {
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
        this.reloadSet();
    }
});
