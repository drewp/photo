Polymer("photo-image-set", {
    out: {images: [{uri: 'one'}]},
    
    seedChanged: function() {
        console.log('seed', this.seed);
        this.reloadSet();
    },
    reloadSet: function() {
        var self = this;
        self.status = 'loading';

        params = {};
        ['limit', 'sort'].forEach(function(a) {
            if (self[a]) {
                params[a] = self[a];
            }
        });
        if (self.seed && params.sort == 'random') {
            params.sort = 'random ' + self.seed
        }
        $.getJSON('/imageSet/set.json', params, function(js) {
            self.out = js;
            self.status = 'ok';
        });

    },

    
    ready: function() {
        this.reloadSet();
    }
});
